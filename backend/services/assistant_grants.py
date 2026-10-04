"""
Who may save a chat message with role 'assistant' (shown as the AI Storyteller).

The browser saves AI replies itself: it calls /api/ai/chat or /api/ai/slash, gets the text,
then POSTs it to /api/campaigns/<c>/locations/<l> with role 'assistant'. Without a check any
chronicle member could post anything as the Storyteller (and skip the OOC monitor, which only
looks at role 'user').

So the AI endpoints record a one-time grant (SHA-256 of the exact text, user, campaign,
room) for every reply they hand out, and an assistant message is accepted only when:
- the poster is a site admin, or
- it's a dice-animation marker (ai_message_kind dice_animation[_hidden]:<id>) whose content
  is the marker JSON for that same id, with only the known marker keys and scalar / short
  list values, at most MAX_MARKER_CHARS (visual only, carries no free text), or
- it matches an unused grant for that user/campaign/room from the last GRANT_TTL_MINUTES;
  the grant is consumed atomically (two parallel saves of one grant: exactly one wins).

A grant is bound to the room it was issued for; replies issued without a room get no grant.
Failed generations (the AI was unavailable) get no grant either (routes/ai.py).
"""

from __future__ import annotations

import hashlib
import json
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


# Keys frontend/src/dice/diceMarker.js buildDiceMarker() writes (plus the legacy diceFinal).
MARKER_KEYS = frozenset({
    "animation_id", "started_at_ms", "duration_ms", "rules_edition", "difficulty", "successes",
    "is_botch", "dice_preview", "hunger_flags", "extra_dice_count", "pool_size", "margin",
    "outcome", "is_critical", "is_messy_critical", "is_bestial_failure", "is_total_failure",
    "is_exceptional", "specialty", "specialty_rerolls", "willpower", "diceFinal",
})
MAX_MARKER_CHARS = 2000
_MAX_MARKER_STR = 64
_MAX_MARKER_LIST = 40


def _marker_value_ok(v) -> bool:
    if v is None or isinstance(v, (bool, int, float)):
        return True
    if isinstance(v, str):
        return len(v) <= _MAX_MARKER_STR
    if isinstance(v, list):
        return len(v) <= _MAX_MARKER_LIST and all(
            x is None or isinstance(x, (bool, int, float)) for x in v
        )
    return False


def is_dice_marker(content: str, ai_message_kind: Optional[str]) -> bool:
    """A dice animation marker: kind dice_animation[_hidden]:<id> and content = that marker's JSON."""
    kind = str(ai_message_kind or "")
    prefix, _, anim_id = kind.partition(":")
    if prefix not in ("dice_animation", "dice_animation_hidden") or not anim_id:
        return False
    if not isinstance(content, str) or len(content) > MAX_MARKER_CHARS:
        return False
    try:
        obj = json.loads(content)
    except (TypeError, ValueError):
        return False
    if not isinstance(obj, dict) or str(obj.get("animation_id")) != anim_id:
        return False
    return set(obj) <= MARKER_KEYS and all(_marker_value_ok(v) for v in obj.values())


def assistant_post_allowed(cursor, user_id: int, campaign_id: int, location_id: int,
                           content: str, ai_message_kind: Optional[str], site_role: str) -> bool:
    if (site_role or "").strip().lower() == "admin":
        return True
    if is_dice_marker(content, ai_message_kind):
        return True
    return consume_grant(cursor, user_id, campaign_id, location_id, content)
