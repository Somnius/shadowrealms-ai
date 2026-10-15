"""The committed V5 catalog (docs/rules/v5/catalog): schema, ids, references, books vs manifest.

Runs without the books or the network. The checker lives in scripts/v5_catalog (repo root);
inside the backend container only docs/ is mounted, so these tests skip there and run in CI.
"""

import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _catalog_dir() -> Path | None:
    for cand in (os.environ.get("V5_RULES_DIR"), "/app/project_docs/rules/v5/catalog",
                 REPO / "docs" / "rules" / "v5" / "catalog"):
        if cand and (Path(cand) / "clans.json").exists():
            return Path(cand)
    return None


CATALOG = _catalog_dir()
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
try:
    from scripts.v5_catalog import checks
except ImportError:  # backend container: scripts/ is not mounted
    checks = None

pytestmark = pytest.mark.skipif(CATALOG is None or checks is None,
                                reason="catalog or scripts/v5_catalog not on disk")


@pytest.fixture(scope="module")
def data():
    return checks.load_catalog(CATALOG)


def _entries(data, name):
    return data[name]["entries"]


def test_schema(data):
    assert checks.schema_problems(CATALOG, data) == []


def test_ids_unique_and_prefixed(data):
    assert checks.id_problems(data) == []


def test_references_resolve(data):
    assert checks.reference_problems(data) == []


def test_books_match_manifest(data):
    yaml = pytest.importorskip("yaml")
    manifest_path = REPO / "books" / "manifest.yaml"
    if not manifest_path.exists():
        pytest.skip("books/manifest.yaml not on disk")
    manifest = {b["book_id"]: b for b in yaml.safe_load(manifest_path.read_text(encoding="utf-8"))["books"]}
    for b in _entries(data, "books"):
        assert b["book_id"] in manifest, b["book_id"]
        m = manifest[b["book_id"]]
        assert b["title"] == m["title"], b["book_id"]
        assert b["precedence"] == m["precedence"], b["book_id"]


def test_counts(data):
    assert len(_entries(data, "clans")) == 16
    assert len(_entries(data, "disciplines")) == 12
    assert len(_entries(data, "predator_types")) == 18
    assert len(_entries(data, "advantages")) == 170
    assert len(_entries(data, "loresheets")) == 32
    lore_books = [e["book"] for e in _entries(data, "loresheets")]
    assert (lore_books.count("v5-corebook"), lore_books.count("v5-players-guide")) == (25, 7)
    names = {d["name"] for d in _entries(data, "disciplines")}
    assert {"Oblivion", "Thin-Blood Alchemy"} <= names
    for name in ("rituals", "ceremonies", "formulae"):
        assert _entries(data, name), name


def test_known_facts(data):
    clans = {c["name"]: c for c in _entries(data, "clans")}
    assert clans["Ventrue"]["disciplines"] == ["discipline:dominate", "discipline:fortitude", "discipline:presence"]
    assert clans["Hecata"]["disciplines"] == ["discipline:auspex", "discipline:fortitude", "discipline:oblivion"]
    assert clans["Caitiff"]["disciplines"] == [] and clans["Thin-blood"]["disciplines"] == []
    auspex = next(d for d in _entries(data, "disciplines") if d["name"] == "Auspex")
    level1 = {p["name"] for p in auspex["powers"] if p["level"] == 1}
    assert {"Heightened Senses", "Sense the Unseen"} <= level1
    preds = {p["name"]: p for p in _entries(data, "predator_types")}
    montero = preds["Montero"]
    assert (montero["book"], montero["page"], montero["humanity"]) == ("v5-players-guide", 108, -1)
    assert montero["advantages"] == [{"pick": "all", "options": [{"id": "background:retainers", "dots": 2}]}]
    assert "clan:ventrue" in preds["Bagger"]["forbidden_clans"]
    assert clans["Caitiff"]["bane"] is None and clans["Thin-blood"]["bane"] is None
    assert clans["Caitiff"]["creation"]["flaws"] == [{"id": "flaw:suspect", "dots": 1}]


def test_players_guide_powers_with_apostrophes(data):
    powers = {p["id"]: p for d in _entries(data, "disciplines") for p in d["powers"]}
    for pid, level in (("power:animalism:messengers-command", 3), ("power:fortitude:earths-perseverance", 2),
                       ("power:fortitude:gorgons-scales", 4), ("power:oblivion:oblivions-sight", 1)):
        assert powers[pid]["book"] == "v5-players-guide" and powers[pid]["level"] == level, pid
    assert powers["power:animalism:messengers-command"]["prerequisite"] == {"all_of": [
        {"power_id": "power:animalism:animal-messenger"},
        {"any_of": ["power:dominate:compel", "power:dominate:mesmerize"]}]}
    favor = powers["power:dominate:domitors-favor"]
    assert (favor["book"], favor["page"], favor["also_in"]) == (
        "v5-players-guide", 74, [{"book": "v5-companion", "page": 25}])
    assert powers["power:animalism:quell-the-beast"]["dice_pool"] == "Charisma + Animalism vs Stamina + Resolve"
    assert sum(len(d["powers"]) for d in _entries(data, "disciplines")) == 145


