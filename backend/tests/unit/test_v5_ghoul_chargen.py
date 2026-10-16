"""Server-side V5 ghoul creation check (services/v5_ghoul_chargen.py) and the ghoul bounds
(services/character_sheet_v5.py). Mira Tanis, Darius Vale's Gifted ghoul, is the acceptance
case: she must pass with no override. The shared vectors (kind 'ghoul' in
docs/rules/v5/tests/creation-cases.json) run in test_v5_chargen.py."""

import copy
import json
import re
from pathlib import Path

import pytest

from services.character_sheet_v5 import GHOUL_TEMPLATES, is_ghoul, sanity_check_v5
from services.v5_ghoul_chargen import (
    BOND_STRENGTH_MAX,
    CANNOT_BUY_FLAGS,
    CANNOT_BUY_GROUPS,
    GHOUL_HUMANITY,
    GHOUL_PROBLEM_CODES,
    MORTAL_TEMPLATES,
    POWER_LEVEL,
    POWERS_AT_CREATION,
    RETAINER_CONVICTIONS,
    RETAINER_GHOUL_NO_ADVANTAGES_AT,
    validate_ghoul_creation,
)

REPO = Path(__file__).resolve().parents[3]


def _first(*paths):
    return next((p for p in paths if p and Path(p).is_file()), None)


CASES_FILE = _first(REPO / "docs" / "rules" / "v5" / "tests" / "creation-cases.json",
                    "/app/project_docs/rules/v5/tests/creation-cases.json")
RULES_FILE = _first(REPO / "docs" / "rules" / "v5.json", "/app/project_docs/rules/v5.json")
pytestmark = pytest.mark.skipif(CASES_FILE is None, reason="docs/rules/v5/tests not on disk")
CATALOG = json.loads(Path(CASES_FILE).read_text("utf-8"))["catalog"] if CASES_FILE else {}

DARIUS = {
    "id": 17, "name": "Darius Vale", "user_id": 3, "campaign_id": None, "rules_edition": "v5",
    "system_type": "vampire",
    "wod_meta": json.dumps({
        "edition": "v5", "clan": "Ventrue",
        "disciplines": [{"name": "Dominate", "level": 3, "powers": ["Cloud Memory", "Mesmerize", "Submerged Directive"]},
                        {"name": "Presence", "level": 1, "powers": ["Awe"]}],
    }),
}


def _skills(by_rating, specialties, distribution):
    groups = {
        "physical": ("athletics", "brawl", "craft", "drive", "firearms", "larceny", "melee", "stealth", "survival"),
        "social": ("animal_ken", "etiquette", "insight", "intimidation", "leadership", "performance", "persuasion",
                   "streetwise", "subterfuge"),
        "mental": ("academics", "awareness", "finance", "investigation", "medicine", "occult", "politics", "science",
                   "technology"),
    }
    rating = {k: r for r, keys in by_rating.items() for k in keys}
    out = {g: {k: rating.get(k, 0) for k in keys} for g, keys in groups.items()}
    out["specialties"] = specialties
    out["distribution"] = distribution
    return out


