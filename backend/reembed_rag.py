#!/usr/bin/env python3
"""
Re-embed ChromaDB collections with the configured embedder (EMBEDDING_MODEL, LM Studio).

Rebuilds only collections whose embedder / model / dimension differs from the current one
(idempotent). Run inside the backend container:

  docker compose exec backend python reembed_rag.py            # rebuild what's stale
  docker compose exec backend python reembed_rag.py --dry-run  # only report
  docker compose exec backend python reembed_rag.py --force    # rebuild everything

The same routine runs at backend startup (in the background) and from the admin panel.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.rag_service import connect_chroma  # noqa: E402
from services.vector_store import embeddings_status, reembed_collections  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="rebuild every collection")
    ap.add_argument("--dry-run", action="store_true", help="report what would be rebuilt")
    ap.add_argument("--only", nargs="*", help="collection names to limit to")
    args = ap.parse_args()
    client = connect_chroma({})
    report = reembed_collections(client, force=args.force, dry_run=args.dry_run, only=args.only)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    status = embeddings_status(client)
    print(json.dumps({c["name"]: {k: c[k] for k in ("count", "embedding_model", "embedding_dim", "needs_reembed")}
                      for c in status["collections"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
