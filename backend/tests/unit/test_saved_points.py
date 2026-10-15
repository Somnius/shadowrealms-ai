"""Saved points (Forge v2 part D): parse, rule check, apply and reverse (services/saved_points.py)."""

import pytest

from services.request_validation import RequestValidationError
from services.saved_points import (
    SheetChanged,
    apply_spend,
    parse_spend,
    reverse_spend,
    saved_balance,
    validate_spend,
)


def meta(**over):
    m = {
        "edition": "v5",
        "clan": "Toreador",
        "hunger": 1,
        "advantages": [
            {"name": "Resources", "dots": 3, "kind": "background"},
            {"name": "Herd", "dots": 2, "kind": "predator"},
            {"name": "Allies", "dots": 4, "kind": "background"},
        ],
        "saved": {"advantage_dots": 2, "specialty": 1},
    }
    m.update(over)
    return m


def skills():
    return {
        "physical": {"brawl": 2},
        "social": {"persuasion": 3},
        "mental": {"occult": 1, "science": 0},
        "specialties": [{"skill": "occult", "name": "Vampires"}],
    }


def adv(*items):
    return parse_spend({"kind": "saved_advantage", "items": list(items)})


def codes(check):
    return [p["code"] for p in check["problems"]]


# ---------- parse ----------

@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {"kind": "xp"},
        {"kind": "saved_advantage"},
        {"kind": "saved_advantage", "items": []},
        {"kind": "saved_advantage", "items": [{"name": "Resources", "dots": 0}]},
        {"kind": "saved_advantage", "items": [{"name": "Resources", "dots": 6}]},
        {"kind": "saved_advantage", "items": [{"name": "Resources", "dots": True}]},
        {"kind": "saved_advantage", "items": [{"name": "  ", "dots": 1}]},
        {"kind": "saved_advantage", "items": [{"name": "Resources", "dots": 1, "kind": "flaw"}]},
        {"kind": "saved_advantage", "items": [{"name": "x", "dots": 1}] * 11},
        {"kind": "saved_specialty", "skill": "alertness", "name": "Ambush"},
        {"kind": "saved_specialty", "skill": "occult", "name": ""},
        {"kind": "saved_specialty", "skill": "occult", "name": "x" * 121},
    ],
)
def test_parse_refuses_bad_shapes(body):
    with pytest.raises(RequestValidationError):
        parse_spend(body)


def test_parse_normalises():
    p = adv({"name": "  Resources ", "dots": 1, "kind": "background", "id": "background:resources", "note": " cash "})
    assert p == {
        "kind": "saved_advantage",
        "items": [{"name": "Resources", "dots": 1, "kind": "background", "id": "background:resources", "note": "cash"}],
    }
    assert adv({"name": "Iron Gullet", "dots": 3})["items"][0]["kind"] == "merit"
    assert parse_spend({"kind": "saved_specialty", "skill": "occult", "name": " Byzantine  rites "}) == {
        "kind": "saved_specialty", "skill": "occult", "name": "Byzantine rites",
    }


def test_balance_reads_only_good_values():
    assert saved_balance({}) == {"advantage_dots": 0, "specialty": 0}
    assert saved_balance({"saved": {"advantage_dots": "3", "specialty": True}}) == {"advantage_dots": 0, "specialty": 0}
    assert saved_balance(meta()) == {"advantage_dots": 2, "specialty": 1}


# ---------- rule check: Advantages ----------

def test_a_spend_within_the_saved_dots_passes():
    check = validate_spend(meta(), adv({"name": "Contacts", "dots": 2, "kind": "background"}), None, {}, skills())
    assert check == {"ok": True, "problems": [], "house_rule": False}


def test_more_than_saved_is_a_house_rule():
    check = validate_spend(meta(), adv({"name": "Contacts", "dots": 3}), None, {}, skills())
    assert check["ok"] is False and check["house_rule"] is True
    assert check["problems"] == [{"code": "saved_short", "params": {"need": 3, "have": 2}}]


def test_the_chronicle_cap_counts():
    s = {"saved_points": {"advantage_dots_cap": 1, "allow_specialty": True}}
    check = validate_spend(meta(), adv({"name": "Contacts", "dots": 2}), None, s, skills())
    assert codes(check) == ["over_cap"]
    assert check["problems"][0]["params"] == {"cap": 1, "total": 2}


def test_a_raise_past_five_dots_is_out_of_range():
    check = validate_spend(meta(), adv({"name": "allies", "dots": 2}), None, {}, skills())
    assert check["problems"] == [{"code": "dots_range", "params": {"name": "Allies", "to": 6}}]


def test_two_items_on_one_row_add_up():
    check = validate_spend(meta(saved={"advantage_dots": 5}), adv({"name": "Allies", "dots": 1}, {"name": "Allies", "dots": 1}), None, {}, skills())
    assert codes(check) == ["dots_range"]