MIRA = {
    "attributes": {"strength": 1, "dexterity": 1, "stamina": 1, "charisma": 2, "manipulation": 4, "composure": 1,
                   "intelligence": 3, "wits": 3, "resolve": 2},
    "skills": _skills(
        {4: ["persuasion", "subterfuge"], 3: ["leadership", "insight", "etiquette", "finance"],
         2: ["academics", "technology", "politics", "streetwise"], 1: ["awareness", "craft", "drive", "investigation"]},
        [{"skill": "persuasion", "name": "Negotiation", "source": "template"},
         {"skill": "academics", "name": "Media studies"}, {"skill": "craft", "name": "Video editing"}],
        "gifted",
    ),
    "wod_meta": {
        "edition": "v5", "sheet_kind": "ghoul",
        "concept": "Former television executive at rock bottom; now Darius's producer",
        "ghoul": {
            "template": "gifted", "retainer_dots": 3,
            "domitor": {"character_id": 17, "name": "Darius Vale", "clan": "Ventrue"},
            "age": 55, "apparent_age": 53, "ghouled_since": "About two to three years ago",
            "bonds": [{"character_id": 17, "name": "Darius Vale", "strength": None, "note": "Bondslave"}],
            "feeding": {"last": "", "note": "About once a month"},
        },
        "disciplines": [{"name": "Dominate", "level": 1, "powers": ["Cloud Memory"], "ghoul": True}],
        "humanity": 7, "stains": 0,
        "health": {"max": 4, "superficial": 0, "aggravated": 0},
        "willpower": {"max": 3, "superficial": 0, "aggravated": 0},
        "advantages": [
            {"id": "merit:beautiful", "name": "Beautiful", "dots": 2, "kind": "merit"},
            {"id": "background:contacts", "name": "Contacts (television production coordinator)", "dots": 2,
             "kind": "background", "note": "television production coordinator"},
            {"id": "background:contacts", "name": "Contacts (network acquisitions executive)", "dots": 3,
             "kind": "background", "note": "network acquisitions executive"},
            {"id": "background:fame", "name": "Fame (television production industry)", "dots": 1, "kind": "background"},
            {"id": "background:influence", "name": "Influence (Istanbul television production)", "dots": 1,
             "kind": "background"},
            {"id": "merit:linguistics", "name": "Linguistics (English)", "dots": 1, "kind": "merit"},
        ],
        "flaws": [
            {"id": "flaw:two-masters", "name": "Two Masters", "dots": 1, "kind": "flaw"},
            {"id": "flaw:bondslave", "name": "Bondslave", "dots": 2, "kind": "flaw"},
            {"id": "flaw:addiction", "name": "Addiction (cocaine)", "dots": 1, "kind": "flaw"},
        ],
        "touchstones": [], "chronicle_tenets": "",
        "forge": {"version": 2, "kind": "ghoul", "settings_v": 1},
    },
}


def mira():
    return copy.deepcopy(MIRA)


def meta(sheet):
    return sheet["wod_meta"]


def codes(sheet, settings=None, domitor=DARIUS, catalog=None):
    return [p["code"] for p in validate_ghoul_creation(sheet, CATALOG if catalog is None else catalog, settings, domitor)]


def problems(sheet, settings=None, domitor=DARIUS):
    return validate_ghoul_creation(sheet, CATALOG, settings, domitor)


# ---------- Mira and the other templates ----------

def test_mira_passes_with_no_override():
    assert problems(mira()) == []
    assert problems(mira(), domitor=None) == []  # without the domitor's row the domitor checks are skipped


def _retainer(template, attrs, by_rating, specialties=(), adv=(), flaws=(), retainer_dots=None, **extra):
    s = mira()
    s["attributes"] = dict(zip(("strength", "dexterity", "stamina", "charisma", "manipulation", "composure",
                                "intelligence", "wits", "resolve"), attrs))
    s["skills"] = _skills(by_rating, list(specialties), template)
    m = meta(s)
    m["ghoul"].update(template=template, retainer_dots=retainer_dots)
    m["advantages"], m["flaws"] = list(adv), list(flaws)
    m["health"]["max"] = s["attributes"]["stamina"] + 3
    m["willpower"]["max"] = s["attributes"]["composure"] + s["attributes"]["resolve"]
    m["ghoul"]["bonds"] = [{"character_id": 17, "name": "Darius Vale", "strength": 3}]
    m.update(extra)
    return s


def weak():
    return _retainer("weak", (2, 1, 1, 2, 1, 1, 1, 1, 1),
                     {2: ["drive", "streetwise", "larceny"], 1: ["brawl", "stealth", "insight", "awareness", "athletics"]},
                     retainer_dots=1)


def average(retainer_dots=2, adv=()):
    return _retainer("average", (2, 2, 3, 1, 1, 3, 1, 2, 1),
                     {3: ["drive", "brawl", "firearms"], 2: ["streetwise", "larceny", "stealth", "athletics"],
                      1: ["insight", "awareness", "intimidation", "melee", "survival"]},
                     adv=adv, flaws=[{"id": "flaw:bondslave", "name": "Bondslave", "dots": 2, "kind": "flaw"}],
                     retainer_dots=retainer_dots)


