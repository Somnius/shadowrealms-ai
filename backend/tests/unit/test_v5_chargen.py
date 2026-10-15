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
# The snapshot without advantages.json / loresheets.json (it has them once the catalog does).
CORE = {k: v for k, v in CATALOG.items() if k not in ("advantages", "loresheets")}


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
        {"id": "background:allies", "name": "Allies", "kind": "background", "dots": {"min": 1, "max": 6}},
        {"id": "background:mask", "name": "Mask", "kind": "background", "dots": {"allowed": [1, 2]}},
        {"id": "background:status", "name": "Status", "kind": "background", "group": "Status", "dots": {"min": 1, "max": 5}},
        {"id": "flaw:folkloric-bane", "name": "Folkloric Bane", "kind": "flaw", "group": "Mythic", "dots": {"min": 1, "max": 1}},
        {"id": "flaw:stake-bait", "name": "Stake Bait", "kind": "flaw", "group": "Mythic", "dots": {"min": 2, "max": 2}},
        {"id": "flaw:shunned", "name": "Shunned", "kind": "flaw", "group": "Status", "dots": {"min": 2, "max": 2}},
        {"id": "flaw:suspect", "name": "Suspect", "kind": "flaw", "group": "Status", "dots": {"min": 1, "max": 1}},
        {"id": "flaw:enemy", "name": "Enemy", "kind": "flaw", "dots": {"min": 1, "max": None}},
        {"id": "merit:iron-gullet", "name": "Iron Gullet", "kind": "merit", "dots": {"min": 3, "max": 3},
         "cannot_buy_for": [{"clan": "clan:ventrue", "when": "always", "book": "v5-corebook", "page": 1}]},
        {"id": "merit:caitiff-mark-of-caine", "name": "Mark of Caine", "kind": "merit", "dots": {"min": 2, "max": 2},
         "caitiff": True},
        {"id": "merit:linguistics", "name": "Linguistics", "kind": "merit", "dots": {"allowed": [1, 2]}},
        {"id": "merit:thin-blood-day-drinker", "name": "Day Drinker", "kind": "merit", "dots": None, "thin_blood": True},
    ],
    "loresheets": [
        {"id": "loresheet:theo-bell", "name": "Theo Bell", "clans_only": None, "thin_blood_only": False,
         "levels": [{"dots": n, "name": f"Level {n}"} for n in range(1, 6)]},
        {"id": "loresheet:the-trinity", "name": "The Trinity", "clans_only": ["clan:hecata"], "thin_blood_only": False},
    ],
}


def _with_adv_catalog():
    """The snapshot with the test entries above in front of any real ones (same id: the test's)."""
    cat = copy.deepcopy(CATALOG)
    for kind, mine in ADV_CATALOG.items():
        ids = {e["id"] for e in mine}
        cat[kind] = copy.deepcopy(mine) + [e for e in cat.get(kind, []) if e.get("id") not in ids]
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
    meta["advantages"] = [{"name": "Theo Bell", "dots": 2, "kind": "merit"},  # an older free-text row
                          {"name": "The Trinity", "dots": 1, "kind": "loresheet", "levels": [1]},
                          {"name": "Resources", "dots": 5, "kind": "background"}] + [
        a for a in meta["advantages"] if a["kind"] == "predator"]
    assert validate_creation(c["payload"], cat, None) == [
        {"code": "adv_over", "params": {"max": 7, "have": 8}},
        {"code": "loresheet_restricted", "params": {"name": "The Trinity", "clan": "Brujah"}},
    ]


def test_unknown_ids_only_when_their_catalog_is_installed():
    c = case("valid: Brujah with no XP spent")
    meta = c["payload"]["wod_meta"]
    row = meta["advantages"][0]
    row.update(id="background:no-such-thing", name="Mystery Background")
    assert validate_creation(c["payload"], CORE, None) == []  # no advantages.json: not checked
    assert codes(validate_creation(c["payload"], _with_adv_catalog(), None)) == ["adv_unknown"]
    # an unknown id falls back to the name, as the forge does (a renamed entry)
    row["name"] = "Resources"
    assert validate_creation(c["payload"], _with_adv_catalog(), None) == []
    row["id"] = "background:resources"
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


