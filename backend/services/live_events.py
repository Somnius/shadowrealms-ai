"""
Pure helpers for the chronicle live-update stream (routes/events.py).

- Stream tickets: EventSource can't send an Authorization header, and the long-lived JWT must not
  end up in URLs (nginx access logs). The browser trades its JWT for a short-lived, single-purpose
  ticket (signed with itsdangerous, salt 'sr-events-ticket', bound to one user + campaign, 60 s) and
  passes that as ?ticket=. A ticket is not a JWT, so it can't be replayed against other endpoints.
- SSE framing and snapshot diffing ("notify, then fetch": events carry ids only, never content, so
  visibility rules such as hidden dice stay in the normal message GET).
"""

from __future__ import annotations

import json
import threading
from typing import Dict, Iterable, List, Optional, Tuple

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

TICKET_SALT = "sr-events-ticket"
TICKET_MAX_AGE_SECONDS = 60


def _serializer(secret: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret, salt=TICKET_SALT)


def make_ticket(secret: str, user_id: int, campaign_id: int) -> str:
    return _serializer(secret).dumps({"u": int(user_id), "c": int(campaign_id)})


def read_ticket(secret: str, ticket: str, campaign_id: int,
                max_age: int = TICKET_MAX_AGE_SECONDS) -> Optional[int]:
    """Return the user id if the ticket is valid, unexpired and for this campaign; else None."""
    if not ticket or not isinstance(ticket, str) or len(ticket) > 512:
        return None
    try:
        data = _serializer(secret).loads(ticket, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    except Exception:  # noqa: BLE001 - malformed payloads
        return None
    if not isinstance(data, dict):
        return None
    try:
        if int(data.get("c")) != int(campaign_id):
            return None
        return int(data.get("u"))
    except (TypeError, ValueError):
        return None


def sse(event: str, data) -> str:
    """One Server-Sent Events frame (data is JSON, always a single line)."""
    payload = json.dumps(data, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {payload}\n\n"


SSE_PING = ": ping\n\n"

# Snapshot: {location_id: (max_message_id, message_count)}
Snapshot = Dict[int, Tuple[int, int]]


def snapshot_from_rows(rows: Iterable) -> Snapshot:
    snap: Snapshot = {}
    for r in rows:
        get = r.get if hasattr(r, "get") else (lambda k, _r=r: _r[k])
        lid = get("location_id")
        if lid is None:
            continue
        snap[int(lid)] = (int(get("last_id") or 0), int(get("n") or 0))
    return snap


def diff_snapshots(prev: Snapshot, cur: Snapshot) -> List[dict]:
    """Locations whose newest id or row count changed (new, deleted or cleaned messages)."""
    changes = []
    for lid in sorted(set(prev) | set(cur)):
        before = prev.get(lid, (0, 0))
        after = cur.get(lid, (0, 0))
        if before != after:
            changes.append({
                "location_id": lid,
                "last_id": after[0],
                "deleted": after[1] < before[1] or after[0] < before[0],
            })
    return changes


def last_ids(snap: Snapshot) -> Dict[str, int]:
    return {str(k): v[0] for k, v in snap.items()}


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