def deadly():
    return _retainer("deadly", (5, 5, 4, 4, 3, 3, 2, 2, 2),
                     {5: ["firearms"], 4: ["brawl", "melee", "athletics"],
                      3: ["stealth", "drive", "awareness", "intimidation", "survival"],
                      2: ["larceny", "streetwise", "insight", "investigation", "medicine", "occult"]},
                     specialties=[{"skill": "firearms", "name": "Sniper rifles", "source": "template"},
                                  {"skill": "brawl", "name": "Grappling", "source": "template"},
                                  {"skill": "melee", "name": "Knives", "source": "template"}],
                     adv=[{"id": "background:resources", "name": "Resources", "dots": 3, "kind": "background"},
                          {"id": "merit:ghoul-blood-empathy", "name": "Blood Empathy", "dots": 2, "kind": "merit"}])


def player():
    s = _retainer("player", (3, 3, 3, 2, 2, 2, 2, 1, 4),
                  {3: ["athletics", "brawl", "stealth"], 2: ["drive", "firearms", "insight", "persuasion", "awareness"],
                   1: ["melee", "larceny", "etiquette", "streetwise", "subterfuge", "investigation", "occult"]},
                  specialties=[{"skill": "athletics", "name": "Parkour"}],
                  adv=[{"id": "background:resources", "name": "Resources", "dots": 3, "kind": "background"},
                       {"id": "background:allies", "name": "Allies (dock workers)", "dots": 2, "kind": "background"},
                       {"id": "merit:ghoul-unseemly-aura", "name": "Unseemly Aura", "dots": 2, "kind": "merit"}],
                  flaws=[{"id": "flaw:ghoul-distressing-fangs", "name": "Distressing Fangs", "dots": 1, "kind": "flaw"},
                         {"id": "flaw:addiction", "name": "Addiction (painkillers)", "dots": 1, "kind": "flaw"}],
                  touchstones=[{"name": "Mia, my niece", "conviction": "Never harm a child"}])
    s["skills"]["distribution"] = "balanced"
    return s


@pytest.mark.parametrize("make", [weak, average, deadly, player], ids=lambda f: f.__name__)
def test_a_valid_sheet_per_template(make):
    assert problems(make()) == []


# ---------- template, spread, Skills, specialties ----------

def test_an_unknown_template():
    s = mira()
    meta(s)["ghoul"]["template"] = "elder"
    assert codes(s) == ["ghoul_template"]


def test_attribute_spread_follows_the_template():
    s = mira()
    s["attributes"]["wits"] = 4  # two 4s
    assert problems(s) == [{"code": "ghoul_attr_spread", "params": {"template": "gifted"}}]
    s = player()
    s["attributes"]["resolve"] = 3  # the vampire spread: one at 4, three at 3...
    s["wod_meta"]["willpower"]["max"] = 5
    assert problems(s) == [{"code": "ghoul_attr_spread", "params": {"template": "player"}}]


def test_skill_counts_and_the_template_key():
    s = mira()
    s["skills"]["mental"]["occult"] = 1  # one dot too many
    assert codes(s) == ["skill_dist"]
    s = mira()
    s["skills"]["distribution"] = "balanced"  # a retainer's distribution is its template
    assert problems(s) == [{"code": "skill_dist", "params": {"distribution": "balanced"}}]


def test_specialties_of_a_template():
    s = mira()
    s["skills"]["specialties"].append({"skill": "subterfuge", "name": "Cover stories"})
    assert problems(s) == [{"code": "ghoul_specialty_count", "params": {"template": "gifted", "max": 3, "have": 4}}]
    s = mira()
    s["skills"]["specialties"] = [sp for sp in s["skills"]["specialties"] if sp["skill"] != "academics"]
    assert problems(s) == [{"code": "specialty_missing", "params": {"skill": "academics"}}]
    s = mira()
    s["skills"]["specialties"][0]["skill"] = "occult"  # an unrated Skill
    assert "specialty_skill" in codes(s)


def test_player_ghoul_specialties_are_the_vampire_rule():
    s = player()
    s["skills"]["specialties"].append({"skill": "brawl", "name": "Grappling"})
    assert codes(s) == ["specialty_count"]


# ---------- the ghoul power ----------

