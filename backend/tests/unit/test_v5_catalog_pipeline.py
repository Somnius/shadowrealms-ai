"""scripts/v5_catalog pipeline units on small synthetic inputs.

Every fixture here is invented text in the shape of the books' layout (headings, labels,
columns), never text from a book. No PDFs, no network.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

v5c = pytest.importorskip("scripts.v5_catalog", reason="scripts/ not on disk (backend container)")

from scripts.v5_catalog import checks, crosscheck, merge, schema_lite  # noqa: E402
from scripts.v5_catalog.parsers import clans, common, powers, predators  # noqa: E402
from scripts.v5_catalog.sources import mediawiki, pdf  # noqa: E402
from scripts.v5_catalog.sources.base import Line  # noqa: E402


def L(text, h=12.0, page=10, book="v5-test"):
    return Line(text=text, book=book, page=page, page_pdf=page + 2, height=h)


# --------------------------------------------------------------------------- common helpers

def test_title_case_slug_and_ids():
    assert common.title_case("a taste of the moon") == "A Taste of the Moon"
    assert common.title_case("MOON ’ S GLOW") == "Moon's Glow"
    assert common.slug("Moon's Glow") == "moons-glow"
    assert common.power_id("Blood Sorcery", "Moon's Glow") == "power:blood-sorcery:moons-glow"


@pytest.mark.parametrize("text,expected", [
    ("Free", (0, False)), ("No additional cost", (0, False)), ("One Rouse Check", (1, False)),
    ("Two Rouse Checks.", (2, False)), ("One Rouse Check per scene", (1, True)),
    ("One or more Rouse Checks", (1, True)), ("Free or one Rouse Check", (None, False)),
    ("Spend a point of Willpower", (None, False)), (None, (None, False)),
])
def test_rouse_cost(text, expected):
    assert common.rouse_cost(text) == expected


def test_dice_pool_only_plain_traits():
    assert common.dice_pool("Wits+Glimmer vs. Resolve + Shade") == "Wits + Glimmer vs Resolve + Shade"
    assert common.dice_pool("None, though a test may be needed") is None
    assert common.dice_pool("N/A") is None


def test_label_and_name_detection():
    assert common.label("■ ■ Cost: One Rouse Check") == ("cost", "One Rouse Check")
    assert common.label("Prerequisite Power: Moon Sight") == ("prerequisite", "Moon Sight")
    assert common.looks_like_name("moon ’ s glow")
    assert common.looks_like_name("SILVER STEP")
    assert not common.looks_like_name("The vampire walks on")
    assert not common.looks_like_name("Cost: Free")


# --------------------------------------------------------------------------- pdf source

FAKE_BBOX = """<doc><page width="612" height="792">
<flow><block><line xMin="300.0" yMin="100.0" xMax="400.0" yMax="112.0">
<word xMin="300.0" yMin="100.0" xMax="330.0" yMax="112.0">right</word>
<word xMin="333.0" yMin="100.0" xMax="360.0" yMax="112.0">first</word></line></block></flow>
<flow><block><line xMin="70.0" yMin="100.0" xMax="280.0" yMax="112.0">
<word xMin="70.0" yMin="100.0" xMax="100.0" yMax="112.0">left</word>
<word xMin="103.0" yMin="100.0" xMax="130.0" yMax="112.0">one</word>
<word xMin="300.0" yMin="100.0" xMax="330.0" yMax="112.0">glued</word></line>
<line xMin="70.0" yMin="114.0" xMax="200.0" yMax="126.0">
<word xMin="70.0" yMin="114.0" xMax="100.0" yMax="126.0">left</word>
<word xMin="103.0" yMin="114.0" xMax="130.0" yMax="126.0">two</word></line></block></flow>
</page></doc>"""


def test_parse_bbox_splits_glued_columns_and_orders_by_column():
    boxes = pdf.parse_bbox(FAKE_BBOX)
    texts = [b["t"] for b in boxes]
    assert "left one" in texts and "glued" in texts  # wide gap split the glued line
    ordered = [b["t"] for b in pdf.column_order(boxes, min_lines=1)]
    assert ordered.index("left one") < ordered.index("left two") < ordered.index("right first")


def test_layout_column_splitter():
    left = ["alpha beta gamma delta", "epsilon zeta eta theta", "iota kappa lambda mu",
            "nu xi omicron pi rho", "sigma tau upsilon phi", "chi psi omega end"]
    right = ["one two three four", "five six seven eight", "nine ten eleven twelve",
             "thirteen fourteen", "fifteen sixteen", "seventeen eighteen"]
    page = "\n".join(f"{a:<30}     {b}" for a, b in zip(left, right))
    out = pdf.reading_order(page)
    assert out[:6] == left and out[6:] == right


def test_noise_lines():
    assert pdf.is_noise("207")
    assert pdf.is_noise("VA M P I R E : T H E M A S Q U E R A D E P L AY E R S G U I D E")
    assert pdf.is_noise("Chapter Two: Rules")
    assert pdf.is_noise("SECTION", height=8.4)
    assert not pdf.is_noise("Glimmer lets the user see in the dark.")


# --------------------------------------------------------------------------- powers parser

def _fake_discipline():
    return [
        L("Auspex", 30.0),
        L("Level 1", 17.0), L("moon sight", 10.8),
        L("Invented flavour text for a test."),
        L("■ ■ Cost: Free"), L("■ ■ Dice Pools: Wits + Glimmer"), L("■ ■ Duration: One scene"),
        L("silver step", 10.8), L("Amalgam: Celerity 2"), L("Prerequisite: Moon Si-"), L("ght"),
        L("More invented text."), L("■ ■ Cost: One Rouse Check per turn"), L("■ ■ System: Roll it."),
        L("Level 2", 17.0), L("moon ’ s long fresh -", 15.4), L("ness", 10.8),
        L("Prerequisite: Moon Sight or Silver Step"), L("Cost: Two Rouse Checks"),
        L("sidebar title", 10.8), L("No labels follow this one."),
        L("Rituals", 30.0), L("Level 1 Rituals", 17.0), L("lantern rite", 10.8),
        L("Ingredients: invented things."), L("System: invented."),
        L("Other Chapter", 40.0), L("Level 1", 17.0), L("stray title", 10.8), L("Cost: Free"),
    ]


def test_powers_parser():
    recs, report = powers.parse(_fake_discipline())
    by = {r["name"]: r for r in recs}
    assert set(by) == {"Moon Sight", "Silver Step", "Moon's Long Freshness", "Lantern Rite"}
    assert by["Moon Sight"]["level"] == 1 and by["Moon Sight"]["rouse_cost"] == 0
    assert by["Moon Sight"]["dice_pool"] == "Wits + Glimmer"
    assert by["Silver Step"]["amalgam"] == {"discipline": "Celerity", "level": 2}
    assert by["Silver Step"]["prerequisite_text"] == "Moon Sight"
    assert (by["Silver Step"]["rouse_cost"], by["Silver Step"]["rouse_cost_conditional"]) == (1, True)
    assert by["Moon's Long Freshness"]["level"] == 2
    assert by["Lantern Rite"]["kind"] == "ritual" and by["Lantern Rite"]["discipline"] == "Blood Sorcery"
    assert by["Moon Sight"]["id"] == "power:auspex:moon-sight"
    assert any("Sidebar Title" in r for r in report)  # dropped: no labels after it


def test_powers_parser_section_pages():
    secs = powers.section_pages(_fake_discipline())
    assert {"kind": "ritual", "discipline": "Blood Sorcery", "book": "v5-test", "page": 10} in secs


# --------------------------------------------------------------------------- predators parser

def test_predator_parser():
    lines = [
        L("Night Owl", 30.0), L("Invented description."),
        L("■ ■ Add a specialty: Stealth (Roof-"), L("tops) or Awareness (Night Sounds)"),
        L("■ ■ Gain one dot of Auspex (Hecata only) or Obfuscate"),
        L("■ ■ Lose one dot of Humanity"), L("■ ■ Gain the Herd Background (••)"),
        L("Predator Pool: Wits + Stealth"),
        L("Next Section", 40.0),
    ]
    orig = predators._BY_KEY.copy()  # the parser only takes known type names
    predators._BY_KEY["night owl"] = "Night Owl"
    try:
        recs, report = predators.parse(lines)
    finally:
        predators._BY_KEY.clear()
        predators._BY_KEY.update(orig)
    assert report == []
    (r,) = recs
    assert r["specialty_choice"] == [{"skill": "Stealth", "name": "Rooftops"},
                                     {"skill": "Awareness", "name": "Night Sounds"}]
    assert r["discipline_choice"] == [{"discipline": "Auspex", "clans_only": ["Hecata"]},
                                      {"discipline": "Obfuscate"}]
    assert r["humanity"] == -1
    assert r["other_bullets"] == ["Gain the Herd Background (••)"]
    assert r["pool_text"] == "Wits + Stealth"


# --------------------------------------------------------------------------- clans parser

def test_clan_block_and_variants():
    lines = [L("Who are they", 30.0), L("Invented."), L("Disciplines", 30.0),
             L("Auspex: invented use."), L("more text"), L("CELERITY: invented."), L("Potence: x."),
             L("Bane", 30.0, page=11), L("Invented bane text."),
             L("Compulsion: Wander", 28.0, page=12), L("Invented.")]
    rec, report = clans.parse_block("Brujah", lines)
    assert rec["disciplines"] == ["Auspex", "Celerity", "Potence"]
    assert (rec["bane_page"], rec["compulsion"], rec["compulsion_page"]) == (11, "Wander", 12)
    assert report == []
    variants, _ = clans.parse_bane_variants([L("Toreador: Odd One Tzimisce: Other One", 30.0),
                                             L("Malkavian:", 30.0), L("Long Name", 30.0)])
    assert variants == {"Toreador": [{"name": "Odd One", "page": 10}],
                        "Tzimisce": [{"name": "Other One", "page": 10}],
                        "Malkavian": [{"name": "Long Name", "page": 10}]}


# --------------------------------------------------------------------------- merge

def test_consolidate_prefers_lowest_precedence_and_reports_conflicts():
    recs = [
        {"id": "power:x:a", "name": "A", "book": "late", "page": 5, "level": 2, "kind": "power"},
        {"id": "power:x:a", "name": "A", "book": "early", "page": 9, "level": 3, "kind": "power"},
    ]
    report = []
    out = merge.consolidate(recs, {"early": 20, "late": 30}, report)
    assert out[0]["book"] == "early" and out[0]["level"] == 3
    assert out[0]["also_in"] == [{"book": "late", "page": 5}]
    assert any("level differs" in r for r in report)


def test_manual_merge_patch_exclude():
    recs = [{"id": "power:x:old", "name": "Old", "book": "b", "page": 1},
            {"id": "power:x:gone", "name": "Gone", "book": "b", "page": 2}]
    man = {"merge": [{"from": "power:x:old", "into": "power:x:new"}],
           "exclude": [{"id": "power:x:gone"}],
           "patch": [{"id": "power:x:new", "set": {"level": 4}}],
           "add": [{"id": "power:x:added", "name": "Added"}]}
    report = []
    out = merge.apply_manual(recs, man, report)
    ids = {r["id"]: r for r in out}
    assert set(ids) == {"power:x:new", "power:x:added"}
    assert ids["power:x:new"]["aliases"] == ["Old"] and ids["power:x:new"]["level"] == 4
    assert ids["power:x:new"]["manual_fields"] == ["level"]
    assert ids["power:x:added"]["source"] == "manual"
    assert report == []


def test_resolve_prerequisite():
    names = {"a": "power:x:a", "b": "power:y:b", "c": "power:y:c"}
    report = []
    assert merge.resolve_prerequisite("A", names, report, "t") == {"power_id": "power:x:a"}
    assert merge.resolve_prerequisite("A, either B or C", names, report, "t") == {
        "all_of": [{"power_id": "power:x:a"}, {"any_of": ["power:y:b", "power:y:c"]}]}
    assert report == []
    assert merge.resolve_prerequisite("Unknown Thing", names, report, "t") is None
    assert report and "not found" in report[0]


# --------------------------------------------------------------------------- checks

def test_schema_lite():
    schema = {"type": "object", "required": ["a"], "additionalProperties": False,
              "properties": {"a": {"type": "integer", "minimum": 1}, "b": {"$ref": "#/$defs/s"}},
              "$defs": {"s": {"type": "string", "pattern": "^x"}}}
    assert schema_lite.validate({"a": 1, "b": "xy"}, schema) == []
    errs = schema_lite.validate({"a": 0, "b": "y", "c": 1}, schema)
    assert len(errs) == 3
    assert schema_lite.validate(1, {"type": "integer", "format": "x"})  # unknown keyword refused


def test_overlap_gate():
    book = "The quick silver lantern burns only when the moon is full and bright tonight"
    ours = ["the silver lantern burns only when the moon is full", "A lantern that needs a full moon."]
    hits = checks.overlap(ours, [book])
    assert len(hits) == 1 and "silver lantern" in hits[0]
    assert checks.overlap(["short text"], [book]) == []


def test_reference_problems_on_tiny_catalog():
    data = {
        "books": {"entries": [{"book_id": "v5-a"}]},
        "clans": {"entries": [{"id": "clan:x", "book": "v5-a", "page": 1, "disciplines": ["discipline:nope"],
                               "bane_variants": [], "compulsion": None}]},
        "disciplines": {"entries": [{"id": "discipline:d", "book": "v5-a", "page": 1, "powers": [
            {"id": "power:d:p", "book": "v5-b", "page": 2, "amalgam": None,
             "prerequisite": {"power_id": "power:d:missing"}}]}]},
        "rituals": {"entries": []}, "ceremonies": {"entries": []}, "formulae": {"entries": []},
        "predator_types": {"entries": [{"id": "predator:p", "book": "v5-a", "page": 1,
                                        "discipline_choice": [{"discipline": "discipline:d", "clans_only": ["clan:x"]}],
                                        "forbidden_clans": [], "advantages": [
                                            {"pick": "all", "options": [{"id": "weird:thing", "dots": 1}]}],
                                        "flaws": []}]},
    }
    probs = checks.reference_problems(data)
    assert any("discipline:nope" in p for p in probs)
    assert any("'v5-b'" in p for p in probs)
    assert any("power:d:missing" in p for p in probs)
    assert any("weird:thing" in p for p in probs)


# --------------------------------------------------------------------------- crosscheck

def test_crosscheck_compare():
    pdf_recs = [{"id": "power:a:x", "name": "X", "level": 2, "book": "b", "page": 3},
                {"id": "power:a:only", "name": "Only", "level": 1, "book": "b", "page": 4}]
    online = [{"id": "power:a:x", "name": "X", "level": 3, "url": "https://example.invalid/X"}]
    rows = crosscheck.compare(pdf_recs, online)
    assert {"id": "power:a:x", "field": "level"}.items() <= rows[0].items()
    assert any(r["id"] == "power:a:only" and r["online"] is None for r in rows)


def test_crosscheck_without_online_file(tmp_path):
    assert "nothing to cross-check" in crosscheck.run("clans", tmp_path, tmp_path / "out")


# --------------------------------------------------------------------------- mediawiki adapter

SOURCES = {"fakewiki": {"site": "fakewiki", "api": "https://wiki.invalid/api.php",
                        "base_url": "https://wiki.invalid", "fetch": True, "rate_limit_seconds": 3},
           "nofetch": {"site": "nofetch", "fetch": False}}
FAKE_WIKITEXT = """Intro.
== Night Owl ==
* Add a specialty
{| class="wikitable"
! Name !! Dots !! Source
|-
| [[Moon Sight|Moon Sight]] || •• || Invented Book p. 1<ref>x</ref>
|-
| '''Silver Step''' || • || Invented Book p. 2
|}
== Other ==
text
"""


def _fake_api(calls):
    def fetch(url):
        calls.append(url)
        return {"query": {"pages": [{"title": "Fake Page", "revisions": [
            {"revid": 42, "slots": {"main": {"content": FAKE_WIKITEXT}}}]}]}}
    return fetch


def test_mediawiki_refuses_sites_not_allowed(tmp_path):
    with pytest.raises(PermissionError):
        mediawiki.MediaWikiSource("nofetch", SOURCES, tmp_path)
    with pytest.raises(PermissionError):
        mediawiki.MediaWikiSource("unknown", SOURCES, tmp_path)


def test_mediawiki_fetch_cache_and_rate_limit(tmp_path):
    calls, sleeps = [], []
    src = mediawiki.MediaWikiSource("fakewiki", SOURCES, tmp_path, fetch_json=_fake_api(calls),
                                    sleep=sleeps.append, today=lambda: "2026-01-01")
    rec = src.page("Fake Page")
    assert rec["revision"] == 42 and rec["fetched"] == "2026-01-01"
    assert rec["url"] == "https://wiki.invalid/Fake_Page"
    src.page("Fake Page")  # cached: no second call
    assert len(calls) == 1
    src.page("Another Page")
    assert len(calls) == 2 and sleeps == [3.0]
    assert json.loads((tmp_path / "fakewiki" / "fake-page.json").read_text())["revision"] == 42
    lines = src.lines("Fake Page")
    assert lines[0].url == "https://wiki.invalid/Fake_Page" and lines[0].revision == 42


def test_wikitext_helpers():
    (table,) = mediawiki.parse_tables(FAKE_WIKITEXT)
    assert table[0] == ["Name", "Dots", "Source"]
    assert table[1] == ["Moon Sight", "••", "Invented Book p. 1"]
    assert table[2][0] == "Silver Step"
    secs = mediawiki.sections(FAKE_WIKITEXT)
    assert list(secs) == ["Night Owl", "Other"]
