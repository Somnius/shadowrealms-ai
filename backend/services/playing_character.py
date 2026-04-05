"""
Per-campaign playing character resolution and storyteller checks.
"""

from __future__ import annotations

import os
from typing import Any, Optional


def _is_active_char_sql(alias: str = "ch") -> str:
    db = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db == "postgresql":
        return f"({alias}.is_active IS NULL OR {alias}.is_active IS TRUE)"
    return f"({alias}.is_active IS NULL OR {alias}.is_active = 1)"


def effective_playing_character_id(
    cursor: Any, user_id: int, campaign_id: int
) -> Optional[int]:
    """
    Prefer campaign_players.active_character_id when valid;
    else single active character in campaign;
    else users.active_character_id if it matches this campaign.
    """
    ichar = _is_active_char_sql("ch")

    cursor.execute(
        """
        SELECT active_character_id FROM campaign_players
        WHERE campaign_id = %s AND user_id = %s
        """,
        (campaign_id, user_id),
    )
    cp_row = cursor.fetchone()
    cp_ac = cp_row.get("active_character_id") if cp_row else None

    if cp_ac is not None:
        cursor.execute(
            f"""
            SELECT ch.id FROM characters ch
            WHERE ch.id = %s AND ch.user_id = %s AND ch.campaign_id = %s
              AND {ichar}
            """,
            (cp_ac, user_id, campaign_id),
        )
        if cursor.fetchone():
            return int(cp_ac)

    cursor.execute(
        f"""
        SELECT ch.id FROM characters ch
        WHERE ch.user_id = %s AND ch.campaign_id = %s
          AND {ichar}
        ORDER BY ch.id ASC
        """,
        (user_id, campaign_id),
    )
    rows = cursor.fetchall()
    if len(rows) == 1:
        cid = int(rows[0]["id"])
        cursor.execute(
            """
            UPDATE campaign_players
            SET active_character_id = %s
            WHERE campaign_id = %s AND user_id = %s
              AND active_character_id IS NULL
            """,
            (cid, campaign_id, user_id),
        )
        return cid

    cursor.execute(
        "SELECT active_character_id FROM users WHERE id = %s",
        (user_id,),
    )
    urow = cursor.fetchone() or {}
    aid = urow.get("active_character_id")
    if aid is not None:
        cursor.execute(
            f"""
            SELECT ch.id FROM characters ch
            WHERE ch.id = %s AND ch.user_id = %s AND ch.campaign_id = %s
              AND {ichar}
            """,
            (aid, user_id, campaign_id),
        )
        if cursor.fetchone():
            return int(aid)

    if len(rows) > 1:
        return int(rows[0]["id"])
    return None


def is_site_staff_role(role: Optional[str]) -> bool:
    return role in ("admin", "helper")


def is_campaign_storyteller_or_staff(
    cursor: Any, user_id: int, campaign_id: int
) -> bool:
    """Campaign creator or site admin/helper."""
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    ur = cursor.fetchone()
    if not ur:
        return False
    role = ur.get("role")
    if is_site_staff_role(role):
        return True
    cursor.execute("SELECT created_by FROM campaigns WHERE id = %s", (campaign_id,))
    crow = cursor.fetchone()
    if not crow or crow.get("created_by") is None:
        return False
    return str(crow["created_by"]) == str(user_id)