@pytest.mark.parametrize("powers,want", [
    ([], ["ghoul_power_count"]),
    (["Cloud Memory", "Compel"], ["ghoul_power_count", "ghoul_power_not_domitors"]),
])
def test_exactly_one_power(powers, want):
    s = mira()
    meta(s)["disciplines"][0]["powers"] = powers
    assert codes(s) == want


def test_a_level_2_power_and_a_level_2_row():
    s = mira()
    meta(s)["disciplines"][0]["powers"] = ["Mesmerize"]
    assert problems(s) == [{"code": "ghoul_power_level", "params": {"discipline": "Dominate", "power": "Mesmerize", "level": 2}}]
    s = mira()
    meta(s)["disciplines"][0]["level"] = 2
    assert codes(s) == ["ghoul_power_level"]


def test_the_discipline_and_power_come_from_the_domitor():
    s = mira()
    meta(s)["disciplines"][0].update(name="Auspex", powers=["Heightened Senses"])
    assert problems(s) == [{"code": "ghoul_power_discipline", "params": {"discipline": "Auspex"}}]
    s = mira()
    meta(s)["disciplines"][0]["powers"] = ["Compel"]  # a Dominate 1 power Darius doesn't have
    assert problems(s) == [{"code": "ghoul_power_not_domitors", "params": {"discipline": "Dominate", "power": "Compel"}}]
    # a domitor whose sheet lists no powers: only the Discipline is checked
    bare = dict(DARIUS, wod_meta={"edition": "v5", "disciplines": [{"name": "Dominate", "level": 2}]})
    assert codes(s, domitor=bare) == []
    s = mira()
    meta(s)["disciplines"][0]["powers"] = ["Mind Over Matter"]
    assert codes(s) == ["power_unknown"]


# ---------- Advantages and Flaws ----------

def test_budget_of_a_gifted_ghoul():
    s = mira()
    meta(s)["advantages"].append({"id": "background:resources", "name": "Resources", "dots": 1, "kind": "background"})
    assert problems(s) == [{"code": "adv_over", "params": {"max": 10, "have": 11}}]
    s = mira()
    meta(s)["flaws"].append({"id": "flaw:dark-secret", "name": "Dark Secret", "dots": 1, "kind": "flaw"})
    assert problems(s) == [{"code": "ghoul_flaws_over", "params": {"template": "gifted", "max": 4, "have": 5}}]


def test_a_retainers_2_ghoul_has_no_advantages():
    one = [{"id": "background:resources", "name": "Resources", "dots": 1, "kind": "background"}]
    assert problems(average(adv=one)) == [{"code": "adv_over", "params": {"max": 0, "have": 1}}]
    assert problems(average(retainer_dots=None, adv=one)) == []  # not a Retainers •• ghoul: Average, up to 3
    assert RETAINER_GHOUL_NO_ADVANTAGES_AT == 2


def test_player_ghoul_budget():
    s = player()
    meta(s)["flaws"] = meta(s)["flaws"][:1]
    assert problems(s) == [{"code": "flaw_under", "params": {"min": 2, "have": 1}}]
    s = player()
    meta(s)["flaws"].append({"id": "flaw:dark-secret", "name": "Dark Secret", "dots": 1, "kind": "flaw"})
    assert problems(s, settings={"flaws_max_dots": 2}) == [{"code": "flaw_over", "params": {"max": 2, "have": 3}}]


@pytest.mark.parametrize("row,why", [
    ({"id": "background:herd", "name": "Herd", "dots": 1, "kind": "background"}, "herd"),
    ({"id": "merit:iron-gullet", "name": "Iron Gullet", "dots": 3, "kind": "merit"}, "feeding"),
    ({"id": "background:domain", "name": "Domain", "dots": 1, "kind": "background"}, "domain"),
])
def test_what_ghouls_cannot_buy(row, why):
    s = mira()
    meta(s)["advantages"] = [row]
    out = problems(s)
    assert {"code": "ghoul_adv_restricted", "params": {"name": row["name"], "why": why}} in out


