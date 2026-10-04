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


def user_is_campaign_viewer(cursor, user_id: Any, campaign_id: int) -> bool:
    """Campaign creator, roster member (campaign_players) or site admin: may read the chronicle."""
    cursor.execute(
        """
        SELECT
            (SELECT LOWER(TRIM(COALESCE(role, ''))) FROM users WHERE id = %s) AS role,
            c.created_by,
            EXISTS (
                SELECT 1 FROM campaign_players cp
                WHERE cp.campaign_id = c.id AND cp.user_id = %s
            ) AS is_member
        FROM campaigns c
        WHERE c.id = %s
        """,
        (user_id, user_id, campaign_id),
    )
    row = cursor.fetchone()
    return viewer_allowed(row, user_id)


def viewer_allowed(row, user_id: Any) -> bool:
    """Pure part of user_is_campaign_viewer: row has role, created_by, is_member (None = no campaign)."""
    if not row:
        return False
    if (row.get("role") or "") == "admin":
        return True
    cb = row.get("created_by")
    if cb is not None and str(cb) == str(user_id):
        return True
    return bool(row.get("is_member"))


def location_is_open(raw_open) -> bool:
    """locations.is_open as stored (PG boolean, SQLite int, NULL = open)."""
    if raw_open is None:
        return True
    if isinstance(raw_open, bool):
        return raw_open
    if isinstance(raw_open, (int, float)):
        return raw_open != 0
    return bool(raw_open)


def readable_location_ids(rows, can_bypass_closed: bool) -> set:
    """
    Ids of the rooms whose messages a viewer may read: active rooms, and closed ones only for
    users who may enter closed rooms (admin/helper/storyteller). rows: id, is_active, is_open.
    """
    out = set()
    for r in rows:
        active = r.get("is_active")
        if active is not None and not location_is_open(active):
            continue
        if not can_bypass_closed and not location_is_open(r.get("is_open")):
            continue
        out.add(int(r["id"]))
    return out


def fetch_readable_location_ids(cursor, user_id: Any, campaign_id: int) -> set:
    cursor.execute(
        "SELECT id, is_active, is_open FROM locations WHERE campaign_id = %s",
        (campaign_id,),
    )
    rows = cursor.fetchall()
    bypass = user_can_bypass_closed_location(cursor, user_id, campaign_id)
    return readable_location_ids(rows, bypass)
