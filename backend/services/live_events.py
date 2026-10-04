"""
Pure helpers for the chronicle live-update stream (routes/events.py).

- Stream tickets: EventSource can't send an Authorization header, and the long-lived JWT must not
  end up in URLs (nginx access logs). The browser trades its JWT for a short-lived, single-purpose
  ticket (signed with itsdangerous, salt 'sr-events-ticket', bound to one user + campaign, 60 s) and
  passes that as ?ticket=. A ticket is not a JWT, so it can't be replayed against other endpoints.
  Tickets are single-use: each carries a random nonce ("n") that the stream claims once
  (TicketLedger; Redis in production, so a ticket leaked from a log can't be replayed).
- SSE framing and snapshot diffing ("notify, then fetch": events carry ids only, never content, so
  visibility rules such as hidden dice stay in the normal message GET).
- Activity snapshots: rows of campaign_activity / campaign_location_activity (bumped by a trigger
  on messages, see init_postgresql_schema.sql); streams only emit rooms the viewer may read.
"""

from __future__ import annotations

import json
import secrets
import threading
from typing import Dict, Iterable, List, Optional, Tuple

from itsdangerous import URLSafeTimedSerializer

TICKET_SALT = "sr-events-ticket"
TICKET_MAX_AGE_SECONDS = 60


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=TICKET_SALT)


def make_ticket(secret: str, user_id: int, campaign_id: int) -> str:
    return _serializer(secret).dumps(
        {"u": int(user_id), "c": int(campaign_id), "n": secrets.token_urlsafe(16)}
    )


def read_ticket_claims(secret: str, ticket: str, campaign_id: int,
                       max_age: int = TICKET_MAX_AGE_SECONDS) -> Optional[Tuple[int, Optional[str]]]:
    """(user_id, nonce) for a valid, unexpired ticket for this campaign; else None."""
    if not ticket or not isinstance(ticket, str) or len(ticket) > 512:
        return None
    try:
        data = _serializer(secret).loads(ticket, max_age=max_age)
    except Exception:  # noqa: BLE001 - bad signature, expired, malformed payloads
        return None
    if not isinstance(data, dict):
        return None
    try:
        if int(data.get("c")) != int(campaign_id):
            return None
        nonce = data.get("n")
        return int(data.get("u")), (str(nonce) if isinstance(nonce, str) and nonce else None)
    except (TypeError, ValueError):
        return None


class TicketLedger:
    """
    Single use: claim(nonce) is True only the first time for a nonce (within ttl).
    store: anything with incr(key, ttl) -> int (services.auth_security RedisStore / MemoryStore /
    FailoverStore). With the in-memory fallback the guarantee is per worker process.
    """

    PREFIX = "srai:sse-ticket:"

    def __init__(self, store, ttl: int = TICKET_MAX_AGE_SECONDS * 2):
        self.store = store
        self.ttl = ttl

    def claim(self, nonce: Optional[str]) -> bool:
        if not nonce or len(nonce) > 64:
            return False
        try:
            return int(self.store.incr(self.PREFIX + nonce, self.ttl)) == 1
        except Exception:  # noqa: BLE001 - store down: refuse (the client falls back to polling)
            return False


def read_ticket(secret: str, ticket: str, campaign_id: int,
                max_age: int = TICKET_MAX_AGE_SECONDS) -> Optional[int]:
    """Return the user id if the ticket is valid, unexpired and for this campaign; else None."""
    claims = read_ticket_claims(secret, ticket, campaign_id, max_age)
    return claims[0] if claims else None


def sse(event: str, data) -> str:
    """One Server-Sent Events frame (data is JSON, always a single line)."""
    payload = json.dumps(data, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {payload}\n\n"


SSE_PING = ": ping\n\n"

# Activity snapshot: {location_id: (version, last_message_id, reset_version)}
Activity = Dict[int, Tuple[int, int, int]]


def activity_from_rows(rows: Iterable, readable: Optional[set] = None) -> Activity:
    """campaign_location_activity rows -> snapshot, keeping only rooms in `readable` (if given)."""
    snap: Activity = {}
    for r in rows:
        get = r.get if hasattr(r, "get") else (lambda k, _r=r: _r[k])
        lid = get("location_id")
        if lid is None:
            continue
        lid = int(lid)
        if readable is not None and lid not in readable:
            continue
        snap[lid] = (int(get("version") or 0), int(get("last_message_id") or 0),
                     int(get("reset_version") or 0))
    return snap


def diff_activity(prev: Activity, cur: Activity) -> List[dict]:
    """
    Rooms whose counter moved. deleted=True when messages were edited/removed there (reset
    counter moved) so the client reloads the room instead of fetching ?since_id=.
    A room that newly became readable shows up as changed; one that stopped being readable
    (closed, deleted) just disappears, without an event.
    """
    changes = []
    for lid in sorted(cur):
        before = prev.get(lid)
        after = cur[lid]
        if before == after:
            continue
        changes.append({
            "location_id": lid,
            "last_id": after[1],
            "version": after[0],
            "deleted": before is not None and after[2] != before[2],
        })
    return changes


def activity_last_ids(snap: Activity) -> Dict[str, int]:
    return {str(k): v[1] for k, v in snap.items()}


def parse_seen(raw: Optional[str], limit: int = 200) -> Dict[int, int]:
    """'12:340,13:0' -> {12: 340, 13: 0} (client-side read state for players without a character)."""
    out: Dict[int, int] = {}
    if not raw:
        return out
    for part in str(raw).split(",")[:limit]:
        lid, sep, mid = part.partition(":")
        if not sep:
            continue
        try:
            out[int(lid)] = max(0, int(mid))
        except ValueError:
            continue
    return out


class StreamSlots:
    """Bounded number of concurrent streams (each holds a server thread), overall and per user."""

    def __init__(self, total: int = 64, per_user: int = 4):
        self.total = total
        self.per_user = per_user
        self._lock = threading.Lock()
        self._count = 0
        self._by_user: Dict[int, int] = {}

    def acquire(self, user_id: int) -> bool:
        with self._lock:
            if self._count >= self.total or self._by_user.get(user_id, 0) >= self.per_user:
                return False
            self._count += 1
            self._by_user[user_id] = self._by_user.get(user_id, 0) + 1
            return True

    def release(self, user_id: int) -> None:
        with self._lock:
            self._count = max(0, self._count - 1)
            n = self._by_user.get(user_id, 0) - 1
            if n > 0:
                self._by_user[user_id] = n
            else:
                self._by_user.pop(user_id, None)

    @property
    def active(self) -> int:
        return self._count