def test_thin_blood_caitiff_and_coterie_entries_are_refused():
    adv = {a["id"]: a for a in CATALOG["advantages"]}
    picks = {
        "thin_blood": next(a for a in adv.values() if a.get("thin_blood") and a["kind"] == "merit"),
        "caitiff": next(a for a in adv.values() if a.get("caitiff") and a["kind"] == "flaw"),
        "coterie": next(a for a in adv.values() if a.get("coterie") and a["kind"] == "merit"
                        and a.get("group") not in CANNOT_BUY_GROUPS),
    }
    for why, e in picks.items():
        s = mira()
        row = {"id": e["id"], "name": e["name"], "dots": 1, "kind": e["kind"]}
        meta(s)["advantages" if e["kind"] != "flaw" else "flaws"] = [row]
        assert {"code": "ghoul_adv_restricted", "params": {"name": e["name"], "why": why}} in problems(s), why
    assert set(CANNOT_BUY_FLAGS) == set(picks)


def test_ghoul_only_entries_are_open_to_a_ghoul():
    s = mira()
    meta(s)["advantages"][0] = {"id": "merit:ghoul-blood-empathy", "name": "Blood Empathy", "dots": 2, "kind": "merit"}
    assert problems(s) == []


def test_catalog_row_rules_still_apply():
    s = mira()
    meta(s)["advantages"][0]["dots"] = 3  # Beautiful is 2
    assert codes(s) == ["adv_over", "adv_dots_range"]
    s = mira()
    meta(s)["advantages"][0] = {"name": "Night Doctor", "dots": 2, "kind": "merit", "custom": True}
    assert codes(s) == ["custom_row"]
    s = mira()
    assert codes(s, settings={"allowed_books": ["v5-corebook"]}) == ["book_not_allowed"]  # Two Masters


# ---------- Bonds, derived values, Convictions, vampire keys ----------

def test_blood_bonds():
    s = mira()
    meta(s)["ghoul"]["bonds"].append({"character_id": None, "name": "Leyla", "strength": 1})
    assert problems(s) == []  # Two Masters is on the sheet
    meta(s)["flaws"] = meta(s)["flaws"][1:]
    meta(s)["ghoul"]["template"] = "gifted"
    assert problems(s) == [{"code": "ghoul_bonds", "params": {"why": "two_masters"}}]
    s = mira()
    meta(s)["ghoul"]["bonds"][0]["strength"] = BOND_STRENGTH_MAX + 1
    assert problems(s) == [{"code": "ghoul_bonds", "params": {"why": "strength"}}]
    s = mira()
    meta(s)["ghoul"]["bonds"][0]["character_id"] = 99
    assert problems(s) == [{"code": "ghoul_bonds", "params": {"why": "domitor"}}]
    s = mira()
    meta(s)["ghoul"]["bonds"] = []
    assert problems(s) == [{"code": "ghoul_bonds", "params": {"why": "count"}}]


def test_derived_values():
    s = mira()
    meta(s)["health"]["max"] = 5
    assert problems(s) == [{"code": "derived_value", "params": {"trait": "health", "have": 5, "want": 4}}]
    s = mira()  # Crone's Curse: one Health box less (PG p. 141)
    meta(s)["flaws"][2] = {"id": "flaw:ghoul-crones-curse", "name": "Crone's Curse", "dots": 2, "kind": "flaw"}
    meta(s)["flaws"].pop(1)
    meta(s)["flaws"].append({"id": "flaw:addiction", "name": "Addiction (cocaine)", "dots": 1, "kind": "flaw"})
    assert problems(s) == [{"code": "derived_value", "params": {"trait": "health", "have": 4, "want": 3}}]
    meta(s)["health"]["max"] = 3
    assert problems(s) == []
    s = mira()
    meta(s)["humanity"] = 8
    assert codes(s) == ["derived_value"]
    del meta(s)["humanity"]
    assert problems(s) == []  # a retainer may leave Humanity out
    s = player()
    del meta(s)["humanity"]
    assert problems(s) == [{"code": "derived_value", "params": {"trait": "humanity", "have": 0, "want": GHOUL_HUMANITY}}]


def test_convictions():
    s = player()
    meta(s)["touchstones"] = []
    assert problems(s) == [{"code": "conviction_count", "params": {"min": 1, "max": 3, "have": 0}}]
    s = mira()
    meta(s)["touchstones"] = [{"name": "", "conviction": "Never go back to the bar"}]
    assert codes(s) == ["conviction_pairs"]
    meta(s)["touchstones"] = [{"name": f"T{i}", "conviction": f"C{i}"} for i in range(4)]
    assert codes(s) == ["conviction_count"]
    assert RETAINER_CONVICTIONS == (0, 3)


