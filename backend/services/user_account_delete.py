"""
Delete a player account and all their characters while keeping location (IC) chat rows.

Messages stay in the DB with user_id reassigned to an internal archive user so FKs are satisfied.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import bcrypt

logger = logging.getLogger(__name__)

ARCHIVE_USERNAME = "ic_history_archive"
ARCHIVE_EMAIL = "ic-history-archive@system.invalid"


def _db_kind() -> str:
    return os.getenv("DATABASE_TYPE", "sqlite").lower()


def _ph() -> str:
    return "%s" if _db_kind() == "postgresql" else "?"


def _row_id(row: Any) -> Optional[int]:
    if row is None:
        return None
    if isinstance(row, dict):
        v = row.get("id")
        return int(v) if v is not None else None
    return int(row[0])


def _table_exists(cursor, table: str) -> bool:
    db = _db_kind()
    if db == "postgresql":
        cursor.execute(
            """
            SELECT EXISTS (
              SELECT FROM information_schema.tables
              WHERE table_schema = 'public' AND table_name = %s
            )
            """,
            (table,),
        )
        r = cursor.fetchone()
        return bool(r and (r.get("exists") if isinstance(r, dict) else r[0]))
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _column_exists(cursor, table: str, column: str) -> bool:
    db = _db_kind()
    if db == "postgresql":
        cursor.execute(
            """
            SELECT EXISTS (
              SELECT FROM information_schema.columns
              WHERE table_schema = 'public'
                AND table_name = %s
                AND column_name = %s
            )
            """,
            (table, column),
        )
        r = cursor.fetchone()
        return bool(r and (r.get("exists") if isinstance(r, dict) else r[0]))
    cursor.execute(f"PRAGMA table_info({table})")
    for row in cursor.fetchall():
        name = row["name"] if isinstance(row, dict) else row[1]
        if name == column:
            return True
    return False


def _friendly_admin_delete_error(exc: BaseException) -> str:
    """Plain-language message for admin UI; full detail stays in logs."""
    try:
        from psycopg2 import errors as pg_errors

        if isinstance(exc, pg_errors.ForeignKeyViolation):
            return (
                "Could not delete this account: some records still reference this user "
                "(for example locations or other world data they created). "
                "Check the server log for the exact table, or retry after updating the app."
            )
    except ImportError:
        pass
    try:
        import sqlite3

        if isinstance(exc, sqlite3.IntegrityError):
            return (
                "Could not delete this account: a database integrity rule blocked the change. "
                "Check the server log for details."
            )
    except ImportError:
        pass
    low = str(exc).lower()
    if "foreign key" in low:
        return (
            "Could not delete this account: related data still points to this user. "
            "Check the server log for details."
        )
    return "Could not delete this account. Check the server log for details."


def get_or_create_archive_user_id(cursor) -> int:
    ph = _ph()
    cursor.execute(
        f"SELECT id FROM users WHERE username = {ph}",
        (ARCHIVE_USERNAME,),
    )
    row = cursor.fetchone()
    rid = _row_id(row)
    if rid is not None:
        return rid
    pw = bcrypt.hashpw(b"<invalid>", bcrypt.gensalt()).decode("utf-8")
    db = _db_kind()
    if db == "postgresql":
        cursor.execute(
            f"""
            INSERT INTO users (username, email, password_hash, role, is_active)
            VALUES ({ph}, {ph}, {ph}, 'player', FALSE)
            RETURNING id
            """,
            (ARCHIVE_USERNAME, ARCHIVE_EMAIL, pw),
        )
        return _row_id(cursor.fetchone())
    cursor.execute(
        f"""
        INSERT INTO users (username, email, password_hash, role, is_active)
        VALUES ({ph}, {ph}, {ph}, 'player', 0)
        """,
        (ARCHIVE_USERNAME, ARCHIVE_EMAIL, pw),
    )
    return int(cursor.lastrowid)


def _character_ids_for_user(cursor, user_id: int) -> List[int]:
    ph = _ph()
    cursor.execute(
        f"SELECT id FROM characters WHERE user_id = {ph}",
        (user_id,),
    )
    out: List[int] = []
    for row in cursor.fetchall():
        cid = row["id"] if isinstance(row, dict) else row[0]
        out.append(int(cid))
    return out


def delete_player_account_preserving_chats(
    conn, target_user_id: int, acting_admin_id: int
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Remove user + their characters. Reassign IC messages and related rows to archive user.
    Storyteller-owned campaigns get created_by transferred to acting_admin_id.
    """
    if int(target_user_id) == int(acting_admin_id):
        return False, "You cannot delete your own account", {}

    cursor = conn.cursor()
    ph = _ph()
    db = _db_kind()
    stats: Dict[str, Any] = {}

    try:
        cursor.execute(
            f"SELECT id, username, role FROM users WHERE id = {ph}",
            (target_user_id,),
        )
        victim = cursor.fetchone()
        if not victim:
            return False, "User not found", {}
        uname = victim["username"] if isinstance(victim, dict) else victim[1]
        role = victim["role"] if isinstance(victim, dict) else victim[2]
        if uname == ARCHIVE_USERNAME:
            return False, "Cannot delete the system archive account", {}

        if role == "admin":
            cursor.execute("SELECT COUNT(*) AS c FROM users WHERE role = 'admin'")
            ac = cursor.fetchone()
            n_admins = int(ac["c"] if isinstance(ac, dict) else ac[0])
            if n_admins <= 1:
                return False, "Cannot delete the last admin account", {}

        archive_id = get_or_create_archive_user_id(cursor)

        cursor.execute(
            f"UPDATE campaigns SET created_by = {ph} WHERE created_by = {ph}",
            (acting_admin_id, target_user_id),
        )
        stats["campaigns_transferred"] = cursor.rowcount if cursor.rowcount is not None else 0

        if _table_exists(cursor, "locations") and _column_exists(
            cursor, "locations", "created_by"
        ):
            cursor.execute(
                f"UPDATE locations SET created_by = {ph} WHERE created_by = {ph}",
                (acting_admin_id, target_user_id),
            )
            stats["locations_created_by_transferred"] = (
                cursor.rowcount if cursor.rowcount is not None else 0
            )

        cursor.execute(
            f"""
            UPDATE messages SET user_id = {ph}, character_id = NULL
            WHERE user_id = {ph}
            """,
            (archive_id, target_user_id),
        )
        stats["messages_reassigned"] = cursor.rowcount if cursor.rowcount is not None else 0

        if _table_exists(cursor, "dice_rolls"):
            cursor.execute(
                f"""
                UPDATE dice_rolls SET user_id = {ph}, character_id = NULL
                WHERE user_id = {ph}
                """,
                (archive_id, target_user_id),
            )
            stats["dice_rolls_reassigned"] = cursor.rowcount if cursor.rowcount is not None else 0

        if _table_exists(cursor, "ai_interactions"):
            cursor.execute(
                f"UPDATE ai_interactions SET user_id = {ph} WHERE user_id = {ph}",
                (archive_id, target_user_id),
            )

        if _table_exists(cursor, "user_moderation_log"):
            cursor.execute(
                f"UPDATE user_moderation_log SET user_id = {ph} WHERE user_id = {ph}",
                (archive_id, target_user_id),
            )
            cursor.execute(
                f"UPDATE user_moderation_log SET admin_id = {ph} WHERE admin_id = {ph}",
                (acting_admin_id, target_user_id),
            )

        if _table_exists(cursor, "character_moderation"):
            cursor.execute(
                f"""
                UPDATE character_moderation SET moderated_by = {ph}
                WHERE moderated_by = {ph}
                """,
                (acting_admin_id, target_user_id),
            )

        if _table_exists(cursor, "npcs"):
            cursor.execute(
                f"UPDATE npcs SET created_by = {ph} WHERE created_by = {ph}",
                (archive_id, target_user_id),
            )

        if _table_exists(cursor, "location_deletion_log"):
            cursor.execute(
                f"UPDATE location_deletion_log SET deleted_by = {ph} WHERE deleted_by = {ph}",
                (archive_id, target_user_id),
            )

        char_ids = _character_ids_for_user(cursor, target_user_id)
        stats["characters_deleted"] = len(char_ids)
        for cid in char_ids:
            cursor.execute(
                f"UPDATE users SET active_character_id = NULL WHERE active_character_id = {ph}",
                (cid,),
            )
            if _table_exists(cursor, "campaign_players"):
                cursor.execute(
                    f"""
                    UPDATE campaign_players SET active_character_id = NULL
                    WHERE active_character_id = {ph}
                    """,
                    (cid,),
                )

        if _table_exists(cursor, "campaign_players"):
            cursor.execute(
                f"DELETE FROM campaign_players WHERE user_id = {ph}",
                (target_user_id,),
            )

        if char_ids and _table_exists(cursor, "character_locations"):
            for cid in char_ids:
                cursor.execute(
                    f"DELETE FROM character_locations WHERE character_id = {ph}",
                    (cid,),
                )

        cursor.execute(
            f"DELETE FROM characters WHERE user_id = {ph}",
            (target_user_id,),
        )

        if _table_exists(cursor, "user_moderation_log"):
            details = json.dumps(
                {
                    "former_user_id": target_user_id,
                    "former_username": uname,
                    **stats,
                },
                default=str,
            )
            cursor.execute(
                f"""
                INSERT INTO user_moderation_log (user_id, admin_id, action, details, created_at)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph})
                """,
                (
                    archive_id,
                    acting_admin_id,
                    "account_deleted_preserve_chats",
                    details,
                    datetime.utcnow(),
                ),
            )

        cursor.execute(
            f"DELETE FROM users WHERE id = {ph}",
            (target_user_id,),
        )

        conn.commit()
        logger.info(
            "Admin %s deleted user %s (%s); messages reassigned to archive user %s",
            acting_admin_id,
            target_user_id,
            uname,
            archive_id,
        )
        return True, "", stats
    except Exception as e:
        conn.rollback()
        logger.exception("delete_player_account_preserving_chats failed: %s", e)
        return False, _friendly_admin_delete_error(e), {}
