"""Storyteller-closed locations: who may enter and API helpers."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from flask import jsonify


def user_can_bypass_closed_location(
    cursor,
    user_id: Any,
    campaign_id: int,
) -> bool:
    """Site admin, helper, or campaign creator may enter/read closed rooms."""
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    urow = cursor.fetchone() or {}
    role = (urow.get("role") or "").strip().lower()
    if role in ("admin", "helper"):
        return True
    cursor.execute("SELECT created_by FROM campaigns WHERE id = %s", (campaign_id,))
    crow = cursor.fetchone() or {}
    cb = crow.get("created_by")
    return cb is not None and str(cb) == str(user_id)


def get_location_open_state(cursor, location_id: int, campaign_id: int):
    cursor.execute(
        """
        SELECT is_open, closure_reason, type
        FROM locations
        WHERE id = %s AND campaign_id = %s
        """,
        (location_id, campaign_id),
    )
    return cursor.fetchone()


def closed_location_error_response(
    closure_reason: Optional[str],
    game_system: Optional[str] = None,
) -> Tuple[Any, int]:
    """403 payload for players when a room is closed."""
    gs = (game_system or "").lower()
    if "vampire" in gs or "masquerade" in gs:
        flavor = "The Prince's decree holds: this chamber stays sealed."
    elif "werewolf" in gs or "garou" in gs or "apocalypse" in gs:
        flavor = "The spirits whisper that this hunting ground is not to be trod — not yet."
    elif "mage" in gs or "ascension" in gs or "awakening" in gs:
        flavor = "The Consensus here is locked; the doors exist in more dimensions than one."
    else:
        flavor = "The Storyteller has drawn the curtain on this scene for now."

    msg = (closure_reason or "").strip()
    return (
        jsonify(
            {
                "error": "location_closed",
                "message": msg
                or "This location is temporarily unavailable.",
                "flavor": flavor,
            }
        ),
        403,
    )
