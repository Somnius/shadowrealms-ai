#!/usr/bin/env python3
"""
ShadowRealms AI - Database Module
SQLite database management for characters, campaigns, and user data
"""

import sqlite3
import psycopg2
import psycopg2.extras
import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime
import os
import threading

logger = logging.getLogger(__name__)

import contextlib
import functools

# Schema "ensure" helpers run ALTER TABLE ... IF NOT EXISTS. On PostgreSQL that still takes an
# AccessExclusiveLock even when nothing changes, so calling them on every request made concurrent
# requests deadlock each other. migrate_db() runs every decorated helper at startup and commits;
# only then are the helpers marked done, and from that point they are no-ops for the rest of the
# process. A helper called outside migrate_db() (a request path) always runs its DDL and is never
# marked done there, because the request may roll back and leave the object missing while the flag
# says it exists. Every decorated helper must therefore be called from migrate_db() (and its object
# must also be in init_postgresql_schema.sql).
_SCHEMA_ENSURED = set()
_MIGRATION_PENDING = None  # set of keys run during the current migrate_db() call, else None


def _once_key(fn, args):
    return (fn.__module__, fn.__qualname__, tuple(repr(a) for a in args[1:]))


def once_per_process(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if os.getenv('DATABASE_TYPE', 'sqlite').lower() != 'postgresql':
            return fn(*args, **kwargs)
        key = _once_key(fn, args)
        if key in _SCHEMA_ENSURED:
            return None
        result = fn(*args, **kwargs)
        if _MIGRATION_PENDING is not None:
            _MIGRATION_PENDING.add(key)
        return result
    return wrapper


@contextlib.contextmanager
def schema_migration():
    """
    Wrap migrate_db()'s DDL. once_per_process helpers run inside the block are marked
    done only when the block exits without an exception, so the block must end with the
    COMMIT. If anything (the COMMIT included) fails, nothing is marked.
    """
    global _MIGRATION_PENDING
    _MIGRATION_PENDING = set()
    try:
        yield
        _SCHEMA_ENSURED.update(_MIGRATION_PENDING)
    finally:
        _MIGRATION_PENDING = None


def get_db():
    """Get database connection (PostgreSQL or SQLite based on DATABASE_TYPE env var)"""
    from config import Config
    
    db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
    
    if db_type == 'postgresql':
        # PostgreSQL connection
        logger.info("Connecting to PostgreSQL database...")
        conn = psycopg2.connect(
            dbname=os.getenv('DATABASE_NAME') or os.getenv('POSTGRES_DB', 'shadowrealms_db'),
            user=os.getenv('DATABASE_USER') or os.getenv('POSTGRES_USER', 'shadowrealms'),
            password=os.getenv('DATABASE_PASSWORD') or os.getenv('POSTGRES_PASSWORD', ''),
            host=os.getenv('DATABASE_HOST', 'localhost'),
            port=os.getenv('DATABASE_PORT', '5432'),
        )
        # Use RealDictCursor for dict-like rows (similar to SQLite's Row)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        # SQLite connection (fallback)
        db_path = Config.DATABASE
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        
        # CRITICAL: Enable foreign key constraints for CASCADE deletes
        conn.execute("PRAGMA foreign_keys = ON")
        
        return conn


# Small per-process pool for very short reads that run often (the SSE stream polls once a second
# per open stream, routes/events.py). A stream borrows a connection for one tiny query and gives
# it back, so 40 open streams don't hold 40 PostgreSQL connections for ~55 s each.
_POLL_POOL = None
_POLL_POOL_PID = None
_POLL_POOL_SEM = None
_POLL_POOL_LOCK = threading.Lock()


@contextlib.contextmanager
def poll_db(timeout: float = 5.0):
    """Borrow an autocommit RealDictCursor connection from the per-process poll pool (PostgreSQL)."""
    global _POLL_POOL, _POLL_POOL_PID, _POLL_POOL_SEM
    from psycopg2.pool import ThreadedConnectionPool

    size = max(1, int(os.getenv("SR_EVENTS_DB_POOL", "4")))
    with _POLL_POOL_LOCK:
        if _POLL_POOL is None or _POLL_POOL_PID != os.getpid():  # gunicorn --preload forks
            # minconn == maxconn: psycopg2 closes a returned connection when the pool already
            # holds minconn idle ones, so a lower minconn would reconnect on almost every poll.
            _POLL_POOL = ThreadedConnectionPool(
                size, size,
                dbname=os.getenv('DATABASE_NAME') or os.getenv('POSTGRES_DB', 'shadowrealms_db'),
                user=os.getenv('DATABASE_USER') or os.getenv('POSTGRES_USER', 'shadowrealms'),
                password=os.getenv('DATABASE_PASSWORD') or os.getenv('POSTGRES_PASSWORD', ''),
                host=os.getenv('DATABASE_HOST', 'localhost'),
                port=os.getenv('DATABASE_PORT', '5432'),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            _POLL_POOL_PID = os.getpid()
            _POLL_POOL_SEM = threading.BoundedSemaphore(size)
        pool, sem = _POLL_POOL, _POLL_POOL_SEM
    if not sem.acquire(timeout=timeout):
        raise TimeoutError("poll pool busy")
    conn = None
    broken = False
    try:
        conn = pool.getconn()
        conn.autocommit = True
        yield conn
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        broken = True
        raise
    finally:
        if conn is not None:
            pool.putconn(conn, close=broken or bool(conn.closed))
        sem.release()


def _pg_table_exists(cursor, table: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table,),
    )
    row = cursor.fetchone()
    return bool(row and row.get("exists"))


def _pg_table_columns(cursor, table: str) -> set:
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table,),
    )
    return {r["column_name"] for r in cursor.fetchall()}


