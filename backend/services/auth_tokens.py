"""
Server-side session state for JWTs (phase 5; docs/SECURITY_MODEL.md).

- Every access/refresh token carries `tv` = users.token_version at issue time. A database trigger
  (users_bump_token_version, init_postgresql_schema.sql) bumps token_version whenever a password
  hash or role changes or an account is deactivated/banned, from any code path; "log out
  everywhere" bumps it explicitly. Tokens with an old `tv` are rejected on the next request.
- Single tokens are revoked by jti (auth_revoked_tokens, kept until the token would expire).
- Refresh tokens rotate: each is single-use (auth_refresh_tokens). Presenting a used one again is
  reuse => the whole family (that login's chain) is revoked.
- auth_events: audit rows for logins, failures, lockouts, logouts, refresh reuse.

The blocklist check runs on every authenticated request, so it uses a small per-process
connection pool instead of opening a new PostgreSQL connection each time.
"""

from __future__ import annotations

import json
import logging
import os
import random
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

REFRESH_COOKIE = "srai_refresh"
REFRESH_COOKIE_PATH = "/api/auth"


class AuthStoreUnavailable(Exception):
    """The session database could not be reached; answered with 503, never as 'logged out'."""


def _is_pg() -> bool:
    return os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql"


# ---------------------------------------------------------------------------------------------
# Connection pool (created lazily per process: safe with gunicorn --preload forks)
# ---------------------------------------------------------------------------------------------

_pool = None
_pool_pid = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool, _pool_pid
    pid = os.getpid()
    with _pool_lock:
        if _pool is None or _pool_pid != pid:
            import psycopg2.extras
            from psycopg2.pool import ThreadedConnectionPool

            _pool = ThreadedConnectionPool(
                0,
                int(os.getenv("AUTH_DB_POOL_MAX", "8")),
                dbname=os.getenv("DATABASE_NAME") or os.getenv("POSTGRES_DB", "shadowrealms_db"),
                user=os.getenv("DATABASE_USER") or os.getenv("POSTGRES_USER", "shadowrealms"),
                password=os.getenv("DATABASE_PASSWORD") or os.getenv("POSTGRES_PASSWORD", ""),
                host=os.getenv("DATABASE_HOST", "localhost"),
                port=os.getenv("DATABASE_PORT", "5432"),
                cursor_factory=psycopg2.extras.RealDictCursor,
                connect_timeout=5,
            )
            _pool_pid = pid
        return _pool


@contextmanager
def _conn():
    """Pooled connection; falls back to a one-off connection when the pool is exhausted."""
    import psycopg2
    from psycopg2.pool import PoolError

    pool = None
    try:
        pool = _get_pool()
        conn = pool.getconn()
    except PoolError:
        pool = None
        from database import get_db

        conn = get_db()
    except psycopg2.Error as e:
        raise AuthStoreUnavailable(str(e)) from e
    broken = False
    try:
        yield conn
        conn.commit()
    except psycopg2.Error as e:
        broken = conn.closed != 0
        try:
            conn.rollback()
        except psycopg2.Error:
            broken = True
        raise AuthStoreUnavailable(str(e)) from e
    except Exception:
        try:
            conn.rollback()
        except psycopg2.Error:
            broken = True
        raise
    finally:
        if pool is not None:
            pool.putconn(conn, close=broken or conn.closed != 0)
        else:
            conn.close()


# ---------------------------------------------------------------------------------------------
# Blocklist check (Flask-JWT-Extended token_in_blocklist_loader)
# ---------------------------------------------------------------------------------------------

def is_token_revoked(claims: dict) -> Tuple[bool, str]:
    from services.auth_security import token_revoked

    if not _is_pg():
        return False, ""
    try:
        uid = int(claims.get("sub"))
    except (TypeError, ValueError):
        return True, "bad_sub"
    jti = str(claims.get("jti") or "")
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.token_version, u.is_active,
                   EXISTS (SELECT 1 FROM auth_revoked_tokens r WHERE r.jti = %s) AS jti_revoked
            FROM users u WHERE u.id = %s
            """,
            (jti, uid),
        )
        row = cur.fetchone()
    return token_revoked(claims, row, bool(row and row.get("jti_revoked")))


def revoke_jti(user_id: int, jti: str, exp_ts: Optional[int]) -> None:
    if not _is_pg() or not jti:
        return
    expires = (
        datetime.fromtimestamp(int(exp_ts), tz=timezone.utc).replace(tzinfo=None)
        if exp_ts else datetime.utcnow() + timedelta(days=1)
    )
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO auth_revoked_tokens (jti, user_id, expires_at) VALUES (%s, %s, %s) "
            "ON CONFLICT (jti) DO NOTHING",
            (jti, user_id, expires),
        )
        cur.execute("DELETE FROM auth_revoked_tokens WHERE expires_at < NOW() - INTERVAL '1 hour'")


def bump_token_version(user_id: int) -> int:
    """Invalidate every token of the user (log out everywhere). Returns the new version."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = %s RETURNING token_version",
            (user_id,),
        )
        row = cur.fetchone()
        cur.execute(
            "UPDATE auth_refresh_tokens SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL",
            (user_id,),
        )
    return int(row["token_version"]) if row else 0


