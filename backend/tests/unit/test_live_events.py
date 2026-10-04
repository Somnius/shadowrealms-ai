"""Unit tests for services/live_events.py (stream tickets, SSE framing, activity diffs, single-use tickets, slots)."""

import json
import time

from services.auth_security import MemoryStore
from services.live_events import (
    StreamSlots,
    TicketLedger,
    activity_from_rows,
    activity_last_ids,
    diff_activity,
    make_ticket,
    parse_seen,
    read_ticket,
    read_ticket_claims,
    sse,
)

SECRET = "test-secret"


def test_ticket_round_trip():
    t = make_ticket(SECRET, 7, 3)
    assert read_ticket(SECRET, t, 3) == 7


def test_ticket_bound_to_campaign():
    t = make_ticket(SECRET, 7, 3)
    assert read_ticket(SECRET, t, 4) is None


def test_ticket_wrong_secret_or_garbage():
    t = make_ticket(SECRET, 7, 3)
    assert read_ticket("other", t, 3) is None
    assert read_ticket(SECRET, "not-a-ticket", 3) is None
    assert read_ticket(SECRET, "", 3) is None
    assert read_ticket(SECRET, None, 3) is None
    assert read_ticket(SECRET, "x" * 600, 3) is None


def test_ticket_expires():
    t = make_ticket(SECRET, 7, 3)
    time.sleep(1.1)
    assert read_ticket(SECRET, t, 3, max_age=0) is None


def test_ticket_is_not_a_jwt():
    # Not a JWT: the first segment isn't a base64 JSON header with "alg", so JWT decoders reject it.
    import base64
    head = make_ticket(SECRET, 7, 3).split(".")[0]
    raw = base64.urlsafe_b64decode(head + "=" * (-len(head) % 4))
    assert b'"alg"' not in raw


def test_sse_frame():
    frame = sse("changed", {"location_id": 4, "last_id": 9})
    assert frame.startswith("event: changed\ndata: ")
    assert frame.endswith("\n\n")
    data = frame.split("data: ", 1)[1].strip()
    assert json.loads(data) == {"location_id": 4, "last_id": 9}
    assert "\n" not in data


def rows(*items):
    return [{"location_id": lid, "version": v, "last_message_id": last, "reset_version": r}
            for lid, v, last, r in items]


def test_activity_diff_reports_rooms_whose_counter_moved():
    prev = activity_from_rows(rows((4, 3, 10, 0), (7, 1, 3, 0)))
    cur = activity_from_rows(rows((4, 5, 12, 0), (7, 1, 3, 0), (9, 1, 13, 0)))
    changes = diff_activity(prev, cur)
    assert [c["location_id"] for c in changes] == [4, 9]
    assert changes[0] == {"location_id": 4, "last_id": 12, "version": 5, "deleted": False}
    assert not changes[1]["deleted"]  # a room seen for the first time is new messages, not a reset
    assert activity_last_ids(cur) == {"4": 12, "7": 3, "9": 13}
    assert diff_activity(cur, cur) == []


def test_activity_diff_flags_edits_and_deletes():
    prev = activity_from_rows(rows((4, 3, 10, 0)))
    cur = activity_from_rows(rows((4, 4, 10, 1)))  # trigger: DELETE bumps version + reset_version
    assert diff_activity(prev, cur) == [{"location_id": 4, "last_id": 10, "version": 4, "deleted": True}]


def test_activity_only_reports_readable_rooms():
    all_rows = rows((4, 3, 10, 0), (5, 9, 50, 0))
    readable = {4}
    prev = activity_from_rows(all_rows, readable)
    assert set(prev) == {4}
    cur = activity_from_rows(rows((4, 3, 10, 0), (5, 10, 51, 0)), readable)
    assert diff_activity(prev, cur) == []  # activity in the closed room 5 never leaks
    # Room closed while streaming: it just disappears, no event that would hint at activity.
    assert diff_activity(prev, activity_from_rows(rows((4, 3, 10, 0)), set())) == []


def test_ticket_carries_a_nonce_and_is_single_use():
    t1, t2 = make_ticket(SECRET, 7, 3), make_ticket(SECRET, 7, 3)
    (u1, n1), (u2, n2) = read_ticket_claims(SECRET, t1, 3), read_ticket_claims(SECRET, t2, 3)
    assert u1 == u2 == 7 and n1 and n2 and n1 != n2
    ledger = TicketLedger(MemoryStore())
    assert ledger.claim(n1) is True
    assert ledger.claim(n1) is False  # replay
    assert ledger.claim(n2) is True
    assert ledger.claim(None) is False  # old tickets without a nonce are refused


def test_ticket_ledger_refuses_when_store_is_down():
    class Down:
        def incr(self, key, ttl):
            raise ConnectionError("redis down")

    assert TicketLedger(Down()).claim("abc") is False


def test_parse_seen():
    assert parse_seen("12:340,13:0") == {12: 340, 13: 0}
    assert parse_seen("bad,1:x,2:-5,3:4") == {2: 0, 3: 4}
    assert parse_seen(None) == {}


def test_stream_slots_limits():
    s = StreamSlots(total=3, per_user=2)
    assert s.acquire(1) and s.acquire(1)
    assert not s.acquire(1)  # per-user cap
    assert s.acquire(2)
    assert not s.acquire(3)  # total cap
    s.release(1)
    assert s.acquire(3)
    assert s.active == 3
