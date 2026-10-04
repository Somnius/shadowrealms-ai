"""
Server-side posting of dice results to a room (routes/dice.py /roll, /roll/<id>/reroll, /rouse).

When a dice request names a location_id, the dice API saves, in the same transaction as the
dice_rolls row:
  1. the animation marker: role assistant, message_type system,
     ai_message_kind dice_animation[_hidden]:<animation_id>, content = marker JSON with roll_id
     (services/dice_markers.build_marker); not for Rouse checks, which have no animation;
  2. the result line: role user, message_type action, attributed to the roller and the voice
     they asked for (speak_as character / player / staff), ai_message_kind
     dice_roll[_hidden]:<animation_id> (Rouse: dice_rouse:<roll_id>).
Clients can't post dice_* kinds themselves any more (routes/messages.py), so a dice card in chat
always comes from a roll the server made.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.dice_markers import build_marker, new_animation_id
from services.location_access import (
    closed_location_error_response,
    location_is_open,
    user_can_bypass_closed_location,
)

logger = logging.getLogger(__name__)

SPEAK_AS = ("character", "player", "staff")


class DicePostError(Exception):
    """A request the dice API refuses before rolling: (payload, status)."""

    def __init__(self, payload, status: int):
        super().__init__(payload)
        self.payload = payload
        self.status = status


def choose_speaker(speak_as: Optional[str], can_staff_voice: bool,
                   character_id: Optional[int], playing_character_id: Optional[int]
                   ) -> Tuple[str, Optional[int]]:
    """
    (speaker_mode, character_id) for the result line. Pure.
    staff needs admin/helper/storyteller (else DicePostError 403); character falls back to the
    playing character and to player voice when the user has no character.
    """
    sa = str(speak_as or "").strip().lower()
    if sa not in SPEAK_AS:
        sa = "character" if (character_id or playing_character_id) else "player"
    if sa == "staff":
        if not can_staff_voice:
            raise DicePostError(
                {"error": "Only the chronicle Storyteller or site staff can post with staff voice."}, 403
            )
        return "staff", None
    if sa == "player":
        return "player", None
    cid = character_id or playing_character_id
    return ("character", int(cid)) if cid else ("player", None)


def check_room(cursor, user_id: int, campaign_id: int, location_id: int) -> None:
    """Raise DicePostError unless this user may post in the room right now (before rolling)."""
    cursor.execute(
        """
        SELECT l.is_open, l.closure_reason, c.game_system
        FROM locations l JOIN campaigns c ON c.id = l.campaign_id
        WHERE l.id = %s AND l.campaign_id = %s AND (l.is_active IS NULL OR l.is_active = TRUE)
        """,
        (location_id, campaign_id),
    )
    row = cursor.fetchone()
    if not row:
        raise DicePostError({"error": "Location not found in this campaign"}, 400)
    if not location_is_open(row.get("is_open")) and not user_can_bypass_closed_location(
        cursor, user_id, campaign_id
    ):
        resp, status = closed_location_error_response(row.get("closure_reason"), row.get("game_system"))
        raise DicePostError(resp.get_json(), status)
    try:
        from services.ooc_monitor import create_ooc_monitor

        banned, ban_message = create_ooc_monitor().check_user_ban(user_id, campaign_id)
    except Exception as e:  # noqa: BLE001 - same as routes/messages.py: a failed check doesn't block
        logger.error("Ban check failed for dice post: %s", e)
        banned, ban_message = False, ""
    if banned:
        raise DicePostError({"error": "You are temporarily banned", "ban_message": ban_message}, 403)


def resolve_speaker(cursor, user_id: int, campaign_id: int, speak_as: Optional[str],
                    character_id: Optional[int]) -> Tuple[str, Optional[int]]:
    from services.playing_character import effective_playing_character_id

    cursor.execute(
        "SELECT (SELECT LOWER(COALESCE(role, '')) FROM users WHERE id = %s) AS role, created_by "
        "FROM campaigns WHERE id = %s",
        (user_id, campaign_id),
    )
    row = cursor.fetchone() or {}
    can_staff = (row.get("role") or "") in ("admin", "helper") or (
        row.get("created_by") is not None and str(row.get("created_by")) == str(user_id)
    )
    playing = None
    if not character_id and str(speak_as or "character").strip().lower() == "character":
        playing = effective_playing_character_id(cursor, int(user_id), int(campaign_id))
    return choose_speaker(speak_as, can_staff, character_id, playing)


def _insert(cursor, campaign_id, location_id, user_id, character_id, message_type, content,
            role, kind, speaker_mode) -> int:
    cursor.execute(
        """
        INSERT INTO messages (
            campaign_id, location_id, user_id, character_id,
            message_type, content, role, created_at, ai_message_kind, speaker_mode
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (campaign_id, location_id, user_id, character_id, message_type, content, role,
         datetime.now().isoformat(), kind, speaker_mode),
    )
    return int(cursor.fetchone()["id"])


def post_roll(cursor, *, campaign_id: int, location_id: int, user_id: int, roll_id: int,
              roll_kind: str, roll_result: Optional[Dict[str, Any]], chat_text: str,
              hidden: bool, speaker: Tuple[str, Optional[int]]) -> List[int]:
    """Insert marker (if roll_result) + result line; the caller commits. Returns message ids."""
    speaker_mode, character_id = speaker
    ids: List[int] = []
    if roll_result is None:  # Rouse check: a line only
        kind = f"dice_rouse:{int(roll_id)}"
    else:
        anim = new_animation_id(roll_id)
        marker = build_marker(roll_result, animation_id=anim, roll_id=roll_id, roll_kind=roll_kind)
        ids.append(_insert(
            cursor, campaign_id, location_id, user_id, None, "system",
            json.dumps(marker, separators=(",", ":")), "assistant",
            f"{'dice_animation_hidden' if hidden else 'dice_animation'}:{anim}", None,
        ))
        kind = f"{'dice_roll_hidden' if hidden else 'dice_roll'}:{anim}"
    ids.append(_insert(
        cursor, campaign_id, location_id, user_id, character_id, "action",
        chat_text, "user", kind, speaker_mode,
    ))
    return ids


def fetch_messages(cursor, message_ids: List[int]) -> List[dict]:
    """The saved rows in the GET /campaigns/<c>/locations/<l> shape."""
    if not message_ids:
        return []
    from routes.messages import _message_dict_from_row

    cursor.execute(
        """
        SELECT m.id, m.campaign_id, m.location_id, m.user_id, m.character_id, m.message_type,
               m.content, m.role, m.created_at, u.username, u.role AS poster_role,
               u.player_avatar_url AS player_avatar_url, c.name AS character_name,
               c.portrait_url AS character_portrait_url, m.ai_message_kind, m.speaker_mode,
               camp.created_by AS campaign_created_by
        FROM messages m
        JOIN users u ON m.user_id = u.id
        JOIN campaigns camp ON m.campaign_id = camp.id
        LEFT JOIN characters c ON m.character_id = c.id
        WHERE m.id = ANY(%s)
        ORDER BY m.id ASC
        """,
        (list(message_ids),),
    )
    return [_message_dict_from_row(r) for r in cursor.fetchall()]


def embed_line(message: Optional[dict]) -> None:
    """Best effort, like routes/messages.py: the result line goes into the semantic memory."""
    if not message:
        return
    try:
        from services.rag_service import get_rag_service

        get_rag_service().store_message_embedding(
            message_id=message["id"], campaign_id=message["campaign_id"],
            location_id=message["location_id"], user_id=message["user_id"],
            content=message["content"], role=message["role"],
            character_name=message.get("character_name"),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to embed dice line: %s", e)