@once_per_process
def ensure_users_display_timezone_column(cursor):
    """Add users.display_timezone (IANA name) if missing."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_timezone TEXT"
        )
    else:
        cursor.execute("PRAGMA table_info(users)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "display_timezone" not in cols:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN display_timezone TEXT"
            )


@once_per_process
def ensure_messages_speaker_mode_column(cursor):
    """Who is speaking: character (IC mask), player (OOC self), staff (ST/site)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS speaker_mode TEXT"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(messages)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "speaker_mode" not in cols:
            cursor.execute("ALTER TABLE messages ADD COLUMN speaker_mode TEXT")


@once_per_process
def ensure_messages_ai_message_kind_column(cursor):
    """Tag /ai slash user+assistant rows for cleanup (messages.ai_message_kind)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS ai_message_kind TEXT"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(messages)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "ai_message_kind" not in cols:
            cursor.execute(
                "ALTER TABLE messages ADD COLUMN ai_message_kind TEXT"
            )


@once_per_process
def ensure_messages_reply_to_column(cursor):
    """messages.reply_to_id: the message a chat line replies to (NULL once that one is deleted)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE messages ADD COLUMN IF NOT EXISTS reply_to_id INTEGER "
            "REFERENCES messages(id) ON DELETE SET NULL"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_reply_to ON messages(reply_to_id) "
            "WHERE reply_to_id IS NOT NULL"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(messages)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "reply_to_id" not in cols:
            cursor.execute(
                "ALTER TABLE messages ADD COLUMN reply_to_id INTEGER "
                "REFERENCES messages(id) ON DELETE SET NULL"
            )


@once_per_process
def ensure_locations_dice_leniency_floor_column(cursor):
    """Per-room Storyteller leniency (minimum die floor); NULL = normal RNG."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS dice_leniency_floor INTEGER"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='locations'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(locations)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "dice_leniency_floor" not in cols:
            cursor.execute(
                "ALTER TABLE locations ADD COLUMN dice_leniency_floor INTEGER"
            )


@once_per_process
def ensure_locations_dice_leniency_v5_column(cursor):
    """Per-room V5 leniency switches as JSON text {no_bestial, no_messy, min_successes}; NULL = off."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS dice_leniency_v5 TEXT"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='locations'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(locations)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "dice_leniency_v5" not in cols:
            cursor.execute(
                "ALTER TABLE locations ADD COLUMN dice_leniency_v5 TEXT"
            )


@once_per_process
def ensure_locations_player_access_columns(cursor):
    """Storyteller may close a location to players (is_open=false) with optional closure_reason."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS is_open BOOLEAN NOT NULL DEFAULT TRUE"
        )
        cursor.execute(
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS closure_reason TEXT"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='locations'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(locations)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "is_open" not in cols:
            cursor.execute(
                "ALTER TABLE locations ADD COLUMN is_open INTEGER NOT NULL DEFAULT 1"
            )
        if "closure_reason" not in cols:
            cursor.execute(
                "ALTER TABLE locations ADD COLUMN closure_reason TEXT"
            )


@once_per_process
def ensure_character_portrait_url_column(cursor):
    """Add characters.portrait_url if missing (PostgreSQL and SQLite)."""
    db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
    if db_type == 'postgresql':
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS portrait_url TEXT"
        )
    else:
        cursor.execute("PRAGMA table_info(characters)")
        cols = [row['name'] for row in cursor.fetchall()]
        if 'portrait_url' not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN portrait_url TEXT"
            )


@once_per_process
def ensure_users_player_profile_columns(cursor):
    """player OOC avatar + globally active character pointer."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS player_avatar_url TEXT"
        )
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS active_character_id INTEGER"
        )
    else:
        cursor.execute("PRAGMA table_info(users)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "player_avatar_url" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN player_avatar_url TEXT")
        if "active_character_id" not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN active_character_id INTEGER")


@once_per_process
def ensure_characters_is_active_column(cursor):
    """Soft-toggle for character validity (messages routes expect is_active)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='characters'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(characters)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "is_active" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
            )


@once_per_process
def ensure_characters_wod_sheet_columns(cursor):
    """sheet_locked (player edits) + structured WoD chargen metadata JSON."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS system_type TEXT NOT NULL DEFAULT 'd20'"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS attributes TEXT NOT NULL DEFAULT '{}'"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS skills TEXT NOT NULL DEFAULT '{}'"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS background TEXT NOT NULL DEFAULT ''"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS merits_flaws TEXT NOT NULL DEFAULT '{}'"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS sheet_locked BOOLEAN NOT NULL DEFAULT FALSE"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS wod_meta TEXT NOT NULL DEFAULT '{}'"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='characters'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(characters)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "sheet_locked" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN sheet_locked INTEGER NOT NULL DEFAULT 0"
            )
        if "wod_meta" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN wod_meta TEXT NOT NULL DEFAULT '{}'"
            )


@once_per_process
def ensure_characters_is_npc_column(cursor):
    """Player vs NPC flag (admin tooling)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_npc BOOLEAN NOT NULL DEFAULT FALSE"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='characters'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(characters)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "is_npc" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN is_npc INTEGER NOT NULL DEFAULT 0"
            )


@once_per_process
def ensure_characters_play_suspension_columns(cursor):
    """Admin can suspend a PC (downtime / need info); players see reason when blocked."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS play_suspended BOOLEAN NOT NULL DEFAULT FALSE"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS play_suspension_reason_code TEXT"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS play_suspension_message TEXT"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS play_suspended_at TIMESTAMP"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS play_suspended_by INTEGER REFERENCES users(id) ON DELETE SET NULL"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS play_suspension_updated_at TIMESTAMP"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='characters'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(characters)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "play_suspended" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN play_suspended INTEGER NOT NULL DEFAULT 0"
            )
        if "play_suspension_reason_code" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN play_suspension_reason_code TEXT"
            )
        if "play_suspension_message" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN play_suspension_message TEXT"
            )
        if "play_suspended_at" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN play_suspended_at TIMESTAMP"
            )
        if "play_suspended_by" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN play_suspended_by INTEGER REFERENCES users(id)"
            )
        if "play_suspension_updated_at" not in cols:
            cursor.execute(
                "ALTER TABLE characters ADD COLUMN play_suspension_updated_at TIMESTAMP"
            )


