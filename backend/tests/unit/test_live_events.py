"""Unit tests for services/live_events.py (stream tickets, SSE framing, snapshot diffs, slots)."""

import json
import time

from services.live_events import (
    StreamSlots,
    diff_snapshots,
    last_ids,
    make_ticket,
    parse_seen,
    read_ticket,
    snapshot_from_rows,
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


def test_snapshot_and_diff():
    prev = snapshot_from_rows([{"location_id": 4, "last_id": 10, "n": 5}, {"location_id": 7, "last_id": 3, "n": 1}])
    cur = snapshot_from_rows([
        {"location_id": 4, "last_id": 12, "n": 7},
        {"location_id": 7, "last_id": 3, "n": 1},
        {"location_id": 9, "last_id": 13, "n": 1},
    ])
    changes = diff_snapshots(prev, cur)
    assert [c["location_id"] for c in changes] == [4, 9]
    assert all(not c["deleted"] for c in changes)
    assert last_ids(cur) == {"4": 12, "7": 3, "9": 13}


def test_diff_detects_deletes():
    prev = {4: (10, 5)}
    assert diff_snapshots(prev, {4: (10, 4)}) == [{"location_id": 4, "last_id": 10, "deleted": True}]
    assert diff_snapshots(prev, {}) == [{"location_id": 4, "last_id": 0, "deleted": True}]
    assert diff_snapshots(prev, {4: (10, 5)}) == []


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