def test_catalog_checks_only_when_the_catalog_exists():
    cat = {
        "advantages": [
            {"id": "background:resources", "name": "Resources", "kind": "background", "dots": {"min": 1, "max": 5}, "book": "v5-corebook"},
            {"id": "merit:iron-gullet", "name": "Iron Gullet", "kind": "merit", "dots": {"min": 3, "max": 3}, "book": "v5-corebook"},
            {"id": "flaw:prey-exclusion", "name": "Prey Exclusion", "kind": "flaw", "fixed": 1, "book": "v5-corebook"},
            {"id": "merit:bloodhound", "name": "Bloodhound", "kind": "merit", "dots": 1, "book": "v5-companion",
             "also_in": [{"book": "v5-players-guide", "page": 1}], "aliases": ["Blood Hound"]},
            {"id": "merit:nos-only", "name": "Tunnel Rat", "kind": "merit", "dots": 1, "book": "v5-corebook", "clans_only": ["Nosferatu"]},
        ]
    }
    ok = validate_spend(meta(), adv({"name": "resources", "dots": 1, "kind": "background"}), cat, {}, skills())
    assert ok["ok"], ok
    by_id = validate_spend(meta(), adv({"id": "merit:bloodhound", "name": "Nose", "dots": 1}), cat, {}, skills())
    assert by_id["ok"], by_id
    assert validate_spend(meta(), adv({"name": "Blood  hound", "dots": 1}), cat, {}, skills())["ok"]
    assert codes(validate_spend(meta(), adv({"name": "Made Up", "dots": 1}), cat, {}, skills())) == ["unknown_advantage"]
    assert codes(validate_spend(meta(), adv({"name": "Prey Exclusion", "dots": 1}), cat, {}, skills())) == ["not_an_advantage"]
    rng = validate_spend(meta(), adv({"name": "Iron Gullet", "dots": 2}), cat, {}, skills())
    assert rng["problems"] == [{"code": "adv_dots_range", "params": {"name": "Iron Gullet", "to": 2, "min": 3, "max": 3}}]
    books = {"allowed_books": ["v5-corebook"]}
    assert codes(validate_spend(meta(), adv({"name": "Bloodhound", "dots": 1}), cat, books, skills())) == ["book_not_allowed"]
    # listed in an allowed book too (also_in): fine
    assert validate_spend(meta(), adv({"name": "Bloodhound", "dots": 1}), cat, {"allowed_books": ["v5-players-guide"]}, skills())["ok"]
    assert codes(validate_spend(meta(), adv({"name": "Tunnel Rat", "dots": 1}), cat, {}, skills())) == ["clan_only"]
    assert validate_spend(meta(clan="Nosferatu"), adv({"name": "Tunnel Rat", "dots": 1}), cat, {}, skills())["ok"]
    # no catalog: names are not checked
    assert validate_spend(meta(), adv({"name": "Made Up", "dots": 1}), {}, {}, skills())["ok"]
    assert validate_spend(meta(), adv({"name": "Made Up", "dots": 1}), None, {}, skills())["ok"]


def test_loresheets_resolve_in_their_own_catalog():
    cat = {"advantages": [], "loresheets": [{"id": "loresheet:carthage", "name": "Carthage", "book": "v5-corebook"}]}
    assert validate_spend(meta(), adv({"name": "Carthage", "dots": 1, "kind": "loresheet"}), cat, {}, skills())["ok"]
    assert codes(validate_spend(meta(), adv({"name": "Carthage", "dots": 1, "kind": "merit"}), cat, {}, skills())) == ["unknown_advantage"]


# ---------- rule check: the specialty ----------

def spec(skill, name):
    return parse_spend({"kind": "saved_specialty", "skill": skill, "name": name})


def test_specialty_checks():
    assert validate_spend(meta(), spec("persuasion", "Bargaining"), None, {}, skills())["ok"]
    assert codes(validate_spend(meta(), spec("science", "Chemistry"), None, {}, skills())) == ["skill_no_dot"]
    dup = validate_spend(meta(), spec("occult", "vampires"), None, {}, skills())
    assert dup["problems"] == [{"code": "specialty_duplicate", "params": {"skill": "occult", "name": "vampires"}}]
    none_left = meta(saved={"advantage_dots": 2, "specialty": 0})
    assert codes(validate_spend(none_left, spec("persuasion", "Bargaining"), None, {}, skills())) == ["no_saved_specialty"]
    off = {"saved_points": {"advantage_dots_cap": 7, "allow_specialty": False}}
    assert codes(validate_spend(meta(), spec("persuasion", "Bargaining"), None, off, skills())) == ["specialty_not_allowed"]


# ---------- apply and reverse ----------