@once_per_process
def ensure_users_allow_multi_campaign_play_column(cursor):
    """When true, player may have sheet_locked PCs in more than one campaign (admin grant)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS allow_multi_campaign_play BOOLEAN NOT NULL DEFAULT FALSE"
        )
    else:
        cursor.execute("PRAGMA table_info(users)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "allow_multi_campaign_play" not in cols:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN allow_multi_campaign_play INTEGER NOT NULL DEFAULT 0"
            )


@once_per_process
def ensure_users_self_switch_playing_character_column(cursor):
    """When true, player may change active PC in a chronicle without storyteller approval."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS self_switch_playing_character "
            "BOOLEAN NOT NULL DEFAULT FALSE"
        )
    else:
        cursor.execute("PRAGMA table_info(users)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "self_switch_playing_character" not in cols:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN self_switch_playing_character "
                "INTEGER NOT NULL DEFAULT 0"
            )


@once_per_process
def ensure_users_restrict_self_join_new_chronicles_column(cursor):
    """After voluntary campaign detach, block self-join to new chronicles until ST/admin adds them."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS restrict_self_join_new_chronicles "
            "BOOLEAN NOT NULL DEFAULT FALSE"
        )
    else:
        cursor.execute("PRAGMA table_info(users)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "restrict_self_join_new_chronicles" not in cols:
            cursor.execute(
                "ALTER TABLE users ADD COLUMN restrict_self_join_new_chronicles "
                "INTEGER NOT NULL DEFAULT 0"
            )


@once_per_process
def ensure_campaign_players_active_character_id_column(cursor):
    """Per-membership: which PC is live for this chronicle (ST approval to switch)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            """
            ALTER TABLE campaign_players
            ADD COLUMN IF NOT EXISTS active_character_id INTEGER
            REFERENCES characters(id) ON DELETE SET NULL
            """
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='campaign_players'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(campaign_players)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "active_character_id" not in cols:
            cursor.execute(
                "ALTER TABLE campaign_players ADD COLUMN active_character_id INTEGER"
            )


def backfill_campaign_players_active_character(cursor):
    """One-time align membership active PC with users.active_character_id when campaign matches."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            """
            UPDATE campaign_players AS cp
            SET active_character_id = u.active_character_id
            FROM users AS u
            INNER JOIN characters AS ch ON ch.id = u.active_character_id
            WHERE cp.user_id = u.id
              AND cp.campaign_id = ch.campaign_id
              AND cp.active_character_id IS NULL
              AND (ch.is_active IS NULL OR ch.is_active IS TRUE)
            """
        )
    else:
        cursor.execute(
            """
            UPDATE campaign_players AS cp
            SET active_character_id = u.active_character_id
            FROM users AS u, characters AS ch
            WHERE u.id = cp.user_id
              AND ch.id = u.active_character_id
              AND ch.user_id = u.id
              AND ch.campaign_id = cp.campaign_id
              AND cp.active_character_id IS NULL
              AND (ch.is_active IS NULL OR ch.is_active = 1)
            """
        )


@once_per_process
def ensure_campaigns_listing_columns(cursor):
    """listed campaigns appear in discover; accepting_players allows self-serve join."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS listing_visibility TEXT NOT NULL DEFAULT 'private'"
        )
        cursor.execute(
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS accepting_players BOOLEAN NOT NULL DEFAULT FALSE"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='campaigns'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(campaigns)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "listing_visibility" not in cols:
            cursor.execute(
                "ALTER TABLE campaigns ADD COLUMN listing_visibility TEXT NOT NULL DEFAULT 'private'"
            )
        if "accepting_players" not in cols:
            cursor.execute(
                "ALTER TABLE campaigns ADD COLUMN accepting_players INTEGER NOT NULL DEFAULT 0"
            )


@once_per_process
def ensure_rules_edition_columns(cursor):
    """campaigns.rules_edition / characters.rules_edition: 'classic' (oWoD Revised) or 'v5'."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS rules_edition TEXT NOT NULL DEFAULT 'classic'"
        )
        cursor.execute(
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS rules_edition TEXT NOT NULL DEFAULT 'classic'"
        )
        return
    for table in ("campaigns", "characters"):
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        if not cursor.fetchone():
            continue
        cursor.execute(f"PRAGMA table_info({table})")
        cols = [row["name"] for row in cursor.fetchall()]
        if "rules_edition" not in cols:
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN rules_edition TEXT NOT NULL DEFAULT 'classic'"
            )


@once_per_process
def ensure_campaigns_staff_pause_columns(cursor):
    """Optional note when staff sets campaigns.is_active false (discover/join gate)."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS admin_inactive_reason TEXT"
        )
        cursor.execute(
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS admin_inactive_at TIMESTAMP"
        )
    else:
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='campaigns'"
        )
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(campaigns)")
        cols = [row["name"] for row in cursor.fetchall()]
        if "admin_inactive_reason" not in cols:
            cursor.execute("ALTER TABLE campaigns ADD COLUMN admin_inactive_reason TEXT")
        if "admin_inactive_at" not in cols:
            cursor.execute("ALTER TABLE campaigns ADD COLUMN admin_inactive_at TIMESTAMP")