def test_vampire_keys_are_refused():
    s = mira()
    meta(s).update(clan="Ventrue", hunger=1, predator_type="")
    meta(s)["advantages"].append({"name": "Herd", "dots": 1, "kind": "predator"})
    assert [p["params"]["field"] for p in problems(s) if p["code"] == "ghoul_vampire_field"] == [
        "clan", "hunger", "predator_rows"]


def test_the_domitor_row():
    s = mira()
    assert problems(s, domitor=dict(DARIUS, id=18)) == [{"code": "ghoul_domitor", "params": {"why": "mismatch"}}]
    ghoul_row = dict(DARIUS, wod_meta=json.dumps({"edition": "v5", "sheet_kind": "ghoul", "disciplines": [
        {"name": "Dominate", "level": 1, "powers": ["Cloud Memory"]}]}))
    assert codes(s, domitor=ghoul_row) == ["ghoul_domitor"]
    classic = dict(DARIUS, rules_edition="classic", wod_meta="{}")
    assert "ghoul_domitor" in codes(s, domitor=classic)
    meta(s)["ghoul"]["domitor"] = {"name": "Darius"}
    assert codes(s, domitor=None) == ["ghoul_domitor", "ghoul_bonds"]


def test_retainer_dots_buy_the_template():
    s = mira()
    meta(s)["ghoul"]["retainer_dots"] = 2
    assert problems(s) == [{"code": "ghoul_retainer_dots", "params": {"template": "gifted", "dots": 2, "need": 3}}]
    s = weak()
    meta(s)["ghoul"]["retainer_dots"] = 3  # one to one (core p. 194): Retainers ••• is a Gifted ghoul
    assert problems(s) == [{"code": "ghoul_retainer_dots", "params": {"template": "weak", "dots": 3, "need": 1}}]
    s = deadly()
    meta(s)["ghoul"]["retainer_dots"] = 3  # no Retainers rating buys a Deadly mortal
    assert codes(s) == ["ghoul_retainer_dots"]


def test_the_templates_own_specialties():
    s = mira()
    s["skills"]["specialties"][0]["skill"] = "finance"  # Finance 3: not one of the two Skills at 4
    assert problems(s) == [{"code": "ghoul_template_specialty",
                            "params": {"template": "gifted", "why": "rating", "need": 1, "have": 1}}]
    s = mira()
    del s["skills"]["specialties"][0]  # only the free Academics and Craft ones
    assert problems(s) == [{"code": "ghoul_template_specialty",
                            "params": {"template": "gifted", "why": "count", "need": 1, "have": 0}}]
    s = deadly()
    s["skills"]["specialties"] = s["skills"]["specialties"][:1]
    assert codes(s) == ["ghoul_template_specialty"]


def test_a_non_repeatable_entry_twice():
    s = mira()
    meta(s)["advantages"] = [a for a in meta(s)["advantages"] if a["id"] not in ("background:fame", "background:influence")]
    meta(s)["advantages"].append({"id": "merit:beautiful", "name": "Beautiful", "dots": 2, "kind": "merit"})
    assert problems(s) == [{"code": "adv_repeat", "params": {"name": "Beautiful", "max": 1}}]
    s = mira()  # Contacts is repeatable: two rows are fine
    assert codes(s) == []


def test_no_bond_rows_and_xp():
    s = mira()
    del meta(s)["ghoul"]["bonds"]
    assert problems(s) == [{"code": "ghoul_bonds", "params": {"why": "count"}}]
    s = mira()
    meta(s)["experience"] = {"total": 10, "spent": 0, "unspent": 10, "log": []}  # ghouls earn XP (PG p. 141)
    assert problems(s) == []


def test_garbage_never_raises():
    for junk in (None, 3, "x", [], {"wod_meta": "y"}, {"wod_meta": {"ghoul": [], "disciplines": {}, "advantages": 5,
                                                                    "flaws": [None, 3], "touchstones": "z"}}):
        for domitor in (None, {}, {"wod_meta": "{bad json"}, DARIUS, [1]):
            out = validate_ghoul_creation(junk, CATALOG, {"flaws_max_dots": "x"}, domitor)
            assert all(p["code"] in GHOUL_PROBLEM_CODES for p in out)
    assert validate_ghoul_creation(mira(), None, None, DARIUS) == []  # no catalog: rows are free text


