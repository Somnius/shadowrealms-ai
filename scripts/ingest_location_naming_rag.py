#!/usr/bin/env python3
"""
Ingest docs/location-naming-world-of-darkness.md into ChromaDB rule_books (global campaign_id=0).

Run from repo root (host with Chroma on localhost:8000):
  python3 scripts/ingest_location_naming_rag.py

Or inside backend container (has chromadb + /app/project_docs):
  docker compose exec backend python3 /app/ingest_location_naming_rag.py

Requires: pip install chromadb (see backend/requirements.txt)
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path


def main() -> int:
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        print("Install chromadb: pip install chromadb", file=sys.stderr)
        return 1

    repo = Path(__file__).resolve().parents[1]
    doc = Path(os.getenv("LOCATION_NAMING_DOCS_PATH", "")).expanduser()
    if not doc.is_file():
        # Docker backend: docs mounted at /app/project_docs
        docker_doc = Path("/app/project_docs/location-naming-world-of-darkness.md")
        if docker_doc.is_file():
            doc = docker_doc
        else:
            doc = repo / "docs" / "location-naming-world-of-darkness.md"
    if not doc.is_file():
        print(f"Missing guide: {doc}", file=sys.stderr)
        return 1

    host = os.getenv("CHROMADB_HOST", "localhost")
    port = int(os.getenv("CHROMADB_PORT", "8000"))

    text = doc.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"\n(?=## )", text)
    chunks = [p.strip() for p in parts if p.strip() and len(p.strip()) >= 40]

    client = chromadb.HttpClient(
        host=host,
        port=port,
        settings=Settings(anonymized_telemetry=False),
    )
    coll = client.get_or_create_collection(
        name="rule_books",
        metadata={"description": "Rule books and ShadowRealms tooling docs"},
    )

    book_id = "location_naming_wod"
    try:
        coll.delete(where={"book_id": book_id})
        print(f"Removed prior chunks for book_id={book_id}")
    except Exception as e:
        print(f"(delete skipped or none) {e}")

    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    for i, chunk in enumerate(chunks):
        slug = hashlib.md5(chunk[:240].encode()).hexdigest()[:10]
        cid = f"{book_id}_{i}_{slug}"
        title = chunk.split("\n", 1)[0].lstrip("#").strip()[:200]
        ids.append(cid)
        docs.append(chunk)
        metas.append(
            {
                "book_id": book_id,
                "book_name": "Location naming (WoD)",
                "system": "world_of_darkness",
                "page_number": int(i),
                "chunk_id": cid,
                "word_count": int(len(chunk.split())),
                "processed_at": "scripts/ingest_location_naming_rag",
                "section_title": title,
                "campaign_id": int(0),
                "user_id": int(0),
            }
        )

    coll.add(ids=ids, documents=docs, metadatas=metas)
    print(f"OK: added {len(docs)} chunks from {doc} → Chroma {host}:{port} collection rule_books")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
