"""
A cross-process "the Storyteller is writing" marker (docs/CHRONICLE.md).

last_generation_meta() lives in one request of one gunicorn worker, so a background job can't use
it. Every Storyteller generation instead bumps a row in ai_busy_marks (active + 1 before, - 1
after); the chronicle writer waits while active > 0. A worker that dies mid-reply leaves the count
up, so a row not touched for STALE_S seconds counts as idle. Best effort: a database error never
gets in the way of a reply.
"""

from __future__ import annotations

import contextlib
import logging
import os

logger = logging.getLogger(__name__)

STORYTELLER = "storyteller"
STALE_S = 90


def _pg() -> bool:
    return os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql"


def _bump(name: str, delta: int) -> None:
    if not _pg():
        return
    conn = None
    try:
        from database import get_db

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ai_busy_marks (name, active, updated_at) VALUES (%s, GREATEST(%s, 0), NOW())
            ON CONFLICT (name) DO UPDATE
               SET active = GREATEST(ai_busy_marks.active + %s, 0), updated_at = NOW()
            """,
            (name, delta, delta),
        )
        conn.commit()
    except Exception as e:  # noqa: BLE001 - a hint for the chronicle writer, never a failure
        logger.debug("ai_busy_marks update failed: %s", e)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass


@contextlib.contextmanager
def storyteller_busy():
    """Wrap one Storyteller generation."""
    _bump(STORYTELLER, 1)
    try:
        yield
    finally:
        _bump(STORYTELLER, -1)


def is_busy(cursor, name: str = STORYTELLER, stale_s: int = STALE_S) -> bool:
    """True while a generation is running somewhere (rows older than stale_s are ignored)."""
    if not _pg():
        return False
    try:
        cursor.execute(
            "SELECT active FROM ai_busy_marks WHERE name = %s AND updated_at > NOW() - make_interval(secs => %s)",
            (name, int(stale_s)),
        )
        row = cursor.fetchone()
    except Exception:  # noqa: BLE001
        return False
    return bool(row and int(row.get("active") or 0) > 0)
