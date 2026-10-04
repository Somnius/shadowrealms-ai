"""
Query parsing and output shaping for the admin login audit (GET /api/admin/auth-events).

Pure (no Flask, no DB) so it can be unit-tested. Filters: user_id, username (case-insensitive,
exact), event, ip. Paging: limit + offset; the route reads one extra row to know whether another
page exists.
"""

from __future__ import annotations

import ipaddress
import json
from typing import Any, Mapping

from services.request_validation import RequestValidationError

AUTH_EVENT_TYPES = (
    'login',
    'login_failed',
    'login_blocked',
    'login_disabled',
    'lockout',
    'logout',
    'logout_all',
    'refresh_reuse',
    'register',
    'invite_invalid',
    'password_changed',
    'password_change_failed',
)

# Only these detail fields leave the server. Anything else (refresh-token family ids, invite code
# prefixes, ...) stays in the database.
PUBLIC_DETAIL_KEYS = ('role', 'known_user', 'seconds', 'retry_after')

DEFAULT_LIMIT = 100
MAX_LIMIT = 500
MAX_OFFSET = 100_000


def _int_arg(args: Mapping[str, Any], name: str, default: int, lo: int, hi: int) -> int:
    raw = args.get(name)
    if raw is None or str(raw).strip() == '':
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        raise RequestValidationError(f'{name} must be an integer') from None
    return min(max(value, lo), hi)


def parse_ip(value: Any) -> str:
    """A single IPv4/IPv6 address as text, or '' when empty. Wildcards and ranges are refused."""
    text = str(value or '').strip()[:64]
    if not text:
        return ''
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        raise RequestValidationError('ip must be an IPv4 or IPv6 address') from None


def parse_auth_events_query(args: Mapping[str, Any]) -> dict:
    """
    Turn query-string args into ``{'where': [...], 'params': [...], 'limit': n, 'offset': n}``.

    ``where`` holds fixed SQL fragments with %s placeholders; values only go into ``params``.
    Raises ``RequestValidationError`` for a malformed user_id, limit, offset or ip.
    """
    where: list[str] = []
    params: list[Any] = []

    raw_user_id = str(args.get('user_id') or '').strip()
    if raw_user_id:
        try:
            params.append(int(raw_user_id))
        except ValueError:
            raise RequestValidationError('user_id must be an integer') from None
        where.append('user_id = %s')

    username = str(args.get('username') or '').strip()[:150]
    if username:
        where.append('LOWER(username) = LOWER(%s)')
        params.append(username)

    event = str(args.get('event') or '').strip()[:64]
    if event:
        where.append('event = %s')
        params.append(event)

    ip = parse_ip(args.get('ip'))
    if ip:
        where.append('ip = %s')
        params.append(ip)

    return {
        'where': where,
        'params': params,
        'limit': _int_arg(args, 'limit', DEFAULT_LIMIT, 1, MAX_LIMIT),
        'offset': _int_arg(args, 'offset', 0, 0, MAX_OFFSET),
    }


def build_auth_events_sql(query: dict) -> tuple[str, list]:
    """SELECT for one page plus one extra row (to detect a next page)."""
    sql = (
        "SELECT id, created_at, event, user_id, username, ip, user_agent, details FROM auth_events "
        + ("WHERE " + " AND ".join(query['where']) + " " if query['where'] else "")
        + "ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s"
    )
    return sql, [*query['params'], query['limit'] + 1, query['offset']]


def public_details(raw: Any) -> dict | None:
    """Keep only the whitelisted detail fields (``raw`` is the JSON text or an already-parsed dict)."""
    if not raw:
        return None
    if isinstance(raw, (str, bytes)):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    if not isinstance(raw, dict):
        return None
    kept = {k: raw[k] for k in PUBLIC_DETAIL_KEYS if k in raw}
    return kept or None


def utc_iso(value: Any) -> Any:
    """ISO 8601 with an explicit zone. auth_events.created_at is a naive TIMESTAMP in UTC
    (PostgreSQL runs with timezone=UTC), so a naive value gets a ``Z``."""
    if not hasattr(value, 'isoformat'):
        return value
    if getattr(value, 'tzinfo', None) is None:
        return value.isoformat() + 'Z'
    return value.isoformat()


def public_auth_event(row: Mapping[str, Any]) -> dict:
    """One auth_events row as the admin API returns it."""
    return {
        'id': row.get('id'),
        'created_at': utc_iso(row.get('created_at')),
        'event': row.get('event'),
        'user_id': row.get('user_id'),
        'username': row.get('username'),
        'ip': row.get('ip'),
        'user_agent': row.get('user_agent'),
        'details': public_details(row.get('details')),
    }
