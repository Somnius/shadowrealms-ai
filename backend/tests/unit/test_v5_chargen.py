"""Server-side V5 creation check (services/v5_chargen.py).

The shared vectors (docs/rules/v5/tests/creation-cases.json, real forge payloads made by the
frontend's buildV5Payload) are run here and by frontend/src/characterSheet/v5/creationCases.test.js.
"""

import copy
import json
import re
from pathlib import Path

import pytest

from services.v5_chargen import (
    AGE_BRACKETS,
    ATTRIBUTE_SPREAD,
    PROBLEM_CODES,
    SKILL_DISTRIBUTIONS,
    XP_COSTS,
    validate_creation,
)

REPO = Path(__file__).resolve().parents[3]


def _first(*paths):
    return next((p for p in paths if p and Path(p).is_file()), None)


CASES_FILE = _first(
    REPO / "docs" / "rules" / "v5" / "tests" / "creation-cases.json",
    "/app/project_docs/rules/v5/tests/creation-cases.json",  # backend container: docs mounted here
)
FRONT_COPY = REPO / "frontend" / "src" / "characterSheet" / "v5" / "__fixtures__" / "creation-cases.json"
RULES_FILE = _first(REPO / "docs" / "rules" / "v5.json", "/app/project_docs/rules/v5.json")

pytestmark = pytest.mark.skipif(CASES_FILE is None, reason="docs/rules/v5/tests not on disk")

DOC = json.loads(Path(CASES_FILE).read_text("utf-8")) if CASES_FILE else {"catalog": {}, "cases": []}
CATALOG = DOC["catalog"]


def codes(problems):
    return sorted({p["code"] for p in problems})


def case(name):
    return copy.deepcopy(next(c for c in DOC["cases"] if c["name"] == name))


@pytest.mark.parametrize("c", DOC["cases"], ids=[c["name"] for c in DOC["cases"]])
def test_shared_case(c):
    assert codes(validate_creation(c["payload"], CATALOG, c["settings"])) == c["expect"]


def test_frontend_copy_is_the_same_file():
    if not FRONT_COPY.is_file():
        pytest.skip("needs the whole repo (not available inside the backend container)")
    assert Path(CASES_FILE).read_bytes() == FRONT_COPY.read_bytes(), (
        "docs/rules/v5/tests/creation-cases.json differs from the frontend fixture: "
        "python3 scripts/v5_creation_cases.py sync"
    )


def test_vectors_cover_the_vocabulary():
    seen = {code for c in DOC["cases"] for code in c["expect"]}
    assert seen <= set(PROBLEM_CODES)
    assert len(DOC["cases"]) >= 40
    assert sum(1 for c in DOC["cases"] if not c["expect"]) >= 10


def test_every_code_has_a_translation():
    i18n = REPO / "frontend" / "src" / "characterSheet" / "i18nErrors.js"
    if not i18n.is_file():
        pytest.skip("needs the whole repo")
    text = i18n.read_text("utf-8")
    missing = [c for c in PROBLEM_CODES if not re.search(rf"\b{c}:", text)]
    assert missing == []


def test_constants_match_the_rules_file():
    if RULES_FILE is None:
        pytest.skip("docs/rules/v5.json not on disk")
    rules = json.loads(Path(RULES_FILE).read_text("utf-8"))
    cr = rules["creation"]
    assert sorted(cr["attributes"]["spread"]) == sorted(ATTRIBUTE_SPREAD)
    names = {"jack": "jack_of_all_trades", "balanced": "balanced", "specialist": "specialist"}
    for key, dist in SKILL_DISTRIBUTIONS.items():
        assert {int(r): n for r, n in cr["skill_distributions"][names[key]].items()} == dist
    assert cr["advantages_dots"] == 7 and cr["flaws_min_dots"] == 2 and cr["convictions"] == [1, 3]
    assert cr["thin_blood"]["merits"] == [1, 3] and cr["humanity"] == 7
    assert rules["humanity"]["start_fledgling_option"] == 8
    for age, row in cr["age_brackets"].items():
        lo, hi = (int(x) for x in row["generation"].split("-"))
        assert AGE_BRACKETS[age]["generations"] == tuple(range(lo, hi + 1))
        for k in ("xp", "blood_potency_bonus", "advantage_dots_bonus", "flaw_dots_bonus", "humanity_change"):
            assert AGE_BRACKETS[age].get(k, 0) == row.get(k, 0), (age, k)
    costs = rules["experience"]["costs"]

    def num(v):
        return v if isinstance(v, int) else int(re.search(r"\d+", v).group())

    for key, src in (("attribute", "attribute"), ("skill", "skill"), ("specialty", "specialty"),
                     ("clan_discipline", "clan_discipline"), ("other_discipline", "other_discipline"),
                     ("caitiff_discipline", "caitiff_discipline"), ("ritual", "blood_sorcery_ritual")):
        assert XP_COSTS[key] == num(costs[src]), key
    rows = {r["generation"]: r for r in rules["generation_blood_potency"]}
    assert rows["10-11"]["starting_bp"] == 2 and rows["12-13"]["starting_bp"] == 1
    assert rows["14-16"]["thin_blood"] is True