# ---------- constants, codes, bounds ----------

def test_constants_match_the_rules_file():
    if RULES_FILE is None:
        pytest.skip("docs/rules/v5.json not on disk")
    rules = json.loads(Path(RULES_FILE).read_text("utf-8"))
    for key, row in rules["mortal_templates"].items():
        if not isinstance(row, dict):
            continue
        mine = MORTAL_TEMPLATES[key]
        assert list(mine["attributes"]) == row["attributes"], key
        assert {str(r): n for r, n in mine["skills"].items()} == row["skills"], key
        for k in ("specialties", "advantages_max", "flaws_max", "retainer_dots"):
            assert mine[k] == row[k], (key, k)
    assert set(MORTAL_TEMPLATES) == {k for k, v in rules["mortal_templates"].items() if isinstance(v, dict)}
    g = rules["ghoul"]
    assert tuple(g["templates"]) == GHOUL_TEMPLATES
    assert (g["humanity"], g["powers_at_creation"], g["power_level"]) == (GHOUL_HUMANITY, POWERS_AT_CREATION, POWER_LEVEL)
    assert g["retainer_ghoul_no_advantages_at"] == RETAINER_GHOUL_NO_ADVANTAGES_AT
    assert tuple(g["cannot_buy_groups"]) == CANNOT_BUY_GROUPS and tuple(g["cannot_buy_flags"]) == CANNOT_BUY_FLAGS
    assert g["bond_strength_max"] == BOND_STRENGTH_MAX and tuple(g["retainer_convictions"]) == RETAINER_CONVICTIONS
    for key, row in MORTAL_TEMPLATES.items():  # the counts are the book's
        assert sum(row["attributes"]) == {"weak": 11, "average": 16, "gifted": 18, "deadly": 30}[key]


def test_every_code_has_a_translation():
    i18n = REPO / "frontend" / "src" / "characterSheet" / "i18nErrors.js"
    if not i18n.is_file():
        pytest.skip("needs the whole repo")
    text = i18n.read_text("utf-8")
    assert [c for c in GHOUL_PROBLEM_CODES if not re.search(rf"\b{c}:", text)] == []


def test_ghoul_bounds():
    m = meta(mira())
    assert is_ghoul(m) and is_ghoul(json.dumps(m)) and not is_ghoul({"edition": "v5"}) and not is_ghoul("{")
    assert sanity_check_v5(mira()["attributes"], mira()["skills"], m) == []
    bad = copy.deepcopy(m)
    bad["disciplines"][0]["level"] = 2
    bad["ghoul"].update(template="elder", retainer_dots=4, age=200, ghouled_since="x" * 201,
                        bonds=[{"strength": 7, "note": "n" * 501}], feeding={"last": "l" * 61},
                        vitae={"note": "v" * 501})  # the key's earlier name is bounded too
    errs = sanity_check_v5(None, None, bad)
    for frag in ("disciplines[0].level", "ghoul.template", "retainer_dots", "ghoul.age", "ghouled_since",
                 "bonds[0].strength", "bonds[0].note", "feeding.last", "vitae.note"):
        assert any(frag in e for e in errs), frag
    assert sanity_check_v5(None, None, {"sheet_kind": "ghoul"}) == ["wod_meta.ghoul is required on a ghoul's sheet"]
    assert sanity_check_v5(None, None, {"sheet_kind": "mummy"}) == ["wod_meta.sheet_kind must be 'ghoul' when present"]
    no_dom = copy.deepcopy(m)
    no_dom["ghoul"]["domitor"] = {"character_id": "17"}
    assert sanity_check_v5(None, None, no_dom) == ["wod_meta.ghoul.domitor.character_id must be a character id"]
    three = copy.deepcopy(m)
    three["ghoul"]["bonds"] = [{}, {}, {}]
    assert sanity_check_v5(None, None, three) == ["wod_meta.ghoul.bonds must be a list of at most 2 Blood Bonds"]