# ---------------------------------------------------------------------------------------------
# Issuing tokens + refresh rotation
# ---------------------------------------------------------------------------------------------

def access_minutes() -> int:
    try:
        return max(5, int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "30")))
    except ValueError:
        return 30


def refresh_days() -> int:
    try:
        return max(1, int(os.getenv("JWT_REFRESH_TOKEN_DAYS", "14")))
    except ValueError:
        return 14


def session_max_days() -> int:
    try:
        return max(1, int(os.getenv("JWT_SESSION_MAX_DAYS", "30")))
    except ValueError:
        return 30


def issue_tokens(user: dict, family_id: Optional[str] = None, auth_time: Optional[int] = None) -> dict:
    """
    New access + refresh token for `user` ({id, username, role, token_version}). A new login
    starts a new family; a refresh continues the family and keeps the original auth_time so the
    session can't be extended past JWT_SESSION_MAX_DAYS.
    """
    from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

    uid = int(user["id"])
    tv = int(user.get("token_version") or 0)
    now = int(datetime.now(timezone.utc).timestamp())
    auth_time = int(auth_time or now)
    family_id = family_id or uuid.uuid4().hex
    access = create_access_token(
        identity=str(uid),
        additional_claims={"tv": tv, "username": user.get("username"), "role": user.get("role")},
        expires_delta=timedelta(minutes=access_minutes()),
    )
    max_left = auth_time + session_max_days() * 86400 - now
    refresh_ttl = max(60, min(refresh_days() * 86400, max_left))
    refresh = create_refresh_token(
        identity=str(uid),
        additional_claims={"tv": tv, "fam": family_id, "auth_time": auth_time},
        expires_delta=timedelta(seconds=refresh_ttl),
    )
    rclaims = decode_token(refresh)
    if _is_pg():
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO auth_refresh_tokens (jti, user_id, family_id, expires_at) VALUES (%s, %s, %s, %s)",
                (rclaims["jti"], uid, family_id,
                 datetime.fromtimestamp(rclaims["exp"], tz=timezone.utc).replace(tzinfo=None)),
            )
            if random.random() < 0.05:
                cur.execute("DELETE FROM auth_refresh_tokens WHERE expires_at < NOW() - INTERVAL '1 day'")
    return {
        "access_token": access,
        "refresh_token": refresh,
        "refresh_max_age": refresh_ttl,
        "expires_in": access_minutes() * 60,
    }


def consume_refresh(claims: dict) -> Tuple[str, Optional[dict]]:
    """
    Mark a presented refresh token used. Returns ("ok", user_row) or (reason, None) with
    reason in {"unknown", "reuse", "revoked", "user"}. Reuse revokes the whole family.
    """
    jti = claims.get("jti")
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT user_id, family_id, used_at, revoked_at FROM auth_refresh_tokens WHERE jti = %s FOR UPDATE",
            (jti,),
        )
        row = cur.fetchone()
        if not row:
            return "unknown", None
        if row["revoked_at"] is not None:
            return "revoked", None
        if row["used_at"] is not None:
            cur.execute(
                "UPDATE auth_refresh_tokens SET revoked_at = NOW() WHERE family_id = %s AND revoked_at IS NULL",
                (row["family_id"],),
            )
            return "reuse", None
        cur.execute("UPDATE auth_refresh_tokens SET used_at = NOW() WHERE jti = %s", (jti,))
        cur.execute(
            "SELECT id, username, email, role, is_active, token_version FROM users WHERE id = %s",
            (row["user_id"],),
        )
        user = cur.fetchone()
        if not user or not user["is_active"] or int(user["token_version"] or 0) != claims.get("tv"):
            return "user", None
        return "ok", dict(user)


def revoke_family(family_id: Optional[str]) -> None:
    if not family_id or not _is_pg():
        return
    with _conn() as conn:
        conn.cursor().execute(
            "UPDATE auth_refresh_tokens SET revoked_at = NOW() WHERE family_id = %s AND revoked_at IS NULL",
            (family_id,),
        )


# ---------------------------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------------------------

def log_auth_event(event: str, *, user_id=None, username=None, ip=None, user_agent=None, details=None) -> None:
    """Best effort: an audit failure never breaks a login."""
    if not _is_pg():
        return
    try:
        with _conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO auth_events (event, user_id, username, ip, user_agent, details)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    event[:64],
                    user_id,
                    (username or None) and str(username)[:150],
                    (ip or None) and str(ip)[:64],
                    (user_agent or None) and str(user_agent)[:300],
                    json.dumps(details) if details else None,
                ),
            )
            if random.random() < 0.01:
                cur.execute("DELETE FROM auth_events WHERE created_at < NOW() - INTERVAL '180 days'")
    except Exception as e:  # noqa: BLE001
        logger.warning("auth_events insert failed (%s): %s", event, e)