# ---------- params the client's messages need ----------

def test_params_name_the_numbers():
    c = case("advantages: 8 dots of your own")
    assert validate_creation(c["payload"], CATALOG, None) == [{"code": "adv_over", "params": {"max": 7, "have": 8}}]
    c = case("server: an XP dot priced too low")
    assert validate_creation(c["payload"], CATALOG, None) == [
        {"code": "xp_price", "params": {"index": 0, "trait": "Presence", "cost": 5, "want": 10}}
    ]
    c = case("disciplines: Dominate is not a Brujah Discipline")
    assert validate_creation(c["payload"], CATALOG, None) == [
        {"code": "disc_clan", "params": {"name": "Dominate", "clan": "Brujah"}}
    ]


def test_ancilla_budget_is_9_and_4():
    c = case("valid: Ventrue ancilla Tithe Collector spends all 35 XP")
    meta = c["payload"]["wod_meta"]
    meta["advantages"].append({"name": "Allies", "dots": 1, "kind": "background"})
    assert validate_creation(c["payload"], CATALOG, None) == [{"code": "adv_over", "params": {"max": 9, "have": 10}}]
    meta["advantages"].pop()
    meta["flaws"] = [f for f in meta["flaws"] if f["kind"] == "predator"] + [{"name": "Enemy", "dots": 3, "kind": "flaw"}]
    assert validate_creation(c["payload"], CATALOG, None) == [{"code": "flaw_under", "params": {"min": 4, "have": 3}}]


def test_caitiff_xp_uses_the_x6_multiplier():
    c = case("valid: Caitiff Osiris, Performance 0 becomes 1, split grants, Caitiff XP")
    log = c["payload"]["wod_meta"]["experience"]["log"]
    entry = next(e for e in log if e["kind"] == "discipline")
    assert entry["cost"] == 12  # Animalism 1 -> 2, new x 6
    entry["cost"] = 10  # priced as a clan Discipline
    assert codes(validate_creation(c["payload"], CATALOG, None)) == ["xp_price"]


def test_case_and_space_insensitive_names():
    c = case("valid: Brujah Alleycat neonate with 13 XP spent")
    meta = c["payload"]["wod_meta"]
    meta["clan"] = " brujah "
    meta["predator_type"] = "ALLEYCAT"
    meta["disciplines"][0]["powers"] = ["lethal  body", "PROWESS"]
    assert validate_creation(c["payload"], CATALOG, None) == []


def test_power_objects_are_read_too():
    c = case("valid: Brujah Alleycat neonate with 13 XP spent")
    d = c["payload"]["wod_meta"]["disciplines"][0]
    d["powers"] = [{"id": "power:potence:lethal-body", "name": "Lethal Body", "level": 1}, {"id": "power:potence:prowess"}]
    assert validate_creation(c["payload"], CATALOG, None) == []


def test_settings_problems_carry_the_names():
    c = case("valid: Brujah Alleycat neonate with 13 XP spent")
    got = validate_creation(c["payload"], CATALOG, {"allowed_clans": ["Tremere"], "allowed_predators": ["Siren"]})
    assert got == [
        {"code": "clan_not_allowed", "params": {"clan": "Brujah"}},
        {"code": "predator_not_allowed", "params": {"predator": "Alleycat"}},
    ]
    # settings as stored (JSON text) work too
    assert validate_creation(c["payload"], CATALOG, '{"allowed_clans": ["brujah"]}') == []


def test_missing_and_garbage_input_never_raises():
    for payload in (None, {}, [], "x", {"wod_meta": "x", "skills": 3, "attributes": []},
                    {"wod_meta": {"disciplines": "x", "experience": {"log": "x"}, "advantages": [1, None]}}):
        got = validate_creation(payload, CATALOG, None)
        assert {"clan_missing", "age_missing", "attr_range"} <= set(codes(got))
    assert codes(validate_creation({}, None, None))  # no catalog: still a list of problems


def test_catalog_without_powers_leaves_powers_free_text():
    c = case("powers: not a Potence power")
    cat = copy.deepcopy(CATALOG)
    for d in cat["disciplines"]:
        d["powers"] = []
    assert validate_creation(c["payload"], cat, None) == []


# ---------- Advantages and loresheets against their catalogs (when installed) ----------

ADV_CATALOG = {
    "advantages": [
        {"id": "background:resources", "name": "Resources", "kind": "background", "dots": {"min": 1, "max": 5}},
        {"id": "background:haven", "name": "Haven", "kind": "background", "dots": {"min": 1, "max": 3}},
        {"id": "background:allies", "name": "Allies", "kind": "background", "dots": {"min": 1, "max": 5}},
        {"id": "flaw:enemy", "name": "Enemy", "kind": "flaw", "dots": {"min": 1, "max": None}},
        {"id": "merit:iron-gullet", "name": "Iron Gullet", "kind": "merit", "dots": {"min": 3, "max": 3},
         "cannot_buy_for": [{"clan": "clan:ventrue", "when": "always", "book": "v5-corebook", "page": 1}]},
        {"id": "merit:caitiff-mark-of-caine", "name": "Mark of Caine", "kind": "merit", "dots": {"min": 2, "max": 2},
         "caitiff": True},
        {"id": "merit:linguistics", "name": "Linguistics", "kind": "merit", "dots": {"allowed": [1, 2]}},
        {"id": "merit:thin-blood-day-drinker", "name": "Day Drinker", "kind": "merit", "dots": None, "thin_blood": True},
    ],
    "loresheets": [
        {"id": "loresheet:theo-bell", "name": "Theo Bell", "clans_only": None, "thin_blood_only": False},
        {"id": "loresheet:the-trinity", "name": "The Trinity", "clans_only": ["clan:hecata"], "thin_blood_only": False},
    ],
}


