"""Caching and state: extract/chunk caches under data/rule_books/cache, import state in
data/rule_books/state.json. Extraction is keyed by the PDF's sha256 + extractor version + the
manifest fields that change extraction, so unchanged books are never re-extracted."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Dict, List, Optional

from . import chunker, extract
from .manifest import CHRONICLE_COLLECTION, collection_for
from .textutil import TokenCounter, file_sha256, sha1

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # books/
REPO = os.path.dirname(HERE)
BOOKS_ROOT = os.path.join(HERE, "World_of_Darkness")
DATA = os.path.join(REPO, "data", "rule_books")
EXTRACT_FIELDS = ("include", "exclude", "page_offset", "strip_lines", "sidebar_fonts", "toc_fixes",
                  "skip_sections", "toc_strip_prefix", "outline", "toc", "page_map_from", "edition")


class Paths:
    def __init__(self, books_root: str = BOOKS_ROOT, data: str = DATA):
        self.books_root = books_root
        self.data = data
        self.cache = os.path.join(data, "cache")
        self.state = os.path.join(data, "state.json")
        self.eval = os.path.join(data, "eval")

    def pdf(self, book) -> str:
        return os.path.join(self.books_root, book["path"])

    def extract_file(self, book) -> str:
        return os.path.join(self.cache, f"{book['book_id']}.extract.json")

    def chunks_file(self, book, campaign_id: int = 0) -> str:
        suffix = f".c{campaign_id}" if campaign_id else ""
        return os.path.join(self.cache, f"{book['book_id']}{suffix}.chunks.json")


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _write_json(path: str, data: Any):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    os.replace(tmp, path)


def extract_key(book: Dict[str, Any], file_sha: str) -> str:
    fields = {k: book.get(k) for k in EXTRACT_FIELDS}
    return sha1(json.dumps([file_sha, extract.EXTRACTOR_VERSION, fields], sort_keys=True))


# --- extract ---------------------------------------------------------------------------------

def _extract_worker(args):
    pdf, book, key, file_sha, out = args
    t = time.time()
    try:
        res = extract.extract_book(pdf, book)
    except Exception as e:  # noqa: BLE001 - one bad PDF must not stop the batch
        res = {"book_id": book["book_id"], "status": "failed", "warnings": [f"extract failed: {e!r}"]}
    res["key"] = key
    res["file_sha256"] = file_sha
    res["seconds"] = round(time.time() - t, 1)
    _write_json(out, res)
    return book["book_id"], res.get("status"), res["seconds"]


def extract_books(books: List[dict], paths: Paths, workers: int = 4, force: bool = False,
                  log: Callable[[str], None] = print) -> Dict[str, dict]:
    """Extract every book whose cache is missing or stale. Returns {book_id: extract result}."""
    jobs, results = [], {}
    for b in books:
        pdf = paths.pdf(b)
        if not os.path.exists(pdf):
            results[b["book_id"]] = {"book_id": b["book_id"], "status": "missing", "warnings": [f"file not found: {b['path']}"]}
            continue
        fsha = file_sha256(pdf)
        key = extract_key(b, fsha)
        cached = _read_json(paths.extract_file(b))
        if cached and cached.get("key") == key and not force:
            results[b["book_id"]] = cached
            continue
        jobs.append((pdf, dict(b, _books_root=paths.books_root), key, fsha, paths.extract_file(b)))
    if jobs:
        log(f"extracting {len(jobs)} book(s) with {min(workers, len(jobs))} worker(s); {len(results)} cached")
        workers = max(1, min(workers, 8, len(jobs)))
        if workers == 1:
            done = map(_extract_worker, jobs)
        else:
            pool = ProcessPoolExecutor(max_workers=workers)
            done = pool.map(_extract_worker, jobs)
        for n, (bid, status, secs) in enumerate(done, 1):
            log(f"  [{n}/{len(jobs)}] {bid}: {status} ({secs}s)")
        if workers > 1:
            pool.shutdown()
        for _, b, _, _, out in jobs:
            results[b["book_id"]] = _read_json(out) or {"status": "failed"}
    return results


# --- chunk -----------------------------------------------------------------------------------

def _book_order(b: dict):
    return (b["edition"], b["precedence"], b["book_id"])


def chunk_books(books: List[dict], all_books: List[dict], extracts: Dict[str, dict], paths: Paths,
                counter: TokenCounter, write: bool = True, campaign_id: int = 0) -> Dict[str, dict]:
    """Chunk the given books in precedence order. A chunk whose text already exists in a
    higher-precedence book of the same edition (in this run or in its chunk cache) is skipped."""
    out: Dict[str, dict] = {}
    seen: Dict[str, Dict[str, str]] = {}   # edition -> {content_sha: book_id}
    used: Dict[str, Dict[str, str]] = {}   # edition -> {book_id: chunks_sha} of the books seen so far
    selected = {b["book_id"] for b in books}
    for b in sorted(all_books, key=_book_order):
        ed = seen.setdefault(b["edition"], {})
        before = used.setdefault(b["edition"], {})
        if b["book_id"] in selected:
            ext = extracts.get(b["book_id"])
            if not ext or ext.get("status") != "ok":
                out[b["book_id"]] = {"status": (ext or {}).get("status", "not extracted"), "chunks": [],
                                     "stats": {}, "warnings": (ext or {}).get("warnings", [])}
                continue
            res = chunker.chunk_book(ext, b, counter, seen=ed, campaign_id=campaign_id)
            res.update({"status": "ok", "extract_key": ext["key"], "file_sha256": ext.get("file_sha256"),
                        "counter": counter.name,
                        "chunker_version": chunker.CHUNKER_VERSION, "warnings": ext.get("warnings", []),
                        "pages_used": ext.get("pages_used"), "outline": ext.get("outline"),
                        "page_numbers": ext.get("page_numbers"), "dedup_key": dedup_key(before)})
            res["chunks_sha"] = sha1(json.dumps([[c["id"], c["document"], c["metadata"]] for c in res["chunks"]],
                                                sort_keys=True, ensure_ascii=False))
            if write:
                _write_json(paths.chunks_file(b, campaign_id), res)
            out[b["book_id"]] = res
            chunks, csha = res["chunks"], res["chunks_sha"]
        else:
            cached = _read_json(paths.chunks_file(b))
            chunks = cached.get("chunks", []) if cached else []
            csha = cached.get("chunks_sha") if cached else None
        if csha:
            before[b["book_id"]] = csha
        for c in chunks:
            ed.setdefault(c["metadata"]["content_sha"], b["book_id"])
    return out


def dedup_key(before: Dict[str, str]) -> str:
    """Identity of the higher-precedence chunk sets a book was de-duplicated against."""
    return sha1(json.dumps(sorted(before.items())))


def higher_books_key(book: dict, all_books: List[dict], paths: "Paths") -> str:
    """dedup_key for `book` from the chunk caches as they are now."""
    before: Dict[str, str] = {}
    for b in sorted(all_books, key=_book_order):
        if b["book_id"] == book["book_id"]:
            break
        if b["edition"] != book["edition"]:
            continue
        cached = _read_json(paths.chunks_file(b))
        if cached and cached.get("chunks_sha"):
            before[b["book_id"]] = cached["chunks_sha"]
    return dedup_key(before)


def load_chunks(book: dict, paths: Paths, campaign_id: int = 0, counter_name: Optional[str] = None,
                all_books: Optional[List[dict]] = None) -> Optional[dict]:
    """Cached chunks if still valid, else None (run extract/chunk). Valid = same extract, chunker
    version, token counter, and the same higher-precedence chunk sets it was de-duplicated against
    (a changed corebook re-chunks the supplements of its edition)."""
    res = _read_json(paths.chunks_file(book, campaign_id))
    ext = _read_json(paths.extract_file(book))
    if not res or not ext or res.get("extract_key") != ext.get("key"):
        return None
    if res.get("chunker_version") != chunker.CHUNKER_VERSION:
        return None
    if counter_name is not None and res.get("counter") != counter_name:
        return None
    if all_books is not None and res.get("dedup_key") != higher_books_key(book, all_books, paths):
        return None
    return res


# --- state -----------------------------------------------------------------------------------

class State:
    def __init__(self, path: str):
        self.path = path
        self.data = _read_json(path) or {"books": {}, "attachments": {}}
        self.data.setdefault("books", {})
        self.data.setdefault("attachments", {})

    def entry(self, book_id: str, campaign_id: int = 0) -> dict:
        if campaign_id:
            return self.data["attachments"].setdefault(f"{book_id}@{campaign_id}", {})
        return self.data["books"].setdefault(book_id, {})

    def drop(self, book_id: str, campaign_id: int = 0):
        if campaign_id:
            self.data["attachments"].pop(f"{book_id}@{campaign_id}", None)
        else:
            self.data["books"].pop(book_id, None)

    def save(self):
        _write_json(self.path, self.data)


def target_collection(book: dict, campaign_id: int = 0) -> str:
    return CHRONICLE_COLLECTION if campaign_id else collection_for(book)
