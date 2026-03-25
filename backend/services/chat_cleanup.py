"""
Remove /ai slash command lines and their assistant replies from a location.
"""

from __future__ import annotations

import logging
import re
from typing import Any, List, Set

logger = logging.getLogger(__name__)

_SLASH_USER_RE = re.compile(r"^\s*/ai(\s|$)", re.IGNORECASE)
# Assistant markdown from slash commands usually contains **`/ai verb`**
_SLASH_ASSISTANT_RE = re.compile(r"\*\*`/ai\s+\S+", re.IGNORECASE)


def collect_slash_ai_message_ids(rows: List[Any]) -> Set[int]:
    """rows: iterable of dict-like with id, role, content, ai_message_kind."""
    to_del: Set[int] = set()
    for r in rows:
        rid = r["id"]
        role = (r.get("role") or "").strip().lower()
        content = r.get("content") or ""
        kind = (r.get("ai_message_kind") or "").strip().lower()

        if kind in ("slash_user", "slash_assistant"):
            to_del.add(rid)
            continue
        if role == "user" and _SLASH_USER_RE.match(content):
            to_del.add(rid)
            continue
        if role == "assistant" and _SLASH_ASSISTANT_RE.search(content[:800]):
            to_del.add(rid)
    return to_del


def delete_slash_ai_messages(conn, campaign_id: int, location_id: int) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, role, content,
               COALESCE(ai_message_kind, '') AS ai_message_kind
        FROM messages
        WHERE campaign_id = %s AND location_id = %s
        ORDER BY id ASC
        """,
        (campaign_id, location_id),
    )
    rows = cur.fetchall()
    ids = sorted(collect_slash_ai_message_ids(rows))
    if not ids:
        conn.commit()
        return 0
    for mid in ids:
        cur.execute("DELETE FROM messages WHERE id = %s", (mid,))
    conn.commit()
    logger.info(
        "clean ai: deleted %s messages in campaign=%s location=%s",
        len(ids),
        campaign_id,
        location_id,
    )
    return len(ids)
