"""
Key/value app settings stored in PostgreSQL or SQLite (app_settings table).
Used for admin-configurable LM Studio model override and global AI master system prompt.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from database import get_db

logger = logging.getLogger(__name__)


def ensure_app_settings_table(cursor) -> None:
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key VARCHAR(255) PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    else:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def _row_value(row: Any) -> Optional[str]:
    if row is None:
        return None
    if isinstance(row, dict):
        v = row.get("value")
        return None if v is None else str(v)
    return None if row[0] is None else str(row[0])


def get_app_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        ph = "%s" if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql" else "?"
        cursor.execute(f"SELECT value FROM app_settings WHERE key = {ph}", (key,))
        row = cursor.fetchone()
        if not row:
            return default
        return _row_value(row)
    finally:
        conn.close()


def set_app_setting(key: str, value: Optional[str]) -> None:
    """Persist value; None or empty string deletes the row (revert to env/default)."""
    conn = get_db()
    try:
        cursor = conn.cursor()
        db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
        if value is None or (isinstance(value, str) and value.strip() == ""):
            ph = "%s" if db_type == "postgresql" else "?"
            cursor.execute(f"DELETE FROM app_settings WHERE key = {ph}", (key,))
        elif db_type == "postgresql":
            cursor.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
        else:
            cursor.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = datetime('now')
                """,
                (key, value),
            )
        conn.commit()
    finally:
        conn.close()


def delete_app_setting(key: str) -> None:
    set_app_setting(key, None)