def _with_adv_catalog():
    cat = copy.deepcopy(CATALOG)
    cat.update(copy.deepcopy(ADV_CATALOG))
    return cat


def test_forge_sheets_still_pass_with_the_advantages_catalog():
    cat = _with_adv_catalog()
    for c in DOC["cases"]:
        if not c["expect"]:
            assert validate_creation(c["payload"], cat, c["settings"]) == [], c["name"]


def test_catalog_dot_ranges_and_restrictions():
    cat = _with_adv_catalog()
    c = case("valid: Brujah with no XP spent")
    meta = c["payload"]["wod_meta"]
    own = [{"name": "Haven", "dots": 4, "kind": "background"},
           {"name": "Mark of Caine", "dots": 2, "kind": "merit"},
           {"name": "Linguistics", "dots": 1, "kind": "merit"}]
    meta["advantages"] = own + [a for a in meta["advantages"] if a["kind"] == "predator"]
    assert validate_creation(c["payload"], cat, None) == [
        {"code": "adv_dots_range", "params": {"name": "Haven", "dots": 4, "min": 1, "max": 3}},
        {"code": "adv_restricted", "params": {"name": "Mark of Caine", "clan": "Brujah"}},
    ]
    meta["advantages"] = [{"name": "Haven", "dots": 1, "kind": "background"},
                          {"name": "Linguistics (Greek)", "dots": 3, "kind": "merit"}]
    assert validate_creation(c["payload"], cat, None) == [
        {"code": "predator_grant", "params": {"predator": "Alleycat"}},  # its Contacts row is gone too
        {"code": "adv_dots_range", "params": {"name": "Linguistics (Greek)", "dots": 3, "min": 1, "max": 2}},
    ]


def test_cannot_buy_for_and_thin_blood_merits():
    cat = _with_adv_catalog()
    c = case("valid: Brujah with no XP spent")
    meta = c["payload"]["wod_meta"]
    meta["advantages"] = [{"name": "Day Drinker", "dots": 1, "kind": "merit"}] + [
        a for a in meta["advantages"] if a["kind"] == "predator"
    ]
    assert codes(validate_creation(c["payload"], cat, None)) == ["adv_restricted"]
    c = case("predator: Ventrue cannot be a Bagger")
    c["payload"]["wod_meta"]["advantages"].insert(0, {"name": "Iron Gullet", "dots": 3, "kind": "merit"})
    got = codes(validate_creation(c["payload"], cat, None))
    assert "adv_restricted" in got and "predator_forbidden" in got


def test_loresheets_count_and_follow_their_restriction():
    cat = _with_adv_catalog()
    c = case("valid: Brujah with no XP spent")
    meta = c["payload"]["wod_meta"]
    meta["advantages"] = [{"name": "Theo Bell", "dots": 2, "kind": "merit"},
                          {"name": "The Trinity", "dots": 1, "kind": "loresheet"},
                          {"name": "Resources", "dots": 5, "kind": "background"}] + [
        a for a in meta["advantages"] if a["kind"] == "predator"]
    assert validate_creation(c["payload"], cat, None) == [
        {"code": "adv_over", "params": {"max": 7, "have": 8}},
        {"code": "loresheet_restricted", "params": {"name": "The Trinity", "clan": "Brujah"}},
    ]


def test_unknown_ids_only_when_their_catalog_is_installed():
    c = case("valid: Brujah with no XP spent")
    meta = c["payload"]["wod_meta"]
    meta["advantages"][0]["id"] = "background:no-such-thing"
    assert validate_creation(c["payload"], CATALOG, None) == []  # no advantages.json: not checked
    assert codes(validate_creation(c["payload"], _with_adv_catalog(), None)) == ["adv_unknown"]
    meta["advantages"][0]["id"] = "background:resources"
    assert validate_creation(c["payload"], _with_adv_catalog(), None) == []


def test_predator_grant_ids_resolve_through_the_advantages_catalog():
    cat = _with_adv_catalog()
    c = case("valid: Tremere Bagger, starting ritual, XP ritual and XP Dominate")
    row = next(a for a in c["payload"]["wod_meta"]["advantages"] if a["kind"] == "predator")
    assert row["name"] == "Iron Gullet"
    row["name"] = "Iron Gullet (Feeding Merit)"  # the v5.json fallback label
    assert validate_creation(c["payload"], cat, None) == []
    row["dots"] = 2
    assert codes(validate_creation(c["payload"], cat, None)) == ["predator_grant"]