def test_advantages_json_on_disk_reaches_the_check(tmp_path, monkeypatch):
    """advantages.json / loresheets.json are read by the loader when they exist (Part C)."""
    from services import v5_catalog

    for name, entries in CORE.items():
        (tmp_path / f"{name}.json").write_text(json.dumps({"catalog": name, "version": 1, "entries": entries}))
    monkeypatch.setenv("V5_CATALOG_DIR", str(tmp_path))
    v5_catalog._cache.update(key=None, data=None, etag=None)
    try:
        c = case("valid: Brujah with no XP spent")
        assert c["payload"]["wod_meta"]["advantages"][1] == {"name": "Haven", "dots": 2, "kind": "background"}
        loaded = v5_catalog.load_catalog()
        assert loaded["advantages"] == [] and loaded["loresheets"] == []
        assert validate_creation(c["payload"], loaded, None) == []
        (tmp_path / "advantages.json").write_text(json.dumps({"catalog": "advantages", "version": 1, "entries": [
            {"id": "background:haven", "name": "Haven", "kind": "background", "dots": {"min": 3, "max": 3}},
        ]}))
        loaded = v5_catalog.load_catalog()
        assert [a["id"] for a in loaded["advantages"]] == ["background:haven"]
        assert codes(validate_creation(c["payload"], loaded, None)) == ["adv_dots_range"]
    finally:
        v5_catalog._cache.update(key=None, data=None, etag=None)


# ---------- review fixes ----------

TZIMISCE = "valid: Tzimisce Messenger's Command with Compel from Dominate (prerequisite in another Discipline)"


def test_prerequisites_can_sit_in_another_discipline():
    c = case(TZIMISCE)
    meta = c["payload"]["wod_meta"]
    animalism = next(d for d in meta["disciplines"] if d["name"] == "Animalism")
    assert "Messenger's Command" in animalism["powers"]
    assert validate_creation(c["payload"], CATALOG, None) == []
    next(d for d in meta["disciplines"] if d["name"] == "Dominate")["powers"] = ["Cloud Memory"]
    assert validate_creation(c["payload"], CATALOG, None) == [
        {"code": "power_prereq", "params": {"power": "Messenger's Command", "needs": "Compel or Mesmerize"}}
    ]
    # duplicates stay per Discipline: the same name in two Disciplines is not "taken twice"
    c = case(TZIMISCE)
    next(d for d in c["payload"]["wod_meta"]["disciplines"] if d["name"] == "Animalism")["powers"][0] = "Bond Famulus"
    assert validate_creation(c["payload"], CATALOG, None) == []


def _brujah_with(own, cat=None, flaws=None):
    c = case("valid: Brujah with no XP spent")
    meta = c["payload"]["wod_meta"]
    meta["advantages"] = own + [a for a in meta["advantages"] if a["kind"] == "predator"]
    if flaws is not None:
        meta["flaws"] = flaws + [f for f in meta["flaws"] if f["kind"] == "predator"]
    return validate_creation(c["payload"], cat or _with_adv_catalog(), None)


def test_known_rows_take_the_catalog_range_unknown_rows_1_to_5():
    assert _brujah_with([{"name": "Allies (dock workers)", "dots": 6, "kind": "background"}]) == []
    assert _brujah_with([{"name": "Allies", "dots": 7, "kind": "background"}]) == [
        {"code": "adv_dots_range", "params": {"name": "Allies", "dots": 7, "min": 1, "max": 6}},
    ]
    assert _brujah_with([{"name": "Mystery Merit", "dots": 6, "kind": "merit"}]) == [
        {"code": "adv_dots_range", "params": {"name": "Mystery Merit", "dots": 6, "min": 1, "max": 5}},
    ]
    assert _brujah_with([{"name": "Mask", "dots": 2, "kind": "background"}]) == []
    assert _brujah_with([{"name": "Mask", "dots": 3, "kind": "background"}]) == [
        {"code": "adv_dots_range", "params": {"name": "Mask", "dots": 3, "min": 1, "max": 2}},
    ]
    # without advantages.json every row is 1-5
    assert codes(_brujah_with([{"name": "Allies", "dots": 6, "kind": "background"}], cat=CORE)) == ["adv_dots_range"]


