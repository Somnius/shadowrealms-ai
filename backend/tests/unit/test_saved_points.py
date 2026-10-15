"""Saved points (Forge v2 part D): parse, rule check, apply and reverse (services/saved_points.py)."""

import pytest

from services.request_validation import RequestValidationError
from services.saved_points import (
    SheetChanged,
    apply_spend,
    clamp_saved,
    saved_at_creation,
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
        {"kind": "saved_advantage", "items": [{"name": "The Bahari", "kind": "loresheet", "dots": 2}]},
        {"kind": "saved_advantage", "items": [{"name": "The Bahari", "kind": "loresheet", "levels": [2, 2]}]},
        {"kind": "saved_advantage", "items": [{"name": "The Bahari", "kind": "loresheet", "levels": [6]}]},
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
    lore = adv({"name": "The Bahari", "kind": "loresheet", "levels": [3, 1], "dots": 99})["items"][0]
    assert lore == {"name": "The Bahari", "kind": "loresheet", "levels": [1, 3], "dots": 4}
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



# ---------- review fixes ----------

def test_saved_at_creation_counts_from_the_sheet():
    meta_ = {"age": "neonate", "advantages": [
        {"name": "Resources", "dots": 3, "kind": "background"},
        {"name": "Herd", "dots": 2, "kind": "predator"},
        {"name": "Haven", "dots": 2, "kind": "background"},
    ]}
    sk = {"mental": {"academics": 1, "science": 0}, "physical": {"craft": 2},
          "specialties": [{"skill": "academics", "name": "History"}, {"skill": "brawl", "name": "Grappling", "source": "predator"}]}
    # 7 - (3 + 2) = 2; free specialties: 1 + Academics + Craft = 3, one named
    assert saved_at_creation(meta_, sk, {}) == {"advantage_dots": 2, "specialty": 1}
    sk["specialties"] += [{"skill": "craft", "name": "Woodwork"}, {"skill": "occult", "name": "Rites"}]
    assert saved_at_creation(meta_, sk, {})["specialty"] == 0
    assert saved_at_creation({**meta_, "age": "ancilla"}, sk, {})["advantage_dots"] == 4
    tight = {"saved_points": {"advantage_dots_cap": 1, "allow_specialty": False}}
    assert saved_at_creation(meta_, {}, tight) == {"advantage_dots": 1, "specialty": 0}
    assert saved_at_creation({"advantages": [{"name": "Allies", "dots": 9, "kind": "background"}]}, {}, {})["advantage_dots"] == 0
    assert saved_at_creation(None, None, None) == {"advantage_dots": 7, "specialty": 1}


def test_a_forged_balance_is_cut_to_the_servers_count():
    meta_ = {"advantages": [{"name": "Resources", "dots": 5, "kind": "background"}], "saved": {"advantage_dots": 20, "specialty": 1}}
    sk = {"specialties": [{"skill": "brawl", "name": "Grappling"}]}
    assert clamp_saved(meta_, sk, {}) == {"advantage_dots": 2, "specialty": 0}
    # the forge's lower number wins (it doesn't count a predator type's dot as rated)
    assert clamp_saved({**meta_, "saved": {"advantage_dots": 1, "specialty": 0}}, {}, {}) == {"advantage_dots": 1, "specialty": 0}
    assert clamp_saved({**meta_, "saved": "lots"}, {}, {}) == {"advantage_dots": 2, "specialty": 1}


def test_the_cap_counts_every_spend_from_saved_points():
    m = meta(saved={"advantage_dots": 4})
    m["advantages"][0] = {"name": "Resources", "dots": 4, "kind": "background", "saved_dots": 1}
    capped = {"saved_points": {"advantage_dots_cap": 2, "allow_specialty": True}}
    assert validate_spend(m, adv({"name": "Contacts", "dots": 1}), None, capped, skills())["ok"]
    check = validate_spend(m, adv({"name": "Contacts", "dots": 2}), None, capped, skills())
    assert check["problems"] == [{"code": "over_cap", "params": {"cap": 2, "total": 3}}]




# ---------- the rows a spend makes go through the creation check's row rules ----------

CATALOG = {
    "clans": [
        {"id": "clan:banu-haqim", "name": "Banu Haqim", "aliases": ["Assamites"], "disciplines": []},
        {"id": "clan:thin-blood", "name": "Thin-blood", "thin_blood": True, "disciplines": []},
        {"id": "clan:caitiff", "name": "Caitiff", "caitiff": True, "disciplines": [], "creation": {"no_positive_status": True}},
        {"id": "clan:ventrue", "name": "Ventrue", "disciplines": []},
        {"id": "clan:toreador", "name": "Toreador", "disciplines": []},
        {"id": "clan:hecata", "name": "Hecata", "disciplines": []},
    ],
    "disciplines": [{"id": "discipline:oblivion", "name": "Oblivion", "powers": []}],
    "advantages": [
        {"id": "background:allies", "name": "Allies", "kind": "background", "group": "Allies", "dots": {"min": 1, "max": 6}, "repeatable": True, "book": "v5-corebook"},
        {"id": "background:mask", "name": "Mask", "kind": "background", "group": "Mask", "dots": {"allowed": [1, 2]}, "repeatable": True, "book": "v5-corebook"},
        {"id": "background:resources", "name": "Resources", "kind": "background", "group": "Resources", "dots": {"min": 1, "max": 5}, "repeatable": False, "book": "v5-corebook"},
        {"id": "background:status", "name": "Status", "kind": "background", "group": "Status", "dots": {"min": 1, "max": 5}, "repeatable": True, "book": "v5-corebook"},
        {"id": "merit:day-drinker", "name": "Day Drinker", "kind": "merit", "group": "Thin-blood", "dots": None, "thin_blood": True},
        {"id": "merit:ghoul-empathy", "name": "Ghoul Empathy", "kind": "merit", "dots": {"min": 2, "max": 2}, "ghoul_only": True},
        {"id": "background:domain", "name": "Domain", "kind": "background", "dots": None, "coterie": True},
        {"id": "merit:iron-gullet", "name": "Iron Gullet", "kind": "merit", "dots": {"min": 3, "max": 3},
         "cannot_buy_for": [{"clan": "clan:ventrue", "when": "always"}], "book": "v5-corebook"},
        {"id": "merit:cell", "name": "Cell", "kind": "merit", "dots": {"min": 1, "max": 5}, "requires": "Haven \u2022\u2022", "book": "v5-corebook"},
        {"id": "flaw:archaic", "name": "Archaic", "kind": "flaw", "dots": {"min": 2, "max": 2}, "requires": "ancilla or older"},
        {"id": "merit:old-ways", "name": "Old Ways", "kind": "merit", "dots": {"min": 1, "max": 1}, "requires": "ancilla or older", "book": "v5-corebook"},
        {"id": "merit:bond-resistance", "name": "Bond Resistance", "kind": "merit", "dots": {"min": 1, "max": 3},
         "repeatable": False, "aliases": ["Blood Bond Resistance"], "book": "v5-corebook"},
        {"id": "merit:city-secrets", "name": "City Secrets", "kind": "merit", "dots": {"min": 1, "max": 1}, "repeatable": True, "max_instances": 2, "book": "v5-players-guide"},
        {"id": "merit:clan-trick", "name": "Clan Trick", "kind": "merit", "dots": {"min": 1, "max": 1}, "clans_only": ["clan:banu-haqim"], "book": "v5-corebook"},
    ],
    "loresheets": [
        {"id": "loresheet:the-bahari", "name": "The Bahari", "clans_only": None, "disciplines_only": None, "thin_blood_only": False,
         "levels": [{"dots": n, "name": f"L{n}"} for n in range(1, 6)], "book": "v5-corebook"},
        {"id": "loresheet:golconda", "name": "Golconda Seekers", "clans_only": ["clan:hecata"], "disciplines_only": None,
         "thin_blood_only": False, "levels": [{"dots": n, "name": f"L{n}"} for n in range(1, 6)], "book": "v5-corebook"},
        {"id": "loresheet:shadow", "name": "Shadow Walkers", "clans_only": None, "disciplines_only": ["discipline:oblivion"],
         "thin_blood_only": False, "levels": [{"dots": n, "name": f"L{n}"} for n in range(1, 6)], "book": "v5-corebook"},
    ],
}


def rich(**over):
    m = meta(saved={"advantage_dots": 5}, **over)
    m["advantages"][2] = {"id": "background:allies", "name": "Allies (police)", "dots": 5, "kind": "background", "note": "police"}
    return m


def check(m, *items, settings=None):
    return validate_spend(m, adv(*items), CATALOG, settings or {}, skills())


def test_without_the_catalog_rows_keep_to_1_to_5():
    assert check_codes(meta(), None, {"name": "allies", "dots": 2}) == ["adv_dots_range"]
    out = validate_spend(meta(), adv({"name": "Allies", "dots": 2}), None, {}, skills())
    assert out["problems"] == [{"code": "adv_dots_range", "params": {"name": "Allies", "dots": 6, "min": 1, "max": 5}}]
    # two items on one row add up
    m5 = meta(saved={"advantage_dots": 5})
    assert check_codes(m5, None, {"name": "Allies", "dots": 1}, {"name": "Allies", "dots": 1}) == ["adv_dots_range"]
    # no catalog: names are not checked
    assert validate_spend(meta(), adv({"name": "Made Up", "dots": 1}), {}, {}, skills())["ok"]


def check_codes(m, catalog, *items):
    return codes(validate_spend(m, adv(*items), catalog, {}, skills()))


def test_catalog_ratings_as_at_creation():
    assert codes(check(rich(), {"name": "Allies (police)", "dots": 1})) == []  # Allies goes to 6
    out = check(rich(), {"name": "Allies (police)", "dots": 2})
    assert out["problems"] == [{"code": "adv_dots_range", "params": {"name": "Allies (police)", "dots": 7, "min": 1, "max": 6}}]
    assert codes(check(rich(), {"id": "background:mask", "name": "Mask", "dots": 2})) == []
    assert codes(check(rich(), {"id": "background:mask", "name": "Mask", "dots": 3})) == ["adv_dots_range"]
    # a second, separate Allies row (another note) is a new row of a repeatable Background
    assert codes(check(rich(), {"id": "background:allies", "name": "Allies (mob)", "dots": 2, "note": "mob"})) == []


def test_catalog_restrictions_as_at_creation():
    assert codes(check(rich(), {"name": "Day Drinker", "dots": 1})) == ["adv_restricted"]
    assert codes(check(meta(clan="Thin-blood"), {"name": "Day Drinker", "dots": 1})) == []
    assert codes(check(rich(), {"name": "Ghoul Empathy", "dots": 2})) == ["adv_restricted"]
    assert codes(check(rich(), {"name": "Domain", "dots": 1})) == ["adv_restricted"]  # a coterie's
    ventrue = check(meta(clan="Ventrue", saved={"advantage_dots": 3}), {"name": "Iron Gullet", "dots": 3})
    assert ventrue["problems"] == [{"code": "adv_restricted", "params": {"name": "Iron Gullet", "clan": "Ventrue"}}]
    assert codes(check(meta(clan="Banu Haqim"), {"name": "Clan Trick", "dots": 1})) == []
    assert codes(check(meta(clan="Assamites"), {"name": "Clan Trick", "dots": 1})) == []
    assert codes(check(rich(), {"name": "Clan Trick", "dots": 1})) == ["adv_restricted"]
    assert codes(check(meta(clan="Caitiff"), {"name": "Status", "dots": 1})) == ["caitiff_status"]


def test_what_a_spend_adds_to_the_creation_rules():
    assert check(rich(), {"name": "Made Up", "dots": 1})["problems"] == [{"code": "adv_unknown", "params": {"name": "Made Up"}}]
    assert codes(check(rich(), {"name": "Archaic", "dots": 2})) == ["adv_unknown"]  # a Flaw, not an Advantage
    cell = check(rich(), {"name": "Cell", "dots": 1})
    assert cell["problems"] == [{"code": "adv_requires", "params": {"name": "Cell", "requires": "Haven \u2022\u2022"}}]
    assert codes(check(rich(), {"name": "Old Ways", "dots": 1})) == ["adv_requires"]
    assert codes(check(rich(age="ancilla"), {"name": "Old Ways", "dots": 1})) == []
    # once only: already on the sheet under an alias (here a predator grant)
    m = meta()
    m["advantages"].append({"name": "Blood Bond Resistance", "dots": 1, "kind": "predator"})
    assert codes(check(m, {"name": "Bond Resistance", "dots": 1})) == ["adv_repeat"]
    assert codes(check(meta(), {"name": "Bond Resistance", "dots": 1})) == []
    two = meta()
    two["advantages"] += [{"name": "City Secrets (Athens)", "dots": 1, "kind": "merit"}, {"name": "City Secrets (Rome)", "dots": 1, "kind": "merit"}]
    assert codes(check(two, {"name": "City Secrets (Paris)", "dots": 1})) == ["adv_repeat"]
    books = {"allowed_books": ["v5-corebook"]}
    assert codes(check(meta(), {"name": "City Secrets", "dots": 1}, settings=books)) == ["book_not_allowed"]


def test_loresheet_levels_and_restrictions():
    lore = lambda name, *levels: {"name": name, "kind": "loresheet", "levels": list(levels)}  # noqa: E731
    assert codes(check(meta(), lore("The Bahari", 2))) == []
    m = meta()
    m["advantages"].append({"id": "loresheet:the-bahari", "name": "The Bahari", "dots": 1, "kind": "loresheet", "levels": [1]})
    assert codes(check(m, lore("The Bahari", 1))) == ["loresheet_levels"]  # each level once
    out = check(m, lore("The Bahari", 2))
    assert out["ok"], out
    new, _, after = apply_spend({"wod_meta": m}, adv(lore("The Bahari", 2)))
    assert new["wod_meta"]["advantages"][-1] == {
        "id": "loresheet:the-bahari", "name": "The Bahari", "dots": 3, "kind": "loresheet", "levels": [1, 2], "saved_dots": 2,
    }
    assert after["changes"] == [{"name": "The Bahari", "kind": "loresheet", "from": 1, "to": 3, "levels": [2]}]
    assert codes(check(meta(), lore("Golconda Seekers", 1))) == ["loresheet_restricted"]
    assert codes(check(meta(clan="Hecata"), lore("Golconda Seekers", 1))) == []
    assert codes(check(meta(), lore("Shadow Walkers", 1))) == ["loresheet_restricted"]
    oblivion = meta(disciplines=[{"name": "Oblivion", "level": 1, "powers": []}])
    assert codes(check(oblivion, lore("Shadow Walkers", 1))) == []
    assert codes(check(meta(), lore("No Such Sheet", 1))) == ["adv_unknown"]


def test_the_real_catalog_when_installed():
    from services.v5_catalog import load_catalog

    cat = load_catalog() or {}
    if not cat.get("advantages"):
        pytest.skip("no advantages.json")
    out = validate_spend(rich(), adv({"id": "background:allies", "name": "Allies (police)", "dots": 1}), cat, {}, skills())
    assert out["ok"], out