def state():
    return {
        "wod_meta": meta(),
        "skills": skills(),
        "merits_flaws": {"entries": [
            {"name": "Resources", "points": 3, "note": "background"},
            {"name": "Herd", "points": 2, "note": "predator type"},
        ]},
    }


def test_apply_raises_an_own_row_and_adds_new_ones():
    s0 = state()
    new, before, after = apply_spend(s0, adv({"name": "Resources", "dots": 1}, {"name": "Herd", "dots": 1, "kind": "background"}))
    rows = new["wod_meta"]["advantages"]
    assert rows[0] == {"name": "Resources", "dots": 4, "kind": "background", "saved_dots": 1}
    # the predator grant is not raised: the player's own Herd is a new row
    assert rows[1] == {"name": "Herd", "dots": 2, "kind": "predator"}
    assert rows[3] == {"name": "Herd", "dots": 1, "kind": "background", "saved_dots": 1}
    assert new["wod_meta"]["saved"] == {"advantage_dots": 0, "specialty": 1}
    assert after["changes"] == [
        {"name": "Resources", "kind": "background", "from": 3, "to": 4},
        {"name": "Herd", "kind": "background", "from": 0, "to": 1},
    ]
    entries = new["merits_flaws"]["entries"]
    assert {"name": "Resources", "points": 4, "note": "background"} in entries
    assert {"name": "Herd", "points": 2, "note": "predator type"} in entries
    assert {"name": "Herd", "points": 1, "note": "background"} in entries
    assert before["wod_meta"]["advantages"] == s0["wod_meta"]["advantages"]
    assert set(before) == {"wod_meta", "merits_flaws"} and set(before["wod_meta"]) == {"advantages", "saved"}
    # the input is not changed
    assert s0 == state()


def test_reverse_restores_only_the_touched_keys():
    s0 = state()
    new, before, after = apply_spend(s0, adv({"name": "Resources", "dots": 2}))
    new["wod_meta"]["hunger"] = 4
    new["wod_meta"]["willpower"] = {"max": 5, "superficial": 1, "aggravated": 0}
    back = reverse_spend(new, "saved_advantage", before, after)
    assert back["wod_meta"]["advantages"] == s0["wod_meta"]["advantages"]
    assert back["wod_meta"]["saved"] == s0["wod_meta"]["saved"]
    assert back["merits_flaws"] == s0["merits_flaws"]
    assert back["wod_meta"]["hunger"] == 4 and back["wod_meta"]["willpower"]["superficial"] == 1


def test_reverse_refuses_when_a_later_spend_changed_the_keys():
    s0 = state()
    s1, b1, a1 = apply_spend(s0, adv({"name": "Resources", "dots": 1}))
    s2, b2, a2 = apply_spend(s1, adv({"name": "Contacts", "dots": 1}))
    with pytest.raises(SheetChanged):
        reverse_spend(s2, "saved_advantage", b1, a1)
    s1b = reverse_spend(s2, "saved_advantage", b2, a2)
    assert reverse_spend(s1b, "saved_advantage", b1, a1)["wod_meta"]["advantages"] == s0["wod_meta"]["advantages"]


def test_specialty_apply_and_reverse_with_absent_keys():
    s0 = {"wod_meta": {"saved": {"advantage_dots": 0, "specialty": 1}}, "skills": {"mental": {"occult": 2}}}
    new, before, after = apply_spend(s0, spec("occult", "Byzantine rites"))
    assert new["skills"]["specialties"] == [{"skill": "occult", "name": "Byzantine rites", "source": "saved"}]
    assert new["wod_meta"]["saved"] == {"advantage_dots": 0, "specialty": 0}
    assert after["changes"] == [{"skill": "occult", "name": "Byzantine rites"}]
    back = reverse_spend(new, "saved_specialty", before, after)
    assert "specialties" not in back["skills"]
    assert back["wod_meta"]["saved"] == {"advantage_dots": 0, "specialty": 1}


def test_an_approved_house_rule_never_drives_the_balance_below_zero():
    s0 = state()
    new, _, _ = apply_spend(s0, adv({"name": "Contacts", "dots": 4}))
    assert new["wod_meta"]["saved"]["advantage_dots"] == 0


def test_the_sheet_bounds_check_knows_saved():
    from services.character_sheet_v5 import sanity_check_v5

    assert sanity_check_v5(wod_meta={"saved": {"advantage_dots": 2, "specialty": 1}}) == []
    assert sanity_check_v5(wod_meta={"saved": {"advantage_dots": 21}}) == ["wod_meta.saved.advantage_dots must be between 0 and 20"]
    assert sanity_check_v5(wod_meta={"saved": {"specialty": 2}}) == ["wod_meta.saved.specialty must be between 0 and 1"]
    assert sanity_check_v5(wod_meta={"saved": [1]}) == ["wod_meta.saved must be an object"]