@once_per_process
def ensure_character_downtime_requests_table(cursor):
    """Player-submitted downtime; admin approves or rejects with reason."""
    db_type = os.getenv("DATABASE_TYPE", "sqlite").lower()
    if db_type == "postgresql":
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS character_downtime_requests (
                id BIGSERIAL PRIMARY KEY,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                request_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                admin_reason TEXT,
                resolved_at TIMESTAMP,
                resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    else:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS character_downtime_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                request_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                admin_reason TEXT,
                resolved_at TIMESTAMP,
                resolved_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


@once_per_process
def ensure_location_reads_table(cursor):
    """Unread tracking per character and room (also in init_postgresql_schema.sql)."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS location_reads (
            id SERIAL PRIMARY KEY,
            character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
            last_read_message_id INTEGER,
            last_read_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(character_id, location_id)
        )
    """)


@once_per_process
def ensure_users_ui_language_column(cursor):
    """users.ui_language ('en' | 'el' | NULL): Storyteller reply language fallback (phase 3 UI too)."""
    if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql":
        cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ui_language TEXT")
    else:
        cursor.execute("PRAGMA table_info(users)")
        if "ui_language" not in [row["name"] for row in cursor.fetchall()]:
            cursor.execute("ALTER TABLE users ADD COLUMN ui_language TEXT")


@once_per_process
def ensure_ai_reply_grants_table(cursor):
    """One-time permits to save an AI reply as an assistant message (services/assistant_grants.py)."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_reply_grants (
            id             BIGSERIAL PRIMARY KEY,
            user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            campaign_id    INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            location_id    INTEGER,
            content_sha256 TEXT NOT NULL,
            created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            consumed_at    TIMESTAMP
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_reply_grants_lookup "
        "ON ai_reply_grants(user_id, campaign_id, content_sha256)"
    )


@once_per_process
def ensure_campaign_bans_table(cursor):
    """Campaign-scoped posting bans from the OOC monitor (services/ooc_monitor.py)."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaign_bans (
            user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            campaign_id  INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            banned_until TIMESTAMP NOT NULL,
            reason       TEXT,
            created_at   TIMESTAMP NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, campaign_id)
        )
    """)


# users.token_version is bumped by this trigger whenever a password hash or role changes or an
# account is deactivated/banned, from ANY code path (routes/users.py, routes/admin.py, scripts).
# JWTs carry the version they were issued with (services/auth_tokens.py), so the bump logs the
# user out everywhere. A login-time bcrypt rehash sets srai.rehash = 'on' to skip it.
AUTH_TOKEN_VERSION_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION users_bump_token_version() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.password_hash IS DISTINCT FROM OLD.password_hash
            AND COALESCE(current_setting('srai.rehash', true), '') <> 'on')
        OR NEW.role IS DISTINCT FROM OLD.role
        OR (COALESCE(OLD.is_active, TRUE) AND NOT COALESCE(NEW.is_active, TRUE)) THEN
        NEW.token_version := COALESCE(OLD.token_version, 0) + 1;
    END IF;
    RETURN NEW;
END;
$$
"""


@once_per_process
def ensure_laya_eval_tables(cursor):
    """Laya labels + evaluation reports (services/laya_eval.py; also in init_postgresql_schema.sql)."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS laya_labels (
            message_id     INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
            in_character   BOOLEAN NOT NULL,
            intent         TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            labelled_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS laya_eval_reports (
            id          SERIAL PRIMARY KEY,
            status      TEXT NOT NULL DEFAULT 'running',
            source      TEXT NOT NULL DEFAULT 'admin',
            started_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
            started_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMP,
            report      TEXT
        )
    """)
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_laya_eval_reports_one_running "
        "ON laya_eval_reports(status) WHERE status = 'running'"
    )