def test_power_levels_and_split_grants(data):
    for d in _entries(data, "disciplines"):
        ids = [p["id"] for p in d["powers"]]
        assert len(ids) == len(set(ids))
        for p in d["powers"]:
            assert 1 <= p["level"] <= 5
            if p["amalgam"]:
                assert p["amalgam"]["discipline"] != d["id"], p["id"]
    for p in _entries(data, "predator_types"):
        for grant in p["advantages"] + p["flaws"]:
            if grant["pick"] == "split":
                assert grant.get("dots_total"), p["id"]


def test_descriptions_complete(data):
    """Every entry, power, clan Bane and Compulsion has desc.en + desc.el (<= 240 chars) and
    descriptions/*.json has no orphan keys."""
    assert checks.description_problems(CATALOG, data) == []


def test_no_book_text_fields():
    """The committed files carry facts only: no snippets or cost/system text, short strings."""
    forbidden = {"snippet", "cost_text", "dice_pool_text", "prerequisite_text", "bullets", "pool_text"}
    for f in sorted(CATALOG.glob("*.json")):
        def walk(o, where):
            if isinstance(o, dict):
                assert not (forbidden & set(o)), f"{f.name}: {where} has {forbidden & set(o)}"
                for k, v in o.items():
                    walk(v, f"{where}.{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    walk(v, f"{where}[{i}]")
            elif isinstance(o, str):
                assert len(o) <= 400, f"{f.name}: {where} is {len(o)} chars"
        walk(json.loads(f.read_text(encoding="utf-8")), "$")


def test_every_predator_grant_resolves_to_an_advantage(data):
    adv = {e["id"]: e for e in _entries(data, "advantages")}
    groups = {(e["kind"], e["group"].lower()) for e in adv.values()}
    for p in _entries(data, "predator_types"):
        for kind, grants in (("advantage", p["advantages"]), ("flaw", p["flaws"])):
            for g in grants:
                for opt in g["options"]:
                    if opt.get("group"):
                        k, _, name = opt["id"].partition(":")
                        assert (k, name) in groups, (p["id"], opt["id"])
                        continue
                    assert opt["id"] in adv, (p["id"], opt["id"])
                    assert (adv[opt["id"]]["kind"] == "flaw") == (kind == "flaw"), (p["id"], opt["id"])


def test_advantages_facts(data):
    adv = {e["id"]: e for e in _entries(data, "advantages")}
    ids = list(adv)
    assert len(ids) == len(set(ids))
    assert adv["merit:iron-gullet"]["dots"] == {"min": 3, "max": 3}
    assert "Iron Gullet (Feeding Merit)" in adv["merit:iron-gullet"]["aliases"]
    assert adv["merit:iron-gullet"]["cannot_buy_for"][0]["clan"] == "clan:ventrue"
    assert adv["flaw:farmer"]["aliases"] == ["Vegan"]
    assert adv["background:allies"]["repeatable"] and adv["background:allies"]["dots"] == {"min": 1, "max": 6}
    assert [lv["name"] for lv in adv["background:resources"]["levels"]][-1] == "Ultra Rich"
    tb = [e for e in adv.values() if e["thin_blood"]]
    assert all(e["dots"] is None for e in tb)
    assert sum(e["kind"] == "merit" for e in tb) == 14 and sum(e["kind"] == "flaw" for e in tb) == 16
    assert adv["flaw:caitiff-clan-curse"]["caitiff"] and adv["flaw:thin-blood-clan-curse"]["thin_blood"]
    assert adv["merit:coterie-call-to-purpose"]["clans_only"] == ["clan:banu-haqim"]


def test_loresheet_levels(data):
    for e in _entries(data, "loresheets"):
        assert [lv["dots"] for lv in e["levels"]] == [1, 2, 3, 4, 5], e["id"]
        assert all(lv["name"] for lv in e["levels"]), e["id"]
    lore = {e["id"]: e for e in _entries(data, "loresheets")}
    assert lore["loresheet:descendant-of-hardestadt"]["clans_only"] == ["clan:ventrue"]
    assert lore["loresheet:theo-bell"]["levels"][4]["name"] == "Sect Neutrality"
