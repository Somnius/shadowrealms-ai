"""
Who may save a chat message with role 'assistant' (shown as the AI Storyteller).

The browser saves AI replies itself: it calls /api/ai/chat or /api/ai/slash, gets the text,
then POSTs it to /api/campaigns/<c>/locations/<l> with role 'assistant'. Without a check any
chronicle member could post anything as the Storyteller (and skip the OOC monitor, which only
looks at role 'user').

So the AI endpoints record a one-time grant (SHA-256 of the exact text, user, campaign,
room) for every reply they hand out, and an assistant message is accepted only when:
- the poster is a site admin, or
- it matches an unused grant for that user/campaign/room from the last GRANT_TTL_MINUTES;
  the grant is consumed atomically (two parallel saves of one grant: exactly one wins).

A grant is bound to the room it was issued for; replies issued without a room get no grant.
Failed generations (the AI was unavailable) get no grant either (routes/ai.py).

Dice rows (ai_message_kind dice_*) never come through here for non-admins: the dice API saves
them itself and routes/messages.py refuses client-posted ones (services/dice_markers.py).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GRANT_TTL_MINUTES = 30
ALLOWED_ROLES = ("user", "assistant")


def content_hash(content: str) -> str:
    return hashlib.sha256((content or "").strip().encode("utf-8")).hexdigest()


def grant_assistant_reply(user_id: int, campaign_id, location_id, content: Optional[str]) -> None:
    """Record that the backend handed `content` to this user for this room. Never raises."""
    if not content or not str(content).strip() or not campaign_id or not location_id:
        return
    try:
        from database import get_db

        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO ai_reply_grants (user_id, campaign_id, location_id, content_sha256)
                VALUES (%s, %s, %s, %s)
                """,
                (int(user_id), int(campaign_id), int(location_id), content_hash(str(content))),
            )
            cur.execute("DELETE FROM ai_reply_grants WHERE created_at < NOW() - INTERVAL '1 day'")
            conn.commit()
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001 - a missing grant only means the save is refused later
        logger.error("Could not record AI reply grant: %s", e)


def consume_grant(cursor, user_id: int, campaign_id: int, location_id: int, content: str) -> bool:
    """
    Mark one matching unused grant consumed; True if this call consumed it.

    The outer `consumed_at IS NULL` matters: under READ COMMITTED two parallel requests can
    pick the same id in the subquery; the second UPDATE waits for the first, then re-checks
    the outer WHERE on the new row version, finds it consumed and updates nothing.
    """
    cursor.execute(
        f"""
        UPDATE ai_reply_grants SET consumed_at = NOW()
        WHERE consumed_at IS NULL
          AND id = (
            SELECT id FROM ai_reply_grants
            WHERE user_id = %s AND campaign_id = %s
              AND location_id = %s
              AND content_sha256 = %s
              AND consumed_at IS NULL
              AND created_at > NOW() - INTERVAL '{int(GRANT_TTL_MINUTES)} minutes'
            ORDER BY id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id
        """,
        (int(user_id), int(campaign_id), int(location_id), content_hash(content)),
    )
    row = cursor.fetchone()
    return row is not None and getattr(cursor, "rowcount", 1) == 1


def assistant_post_allowed(cursor, user_id: int, campaign_id: int, location_id: int,
                           content: str, ai_message_kind: Optional[str], site_role: str) -> bool:
    if (site_role or "").strip().lower() == "admin":
        return True
    return consume_grant(cursor, user_id, campaign_id, location_id, content)
