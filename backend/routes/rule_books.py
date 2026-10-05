#!/usr/bin/env python3
"""
Rule books API (admin only).

The books are imported outside the app by books/import_books.py into the collections of
docs/rules/RULE_BOOKS_RAG.md. The app only reads them; here an admin can see what is
imported and remove a book. The old in-app PDF import (/scan, /process, /search, /context,
/systems) is gone: any logged-in player could start it, and it duplicated chunks.
"""

import logging
import re

from flask import Blueprint, current_app, jsonify, request

from routes.admin import require_admin
from services.rules_edition import ALL_RULE_BOOK_COLLECTIONS, CHRONICLE_BOOKS_COLLECTION, RULE_BOOK_COLLECTIONS

logger = logging.getLogger(__name__)

bp = Blueprint('rule_books', __name__)

PAGE = 500
_BOOK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


def _chroma():
    from services.rag_service import connect_chroma

    return connect_chroma(current_app.config)


def _get_collection(client, name):
    """The collection, or None when it doesn't exist (nothing imported yet)."""
    try:
        return client.get_collection(name)  # metadata reads only: any embedder
    except Exception as e:  # noqa: BLE001
        logger.debug("Rule book collection %s unavailable: %s", name, e)
        return None


def summarize_collection(col, page_size: int = 0) -> list:
    """
    One entry per book (per book and chronicle in rule_books_chronicle): title, edition,
    line, version, chunk count and chunks per kind. Reads metadatas in pages.
    """
    page_size = page_size or PAGE
    books = {}
    offset = 0
    while True:
        page = col.get(include=["metadatas"], limit=page_size, offset=offset)
        ids = page.get("ids") or []
        metas = page.get("metadatas") or [None] * len(ids)
        for meta in metas:
            meta = meta or {}
            key = (meta.get("book_id") or "?", int(meta.get("campaign_id") or 0))
            b = books.get(key)
            if b is None:
                b = books[key] = {
                    "book_id": key[0], "campaign_id": key[1], "title": meta.get("title"),
                    "edition": meta.get("edition"), "line": meta.get("line"),
                    "version": meta.get("version"), "chunks": 0, "kinds": {},
                }
            b["chunks"] += 1
            kind = meta.get("kind") or "?"
            b["kinds"][kind] = b["kinds"].get(kind, 0) + 1
            if meta.get("line") and b["line"] != meta.get("line"):
                b["line"] = "mixed"
        if len(ids) < page_size:
            break
        offset += page_size
    return sorted(books.values(), key=lambda b: (b["campaign_id"], b["book_id"]))


@bp.route('/status', methods=['GET'])
@require_admin()
def rule_books_status():
    """What is imported: per collection, per book."""
    try:
        client = _chroma()
        out = {}
        for name in ALL_RULE_BOOK_COLLECTIONS:
            col = _get_collection(client, name)
            if col is None:
                out[name] = {"exists": False, "chunks": 0, "books": []}
                continue
            books = summarize_collection(col)
            out[name] = {"exists": True, "chunks": sum(b["chunks"] for b in books), "books": books}
        return jsonify({"success": True, "collections": out}), 200
    except Exception as e:
        logger.error("Rule book status failed: %s", e)
        return jsonify({"success": False, "error": "Rule book request failed"}), 500


def _count_ids(col, where) -> int:
    n, offset = 0, 0
    while True:
        page = col.get(where=where, include=[], limit=PAGE, offset=offset)
        got = len(page.get("ids") or [])
        n += got
        if got < PAGE:
            return n
        offset += PAGE


@bp.route('/<book_id>', methods=['DELETE'])
@require_admin()
def delete_rule_book(book_id):
    """
    Remove a book's chunks from the global collections, or with ?campaign_id=N only from
    that chronicle's attached books (rule_books_chronicle).
    """
    if not _BOOK_ID_RE.match(book_id or ""):
        return jsonify({"success": False, "error": "Invalid book_id"}), 400
    campaign_arg = request.args.get('campaign_id')
    if campaign_arg is not None:
        try:
            campaign_id = int(campaign_arg)
        except ValueError:
            campaign_id = 0
        if campaign_id < 1:
            return jsonify({"success": False, "error": "campaign_id must be a positive integer"}), 400
        targets = [(CHRONICLE_BOOKS_COLLECTION,
                    {"$and": [{"book_id": book_id}, {"campaign_id": campaign_id}]})]
    else:
        targets = [(name, {"book_id": book_id}) for name in RULE_BOOK_COLLECTIONS.values()]
    try:
        client = _chroma()
        deleted = {}
        for name, where in targets:
            col = _get_collection(client, name)
            if col is None:
                continue
            n = _count_ids(col, where)
            if n:
                col.delete(where=where)
                deleted[name] = n
        if not deleted:
            return jsonify({"success": False, "error": "Book not found"}), 404
        logger.info("Rule book %s removed: %s", book_id, deleted)
        return jsonify({"success": True, "book_id": book_id, "deleted": deleted}), 200
    except Exception as e:
        logger.error("Rule book delete failed: %s", e)
        return jsonify({"success": False, "error": "Rule book request failed"}), 500