def test_a_group_option_takes_any_entry_of_its_group():
    def osiris(mythic_name, dots=1, cat=None):
        c = case("valid: Caitiff Osiris, Performance 0 becomes 1, split grants, Caitiff XP")
        row = next(f for f in c["payload"]["wod_meta"]["flaws"] if f["kind"] == "predator" and "mythic" in f["name"].lower())
        row.update(name=mythic_name, dots=dots)
        return codes(validate_creation(c["payload"], cat or _with_adv_catalog(), None))

    assert osiris("Mythic (any Mythic Flaw)") == []  # the forge's label
    assert osiris("Folkloric Bane") == []  # a Mythic Flaw from the catalog
    assert osiris("Mythic (Folkloric Bane)") == []
    assert osiris("Shunned") == ["predator_grant"]  # a Status Flaw, not a Mythic one
    assert osiris("Folkloric Bane", cat=CORE) == ["predator_grant"]  # no advantages.json: no group to look in


def test_predator_rows_with_an_id_are_that_option_and_name_it():
    c = case("valid: Brujah Alleycat neonate with 13 XP spent")
    row = next(a for a in c["payload"]["wod_meta"]["advantages"] if a["kind"] == "predator")
    row.update(id="background:contacts", name="Contacts (criminal)", note="criminal")
    assert validate_creation(c["payload"], CATALOG, None) == []
    row["name"] = "Resources"  # the id says Contacts: a row can't show another name
    assert codes(validate_creation(c["payload"], CATALOG, None)) == ["predator_grant"]
    row.update(id="background:resources", name="Contacts (criminal)")  # nor another option's id
    assert codes(validate_creation(c["payload"], CATALOG, None)) == ["predator_grant"]


def test_a_group_row_may_carry_the_id_of_the_entry_picked():
    c = case("valid: Caitiff Osiris, Performance 0 becomes 1, split grants, Caitiff XP")
    row = next(f for f in c["payload"]["wod_meta"]["flaws"] if f["kind"] == "predator" and "mythic" in f["name"].lower())
    row.update(id="flaw:mythic")
    assert validate_creation(c["payload"], _with_adv_catalog(), None) == []
    row.update(id="flaw:folkloric-bane", name="Folkloric Bane")
    assert validate_creation(c["payload"], _with_adv_catalog(), None) == []
    row.update(id="flaw:shunned", name="Shunned")
    assert codes(validate_creation(c["payload"], _with_adv_catalog(), None)) == ["predator_grant"]


