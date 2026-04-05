"""Append-only audit entries for user_moderation_log (shared by admin routes and other modules)."""

import json
import logging
from datetime import datetime

from database import get_db

logger = logging.getLogger(__name__)


def log_moderation_action(user_id, admin_id, action, details):
    """Record a moderation / audit row. user_id is often the subject of the action (may be archive id)."""
    db = get_db()
    cursor = db.cursor()
    try:
        log_moderation_action_cursor(cursor, user_id, admin_id, action, details)
        db.commit()
    except Exception as e:
        logger.error("log_moderation_action failed: %s", e)
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()


def log_moderation_action_cursor(cursor, user_id, admin_id, action, details):
    """Insert audit row using an existing cursor (caller commits)."""
    cursor.execute(
        """
        INSERT INTO user_moderation_log (user_id, admin_id, action, details, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, admin_id, action, json.dumps(details), datetime.now()),
    )


def moderation_entry_kind(action, user_id, admin_id, details):
    """
    UI hint: admin (staff vs other), user (self-service), system (automated).
    """
    if not action:
        return "admin"
    d = details if isinstance(details, dict) else {}
    if d.get("source") == "system" or (
        isinstance(action, str) and action.startswith("system_")
    ):
        return "system"
    try:
        if (
            user_id is not None
            and admin_id is not None
            and int(user_id) == int(admin_id)
        ):
            return "user"
    except (TypeError, ValueError):
        pass
    return "admin"
