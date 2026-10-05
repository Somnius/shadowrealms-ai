"""ChromaDB side: the backend's own client settings and embedding function, so the collections
are exactly what services.vector_store / rag_service expect (bge-m3 through LM Studio, cosine)."""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional

from .pipeline import REPO, State, target_collection


def backend_vector_store():
    """Import backend/services/vector_store.py (puts backend/ on sys.path)."""
    backend = os.environ.get("BACKEND_DIR") or os.path.join(REPO, "backend")
    if not os.path.isdir(os.path.join(backend, "services")):
        backend = REPO   # inside the backend container the backend code is the app root (/app)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from services import vector_store  # type: ignore
    return vector_store


class Store:
    def __init__(self, host: str, port: int, lmstudio_url: Optional[str] = None):
        import chromadb
        vs = backend_vector_store()
        self.vs = vs
        self.client = chromadb.HttpClient(host=host, port=port)
        model = os.environ.get("EMBEDDING_MODEL") or None
        self.ef = vs.LMStudioEmbeddingFunction(model=model, url=lmstudio_url)
        self._cols: Dict[str, Any] = {}
        self._dim_done = False

    def collection(self, name: str):
        if name not in self._cols:
            if not self._dim_done:
                # records embedding_dim in the collection metadata, like the backend does
                self.vs.embedding_dimension(self.ef)
                self._dim_done = True
            self._cols[name] = self.vs.get_rag_collection(self.client, name, self.ef)
        return self._cols[name]

    def existing(self, name: str):
        names = [c if isinstance(c, str) else c.name for c in self.client.list_collections()]
        return self.collection(name) if name in names else None

    def delete_book(self, name: str, book_id: str, campaign_id: int = 0) -> int:
        col = self.existing(name)
        if col is None:
            return 0
        where: Dict[str, Any] = {"book_id": book_id}
        if campaign_id:
            where = {"$and": [{"book_id": book_id}, {"campaign_id": campaign_id}]}
        ids = col.get(where=where, include=[])["ids"]
        for i in range(0, len(ids), 500):
            col.delete(ids=ids[i:i + 500])
        return len(ids)

    def count_book(self, name: str, book_id: str, campaign_id: int = 0) -> int:
        col = self.existing(name)
        if col is None:
            return 0
        where: Dict[str, Any] = {"book_id": book_id}
        if campaign_id:
            where = {"$and": [{"book_id": book_id}, {"campaign_id": campaign_id}]}
        return len(col.get(where=where, include=[])["ids"])

    def query(self, name: str, text: str, k: int, where: Optional[dict] = None) -> List[dict]:
        col = self.collection(name)
        res = col.query(query_texts=[text], n_results=k, where=where or None,
                        include=["metadatas", "distances"])
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        return [dict(m, _distance=d) for m, d in zip(metas, dists)]


def _fmt_secs(s: float) -> str:
    s = int(s)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


class ImportFailed(RuntimeError):
    pass


def upsert_book(store: Store, state: State, book: dict, res: dict, *, batch: int, pace_ms: int,
                resume: bool = True, force: bool = False, campaign_id: int = 0,
                log: Callable[[str], None] = print) -> dict:
    """Embed + upsert one book's chunks, resumable through state.json. Raises ImportFailed (with
    the state saved as error/partial) when Chroma or LM Studio fails."""
    name = target_collection(book, campaign_id)
    bid = book["book_id"]
    chunks = res["chunks"]
    entry = state.entry(bid, campaign_id)
    same = entry.get("chunks_sha") == res["chunks_sha"]
    start = 0
    try:
        col = store.collection(name)
        if same and entry.get("status") == "done" and not force:
            have = store.count_book(name, bid, campaign_id)
            if have >= len(chunks):
                log(f"{bid}: already imported ({have} chunks in {name})")
                return entry
            log(f"{bid}: state says done but {name} holds {have} of {len(chunks)} chunks: importing again")
        elif same and resume and not force:
            start = int(entry.get("done") or 0)
        elif entry.get("done") or entry.get("status") or force:
            removed = store.delete_book(name, bid, campaign_id)
            if removed:
                log(f"{bid}: removed {removed} old chunks (book changed or --force)")
    except Exception as e:  # noqa: BLE001
        raise ImportFailed(f"{bid}: cannot open {name}: {type(e).__name__}: {str(e)[:200]}") from e
    entry.update({"collection": name, "file_sha256": res.get("file_sha256"), "chunks_sha": res["chunks_sha"],
                  "chunks": len(chunks), "done": start, "status": "running", "campaign_id": campaign_id,
                  "started": entry.get("started") if start else time.strftime("%Y-%m-%dT%H:%M:%S")})
    state.save()
    t0, done0 = time.time(), start
    try:
        for i in range(start, len(chunks), batch):
            part = chunks[i:i + batch]
            col.upsert(ids=[c["id"] for c in part], documents=[c["document"] for c in part],
                       metadatas=[c["metadata"] for c in part])
            entry["done"] = i + len(part)
            entry["seconds"] = round(float(entry.get("seconds_prev", 0)) + time.time() - t0, 1)
            state.save()
            rate = (entry["done"] - done0) / max(time.time() - t0, 1e-6)
            eta = (len(chunks) - entry["done"]) / rate if rate else 0
            log(f"  {bid}: {entry['done']}/{len(chunks)} ({100 * entry['done'] // max(1, len(chunks))}%)"
                f" {rate:.1f} chunks/s ETA {_fmt_secs(eta)}")
            if pace_ms and entry["done"] < len(chunks):
                time.sleep(pace_ms / 1000.0)
    except BaseException as e:
        entry["status"] = "partial" if int(entry.get("done") or 0) > 0 else "error"
        entry["error"] = f"{type(e).__name__}: {str(e)[:300]}"
        entry["seconds_prev"] = entry.get("seconds", 0)
        state.save()
        if isinstance(e, Exception):
            raise ImportFailed(f"{bid}: stopped at {entry['done']}/{len(chunks)} ({entry['error'][:200]}); "
                               f"run the same command again to resume") from e
        raise
    entry.update({"status": "done", "finished": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "seconds_prev": entry.get("seconds", 0)})
    entry.pop("error", None)
    state.save()
    return entry
