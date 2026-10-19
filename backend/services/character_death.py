"""
Whether a character has fallen, from character_moderation (the admin kill and revive rows).

A character is fallen when its latest 'kill' or 'revive' row is a kill. characters.is_active alone
can't say it: staff may set is_active on a sheet, and inactive is not dead.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional


def _table_missing(cursor) -> bool:
    """SQLite only: a database made before the PostgreSQL schema has no character_moderation (nothing has
    fallen there). PostgreSQL always has it (init_postgresql_schema.sql)."""
    if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql":
        return False
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'character_moderation'", ())
    return not cursor.fetchone()


def deaths(cursor, character_ids: Iterable[Any]) -> Dict[int, Dict[str, Any]]:
    """{character_id: {death_type, death_description, died_at}} for the fallen ones among the ids."""
    ids = sorted({int(i) for i in character_ids if i is not None})
    if not ids or _table_missing(cursor):
        return {}
    marks = ", ".join(["%s"] * len(ids))
    cursor.execute(
        f"""
        SELECT id, character_id, action, death_type, death_description, moderated_at
        FROM character_moderation
        WHERE character_id IN ({marks}) AND action IN ('kill', 'revive')
        ORDER BY moderated_at, id
        """,
        tuple(ids),
    )
    latest: Dict[int, Dict[str, Any]] = {}
    for row in cursor.fetchall():
        latest[int(row["character_id"])] = row
    return {
        cid: {
            "death_type": row.get("death_type"),
            "death_description": row.get("death_description"),
            "died_at": row.get("moderated_at"),
        }
        for cid, row in latest.items()
        if row.get("action") == "kill"
    }


def death_of(cursor, character_id: Any) -> Optional[Dict[str, Any]]:
    return deaths(cursor, [character_id]).get(int(character_id))
