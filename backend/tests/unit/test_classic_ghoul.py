"""Classic (Revised) ghoul sheets: services/classic_ghoul.py's constants against docs/rules/classic.json
"ghoul", the helpers (domitor generation, Discipline cap, Domitor Background, Blood Pool) and the
bounds check the routes use."""

import copy
import json
import os

import pytest

from services import classic_ghoul as cg

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CLASSIC_JSON = os.path.join(REPO, "docs", "rules", "classic.json")

META = {
    "sheet_kind": "ghoul", "concept": "Driver", "nature": "Caregiver", "demeanor": "Conformist",
    "ghoul": {"kind": "vassal", "domitor": {"character_id": 21, "name": "Theo", "clan": "Ventrue", "generation": 12},
              "duties": "Drives", "ghouled_since": "1998", "age": 51, "apparent_age": 38,
              "bond": {"stage": 3, "note": "", "dry_since": ""}, "feeding": {"last": "", "note": ""},
              "overdosing": ""},
    "blood_pool": {"max": 10, "current": 6, "per_turn": 1},
    "disciplines": [{"name": "Potence", "dots": 1}, {"name": "Fortitude", "dots": 1}],
    "backgrounds": [{"name": "Domitor", "dots": 1}, {"name": "Resources", "dots": 2}],
    "virtues": {"conscience": 3, "self_control": 3, "courage": 2},
    "humanity": 6, "willpower": 2, "willpower_current": 2, "health_damage": 0,
}
ATTRS = {"strength": 3, "dexterity": 3, "stamina": 2, "charisma": 2, "manipulation": 3, "appearance": 2,
         "perception": 3, "intelligence": 3, "wits": 2}


@pytest.fixture
def rules():
    if not os.path.exists(CLASSIC_JSON):
        pytest.skip("needs the whole repo (not available inside the backend container)")
    with open(CLASSIC_JSON, encoding="utf-8") as f:
        return json.load(f)["ghoul"]


def test_constants_match_classic_json(rules):
    c = rules["creation"]
    assert tuple(c["attributes"]["priorities"]) == cg.ATTRIBUTE_PRIORITIES
    assert tuple(c["abilities"]["priorities"]) == cg.ABILITY_PRIORITIES
    assert c["abilities"]["max_before_freebies"] == cg.ABILITY_MAX_BEFORE_FREEBIES
    assert c["disciplines"]["creation_dots"] == cg.DISCIPLINE_CREATION_DOTS
    assert c["backgrounds"]["dots"] == cg.BACKGROUND_DOTS
    assert [b.lower() for b in c["backgrounds"]["not_allowed"]] == list(cg.NOT_ALLOWED_BACKGROUNDS)
    assert c["virtues"]["dots"] == cg.VIRTUE_DOTS
    assert c["freebies"] == cg.FREEBIES and c["flaws_max_points"] == cg.FLAWS_MAX_POINTS
    assert c["freebie_costs"] == cg.FREEBIE_COSTS
    assert tuple(rules["kinds"]) == cg.KINDS
    assert rules["blood_pool"]["max"] == cg.BLOOD_POOL_MAX and rules["blood_pool"]["per_turn"] == cg.BLOOD_POOL_PER_TURN
    assert rules["blood_bond"]["drinks_to_bind"] == cg.BLOOD_BOND_DRINKS
    cap = {int(k): v for k, v in rules["discipline_cap_by_donor_generation"].items() if k != "ref"}
    assert cap == cg.DISCIPLINE_CAP


@pytest.mark.parametrize("raw, gen", [("12", 12), (12, 12), ("12th", 12), (" 9th ", 9), ("", 13), (None, 13),
                                      ("lots", 13), (True, 13), (2, 13), ("16", 13), (4, 4)])
def test_domitor_generation(raw, gen):
    assert cg.domitor_generation({"generation": raw}) == gen


def test_domitor_generation_of_a_missing_sheet():
    assert cg.domitor_generation(None) == 13 and cg.domitor_generation({}) == 13


@pytest.mark.parametrize("gen, cap", [(13, 1), (12, 1), (8, 1), (7, 2), (6, 3), (5, 4), (4, 5), (3, 5), (None, 1)])
def test_discipline_cap(gen, cap):
    assert cg.discipline_cap(gen) == cap


@pytest.mark.parametrize("gen, dots", [(13, 1), (11, 1), (10, 2), (9, 2), (8, 3), (7, 4), (6, 5), (5, 5), (None, 1)])
def test_domitor_background_dots(gen, dots):
    assert cg.domitor_background_dots(gen) == dots


