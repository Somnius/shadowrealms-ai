"""
The message a player replied to, as context for the Storyteller (/api/ai/chat with reply_to_id).

A reply quote is shown in the chat (routes/messages.py, services/message_actions.py); without
this block the Storyteller never saw what was quoted. The block names the quoted author and
kind and carries a short text, or for a dice card the deterministic roll summary from
services.roll_explainer (the model must not recount it).

Same visibility rules as replying: same room, and a hidden roll only for admin / helper / the
chronicle's owner. Anything else gives no block.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.message_actions import is_hidden_kind, reply_author, reply_excerpt

logger = logging.getLogger(__name__)

REPLY_TEXT_CHARS = 400


def quoted_kind(role: Any, kind: Any, speaker_mode: Any) -> str:
    """Short English label of what was quoted."""
    k = str(kind or "").strip().lower()
    if k.startswith(("dice_roll", "dice_animation")):
        return "dice roll"
    if k.startswith("dice_rouse"):
        return "Rouse check"
    if str(role or "").strip().lower() == "assistant":
        return "Storyteller message"
    sm = str(speaker_mode or "").strip().lower()
    if sm == "staff":
        return "staff message"
    if sm == "player":
        return "player message (out of character)"
    return "message"


def format_reply_context(author: str, kind_label: str, text: str) -> str:
    """The prompt block (pure)."""
    who = author or ("the Storyteller" if kind_label == "Storyteller message" else "someone")
    return (
        "REPLY CONTEXT: The player's new message is a reply to this earlier message in the room. "
        "Answer with it in mind; any dice numbers in it are final, never recount or change them.\n"
        f"Quoted {kind_label} from {who}: {text}"
    )


def build_reply_context(campaign_id: Any, location_id: Any, user_id: Any, reply_to_id: Any) -> str:
    """The block for /api/ai/chat, or '' (no reply, not visible, other room, error). Never raises."""
    if not reply_to_id or not campaign_id or not location_id:
        return ""
    try:
        from database import get_db
        from services import roll_explainer as rx

        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT m.id, m.campaign_id, m.location_id, m.role, m.ai_message_kind, m.speaker_mode,
                       m.content, u.username, c.name AS character_name
                FROM messages m
                LEFT JOIN users u ON u.id = m.user_id
                LEFT JOIN characters c ON c.id = m.character_id
                WHERE m.id = %s
                """,
                (int(reply_to_id),),
            )
            row: Optional[Dict[str, Any]] = cur.fetchone()
            if not row or str(row.get("campaign_id")) != str(campaign_id) \
                    or str(row.get("location_id")) != str(location_id):
                return ""
            kind = row.get("ai_message_kind")
            if is_hidden_kind(kind):
                cur.execute(
                    "SELECT u.role, c.created_by FROM users u, campaigns c WHERE u.id = %s AND c.id = %s",
                    (int(user_id), int(campaign_id)),
                )
                who = cur.fetchone() or {}
                if not rx.can_see_hidden(who.get("role"), user_id, who.get("created_by")):
                    return ""
            author = reply_author(row.get("role"), row.get("speaker_mode"), row.get("username"),
                                  row.get("character_name"))
            label = quoted_kind(row.get("role"), kind, row.get("speaker_mode"))
            text = ""
            if rx.is_roll_message_kind(kind):
                cur.execute("SELECT game_system FROM campaigns WHERE id = %s", (int(campaign_id),))
                gs = str((cur.fetchone() or {}).get("game_system") or "")
                rec = rx.record_for_message(cur, row, int(campaign_id), int(location_id), gs)
                if rec is not None:
                    text = rx.explain(rec, "en")["summary"]
            if not text:
                text = reply_excerpt(row.get("content"), REPLY_TEXT_CHARS)
            cur.close()
        finally:
            conn.close()
        return format_reply_context(author, label, text) if text else ""
    except Exception as e:  # noqa: BLE001 - a reply without the quote beats no reply
        logger.warning("Reply context unavailable: %s", e)
        return ""