def test_malformed_catalog_entries_never_raise():
    bad = {
        "clans": [
            {"id": ["x"], "name": 5, "disciplines": "abc", "aliases": {"a": 1}, "creation": "x"},
            {"id": "clan:brujah", "name": "Brujah", "disciplines": ["discipline:potence", None, 3, ["x"]]},
        ],
        "disciplines": [
            {"id": {}, "name": None, "powers": "x"},
            {"id": "discipline:potence", "name": "Potence", "aliases": "Strength", "powers": [
                {"id": ["p"], "name": "Lethal Body", "aliases": "x", "level": "2",
                 "amalgam": {"discipline": ["d"], "level": "x"},
                 "prerequisite": {"any_of": [None, 3, {"power_id": []}]}},
                {"id": "power:potence:prowess", "name": "Prowess", "prerequisite": {"all_of": "x"}},
            ]},
        ],
        "predator_types": [
            {"id": 7, "name": "Alleycat", "specialty_choice": "x", "aliases": None,
             "discipline_choice": [{"discipline": [], "clans_only": "clan:brujah"}, "x"],
             "advantages": [{"pick": 3, "dots_total": True, "options": [{"id": [], "dots": True, "group": True}]}],
             "flaws": "x", "forbidden_clans": {}, "max_blood_potency": True, "humanity": "x"},
        ],
        "rituals": [{"name": ["x"]}, None, {"name": "Blood Walk", "aliases": 3, "level": None}],
        "ceremonies": "x",
        "advantages": [
            {"id": ["a"], "name": "Allies", "dots": {"allowed": ["x", True]}, "aliases": "Ally",
             "cannot_buy_for": "clan:brujah", "clans_only": 5, "group": None},
            {"id": "background:haven", "name": "Haven", "kind": "background", "dots": {"min": True, "max": "x"}},
        ],
        "loresheets": [{"id": None, "name": "Theo Bell", "clans_only": "x", "levels": "x", "disciplines_only": 3}],
    }
    # book facts of every shape too (allowed books on)
    bad["clans"][1].update(book=3, also_in="v5-companion")
    bad["predator_types"][0].update(book=["v5-corebook"], also_in=[None, 3, {"book": []}])
    bad["advantages"][1].update(book="v5-players-guide", also_in={"book": "v5-corebook"})
    books = {"allowed_books": ["v5-corebook"]}
    for name in [c["name"] for c in DOC["cases"]]:
        validate_creation(case(name)["payload"], bad, None)  # no exception
        validate_creation(case(name)["payload"], bad, books)
    for junk in (None, [], "x", 3, {"clans": "x"}, {"advantages": [None, "x", 3]}):
        validate_creation(case("valid: Brujah with no XP spent")["payload"], junk, None)
        validate_creation(case("valid: Brujah with no XP spent")["payload"], junk, books)


def _lore(dots, levels, **kw):
    return {"name": "Theo Bell", "dots": dots, "kind": "loresheet", "levels": levels, **kw}


def test_loresheet_rows_cost_their_levels():
    lore = _lore
    assert _brujah_with([lore(6, [2, 4])]) == []  # 2 + 4: more than 5 dots, still one row
    assert _brujah_with([lore(6, [2, 4], id="loresheet:theo-bell"), {"name": "Haven", "dots": 1, "kind": "background"}]) == []
    assert _brujah_with([lore(8, [3, 5])]) == [{"code": "adv_over", "params": {"max": 7, "have": 8}}]
    for dots, levels in ((5, [2, 4]), (4, [2, 2]), (6, [6]), (0, []), (3, None), (3, ["3"])):
        assert codes(_brujah_with([lore(dots, levels)])) == ["loresheet_levels"], (dots, levels)
    # no catalog: still levels 1-5 and the sum
    assert _brujah_with([lore(6, [2, 4])], cat=CORE) == []
    assert codes(_brujah_with([lore(7, [2, 4])], cat=CORE)) == ["loresheet_levels"]


def test_custom_rows_need_the_storyteller():
    assert _brujah_with([{"name": "Night Doctor", "dots": 2, "kind": "merit", "custom": True}]) == [
        {"code": "custom_row", "params": {"name": "Night Doctor"}},
    ]
    got = _brujah_with([], flaws=[{"name": "Cursed Name", "dots": 6, "kind": "flaw", "custom": True}])
    assert codes(got) == ["adv_dots_range", "custom_row"]
    # without the advantages catalog too
    assert codes(_brujah_with([{"name": "Night Doctor", "dots": 2, "kind": "merit", "custom": True}], cat=CORE)) == ["custom_row"]