@once_per_process
def ensure_auth_security_schema(cursor):
    """Phase 5 auth: token_version + trigger, revoked jtis, rotating refresh tokens, auth_events
    (also in init_postgresql_schema.sql; services/auth_tokens.py)."""
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0")
    cursor.execute(AUTH_TOKEN_VERSION_FUNCTION_SQL)
    cursor.execute("""
        CREATE OR REPLACE TRIGGER trg_users_token_version
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION users_bump_token_version()
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_revoked_tokens (
            jti        TEXT PRIMARY KEY,
            user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_revoked_tokens_expires ON auth_revoked_tokens(expires_at)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
            jti        TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            family_id  TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            used_at    TIMESTAMP,
            revoked_at TIMESTAMP
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_family ON auth_refresh_tokens(family_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_user ON auth_refresh_tokens(user_id)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auth_events (
            id         BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            event      TEXT NOT NULL,
            user_id    INTEGER,
            username   TEXT,
            ip         TEXT,
            user_agent TEXT,
            details    TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_events_created ON auth_events(created_at DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_events_user ON auth_events(user_id, created_at DESC)")


# Chat activity counters for the SSE stream (routes/events.py): one row per campaign and per room,
# bumped by a trigger on messages so streams poll a primary-key row instead of scanning messages.
# Same text as init_postgresql_schema.sql (CI diffs pg_dump after migrate_db()).
MESSAGES_ACTIVITY_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION messages_bump_activity() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    r RECORD;
    is_reset BOOLEAN := TG_OP <> 'INSERT';
BEGIN
    IF TG_OP = 'DELETE' THEN
        r := OLD;
    ELSE
        r := NEW;
    END IF;
    -- Campaign row first, then the room row: every writer locks in the same order (no deadlocks).
    INSERT INTO campaign_activity AS a (campaign_id, version, updated_at)
    VALUES (r.campaign_id, 1, NOW())
    ON CONFLICT (campaign_id) DO UPDATE SET version = a.version + 1, updated_at = NOW();
    INSERT INTO campaign_location_activity AS a
        (location_id, campaign_id, version, last_message_id, reset_version, updated_at)
    VALUES (r.location_id, r.campaign_id, 1, CASE WHEN is_reset THEN 0 ELSE r.id END,
            CASE WHEN is_reset THEN 1 ELSE 0 END, NOW())
    ON CONFLICT (location_id) DO UPDATE SET
        campaign_id = EXCLUDED.campaign_id,
        version = a.version + 1,
        last_message_id = GREATEST(a.last_message_id, EXCLUDED.last_message_id),
        reset_version = a.reset_version + EXCLUDED.reset_version,
        updated_at = NOW();
    IF TG_OP = 'UPDATE' AND OLD.location_id IS DISTINCT FROM NEW.location_id THEN
        UPDATE campaign_location_activity
           SET version = version + 1, reset_version = reset_version + 1, updated_at = NOW()
         WHERE location_id = OLD.location_id;
    END IF;
    RETURN NULL;
END;
$$
"""


@once_per_process
def ensure_campaign_activity_schema(cursor):
    """campaign_activity / campaign_location_activity + trigger (also in init_postgresql_schema.sql)."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaign_activity (
            campaign_id INTEGER PRIMARY KEY,
            version     BIGINT NOT NULL DEFAULT 0,
            updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaign_location_activity (
            location_id     INTEGER PRIMARY KEY,
            campaign_id     INTEGER NOT NULL,
            version         BIGINT NOT NULL DEFAULT 0,
            last_message_id INTEGER NOT NULL DEFAULT 0,
            reset_version   BIGINT NOT NULL DEFAULT 0,
            updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_campaign_location_activity_campaign "
        "ON campaign_location_activity(campaign_id)"
    )
    cursor.execute(MESSAGES_ACTIVITY_FUNCTION_SQL)
    cursor.execute("""
        CREATE OR REPLACE TRIGGER trg_messages_activity
            AFTER INSERT OR UPDATE OR DELETE ON messages
            FOR EACH ROW EXECUTE FUNCTION messages_bump_activity()
    """)
    # Rooms with messages from before the trigger existed (data only; no-op once filled).
    cursor.execute("""
        INSERT INTO campaign_location_activity (location_id, campaign_id, version, last_message_id)
        SELECT location_id, MIN(campaign_id), 1, MAX(id) FROM messages GROUP BY location_id
        ON CONFLICT (location_id) DO NOTHING
    """)
    cursor.execute("""
        INSERT INTO campaign_activity (campaign_id, version)
        SELECT DISTINCT campaign_id, 1 FROM campaign_location_activity
        ON CONFLICT (campaign_id) DO NOTHING
    """)


@once_per_process
def ensure_dice_tables(cursor, db_kind: str) -> None:
    """
    Create dice_rolls / dice_roll_templates if missing.
    routes/dice.py INSERTs into dice_rolls; without this table rolls return 500.
    """
    if db_kind == 'postgresql':
        # Older DBs had dice_rolls(dice_notation, result_total, created_at, …).
        # CREATE IF NOT EXISTS never upgraded them — rename away and create the Storyteller schema.
        LEGACY_ROLLS = "dice_rolls_legacy_d20_notation"
        LEGACY_TEMPL = "dice_roll_templates_legacy_d20_notation"

        if _pg_table_exists(cursor, "dice_rolls"):
            roll_cols = _pg_table_columns(cursor, "dice_rolls")
            if "roll_type" not in roll_cols:
                logger.warning(
                    "PostgreSQL: renaming legacy dice_rolls → %s (missing roll_type column)",
                    LEGACY_ROLLS,
                )
                cursor.execute(f'ALTER TABLE dice_rolls RENAME TO "{LEGACY_ROLLS}"')

        if _pg_table_exists(cursor, "dice_roll_templates"):
            tmpl_cols = _pg_table_columns(cursor, "dice_roll_templates")
            if "dice_pool_formula" not in tmpl_cols or "is_system" not in tmpl_cols:
                logger.warning(
                    "PostgreSQL: renaming legacy dice_roll_templates → %s",
                    LEGACY_TEMPL,
                )
                cursor.execute(f'ALTER TABLE dice_roll_templates RENAME TO "{LEGACY_TEMPL}"')

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dice_roll_templates (
                id BIGSERIAL PRIMARY KEY,
                campaign_id INTEGER REFERENCES campaigns(id) ON DELETE CASCADE,
                name TEXT NOT NULL DEFAULT '',
                description TEXT,
                dice_pool_formula TEXT,
                default_difficulty INTEGER DEFAULT 6,
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                is_system INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dice_rolls (
                id BIGSERIAL PRIMARY KEY,
                campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
                location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL,
                roll_type TEXT NOT NULL,
                action_description TEXT NOT NULL,
                dice_pool INTEGER NOT NULL,
                difficulty INTEGER NOT NULL,
                results TEXT NOT NULL,
                successes INTEGER NOT NULL,
                is_botch BOOLEAN NOT NULL DEFAULT FALSE,
                is_critical BOOLEAN NOT NULL DEFAULT FALSE,
                modifiers TEXT,
                rolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    else:
        # location_id: no FK here — SQLite migrate order may not have `locations` yet
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dice_rolls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                location_id INTEGER,
                user_id INTEGER NOT NULL,
                character_id INTEGER,
                roll_type TEXT NOT NULL,
                action_description TEXT NOT NULL,
                dice_pool INTEGER NOT NULL,
                difficulty INTEGER NOT NULL,
                results TEXT NOT NULL,
                successes INTEGER NOT NULL,
                is_botch INTEGER NOT NULL DEFAULT 0,
                is_critical INTEGER NOT NULL DEFAULT 0,
                modifiers TEXT,
                rolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dice_roll_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                name TEXT NOT NULL DEFAULT '',
                description TEXT,
                dice_pool_formula TEXT,
                default_difficulty INTEGER DEFAULT 6,
                created_by INTEGER,
                is_system INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
    logger.info("dice_rolls / dice_roll_templates verified")


def migrate_db():
    """Migrate database schema if needed"""
    logger.info("Checking database migrations...")
    
    if os.getenv('DATABASE_TYPE', 'sqlite').lower() == 'postgresql':
        logger.info("PostgreSQL detected — ensuring portrait column and dice tables")
        conn = get_db()
        try:
            with schema_migration():
                cursor = conn.cursor()
                ensure_users_display_timezone_column(cursor)
                ensure_messages_ai_message_kind_column(cursor)
                ensure_messages_speaker_mode_column(cursor)
                ensure_messages_reply_to_column(cursor)
                ensure_locations_dice_leniency_floor_column(cursor)
                ensure_locations_dice_leniency_v5_column(cursor)
                ensure_locations_player_access_columns(cursor)
                ensure_character_portrait_url_column(cursor)
                ensure_users_player_profile_columns(cursor)
                ensure_characters_is_active_column(cursor)
                ensure_characters_wod_sheet_columns(cursor)
                ensure_characters_play_suspension_columns(cursor)
                ensure_users_allow_multi_campaign_play_column(cursor)
                ensure_users_self_switch_playing_character_column(cursor)
                ensure_users_restrict_self_join_new_chronicles_column(cursor)
                ensure_campaign_players_active_character_id_column(cursor)
                ensure_campaigns_listing_columns(cursor)
                ensure_rules_edition_columns(cursor)
                ensure_character_downtime_requests_table(cursor)
                ensure_characters_is_npc_column(cursor)
                ensure_campaigns_staff_pause_columns(cursor)
                ensure_location_reads_table(cursor)
                ensure_users_ui_language_column(cursor)
                ensure_ai_reply_grants_table(cursor)
                ensure_campaign_bans_table(cursor)
                ensure_laya_eval_tables(cursor)
                ensure_auth_security_schema(cursor)
                ensure_campaign_activity_schema(cursor)
                ensure_dice_tables(cursor, 'postgresql')
                backfill_campaign_players_active_character(cursor)
                from services.ai_runtime_settings import ensure_app_settings_table

                ensure_app_settings_table(cursor)
                # Last statement of the block: the helpers become no-ops only once this COMMIT succeeded.
                conn.commit()
        except Exception as e:
            logger.error(f"PostgreSQL schema ensure failed: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
        return
    
    # SQLite migrations
    conn = get_db()
    try:
        cursor = conn.cursor()
        ensure_users_display_timezone_column(cursor)

        # Check if campaigns table has game_system column
        cursor.execute("PRAGMA table_info(campaigns)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'game_system' not in columns:
            # Check if there's a system_type column that should be game_system
            if 'system_type' in columns:
                logger.info("Migrating system_type to game_system...")
                # SQLite doesn't support RENAME COLUMN in older versions, so we need to recreate the table
                cursor.execute("""
                    CREATE TABLE campaigns_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        description TEXT,
                        game_system TEXT NOT NULL DEFAULT 'd20',
                        max_players INTEGER DEFAULT 6,
                        created_by INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        status TEXT NOT NULL DEFAULT 'active',
                        FOREIGN KEY (created_by) REFERENCES users (id)
                    )
                """)
                
                # Copy data from old table to new table
                cursor.execute("""
                    INSERT INTO campaigns_new (id, name, description, game_system, max_players, created_by, created_at, is_active)
                    SELECT id, name, description, system_type, max_players, created_by, created_at, is_active
                    FROM campaigns
                """)
                
                # Drop old table and rename new table
                cursor.execute("DROP TABLE campaigns")
                cursor.execute("ALTER TABLE campaigns_new RENAME TO campaigns")
                conn.commit()
                logger.info("✅ system_type migrated to game_system")
            else:
                logger.info("Adding game_system column to campaigns table...")
                cursor.execute("ALTER TABLE campaigns ADD COLUMN game_system TEXT NOT NULL DEFAULT 'd20'")
                conn.commit()
                logger.info("✅ game_system column added")
        
        if 'status' not in columns:
            logger.info("Adding status column to campaigns table...")
            cursor.execute("ALTER TABLE campaigns ADD COLUMN status TEXT NOT NULL DEFAULT 'active'")
            conn.commit()
            logger.info("✅ status column added")
        
        # Check if campaign_players table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='campaign_players'")
        if not cursor.fetchone():
            logger.info("Creating campaign_players table...")
            cursor.execute('''
                CREATE TABLE campaign_players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    role TEXT DEFAULT 'player',
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(campaign_id, user_id)
                )
            ''')
            conn.commit()
            logger.info("✅ campaign_players table created")
        
        # Check if ai_memory table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_memory'")
        if not cursor.fetchone():
            logger.info("Creating ai_memory table...")
            cursor.execute('''
                CREATE TABLE ai_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            ''')
            conn.commit()
            logger.info("✅ ai_memory table created")
        
        # Check if messages table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages'")
        if not cursor.fetchone():
            logger.info("Creating messages table...")
            cursor.execute('''
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    character_id INTEGER,
                    message_type TEXT NOT NULL DEFAULT 'ic',
                    content TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE SET NULL
                )
            ''')
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX idx_messages_location 
                ON messages(campaign_id, location_id, created_at DESC)
            ''')
            conn.commit()
            logger.info("✅ messages table created")
        
        # Check if npcs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='npcs'")
        if not cursor.fetchone():
            logger.info("Creating npcs table...")
            cursor.execute('''
                CREATE TABLE npcs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    location_id INTEGER,
                    name TEXT NOT NULL,
                    type TEXT,
                    description TEXT,
                    personality TEXT,
                    faction TEXT,
                    npc_data TEXT,
                    created_by INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE SET NULL,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')
            # Create index for location lookups
            cursor.execute('''
                CREATE INDEX idx_npcs_location 
                ON npcs(campaign_id, location_id)
            ''')
            conn.commit()
            logger.info("✅ npcs table created")
        
        # Check if npc_messages table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='npc_messages'")
        if not cursor.fetchone():
            logger.info("Creating npc_messages table...")
            cursor.execute('''
                CREATE TABLE npc_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    npc_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    campaign_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (npc_id) REFERENCES npcs (id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE CASCADE,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
                )
            ''')
            # Create index for NPC history lookups
            cursor.execute('''
                CREATE INDEX idx_npc_messages 
                ON npc_messages(npc_id, created_at DESC)
            ''')
            conn.commit()
            logger.info("✅ npc_messages table created")
        
        # Check if combat_encounters table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='combat_encounters'")
        if not cursor.fetchone():
            logger.info("Creating combat_encounters table...")
            cursor.execute('''
                CREATE TABLE combat_encounters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    initiative_order TEXT,
                    round_number INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (location_id) REFERENCES locations (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            logger.info("✅ combat_encounters table created")
        
        # Check if combat_participants table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='combat_participants'")
        if not cursor.fetchone():
            logger.info("Creating combat_participants table...")
            cursor.execute('''
                CREATE TABLE combat_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    encounter_id INTEGER NOT NULL,
                    character_id INTEGER,
                    npc_id INTEGER,
                    initiative INTEGER DEFAULT 0,
                    current_hp INTEGER,
                    max_hp INTEGER,
                    conditions TEXT,
                    FOREIGN KEY (encounter_id) REFERENCES combat_encounters (id) ON DELETE CASCADE,
                    FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE,
                    FOREIGN KEY (npc_id) REFERENCES npcs (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            logger.info("✅ combat_participants table created")
        
        # Check if relationships table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relationships'")
        if not cursor.fetchone():
            logger.info("Creating relationships table...")
            cursor.execute('''
                CREATE TABLE relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id INTEGER NOT NULL,
                    entity1_type TEXT NOT NULL,
                    entity1_id INTEGER NOT NULL,
                    entity2_type TEXT NOT NULL,
                    entity2_id INTEGER NOT NULL,
                    relationship_type TEXT NOT NULL,
                    strength INTEGER DEFAULT 0,
                    notes TEXT,
                    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
                )
            ''')
            # Create index for relationship lookups
            cursor.execute('''
                CREATE INDEX idx_relationships 
                ON relationships(campaign_id, entity1_type, entity1_id)
            ''')
            conn.commit()
            logger.info("✅ relationships table created")
        
        # Check if location_connections table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='location_connections'")
        if not cursor.fetchone():
            logger.info("Creating location_connections table...")
            cursor.execute('''
                CREATE TABLE location_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location1_id INTEGER NOT NULL,
                    location2_id INTEGER NOT NULL,
                    connection_type TEXT DEFAULT 'path',
                    description TEXT,
                    is_bidirectional BOOLEAN DEFAULT 1,
                    FOREIGN KEY (location1_id) REFERENCES locations (id) ON DELETE CASCADE,
                    FOREIGN KEY (location2_id) REFERENCES locations (id) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            logger.info("✅ location_connections table created")
        
        # Check if location_deletion_log table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='location_deletion_log'")
        if not cursor.fetchone():
            logger.info("Creating location_deletion_log table...")
            cursor.execute('''
                CREATE TABLE location_deletion_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location_id INTEGER NOT NULL,
                    campaign_id INTEGER NOT NULL,
                    location_name TEXT NOT NULL,
                    location_type TEXT NOT NULL,
                    location_description TEXT,
                    deleted_by INTEGER NOT NULL,
                    deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_count INTEGER DEFAULT 0,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (deleted_by) REFERENCES users (id)
                )
            ''')
            # Create index for audit queries
            cursor.execute('''
                CREATE INDEX idx_deletion_log_campaign 
                ON location_deletion_log(campaign_id, deleted_at DESC)
            ''')
            conn.commit()
            logger.info("✅ location_deletion_log table created")
        
        # Check if characters table has the correct schema
        cursor.execute("PRAGMA table_info(characters)")
        columns = [column[1] for column in cursor.fetchall()]
        required_columns = ['system_type', 'attributes', 'skills', 'background', 'merits_flaws', 'updated_at']
        
        if not all(col in columns for col in required_columns):
            logger.info("Updating characters table schema...")
            # Create new table with correct schema
            cursor.execute("""
                CREATE TABLE characters_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    system_type TEXT NOT NULL DEFAULT 'd20',
                    attributes TEXT DEFAULT '{}',
                    skills TEXT DEFAULT '{}',
                    background TEXT DEFAULT '',
                    merits_flaws TEXT DEFAULT '{}',
                    user_id INTEGER NOT NULL,
                    campaign_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # Copy existing data
            cursor.execute("""
                INSERT INTO characters_new (id, name, user_id, campaign_id, created_at, updated_at)
                SELECT id, name, user_id, campaign_id, created_at, last_updated
                FROM characters
            """)
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE characters")
            cursor.execute("ALTER TABLE characters_new RENAME TO characters")
            conn.commit()
            logger.info("✅ characters table schema updated")

        ensure_character_portrait_url_column(cursor)
        ensure_users_player_profile_columns(cursor)
        ensure_characters_is_active_column(cursor)
        ensure_characters_wod_sheet_columns(cursor)
        ensure_characters_play_suspension_columns(cursor)
        ensure_users_allow_multi_campaign_play_column(cursor)
        ensure_users_self_switch_playing_character_column(cursor)
        ensure_users_restrict_self_join_new_chronicles_column(cursor)
        ensure_campaign_players_active_character_id_column(cursor)
        ensure_campaigns_listing_columns(cursor)
        ensure_rules_edition_columns(cursor)
        ensure_character_downtime_requests_table(cursor)
        ensure_messages_ai_message_kind_column(cursor)
        ensure_messages_speaker_mode_column(cursor)
        ensure_messages_reply_to_column(cursor)
        ensure_locations_dice_leniency_floor_column(cursor)
        ensure_locations_dice_leniency_v5_column(cursor)
        ensure_locations_player_access_columns(cursor)
        ensure_dice_tables(cursor, 'sqlite')
        backfill_campaign_players_active_character(cursor)
        from services.ai_runtime_settings import ensure_app_settings_table

        ensure_app_settings_table(cursor)
        conn.commit()
        conn.close()
        logger.info("✅ Database migration completed")
        
    except Exception as e:
        logger.error(f"Migration error: {e}")
        conn.close()
        raise