def test_a_ghoul_in_bounds():
    assert cg.sanity_check_classic_ghoul(ATTRS, {"talents": {"alertness": 2}}, META) == []
    assert cg.sanity_check_classic_ghoul(ATTRS, None, None) == []  # a PUT with attributes only


def test_a_staff_sized_pool_is_in_bounds():
    m = copy.deepcopy(META)
    m["blood_pool"] = {"max": 20, "current": 15, "per_turn": 1}  # an old ghoul (FA: +1 per two centuries)
    assert cg.sanity_check_classic_ghoul(None, None, m) == []


@pytest.mark.parametrize("change, needle", [
    (lambda m: m["blood_pool"].update(max=0), "blood_pool.max"),
    (lambda m: m["blood_pool"].update(current=7, max=6), "blood_pool.current"),
    (lambda m: m["blood_pool"].update(per_turn=2), "blood_pool.per_turn"),
    (lambda m: m.update(blood_pool=[10]), "blood_pool must be an object"),
    (lambda m: m.update(disciplines=[]), "Potence"),
    (lambda m: m.update(disciplines=[{"name": "Potence", "dots": 0}]), "Potence"),
    (lambda m: m["disciplines"].append({"name": "Celerity", "dots": 6}), "disciplines[2].dots"),
    (lambda m: m["backgrounds"].append({"name": "Herd", "dots": 1}), "no Herd"),
    (lambda m: m["backgrounds"].append({"name": "status", "dots": 1}), "no status"),
    (lambda m: m.update(clan="Ventrue"), "no clan"),
    (lambda m: m.update(generation="12"), "no generation"),
    (lambda m: m.update(hunger=1), "no hunger"),
    (lambda m: m.update(predator_type="Alleycat"), "no predator_type"),
    (lambda m: m.update(edition="v5"), "edition"),
    (lambda m: m.update(sheet_kind=None), "sheet_kind"),
    (lambda m: m.pop("ghoul"), "wod_meta.ghoul is required"),
    (lambda m: m["ghoul"].update(kind="thrall"), "ghoul.kind"),
    (lambda m: m["ghoul"].update(domitor={"name": "Theo"}), "domitor.character_id"),
    (lambda m: m["ghoul"]["domitor"].update(generation=16), "domitor.generation"),
    (lambda m: m["ghoul"]["bond"].update(stage=4), "bond.stage"),
    (lambda m: m["ghoul"].update(feeding="yesterday"), "feeding must be an object"),
    (lambda m: m["ghoul"].update(age=-1), "ghoul.age"),
    (lambda m: m["ghoul"].update(duties="x" * 201), "ghoul.duties"),
    (lambda m: m["ghoul"].update(family=["Zantosa"]), "ghoul.family"),
    (lambda m: m["virtues"].update(courage=0), "virtues.courage"),
    (lambda m: m.update(humanity=11), "humanity"),
    (lambda m: m.update(willpower_current=3), "willpower_current"),
    (lambda m: m.update(health_damage=8), "health_damage"),
    (lambda m: m.update(experience=5), "experience must be an object"),
])
def test_out_of_bounds(change, needle):
    m = copy.deepcopy(META)
    change(m)
    problems = cg.sanity_check_classic_ghoul(None, None, m)
    assert problems and any(needle in p for p in problems), problems


def test_attributes_and_abilities_bounds():
    assert cg.sanity_check_classic_ghoul({**ATTRS, "strength": 0}) == ["attributes.strength must be between 1 and 5"]
    assert cg.sanity_check_classic_ghoul(None, {"skills": {"drive": 6}}) == ["skills.skills.drive must be between 0 and 5"]
    assert cg.sanity_check_classic_ghoul(None, {"custom": {"talents": [{"name": "Carousing", "dots": 9}]}})
    assert cg.sanity_check_classic_ghoul([1]) == ["attributes must be an object"]
    assert cg.sanity_check_classic_ghoul(None, None, "x") == ["wod_meta must be an object"]


def test_ghoul_pool():
    assert cg.ghoul_pool(META) == {"max": 10, "current": 6, "per_turn": 1}
    assert cg.ghoul_pool({}) == {"max": 10, "current": 0, "per_turn": 1}
    assert cg.ghoul_pool({"blood_pool": {"max": 30, "current": 40, "per_turn": 3}}) == {"max": 20, "current": 20,
                                                                                      "per_turn": 1}
    assert cg.ghoul_pool({"blood_pool": {"max": "ten", "current": True}}) == {"max": 10, "current": 0, "per_turn": 1}


def test_kind_label():
    assert [cg.kind_label(k) for k in ("vassal", "independent", "revenant", None, "odd")] == [
        "Vassal", "Independent", "Revenant", "", "odd"]