def test_caitiff_suspect_counts_and_status_is_refused():
    c = case("valid: Caitiff Osiris, Performance 0 becomes 1, split grants, Caitiff XP")
    meta = c["payload"]["wod_meta"]
    # the forge adds the clan's Suspect (source 'clan') and counts it as the player's own Flaw
    meta["flaws"] = [{"id": "flaw:suspect", "name": "Suspect", "dots": 1, "kind": "flaw", "source": "clan"},
                     {"name": "Addiction", "dots": 1, "kind": "flaw"}] + [f for f in meta["flaws"] if f["kind"] == "predator"]
    assert validate_creation(c["payload"], CORE, None) == []
    assert validate_creation(c["payload"], _with_adv_catalog(), None) == []
    meta["advantages"][0] = {"name": "Status", "dots": 1, "kind": "background"}
    assert codes(validate_creation(c["payload"], CORE, None)) == ["caitiff_status"]
    assert codes(validate_creation(c["payload"], _with_adv_catalog(), None)) == ["caitiff_status"]
    meta["advantages"][0]["id"] = "background:status"
    assert codes(validate_creation(c["payload"], _with_adv_catalog(), None)) == ["caitiff_status"]
    # other clans may start with Status
    assert _brujah_with([{"name": "Status", "dots": 2, "kind": "background"}]) == []


# ---------- the chronicle's allowed books (creation_settings.allowed_books) ----------

def test_book_problems_name_the_entry_its_book_and_kind():
    c = case("books: a Players Guide clan and Flaw with only the corebook (no Companion)")
    got = validate_creation(c["payload"], CATALOG, c["settings"])
    assert got == [
        {"code": "book_not_allowed", "params": {"name": "Risk-Taker", "book": "v5-players-guide", "kind": "advantage"}},
        {"code": "book_not_allowed", "params": {"name": "Tzimisce", "book": "v5-players-guide", "kind": "clan"}},
    ]
    # the Companion reprints both (also_in): the sheet passes with it, as with the Players Guide
    for books in (["v5-corebook", "v5-companion"], ["v5-corebook", "v5-players-guide"]):
        assert validate_creation(c["payload"], CATALOG, {"allowed_books": books}) == []
    # null allows every book; settings as stored (JSON text) work too
    assert validate_creation(c["payload"], CATALOG, None) == []
    assert codes(validate_creation(c["payload"], CATALOG, '{"allowed_books": ["v5-corebook"]}')) == ["book_not_allowed"]


def _moved(cat, ids, book="v5-test-book"):
    """A copy of the catalog with these Advantages printed only in another book."""
    cat = copy.deepcopy(cat)
    for a in cat["advantages"]:
        if a["id"] in ids:
            a.update(book=book, also_in=[])
    return cat


def test_what_the_clan_or_predator_type_gives_comes_with_it():
    # Grim Reaper gives Prey Exclusion: from a book the chronicle leaves out it still comes with
    # the type, while a Flaw the player took from that book (Enemy) doesn't.
    cat = _moved(CATALOG, {"flaw:prey-exclusion", "flaw:enemies"})
    c = case("valid: Hecata Grim Reaper with Allies and the Summon Spirit ceremony")
    got = validate_creation(c["payload"], cat, {"allowed_books": ["v5-players-guide"]})
    assert got == [{"code": "book_not_allowed", "params": {"name": "Enemy", "book": "v5-test-book", "kind": "advantage"}}]
    # The clan's own Flaws (source 'clan': Caitiff Suspect) come with the clan; Flaws the player took don't.
    cat = _moved(CATALOG, {"flaw:suspect"})
    c = case("valid: Caitiff Osiris, Performance 0 becomes 1, split grants, Caitiff XP")
    suspect = next(f for f in c["payload"]["wod_meta"]["flaws"] if f["name"] == "Suspect")
    assert codes(validate_creation(c["payload"], cat, {"allowed_books": ["v5-corebook"]})) == ["book_not_allowed"]
    suspect["source"] = "clan"
    assert validate_creation(c["payload"], cat, {"allowed_books": ["v5-corebook"]}) == []


def test_the_corebook_is_always_allowed():
    # a Players Guide-only list still has the corebook: the Hecata's corebook picks pass
    c = case("valid: Hecata Grim Reaper with Allies and the Summon Spirit ceremony")
    assert validate_creation(c["payload"], CATALOG, {"allowed_books": ["v5-players-guide"]}) == []


