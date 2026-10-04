"""Chat message actions: delete rules per role, dice pairs, reply quotes, older-history pages."""

import pytest

from services import message_actions as ma

OWNER = 1  # chronicle creator (Storyteller)
PLAYER = 2
OTHER = 3
ADMIN = 9


def msg(user_id=PLAYER, role="user", kind=None):
    return {"user_id": user_id, "role": role, "ai_message_kind": kind}


def decide(row, actor, site_role="player"):
    return ma.delete_decision(row, actor, site_role, OWNER)


@pytest.mark.parametrize(
    "row,expected",
    [
        (msg(), (True, None)),
        (msg(user_id=OTHER), (False, ma.DELETE_NOT_YOURS)),
        (msg(kind="dice_roll:r5-ab12"), (False, ma.DELETE_DICE_STAFF_ONLY)),
        (msg(role="assistant", kind="dice_animation:r5-ab12"), (False, ma.DELETE_DICE_STAFF_ONLY)),
        (msg(kind="dice_rouse:7"), (False, ma.DELETE_DICE_STAFF_ONLY)),
        (msg(kind="DICE_ROLL_HIDDEN:x"), (False, ma.DELETE_DICE_STAFF_ONLY)),
        (msg(role="assistant"), (False, ma.DELETE_AI_STAFF_ONLY)),
        (msg(role="assistant", kind="slash_assistant"), (False, ma.DELETE_AI_STAFF_ONLY)),
        (msg(kind="slash_user"), (True, None)),
        (msg(kind="chat_user"), (True, None)),
    ],
)
def test_player_rules(row, expected):
    assert decide(row, PLAYER) == expected


@pytest.mark.parametrize(
    "row",
    [msg(), msg(user_id=OTHER), msg(kind="dice_roll:a"), msg(role="assistant"), msg(kind="dice_rouse:1")],
)
def test_storyteller_and_admin_delete_anything(row):
    assert decide(row, OWNER) == (True, None)
    assert decide(row, ADMIN, "admin") == (True, None)
    assert decide(row, ADMIN, " Admin ") == (True, None)


def test_helper_is_not_staff_for_deletes():
    # Owner decision names the Storyteller and site admins only.
    assert decide(msg(user_id=OTHER), OTHER + 10, "helper") == (False, ma.DELETE_NOT_YOURS)
    assert decide(msg(user_id=7), 7, "helper") == (True, None)


def test_ids_compare_as_strings():
    assert decide(msg(user_id="2"), 2) == (True, None)
    assert ma.is_staff("player", 1, "1") is True
    assert ma.is_staff("player", None, None) is False
    assert decide(msg(user_id=None), None) == (False, ma.DELETE_NOT_YOURS)


def test_dice_pair_kinds():
    assert ma.dice_pair_kinds("dice_roll:r5-ab") == [
        "dice_animation:r5-ab", "dice_animation_hidden:r5-ab", "dice_roll:r5-ab", "dice_roll_hidden:r5-ab",
    ]
    assert ma.dice_pair_kinds("DICE_ANIMATION_HIDDEN:Z") == ma.dice_pair_kinds("dice_roll:z")
    assert ma.dice_pair_kinds("dice_rouse:4") == []
    assert ma.dice_pair_kinds("dice_roll:") == []
    assert ma.dice_pair_kinds(None) == []
    assert ma.dice_pair_kinds("slash_user") == []


@pytest.mark.parametrize(
    "before,limit,expected",
    [
        ("40", "10", (40, 10)),
        (40, None, (40, ma.OLDER_PAGE_DEFAULT)),
        (40, "x", (40, ma.OLDER_PAGE_DEFAULT)),
        (40, 500, (40, ma.OLDER_PAGE_MAX)),
        (40, 0, (40, 1)),
        (40, -3, (40, 1)),
        ("0", 10, None),
        ("-1", 10, None),
        ("abc", 10, None),
        (None, 10, None),
    ],
)
def test_parse_older_page(before, limit, expected):
    assert ma.parse_older_page(before, limit) == expected


def test_older_page_reverses_and_flags_more():
    rows = [{"id": i} for i in (9, 8, 7, 6)]  # newest first, fetched with limit + 1
    page, more = ma.older_page(rows, 3)
    assert [r["id"] for r in page] == [7, 8, 9]
    assert more is True
    page, more = ma.older_page(rows[:3], 3)
    assert [r["id"] for r in page] == [7, 8, 9]
    assert more is False
    assert ma.older_page([], 3) == ([], False)


def test_reply_excerpt():
    assert ma.reply_excerpt("  **Hello**\n\n  _there_  ") == "Hello there"
    assert ma.reply_excerpt("Roll it [[roll: Wits + Awareness, difficulty 3]] now") == "Roll it now"
    long = "word " * 100
    out = ma.reply_excerpt(long)
    assert len(out) <= ma.REPLY_EXCERPT_CHARS
    assert out.endswith("…")
    assert ma.reply_excerpt(None) == ""


def test_reply_author():
    assert ma.reply_author("assistant", None, "bob", None) == ""
    assert ma.reply_author("user", "character", "bob", "Lucita") == "Lucita"
    assert ma.reply_author("user", None, "bob", "Lucita") == "Lucita"
    assert ma.reply_author("user", "player", "bob", "Lucita") == "bob"
    assert ma.reply_author("user", "staff", "bob", None) == "bob"


def test_reply_payload():
    assert ma.reply_payload({"reply_id": None}, True) is None
    row = {"reply_id": 5, "reply_content": "**Hi** all", "reply_role": "user", "reply_speaker_mode": "player",
           "reply_username": "ann", "reply_character_name": None, "reply_kind": None}
    assert ma.reply_payload(row, False) == {"id": 5, "author": "ann", "excerpt": "Hi all", "role": "user"}
    hidden = dict(row, reply_kind="dice_roll_hidden:abc")
    assert ma.reply_payload(hidden, False) == {"id": 5, "author": "", "excerpt": "", "role": "", "hidden": True}
    assert ma.reply_payload(hidden, True)["excerpt"] == "Hi all"


def target(**kw):
    t = {"id": 5, "campaign_id": 1, "location_id": 2, "ai_message_kind": None}
    t.update(kw)
    return t


def test_reply_target_error():
    assert ma.reply_target_error(target(), 1, 2, False) is None
    assert ma.reply_target_error(None, 1, 2, False) == "reply_target_not_found"
    assert ma.reply_target_error(target(location_id=3), 1, 2, False) == "reply_target_other_room"
    assert ma.reply_target_error(target(campaign_id=8), 1, 2, False) == "reply_target_other_room"
    assert ma.reply_target_error(target(ai_message_kind="dice_animation:x"), 1, 2, True) == "reply_target_not_found"
    assert ma.reply_target_error(target(ai_message_kind="dice_roll_hidden:x"), 1, 2, False) == "reply_target_not_found"
    assert ma.reply_target_error(target(ai_message_kind="dice_roll_hidden:x"), 1, 2, True) is None
    assert ma.reply_target_error(target(ai_message_kind="dice_roll:x"), 1, 2, False) is None


def test_hidden_filter_sql_escapes_percent_for_the_driver():
    sql = ma.hidden_dice_sql_filter()
    assert "dice_animation_hidden%%" in sql and "dice_roll_hidden%%" in sql
    assert sql.startswith(" AND ")
