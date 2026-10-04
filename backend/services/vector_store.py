"""
One embedder for every ChromaDB collection, and re-embedding when it changes.

Before phase 2 every collection used Chroma's built-in default embedder (all-MiniLM-L6-v2,
384 dims, English only); the LM Studio embedding service was never used for storage. Now
every collection is opened through get_rag_collection() with LMStudioEmbeddingFunction
(model EMBEDDING_MODEL, default text-embedding-bge-m3, 1024 dims), so writes (documents=...)
and queries (query_texts=...) all go through the same model.

A collection records the model it was built with in its metadata (`embedding_model`,
`embedding_dim`) and uses cosine distance. reembed_collections() rebuilds every collection
whose embedder, model or dimension differs: it copies ids/documents/metadatas into a new
collection embedded with the current model, deletes the old one and renames the new one into
place. Idempotent: a second run finds nothing to do.

Only one re-embed runs at a time across processes (reloader child, CLI, admin button, later
gunicorn workers): reembed_collections() holds a PostgreSQL advisory lock and skips when
another process has it. Startup runs it once (not in the werkzeug reloader's parent).

Crash safety: the original is deleted only after the `name__reembed` copy is complete. A
leftover copy is never deleted blindly: if the original is missing or empty the copy is
renamed back; if the original holds everything the copy has, the copy was an unfinished run
and is dropped; otherwise it is kept aside under a new name and logged.

Note: writes that land in a collection while it's being rebuilt can be lost (the data here
is small and a rebuild takes seconds; run it when nobody is playing if that matters).
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

from chromadb import Documents, EmbeddingFunction, Embeddings

from services.embedding_service import EmbeddingService, configured_embedding_model

logger = logging.getLogger(__name__)

EF_NAME = "shadowrealms-lmstudio"
REBUILD_SUFFIX = "__reembed"
ORPHAN_SUFFIX = "__reembed_orphan_"
# pg_advisory_lock key for the re-embed ("SRREEMB" in hex-ish; any fixed bigint works).
REEMBED_LOCK_KEY = 0x5352_5245_454D_42
PAGE = 500


class LMStudioEmbeddingFunction(EmbeddingFunction):
    """Chroma embedding function backed by services.embedding_service (LM Studio)."""

    def __init__(self, model: Optional[str] = None, url: Optional[str] = None, service: Optional[EmbeddingService] = None):
        cfg = {"LM_STUDIO_URL": url} if url else {}
        self.service = service or EmbeddingService(cfg)
        if model:
            self.service.embedding_model = model
        self.model = self.service.embedding_model

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - Chroma's signature
        return self.service.embed_texts(list(input))

    @staticmethod
    def name() -> str:
        return EF_NAME

    def get_config(self) -> Dict[str, Any]:
        return {"model": self.model}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "LMStudioEmbeddingFunction":
        return LMStudioEmbeddingFunction(model=config.get("model"))

    def is_legacy(self) -> bool:
        return False

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> List[str]:
        return ["cosine", "l2", "ip"]


_ef_lock = threading.Lock()
_ef: Optional[LMStudioEmbeddingFunction] = None
_dim_cache: Dict[str, int] = {}


def embedding_function() -> LMStudioEmbeddingFunction:
    global _ef
    with _ef_lock:
        if _ef is None or _ef.model != configured_embedding_model():
            _ef = LMStudioEmbeddingFunction(model=configured_embedding_model())
        return _ef


def embedding_dimension(ef: Optional[LMStudioEmbeddingFunction] = None) -> int:
    ef = ef or embedding_function()
    if ef.model not in _dim_cache:
        _dim_cache[ef.model] = len(ef(["dimension probe"])[0])
    return _dim_cache[ef.model]


def collection_metadata(ef: LMStudioEmbeddingFunction, dim: Optional[int], description: Optional[str] = None) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"embedding_model": ef.model, "hnsw:space": "cosine"}
    if dim:
        meta["embedding_dim"] = int(dim)
    if description:
        meta["description"] = description
    return meta


def get_rag_collection(client, name: str, ef: Optional[LMStudioEmbeddingFunction] = None):
    """
    Get or create `name` with the shared embedder. Raises ValueError when the collection was
    built with another embedder (Chroma's 'embedding function conflict'): run the re-embed.
    """
    ef = ef or embedding_function()
    dim = _dim_cache.get(ef.model)
    return client.get_or_create_collection(
        name=name, embedding_function=ef,
        metadata=collection_metadata(ef, dim, f"Memory collection for {name}"),
    )


# --- inspection + re-embed ----------------------------------------------------------------------


def _collection_names(client) -> List[str]:
    out = []
    for c in client.list_collections():
        out.append(c if isinstance(c, str) else c.name)
    return sorted(out)


def _stored_ef_name(col) -> Optional[str]:
    try:
        cfg = getattr(col, "configuration_json", None) or {}
        return ((cfg.get("embedding_function") or {}).get("name"))
    except Exception:  # noqa: BLE001
        return None


def _stored_dim(col) -> Optional[int]:
    try:
        got = col.get(limit=1, include=["embeddings"])
        embs = got.get("embeddings")
        if embs is not None and len(embs):
            return len(embs[0])
    except Exception:  # noqa: BLE001
        pass
    return None


def describe_collection(client, name: str, model: str, dim: Optional[int]) -> Dict[str, Any]:
    col = client.get_collection(name)  # no EF passed: works whatever it was built with
    meta = dict(col.metadata or {})
    count = col.count()
    stored_dim = _stored_dim(col) if count else meta.get("embedding_dim")
    ef_name = _stored_ef_name(col)
    reasons = []
    if ef_name != EF_NAME:
        reasons.append(f"embedder {ef_name or 'unknown'}")
    if meta.get("embedding_model") != model:
        reasons.append(f"model {meta.get('embedding_model') or 'unrecorded'} != {model}")
    if dim and count and stored_dim and stored_dim != dim:
        reasons.append(f"dimension {stored_dim} != {dim}")
    return {
        "name": name, "count": count, "embedding_function": ef_name,
        "embedding_model": meta.get("embedding_model"), "embedding_dim": stored_dim,
        "needs_reembed": bool(reasons), "reasons": reasons,
    }


def embeddings_status(client) -> Dict[str, Any]:
    ef = embedding_function()
    try:
        dim = embedding_dimension(ef)
        err = None
    except Exception as e:  # noqa: BLE001
        dim, err = None, str(e)[:300]
    cols = [describe_collection(client, n, ef.model, dim)
            for n in _collection_names(client) if not _is_temp_name(n)]
    return {"model": ef.model, "dimension": dim, "embedder_error": err, "collections": cols,
            "needs_reembed": any(c["needs_reembed"] for c in cols)}


def _read_all(col) -> Dict[str, list]:
    ids, docs, metas = [], [], []
    offset = 0
    while True:
        page = col.get(include=["documents", "metadatas"], limit=PAGE, offset=offset)
        pids = page.get("ids") or []
        if not pids:
            break
        ids += pids
        docs += page.get("documents") or [None] * len(pids)
        metas += page.get("metadatas") or [None] * len(pids)
        if len(pids) < PAGE:
            break
        offset += PAGE
    return {"ids": ids, "documents": docs, "metadatas": metas}


def rebuild_collection(client, name: str, ef: LMStudioEmbeddingFunction, dim: int) -> Dict[str, Any]:
    old = client.get_collection(name)
    description = (old.metadata or {}).get("description")
    data = _read_all(old)
    keep = [i for i, d in enumerate(data["documents"]) if d is not None and str(d).strip()]
    skipped = len(data["ids"]) - len(keep)

    tmp_name = name + REBUILD_SUFFIX
    # reembed_collections() resolved any leftover copy first; if one exists now, stop rather
    # than overwrite it (create_collection raises).
    tmp = client.create_collection(name=tmp_name, embedding_function=ef,
                                   metadata=collection_metadata(ef, dim, description))
    with_meta = [i for i in keep if data["metadatas"][i]]
    without_meta = [i for i in keep if not data["metadatas"][i]]
    try:
        for group, has_meta in ((with_meta, True), (without_meta, False)):
            for start in range(0, len(group), 64):
                idx = group[start:start + 64]
                docs = [data["documents"][i] for i in idx]
                kwargs = {"metadatas": [data["metadatas"][i] for i in idx]} if has_meta else {}
                tmp.add(ids=[data["ids"][i] for i in idx], documents=docs, embeddings=ef(docs), **kwargs)
    except Exception:
        # The original is untouched; this half-built copy is ours from this run.
        client.delete_collection(tmp_name)
        raise
    client.delete_collection(name)
    try:
        tmp.modify(name=name)
    except Exception:  # noqa: BLE001
        # A request recreated an empty `name` between delete and rename: drop it if empty, retry.
        clash = client.get_collection(name)
        if clash.count() != 0:
            raise
        client.delete_collection(name)
        tmp.modify(name=name)
    return {"name": name, "reembedded": len(keep), "skipped_without_text": skipped}


def _is_temp_name(n: str) -> bool:
    return n.endswith(REBUILD_SUFFIX) or ORPHAN_SUFFIX in n


def _all_ids(col) -> set:
    ids, offset = set(), 0
    while True:
        page = col.get(include=[], limit=PAGE, offset=offset)
        pids = page.get("ids") or []
        ids.update(pids)
        if len(pids) < PAGE:
            return ids
        offset += PAGE


def recover_leftover_copies(client) -> List[Dict[str, Any]]:
    """
    Resolve `name__reembed` copies left by an interrupted re-embed, without losing data:
    - original missing or empty: the copy holds the data -> drop the empty original, rename
      the copy back;
    - original holds every id the copy has: the copy was unfinished -> drop it;
    - otherwise keep the copy aside as name__reembed_orphan_<unix time> and log it.
    """
    actions = []
    names = set(_collection_names(client))
    for tmp_name in sorted(n for n in names if n.endswith(REBUILD_SUFFIX)):
        orig = tmp_name[: -len(REBUILD_SUFFIX)]
        tmp = client.get_collection(tmp_name)
        orig_col = client.get_collection(orig) if orig in names else None
        if orig_col is None or orig_col.count() == 0:
            if orig_col is not None:
                client.delete_collection(orig)
            tmp.modify(name=orig)
            actions.append({"name": orig, "action": "restored_from_copy", "count": tmp.count()})
            logger.warning("Re-embed: restored %s from leftover copy %s", orig, tmp_name)
        elif _all_ids(tmp) <= _all_ids(orig_col):
            client.delete_collection(tmp_name)
            actions.append({"name": orig, "action": "dropped_partial_copy"})
        else:
            aside = f"{orig}{ORPHAN_SUFFIX}{int(time.time())}"
            tmp.modify(name=aside)
            actions.append({"name": orig, "action": "kept_copy_aside", "as": aside})
            logger.error("Re-embed: %s and its leftover copy both hold data; copy kept as %s", orig, aside)
    return actions


@contextlib.contextmanager
def reembed_lock():
    """
    Cross-process lock (PostgreSQL session advisory lock). Yields True if this process holds
    it, False if another process is re-embedding. Without PostgreSQL: a process-local lock.
    """
    if os.getenv("DATABASE_TYPE", "sqlite").lower() != "postgresql":
        got = _local_reembed_lock.acquire(blocking=False)
        try:
            yield got
        finally:
            if got:
                _local_reembed_lock.release()
        return
    from database import get_db

    conn = get_db()
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT pg_try_advisory_lock(%s) AS ok", (REEMBED_LOCK_KEY,))
        got = bool((cur.fetchone() or {}).get("ok"))
        try:
            yield got
        finally:
            if got:
                cur.execute("SELECT pg_advisory_unlock(%s)", (REEMBED_LOCK_KEY,))
    finally:
        conn.close()


_local_reembed_lock = threading.Lock()


def reembed_collections(client, *, force: bool = False, dry_run: bool = False,
                        only: Optional[List[str]] = None) -> Dict[str, Any]:
    """Rebuild every collection that needs it (or all with force). Returns a report.

    Skips (report["skipped"]) when another process holds the re-embed lock.
    """
    with reembed_lock() as got:
        if not got:
            logger.info("Re-embed skipped: another process is re-embedding")
            return {"skipped": "another re-embed is running", "rebuilt": [], "up_to_date": [],
                    "dry_run": dry_run}
        return _reembed_collections_locked(client, force=force, dry_run=dry_run, only=only)


def _reembed_collections_locked(client, *, force: bool, dry_run: bool,
                                only: Optional[List[str]]) -> Dict[str, Any]:
    ef = embedding_function()
    dim = embedding_dimension(ef)  # raises if the embedder is down: nothing is touched then
    report = {"model": ef.model, "dimension": dim, "rebuilt": [], "up_to_date": [], "dry_run": dry_run}
    if not dry_run:
        report["recovered"] = recover_leftover_copies(client)
    names = [n for n in _collection_names(client) if not _is_temp_name(n)]
    for n in sorted(names):
        if only and n not in only:
            continue
        info = describe_collection(client, n, ef.model, dim)
        if not (force or info["needs_reembed"]):
            report["up_to_date"].append(n)
            continue
        if dry_run:
            report["rebuilt"].append({"name": n, "would_reembed": info["count"], "reasons": info["reasons"]})
            continue
        res = rebuild_collection(client, n, ef, dim)
        res["reasons"] = info["reasons"] or ["forced"]
        logger.info("Re-embedded collection %s with %s: %s", n, ef.model, res)
        report["rebuilt"].append(res)
    return report


def in_reloader_parent() -> bool:
    """
    True in the werkzeug reloader's watcher process, which only restarts the real server
    (that child has WERKZEUG_RUN_MAIN=true). Mirrors main.main()'s use_reloader rule.
    Under gunicorn there is no reloader; every worker may start a re-embed and the advisory
    lock lets only one run.
    """
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        return False
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    dev = os.getenv("FLASK_ENV", "").lower() == "development"
    no_reload = os.getenv("FLASK_DISABLE_RELOADER", "").lower() in ("1", "true", "yes")
    return debug or (dev and not no_reload)


def reembed_in_background(config: Dict[str, Any]) -> None:
    """At startup: rebuild stale collections in a daemon thread; never blocks or raises.

    Not in the reloader's parent process (it would race the real server's run)."""
    if in_reloader_parent():
        logger.info("Startup re-embed: left to the reloader's server process")
        return

    def _run():
        try:
            from services.rag_service import connect_chroma

            report = reembed_collections(connect_chroma(config))
            if report.get("rebuilt") or report.get("recovered") or report.get("skipped"):
                logger.info("Startup re-embed: %s", report)
            else:
                logger.info("Startup re-embed: all %d collections up to date", len(report["up_to_date"]))
        except Exception as e:  # noqa: BLE001
            logger.warning("Startup re-embed skipped: %s", e)

    threading.Thread(target=_run, name="rag-reembed", daemon=True).start()
