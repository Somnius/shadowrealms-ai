"""Server-built dice markers, marker whitelist/clamp, speaker choice, campaign viewer + readable rooms."""

import json

import pytest

from services import dice_markers as dm
from services.dice_chat import DicePostError, choose_speaker
from services.location_access import readable_location_ids, viewer_allowed

NOW = 1_700_000_000_000


def marker(**extra):
    m = {"animation_id": "abc123", "started_at_ms": NOW, "duration_ms": 3000, "rules_edition": "v5",
         "difficulty": 3, "successes": 2, "is_botch": False, "dice_preview": [1, 7, 10],
         "hunger_flags": [False, False, True], "outcome": "win"}
    m.update(extra)
    return json.dumps(m)


# --- build_marker (port of frontend/src/dice/diceMarker.js) ---------------------------------

def test_v5_marker_keeps_hunger_dice_and_roll_id():
    res = {"rules_edition": "v5", "normal_dice": list(range(1, 11)), "hunger_dice": [10, 1],
           "difficulty": 3, "successes": 4, "margin": 1, "outcome": "win", "is_messy_critical": True}
    m = dm.build_marker(res, animation_id="r5-aa", roll_id=5, started_at_ms=NOW)
    assert m["roll_id"] == 5 and m["roll_kind"] == "manual" and m["animation_id"] == "r5-aa"
    assert m["dice_preview"] == list(range(1, 9)) + [10, 1]
    assert m["hunger_flags"] == [False] * 8 + [True, True]
    assert m["extra_dice_count"] == 2 and m["pool_size"] == 12
    assert m["is_messy_critical"] is True and m["outcome"] == "win"
    assert m["started_at_ms"] == NOW and m["duration_ms"] == dm.DEFAULT_DURATION_MS
    assert set(m) <= dm.MARKER_KEYS


def test_classic_marker():
    res = {"rules_edition": "classic", "results": [10, 6, 1], "difficulty": 6, "successes": 1,
           "is_botch": False, "is_exceptional": False, "specialty": True, "specialty_rerolls": [7],
           "willpower": False}
    m = dm.build_marker(res, animation_id="r9-bb", roll_id=9, roll_kind="manual", started_at_ms=NOW)
    assert m["dice_preview"] == [10, 6, 1] and m["pool_size"] == 3 and m["extra_dice_count"] == 0
    assert m["specialty"] is True and m["specialty_rerolls"] == [7]
    assert set(m) <= dm.MARKER_KEYS
    # What the server stores is a valid marker for its own kind.
    assert dm.sanitize_marker(json.dumps(m), "dice_animation:r9-bb", now=NOW) is not None


def test_animation_ids_are_unique_per_post():
    a, b = dm.new_animation_id(5), dm.new_animation_id(5)
    assert a != b and a.startswith("r5-") and a == a.lower()


# --- sanitize_marker: whitelist + clamp (admin-posted markers) --------------------------------

def test_marker_whitelist_and_size():
    ok = lambda c, k="dice_animation:abc123": dm.sanitize_marker(c, k, now=NOW)  # noqa: E731
    assert ok(marker()) is not None
    assert ok(marker(), "dice_animation_hidden:abc123") is not None
    for bad in (marker(text="The Prince is dead."),            # unknown key
                marker(outcome="x" * 500),                       # long string
                marker(dice_preview=["The Prince is dead"]),     # text in a list
                marker(difficulty={"text": "hi"}),               # nested object
                marker(dice_preview=list(range(500)))):          # long list
        assert ok(bad) is None, bad
    assert ok(marker(), "dice_animation:zzz") is None          # id mismatch
    assert ok(marker(), "dice_roll:abc123") is None            # not a marker kind
    assert ok("I am the Storyteller") is None
    assert ok(marker() + " " * dm.MAX_MARKER_CHARS) is None


@pytest.mark.parametrize("given,expected", [
    (3000, 3000), (999_999, dm.MAX_DURATION_MS), (-5, 0), ("9999", dm.DEFAULT_DURATION_MS),
    (True, dm.DEFAULT_DURATION_MS), (None, dm.DEFAULT_DURATION_MS),
])
def test_marker_duration_clamped(given, expected):
    out = json.loads(dm.sanitize_marker(marker(duration_ms=given), "dice_animation:abc123", now=NOW))
    assert out["duration_ms"] == expected


@pytest.mark.parametrize("given,expected", [
    (NOW, NOW), (NOW + 10 * 3600_000, NOW + dm.START_SKEW_MS), (0, NOW - dm.START_SKEW_MS),
    (NOW - 30_000, NOW - 30_000), ("soon", NOW),
])
def test_marker_start_clamped_to_now(given, expected):
    out = json.loads(dm.sanitize_marker(marker(started_at_ms=given), "dice_animation:abc123", now=NOW))
    assert out["started_at_ms"] == expected


def test_dice_kinds_are_server_only():
    for k in ("dice_roll:x", "dice_roll_hidden:x", "dice_animation:x", "dice_animation_hidden:x",
              "dice_rouse:5", "DICE_ROLL:x"):
        assert dm.is_dice_kind(k), k
    for k in (None, "", "slash_user", "chat_assistant", "roll", "my_dice_roll"):
        assert not dm.is_dice_kind(k), k


# --- speaker of the server-posted result line -------------------------------------------------

def test_choose_speaker():
    assert choose_speaker("character", False, 12, None) == ("character", 12)
    assert choose_speaker("character", False, None, 34) == ("character", 34)   # playing character
    assert choose_speaker("character", False, None, None) == ("player", None)  # no character
    assert choose_speaker("player", False, 12, 34) == ("player", None)
    assert choose_speaker(None, False, 12, None) == ("character", 12)
    assert choose_speaker("nonsense", False, None, None) == ("player", None)
    assert choose_speaker("staff", True, 12, None) == ("staff", None)
    with pytest.raises(DicePostError) as e:
        choose_speaker("staff", False, None, None)
    assert e.value.status == 403


# --- campaign viewer + readable rooms (services/location_access.py) ---------------------------

def test_viewer_allowed():
    assert not viewer_allowed(None, 5)                                      # no such campaign
    assert viewer_allowed({"role": "admin", "created_by": 1, "is_member": False}, 5)
    assert viewer_allowed({"role": "player", "created_by": 5, "is_member": False}, 5)
    assert viewer_allowed({"role": "player", "created_by": 1, "is_member": True}, "5")
    assert not viewer_allowed({"role": "player", "created_by": 1, "is_member": False}, 5)
    assert not viewer_allowed({"role": "helper", "created_by": 1, "is_member": False}, 5)


def test_readable_location_ids():
    rooms = [
        {"id": 1, "is_active": True, "is_open": True},
        {"id": 2, "is_active": True, "is_open": False},   # closed by the Storyteller
        {"id": 3, "is_active": False, "is_open": True},   # deleted (soft)
        {"id": 4, "is_active": None, "is_open": None},    # legacy NULLs = active, open
        {"id": 5, "is_active": 1, "is_open": 0},          # SQLite ints
    ]
    assert readable_location_ids(rooms, can_bypass_closed=False) == {1, 4}
    assert readable_location_ids(rooms, can_bypass_closed=True) == {1, 2, 4, 5}