def init_db():
    """Initialize database with required tables"""
    logger.info("Initializing database...")
    
    # For PostgreSQL, schema is already initialized via init_postgresql_schema.sql
    # Skip schema creation to avoid SQLite-specific syntax errors
    if os.getenv('DATABASE_TYPE', 'sqlite').lower() == 'postgresql':
        logger.info("PostgreSQL detected - schema already initialized")
        return
    
    # SQLite schema initialization
    conn = get_db()
    try:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'player',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Campaigns table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                game_system TEXT NOT NULL DEFAULT 'd20',
                max_players INTEGER DEFAULT 6,
                created_by INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (created_by) REFERENCES users (id)
            )
        ''')
        
        # Characters table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                character_class TEXT,
                level INTEGER DEFAULT 1,
                campaign_id INTEGER,
                user_id INTEGER NOT NULL,
                character_data TEXT,  -- JSON data for character stats
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            ''')
        
        # Campaign players table (many-to-many)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS campaign_players (
                campaign_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                role TEXT DEFAULT 'player',
                PRIMARY KEY (campaign_id, user_id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # AI interactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                campaign_id INTEGER,
                interaction_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                performance_mode TEXT DEFAULT 'medium',
                tokens_used INTEGER,
                response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
            )
        ''')
        
        # Commit changes
        conn.commit()
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def test_database_module():
    """Standalone test function for Database Module"""
    # Skip test if using PostgreSQL (this test is SQLite-specific)
    import os
    if os.getenv('DATABASE_TYPE', 'sqlite').lower() == 'postgresql':
        print("⏭️  Skipping SQLite-specific database tests (PostgreSQL is configured)")
        return True
    
    print("🧪 Testing Database Module (SQLite)...")
    
    try:
        # Test 1: Test database connection (with local path for standalone testing)
        print("  ✓ Testing database connection...")
        
        # Override database path for standalone testing
        import tempfile
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        # Temporarily modify the database path
        from config import Config
        original_db_path = Config.DATABASE
        Config.DATABASE = temp_db.name
        
        try:
            # Test 2: Test database initialization
            print("  ✓ Testing database initialization...")
            init_db()
            print("  ✓ Database initialization successful")
            
            # Get database connection
            conn = get_db()
            print("  ✓ Database connection successful")
            
            # Test 3: Test table creation
            print("  ✓ Testing table creation...")
            cursor = conn.cursor()
            db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
            if db_type == 'postgresql':
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                tables = [row['tablename'] for row in cursor.fetchall()]
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row['name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
            expected_tables = ['users', 'campaigns', 'characters', 'campaign_players', 'ai_interactions']
            
            for table in expected_tables:
                if table in tables:
                    print(f"    ✓ Table '{table}' exists")
                else:
                    print(f"    ❌ Table '{table}' missing")
                    return False
            
            # Test 4: Test basic operations
            print("  ✓ Testing basic database operations...")
            
            # Insert test user
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
            ''', ('testuser', 'test@example.com', 'hash123', 'player'))
            
            # Insert test campaign
            cursor.execute('''
                INSERT INTO campaigns (name, description, game_system, created_by)
                VALUES (?, ?, ?, ?)
            ''', ('Test Campaign', 'A test campaign', 'd20', 1))
            
            # Verify insertions
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM campaigns")
            campaign_count = cursor.fetchone()[0]
            
            print(f"    ✓ Users: {user_count}, Campaigns: {campaign_count}")
            
            # Clean up test data
            cursor.execute("DELETE FROM campaigns WHERE name = 'Test Campaign'")
            cursor.execute("DELETE FROM users WHERE username = 'testuser'")
            conn.commit()
            
            print("  ✓ Basic operations test successful")
            
            # Test 5: Test error handling
            print("  ✓ Testing error handling...")
            try:
                cursor.execute("SELECT * FROM non_existent_table")
            except sqlite3.OperationalError:
                print("    ✓ Error handling working correctly")
            else:
                print("    ❌ Error handling failed")
                return False
            
            conn.close()
            
            # Clean up temporary database
            import os
            os.unlink(temp_db.name)
            
            print("🎉 All Database Module tests passed!")
            return True
            
        finally:
            # Restore original database path
            Config.DATABASE = original_db_path
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    """Run standalone tests if script is executed directly"""
    print("🚀 Running Database Module Standalone Tests")
    print("=" * 50)
    
    success = test_database_module()
    
    print("=" * 50)
    if success:
        print("✅ All tests passed! Module is ready for integration.")
        sys.exit(0)
    else:
        print("❌ Tests failed! Please fix issues before integration.")
        sys.exit(1)
