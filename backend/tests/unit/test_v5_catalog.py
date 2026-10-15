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
    for cand in (os.environ.get("V5_CATALOG_DIR"), "/app/project_docs/rules/v5/catalog",
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
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest = {b["book_id"]: b for b in raw["books"]}
    # a file left out of the RAG import (the Russian Anarch PDF) can still be cited by book_id
    for x in raw.get("excluded") or []:
        if x.get("book_id"):
            manifest.setdefault(x["book_id"], x)
    for b in _entries(data, "books"):
        assert b["book_id"] in manifest, b["book_id"]
        m = manifest[b["book_id"]]
        assert b["title"] == m["title"], b["book_id"]
        assert b["precedence"] == m["precedence"], b["book_id"]


def test_counts(data):
    assert len(_entries(data, "clans")) == 16
    assert len(_entries(data, "disciplines")) == 12
    assert len(_entries(data, "predator_types")) == 18
    assert len(_entries(data, "advantages")) == 279
    assert len(_entries(data, "loresheets")) == 157
    assert [len(_entries(data, n)) for n in ("rituals", "ceremonies", "formulae")] == [109, 29, 48]
    lore_books = [e["book"] for e in _entries(data, "loresheets")]
    assert (lore_books.count("v5-corebook"), lore_books.count("v5-players-guide")) == (25, 7)
    assert {b: lore_books.count(b) for b in sorted(set(lore_books)) if b not in ("v5-corebook", "v5-players-guide")} == {
        "v5-anarch": 7, "v5-blood-sigils": 4, "v5-camarilla": 5, "v5-chicago-by-night": 22,
        "v5-chicago-folios": 10, "v5-children-of-the-blood": 8, "v5-choice-of-games-loresheets": 3,
        "v5-courts-of-the-damned": 5, "v5-cults-of-the-blood-gods": 5, "v5-fall-of-london": 6,
        "v5-forbidden-religions": 6, "v5-gehenna-war": 3, "v5-in-memoriam": 6, "v5-la-by-night-loresheets": 10,
        "v5-let-the-streets-run-red": 9, "v5-nod-apocrypha": 1, "v5-succubus-club": 9, "v5-tattered-facade": 3,
        "v5-trails-of-ash-and-bone": 3}
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
    assert sum(len(d["powers"]) for d in _entries(data, "disciplines")) == 210
    assert sum(1 for d in _entries(data, "disciplines") for p in d["powers"]
               if p["book"] in ("v5-corebook", "v5-players-guide", "v5-companion")) == 145


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
    """Every entry, power, clan Bane, Compulsion and loresheet level has desc.en + desc.el
    (<= 240 chars) and descriptions/*.json has no orphan keys."""
    assert checks.description_problems(CATALOG, data) == []


def _has_desc(holder: dict) -> bool:
    d = holder.get("desc")
    return isinstance(d, dict) and bool(d.get("en", "").strip()) and bool(d.get("el", "").strip())


def test_advantage_descriptions(data):
    """All 279 Merits, Backgrounds and Flaws carry EN + EL."""
    adv = _entries(data, "advantages")
    assert len(adv) == 279
    assert [e["id"] for e in adv if not _has_desc(e)] == []


def test_loresheet_descriptions(data):
    """All 157 loresheets and each of their named levels carry EN + EL (an online-only sheet's
    unnamed levels have nothing to describe)."""
    lore = _entries(data, "loresheets")
    assert len(lore) == 157
    assert [e["id"] for e in lore if not _has_desc(e)] == []
    assert [f"{e['id']}:{lv['dots']}" for e in lore for lv in e["levels"]
            if lv["name"] is not None and not _has_desc(lv)] == []


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
        if e["source"] != "online":
            assert all(lv["name"] for lv in e["levels"]), e["id"]
    lore = {e["id"]: e for e in _entries(data, "loresheets")}
    assert lore["loresheet:descendant-of-hardestadt"]["clans_only"] == ["clan:ventrue"]
    assert lore["loresheet:theo-bell"]["levels"][4]["name"] == "Sect Neutrality"


def test_supplement_books_are_tier_2(data):
    books = {b["book_id"]: b for b in _entries(data, "books")}
    assert {b for b, x in books.items() if x["tier"] == 1} == {"v5-corebook", "v5-players-guide", "v5-companion"}
    assert books["v5-anarch"]["extractable"] is False
    used = {e["book"] for name in ("loresheets", "advantages", "rituals", "ceremonies", "formulae")
            for e in _entries(data, name)}
    assert used <= set(books)


def test_supplement_loresheets(data):
    lore = {e["id"]: e for e in _entries(data, "loresheets")}
    # a supplement reprint of a Tier-1 sheet is an also_in, never its own entry
    nasyon = lore["loresheet:nasyon-san-an"]
    assert (nasyon["book"], nasyon["page"]) == ("v5-players-guide", 229)
    assert {"book": "v5-cults-of-the-blood-gods", "page": 222} in nasyon["also_in"]
    assert "The Nation of Blood" in nasyon["aliases"]
    assert {"book": "v5-camarilla", "page": 184} in lore["loresheet:carmelita-neillson"]["also_in"]
    assert {"book": "v5-anarch", "page": 195} in lore["loresheet:descendant-of-tyler"]["also_in"]
    # between supplements the lower precedence wins (rules 40 over lore 50), then the earlier book
    pony = lore["loresheet:the-pony-express"]
    assert (pony["book"], pony["also_in"]) == ("v5-succubus-club", [{"book": "v5-chicago-folios", "page": 167}])
    assert lore["loresheet:little-siblings"]["book"] == "v5-children-of-the-blood"
    assert lore["loresheet:descendant-of-montano"]["book"] == "v5-tattered-facade"
    # two different sheets with one name keep two ids
    assert lore["loresheet:annabelle"]["book"] == "v5-chicago-by-night"
    assert lore["loresheet:annabelle-la-by-night"]["name"] == "Annabelle"
    # restrictions as printed, structured for the forge
    assert lore["loresheet:child-of-the-angel-michael"]["clans_excluded"] == ["clan:nosferatu"]
    assert lore["loresheet:occult-artifacts"]["clans_only"] == ["clan:tremere", "clan:banu-haqim"]
    kirin = lore["loresheet:student-of-kirin-taunk"]
    assert kirin["thin_blood_only"] and kirin["disciplines_only"] == ["discipline:thin-blood-alchemy"]
    assert lore["loresheet:vienna-zero"]["disciplines_only"] == ["discipline:blood-sorcery"]
    tegyrius = lore["loresheet:tegyrius-the-vizier"]["levels"][3]
    assert (tegyrius["name"], tegyrius["clans_only"]) == ("Perception is Power", ["clan:banu-haqim"])
    assert lore["loresheet:mark-decker"]["levels"][4]["clans_only"] == ["clan:gangrel"]
    # the Ashfinders misprint (two five-dot lores) is a reviewed manual record
    assert "levels" in lore["loresheet:the-ashfinders"]["manual_fields"]


def test_anarch_loresheets_are_online_facts_only(data):
    anarch = [e for e in _entries(data, "loresheets") if e["book"] == "v5-anarch"]
    assert sorted(e["name"] for e in anarch) == ["Agata Starek", "Anarch Revolt", "Blood Plagued", "Hesha Ruhadze",
                                                "Ruins of Carthage", "Salvador Garcia", "The Church of Set"]
    for e in anarch:
        assert e["source"] == "online" and e["source_urls"][0]["site"] == "paradoxwikis", e["id"]
        assert all(lv["name"] is None for lv in e["levels"]), e["id"]
    hesha = next(e for e in anarch if e["name"] == "Hesha Ruhadze")
    assert [lv.get("clans_only") for lv in hesha["levels"]] == [None, None, None, ["clan:ministry"], ["clan:ministry"]]


def test_supplement_powers_rituals_ceremonies_formulae(data):
    powers = {p["id"]: p for d in _entries(data, "disciplines") for p in d["powers"]}
    rituals = {e["id"]: e for e in _entries(data, "rituals")}
    ceremonies = {e["id"]: e for e in _entries(data, "ceremonies")}
    formulae = {e["id"]: e for e in _entries(data, "formulae")}
    # Tier-1 keeps a power the supplements reprint; a PG rename keeps the old name as an alias
    veil = powers["power:oblivion:where-the-veil-thins"]
    assert veil["book"] == "v5-players-guide" and "Where the Shroud Thins" in veil["aliases"]
    assert {"book": "v5-cults-of-the-blood-gods", "page": 205} in veil["also_in"]
    assert "Fatal Precognition" in powers["power:oblivion:fatal-prediction"]["aliases"]
    assert "Split the Shroud" in ceremonies["ceremony:split-the-veil"]["aliases"]
    # a Cults-only power stays a Cults entry
    assert powers["power:oblivion:withering-spirit"]["book"] == "v5-cults-of-the-blood-gods"
    # Blood Sigils: the Koldunic Sorcery power (Tzimisce) and the rituals that need it
    kold = powers["power:blood-sorcery:koldunic-sorcery"]
    assert (kold["level"], kold["clans_only"], kold["source"]) == (1, ["clan:tzimisce"], "manual")
    koldunic = sorted(e["id"] for e in rituals.values() if e["koldunic"])
    assert koldunic == ["ritual:elemental-attack", "ritual:elemental-grasp", "ritual:elemental-shelter"]
    assert rituals["ritual:elemental-grasp"]["prerequisite"] == {"power_id": "power:blood-sorcery:koldunic-sorcery"}
    # a formula that needs another formula (Cults' Ashfinders)
    assert formulae["formula:chemically-induced-flashback"]["prerequisite"] == {"formula_id": "formula:concoct-ashe"}
    # prerequisites printed with book references and line breaks resolve
    assert ceremonies["ceremony:craft-flesh-golem"]["prerequisite"] == {
        "any_of": ["power:oblivion:aura-of-decay", "power:oblivion:necrotic-plague"]}
    assert ceremonies["ceremony:travelers-call"]["prerequisite"] == {"power_id": "power:oblivion:oblivions-sight"}
    # a prerequisite that names no power printed anywhere is left out, not guessed (Sabbat: Necrotic Touch)
    assert ceremonies["ceremony:befoul-vessel"]["prerequisite"] is None
    # Let the Streets Run Red prints the level under the title (Herd Ward: level 1 or 3, kept at 1)
    assert (rituals["ritual:sleep-of-judas"]["level"], rituals["ritual:herd-ward"]["level"]) == (3, 1)
    assert rituals["ritual:le-sang-de-lamour"]["name"] == "Le Sang de l'Amour"
    assert {e["book"] for e in list(rituals.values()) + list(ceremonies.values()) + list(formulae.values())} >= {
        "v5-blood-sigils", "v5-sabbat", "v5-gehenna-war", "v5-tattered-facade", "v5-chicago-folios"}


def test_supplement_advantages(data):
    adv = {e["id"]: e for e in _entries(data, "advantages")}
    new = [e for e in adv.values() if e["book"] not in ("v5-corebook", "v5-players-guide", "v5-companion")]
    assert len(new) == 109 and all(e["source"] == "manual" for e in new)
    # Succubus Club's Influencer (Fame) and the Ashfinders' Influencer are two Merits
    assert (adv["merit:influencer"]["book"], adv["merit:influencer"]["requires"]) == ("v5-succubus-club", "Fame ••+")
    assert adv["merit:influencer-ashfinders"]["name"] == "Influencer"
    # Gehenna War prints no dot glyphs: ratings read from the rendered pages
    assert adv["merit:bonds-of-fealty"]["dots"] == {"min": 3, "max": 3}
    assert adv["merit:sins-of-the-fathers"]["dots"] == {"allowed": [2, 3]}
    assert adv["merit:up-all-night"]["dots"] == {"allowed": [2, 4]}
    assert adv["merit:up-all-night"]["cannot_buy_for"][0]["clan"] == "clan:nosferatu"
    assert adv["flaw:groveling-worm"]["excludes"] == ["merit:penitence"]
    assert adv["merit:object-of-power"]["requires"] == "ancilla or older"
    assert adv["merit:memories-of-the-fallen"]["clans_only"] == ["clan:thin-blood"]
    assert not adv["merit:memories-of-the-fallen"]["thin_blood"]
    ingrained = [e for e in new if e["group"] == "Discipline"]
    assert len(ingrained) == 11 and all(e["kind"] == "flaw" and e["dots"] is None for e in ingrained)
    assert all(e["coterie"] for e in new if e["group"] in ("Domain", "Influence (Church)"))