def test_disciplines_the_clan_or_predator_type_doesnt_give():
    c = case("books: a Caitiff picks Oblivion (Players Guide) with only the corebook")
    assert validate_creation(c["payload"], CATALOG, c["settings"]) == [
        {"code": "book_not_allowed", "params": {"name": "Oblivion", "book": "v5-players-guide", "kind": "discipline"}},
    ]
    # Oblivion as an XP dot of a Brujah: not a clan Discipline, not Alleycat's dot
    c = case("valid: Brujah Alleycat neonate with 13 XP spent")
    meta = c["payload"]["wod_meta"]
    meta["disciplines"].append({"name": "Oblivion", "level": 1, "powers": []})
    meta["experience"]["log"].append({"kind": "discipline", "trait": "Oblivion", "from": 0, "to": 1, "cost": 7})
    got = validate_creation(c["payload"], CATALOG, {"allowed_books": ["v5-corebook"]})
    assert {"code": "book_not_allowed", "params": {"name": "Oblivion", "book": "v5-players-guide", "kind": "discipline"}} in got
    # Disciplines printed only in a book the chronicle leaves out
    cat = copy.deepcopy(CATALOG)
    for d in cat["disciplines"]:
        if d["name"] in ("Oblivion", "Auspex", "Presence", "Animalism"):
            d.update(book="v5-test-book")
    corebook = {"allowed_books": ["v5-corebook"]}
    # the clan's own (Hecata: Oblivion, Auspex, Fortitude) come with the clan
    hecata = case("valid: Hecata Grim Reaper with Allies and the Summon Spirit ceremony")
    kinds = {p["params"]["kind"] for p in validate_creation(hecata["payload"], cat, corebook)}
    assert "discipline" not in kinds
    # a Caitiff has no clan list: Presence is Osiris's dot (comes with it), Animalism a pick (doesn't)
    caitiff = case("valid: Caitiff Osiris, Performance 0 becomes 1, split grants, Caitiff XP")
    got = [p for p in validate_creation(caitiff["payload"], cat, corebook) if p["params"].get("kind") == "discipline"]
    assert got == [{"code": "book_not_allowed", "params": {"name": "Animalism", "book": "v5-test-book", "kind": "discipline"}}]


def test_loresheets_and_rows_without_a_book():
    cat = copy.deepcopy(CATALOG)
    cat["loresheets"] = [{
        "id": "loresheet:test-sheet", "name": "Test Sheet", "book": "v5-players-guide",
        "also_in": [{"book": "v5-companion", "page": 1}], "clans_only": None, "thin_blood_only": False,
        "levels": [{"dots": n, "name": f"Level {n}"} for n in range(1, 6)],
    }]
    c = case("valid: Brujah with no XP spent")
    meta = c["payload"]["wod_meta"]
    meta["advantages"] = [
        {"name": "Resources", "dots": 3, "kind": "background"},
        {"name": "Haven", "dots": 2, "kind": "background"},
        {"name": "Allies (dock workers)", "dots": 1, "kind": "background"},
        {"id": "loresheet:test-sheet", "name": "Test Sheet", "dots": 1, "kind": "loresheet", "levels": [1]},
    ] + [a for a in meta["advantages"] if a["kind"] == "predator"]
    assert validate_creation(c["payload"], cat, {"allowed_books": ["v5-corebook"]}) == [
        {"code": "book_not_allowed", "params": {"name": "Test Sheet", "book": "v5-players-guide", "kind": "loresheet"}},
    ]
    assert validate_creation(c["payload"], cat, {"allowed_books": ["v5-corebook", "v5-companion"]}) == []
    # a catalog without books (or a custom row) has nothing to check
    bare = copy.deepcopy(cat)
    for kind in ("clans", "predator_types", "advantages", "loresheets"):
        for e in bare[kind]:
            e.pop("book", None)
            e.pop("also_in", None)
    for d in bare["disciplines"]:
        for pw in d["powers"]:
            pw.pop("book", None)
    assert validate_creation(c["payload"], bare, {"allowed_books": ["some-other-book"]}) == []
