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
from scripts.v5_catalog.parsers import advantages, clans, common, loresheets, powers, predators  # noqa: E402
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


def test_capital_titles_with_apostrophes_stay_titles():
    assert common.looks_like_name("GORGON’S SCALES")
    assert common.looks_like_name("MESSENGER’S COMMAND")
    assert common.title_case("GORGON’S SCALES") == "Gorgon's Scales"


def test_join_wrapped_undoes_hyphenation():
    assert common.join_wrapped("Charisma + Animal-", "ism") == "Charisma + Animalism"
    assert common.join_wrapped("Wits +", "Survival") == "Wits + Survival"


def test_dice_pool_only_plain_traits():
    assert common.dice_pool("Wits + Survival (to activate reflexively)") == "Wits + Survival"
    assert common.dice_pool("Manipulation + Glimmer, Charisma + Glimmer") == \
        "Manipulation + Glimmer, Charisma + Glimmer"
    assert common.dice_pool("Dexterity + Athletics, or as needed") is None
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
        L("■ ■ Cost: Free"), L("■ ■ Dice Pools: Wits + Glim-"), L("mer"), L("■ ■ Duration: One scene"),
        L("silver step", 10.8), L("Amalgam: Celerity 2"), L("Prerequisite: Moon Si-"), L("ght"),
        L("More invented text."), L("■ ■ Cost: One Rouse Check per turn"), L("■ ■ System: Roll it."),
        L("Level 2", 17.0), L("moon ’ s long fresh -", 15.4), L("ness", 10.8),
        L("Prerequisite: Moon Sight or Silver Step"), L("Cost: Two Rouse Checks"),
        L("STAR’S EDGE", 10.8), L("Cost: One Rouse Check"),
        L("sidebar title", 10.8), L("No labels follow this one."),
        L("Rituals", 30.0), L("Level 1 Rituals", 17.0), L("lantern rite", 10.8),
        L("Ingredients: invented things."), L("System: invented."),
        L("Other Chapter", 40.0), L("Level 1", 17.0), L("stray title", 10.8), L("Cost: Free"),
    ]


def test_powers_parser():
    recs, report = powers.parse(_fake_discipline())
    by = {r["name"]: r for r in recs}
    assert set(by) == {"Moon Sight", "Silver Step", "Moon's Long Freshness", "Star's Edge", "Lantern Rite"}
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


def test_attach_descriptions_targets_entries_powers_and_clan_parts():
    files = {
        "clans": {"entries": [{"id": "clan:x", "name": "X", "bane": {"name": "B", "page": 1},
                               "compulsion": {"name": "C", "book": "b", "page": 2}},
                              {"id": "clan:y", "name": "Y", "bane": None, "compulsion": None}]},
        "disciplines": {"entries": [{"id": "discipline:d", "name": "D", "powers": [
            {"id": "power:d:p", "name": "P", "level": 1}]}]},
        "rituals": {"entries": []},
        "advantages": {"entries": [{"id": "merit:m", "name": "M", "levels": [{"dots": 1, "name": "L1"}]}]},
        "loresheets": {"entries": [{"id": "loresheet:l", "name": "L", "levels": [
            {"dots": 1, "name": "One"}, {"dots": 2, "name": "Two"}]}]},
    }
    d = {"en": "Does a thing.", "el": "Κάνει κάτι."}
    descs = {"clans": {"clan:x": d, "clan:x:bane": d, "clan:x:compulsion": d, "clan:zzz": d},
             "disciplines": {"discipline:d": d, "power:d:p": {"en": "only en"}},
             "advantages": {"merit:m": d, "merit:m:1": d},
             "loresheets": {"loresheet:l": d, "loresheet:l:1": d}}
    report = []
    merge.attach_descriptions(files, descs, report)
    x = files["clans"]["entries"][0]
    assert x["desc"] == d and x["bane"]["desc"] == d and x["compulsion"]["desc"] == d
    assert list(x)[:3] == ["id", "name", "desc"]  # desc sits right after name
    assert files["disciplines"]["entries"][0]["desc"] == d
    assert "desc" not in files["disciplines"]["entries"][0]["powers"][0]
    assert any("clan:zzz is not in the catalog" in r for r in report)
    assert any("power:d:p needs both en and el" in r for r in report)
    assert any("have no description" in r and "clan:y" in r for r in report)
    # loresheet levels are targets ('<id>:<dots>'); advantage levels are not
    lore = files["loresheets"]["entries"][0]
    assert lore["desc"] == d and lore["levels"][0]["desc"] == d
    assert list(lore["levels"][0]) == ["dots", "name", "desc"]
    assert "desc" not in lore["levels"][1]
    assert any("have no description" in r and "loresheet:l:2" in r for r in report)
    assert any("merit:m:1 is not in the catalog" in r for r in report)
    assert "desc" not in files["advantages"]["entries"][0]["levels"][0]


def test_description_problems(tmp_path):
    d = {"en": "ok", "el": "εντάξει"}
    data = {
        "books": {"entries": []},
        "clans": {"entries": [{"id": "clan:x", "name": "X", "desc": d,
                               "bane": {"name": "B", "page": 1, "desc": {"en": "x" * 241, "el": "y"}},
                               "compulsion": None}]},
        "disciplines": {"entries": [{"id": "discipline:d", "name": "D", "desc": d, "powers": [
            {"id": "power:d:p", "name": "P", "desc": {"en": "x", "el": " "}}]}]},
        "rituals": {"entries": [{"id": "ritual:r", "name": "R"}]},
        "ceremonies": {"entries": []}, "formulae": {"entries": []}, "predator_types": {"entries": []},
    }
    (tmp_path / "descriptions").mkdir()
    (tmp_path / "descriptions" / "rituals.json").write_text('{"ritual:nope": {"en": "a", "el": "b"}}')
    (tmp_path / "descriptions" / "bogus.json").write_text("{}")
    probs = checks.description_problems(tmp_path, data)
    assert any("clan:x:bane: desc.en is 241 chars" in p for p in probs)
    assert any("power:d:p: desc.el missing" in p for p in probs)
    assert any("ritual:r: no description" in p for p in probs)
    assert any("ritual:nope is not in the catalog" in p for p in probs)
    assert any("bogus.json: not a catalog name" in p for p in probs)
    assert len(probs) == 5


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


def test_overlap_gate_reads_columns_in_order_and_soft_hyphens(tmp_path):
    """A run copied across a line break inside one column is caught: the -layout text puts the
    two columns side by side on each line, the cached boxes give them column by column."""
    pages = tmp_path / "v5-x" / "abc" / "pages"
    pages.mkdir(parents=True)
    left = ["the silver lantern burns only", "when the moon is full and bright", "over the old harbour", "on a cold night"]
    right = ["a second column talks of", "something else entirely here", "with words of its own", "until the end"]
    layout = "\n".join(f"{a:<40}{b}" for a, b in zip(left, right)) + "\n"
    (pages / "0001.txt").write_text(layout, encoding="utf-8")
    boxes = [{"t": t, "x": x, "y": 100 + 12 * i, "h": 12, "f": f}
             for f, (x, col) in enumerate(((50, left), (300, right))) for i, t in enumerate(col)]
    (pages / "0001.json").write_text(json.dumps(boxes), encoding="utf-8")
    ours = ["the silver lantern burns only when the moon is full"]
    assert checks.overlap(ours, [layout]) == []  # the layout text alone misses it
    assert len(checks.overlap(ours, checks.page_cache_texts(tmp_path))) == 1
    assert checks.words("a lan\u00ad\ntern") == ["a", "lantern"]
    # printed facts (names, dice pools) are not prose: the gate skips them
    assert checks.catalog_strings({"name": "x y", "dice_pool": "p", "desc": {"en": "z"}}) == ["z"]


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
                                        "flaws": [{"pick": "one_of", "options": [
                                            {"id": "flaw:enemies", "dots": 1},
                                            {"id": "flaw:mythic", "dots": None, "group": True},
                                            {"id": "flaw:psychological", "dots": None, "group": True}]}]}]},
        "advantages": {"entries": [
            {"id": "flaw:enemies", "kind": "flaw", "group": "Allies", "book": "v5-a", "page": 1,
             "clans_only": None, "cannot_buy_for": []},
            {"id": "flaw:stake-bait", "kind": "flaw", "group": "Mythic", "book": "v5-a", "page": 1,
             "clans_only": ["clan:nope"], "cannot_buy_for": []}]},
        "loresheets": {"entries": [{"id": "loresheet:l", "book": "v5-a", "page": 1, "clans_only": None,
                                    "levels": [{"dots": d, "name": "x"} for d in (1, 2, 3, 5)]}]},
    }
    probs = checks.reference_problems(data)
    assert not any("flaw:enemies" in p or "flaw:mythic" in p for p in probs)
    assert any("flaw:psychological" in p for p in probs)
    assert any("clan:nope" in p for p in probs)
    assert any("loresheet:l" in p and "1-5" in p for p in probs)
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


# --------------------------------------------------------------------------- advantages and loresheets

@pytest.mark.parametrize("spec,expected", [
    ("• TO •••", {"min": 1, "max": 3}), ("•+", {"min": 1, "max": None}), ("•• OR •••", {"allowed": [2, 3]}),
    ("(••)", {"min": 2, "max": 2}), ("(• TO ••••)", {"min": 1, "max": 4}), (None, None), ("", None),
])
def test_parse_dots(spec, expected):
    assert advantages.parse_dots(spec) == expected


def _master_fixture():
    return [
        L("Backgrounds", 28.6), L("GLIMMER • TO •••", 13.9), L("Invented summary; V:tM, p. 50."),
        L("Merits", 28.6), L("MOON EYES ••", 13.9), L("Invented summary; p. 12."),
        L("Thin-Blood Merits", 19.6), L("NIGHT SIGHT", 13.9), L("Invented summary."),
        L("Flaws", 28.6), L("SILVER ITCH (•)", 13.9), L("Invented; see Invented Book, p. 99; V:tM, p. 51."),
        L("Clan Coterie Merits", 19.6), L("BRUJAH: LOUD VOICE •••", 13.9), L("Invented; p. 70."),
    ]


def test_parse_master_list():
    recs, report = advantages.parse_master(_master_fixture())
    by = {r["name"]: r for r in recs}
    assert report == []
    assert by["Glimmer"]["kind"] == "background" and by["Glimmer"]["ref"] == ("v5-corebook", 50)
    assert by["Moon Eyes"]["dots"] == {"min": 2, "max": 2} and by["Moon Eyes"]["ref"] == ("v5-players-guide", 12)
    assert by["Night Sight"]["thin_blood"] and by["Night Sight"]["dots"] is None
    assert by["Silver Itch"]["ref"] == ("v5-corebook", 51)  # the last page cited is the entry's own
    assert by["Loud Voice"]["clans_only"] == ["clan:brujah"] and by["Loud Voice"]["coterie"]
    assert advantages.entry_id("merit", "Loud Voice", "Clan Coterie") == "merit:coterie-loud-voice"
    assert advantages.entry_id("flaw", "Silver Itch", None) == "flaw:silver-itch"


def test_chapter_scan_and_match():
    master, report = advantages.parse_master(_master_fixture())
    chapter = [
        L("Merits", 31.4, page=12, book="v5-players-guide"),
        L("looks", 10.8, page=12, book="v5-players-guide"),
        L("MOON EYES •••", 14.6, page=12, book="v5-players-guide"),
        L("Backgrounds", 31.4, page=50, book="v5-corebook"),
        L("Herd", 17.1, page=50, book="v5-corebook"),
        L("Flaw: (•) Silver Itch. Invented text.", 12.2, page=51, book="v5-corebook"),
    ]
    hits = advantages.scan_chapter(chapter)
    advantages.match(master, hits, report, {"v5-corebook": 10, "v5-players-guide": 20})
    by = {r["name"]: r for r in master}
    assert by["Moon Eyes"]["chapter_group"] == "Looks"
    assert by["Silver Itch"]["chapter_group"] == "Herd"  # a Flaw printed inside a Background block
    assert any("Moon Eyes" in r and "'•••'" in r for r in report)  # the two printings disagree


def test_background_levels():
    lines = [L("Glimmer", 17.1), L("Invented intro."), L("•"), L("Faint: invented."), L("•• Bright: invented."),
             L("•••"), L("Blinding: invented."), L("Next", 17.1)]
    assert advantages.background_levels(lines, "Glimmer") == [
        {"dots": 1, "name": "Faint"}, {"dots": 2, "name": "Bright"}, {"dots": 3, "name": "Blinding"}]


def test_loresheet_dots_from_glyphs_and_geometry():
    def LX(text, x, h=13.9):
        return Line(text=text, book="v5-test", page=7, height=h, x=x)
    body = [LX("invented body text", 70.0, 13.4) for _ in range(5)] + \
        [LX("invented body text", 230.0, 13.4) for _ in range(5)]
    page = [LX("the moon court", 100.0, 39.0), LX("(Toreador characters only)", 100.0, 12.1)] + body + [
        LX("First Light: invented", 78.0), LX("Second", 86.0), LX("Light: invented", 70.0),
        LX("Third Light: invented", 254.0), LX("Fourth Light: x", 262.0), LX("Fifth Light: y", 270.0)]
    rec, report = loresheets.parse_page(page, {13.9})
    assert report == []
    assert [lv["name"] for lv in rec["levels"]] == ["First Light", "Second Light", "Third Light",
                                                   "Fourth Light", "Fifth Light"]
    assert rec["clans_only"] == ["clan:toreador"] and rec["id"] == "loresheet:the-moon-court"
    glyphs = [LX("the sun court", 100.0, 39.0)] + body + [
        LX(f"{'•' * n} Ray {n}: invented", 70.0) for n in (1, 2, 3, 4)]
    rec, report = loresheets.parse_page(glyphs)
    assert [lv["dots"] for lv in rec["levels"]] == [1, 2, 3, 4] and report


# --------------------------------------------------------------------------- Tier-2 loresheets (part F)

def B(t, x, y, h=12.0):
    return {"t": t, "x": x, "y": y, "h": h, "f": 0}


def _body(xs, y0=420.0, n=6):
    return [B("invented body text runs on", x, y0 + 13 * i) for x in xs for i in range(n)]


def test_tier2_glyph_page_dots_in_their_own_box_and_wrapped_names():
    page = [B("T H E  MOON  COU RT", 120, 70, 40.0), B("(TOR E A DOR CH A R ACT E R S ON LY )", 150, 115, 14.0),
            B("LORE", 290, 390, 10.7)] + _body((80, 240, 400)) + [
        B("•", 60, 430), B("First Light: invented", 80, 430),
        B("•• Second Light: invented", 80, 500),
        B("•••", 220, 430), B("A Light That", 240, 430), B("Wraps: invented", 240, 443),
        B("••••", 380, 430), B("Ray of the", 400, 430), B("Fourth: invented", 400, 441),
        B("••••• Who Goes There? invented", 400, 520)]
    rec, report = loresheets.parse_boxes(page, "v5-test", 9, glyphs=True)
    assert report == []
    assert [(lv["dots"], lv["name"]) for lv in rec["levels"]] == [
        (1, "First Light"), (2, "Second Light"), (3, "A Light That Wraps"), (4, "Ray of the Fourth"),
        (5, "Who Goes There?")]
    assert loresheets.despace(rec["title_raw"]) == "THEMOONCOURT"
    assert loresheets.despace(rec["restriction_raw"]) == "TOREADORCHARACTERSONLY"


def test_tier2_no_glyph_page_reads_indents_in_order():
    # the 4-dot indent is wider than 4 x 8 pt in some books: five growing indents are dots 1-5
    page = [B("the sun court", 120, 70, 40.0), B("Lore", 290, 390, 10.7)] + _body((71, 233, 396)) + [
        B("Dawn: invented", 79, 412), B("Noon: invented", 87, 530), B("Dusk: invented", 258, 412),
        B("Night: invented", 269, 596), B("Last Light: invented", 437, 503)]
    rec, report = loresheets.parse_boxes(page, "v5-test", 3, glyphs=False)
    assert report == [] and [lv["name"] for lv in rec["levels"]] == ["Dawn", "Noon", "Dusk", "Night", "Last Light"]
    rec, report = loresheets.parse_boxes(page[:-1], "v5-test", 3, glyphs=False)
    assert [lv["dots"] for lv in rec["levels"]] == [1, 2, 3] and report  # never guessed


def test_tier2_continuation_pages_and_one_letter_titles():
    first = [B("Q", 297, 72, 39.0), B("Q", 314, 143, 88.0), B("LORE", 290, 390, 10.7)] + _body((80,)) + [
        B("• One: a", 80, 430), B("•• Two: b", 80, 460)]
    rest = _body((80,), y0=100) + [B("••• Three: c", 80, 130), B("•••• Four: d", 80, 160), B("••••• Five: e", 80, 190)]
    recs, report = loresheets.parse_book([(5, first), (6, rest)], "v5-test", glyphs=True)
    assert report == [] and len(recs) == 1
    assert recs[0]["pages"] == [5, 6] and recs[0]["title_raw"] == "Q"
    assert [lv["name"] for lv in recs[0]["levels"]] == ["One", "Two", "Three", "Four", "Five"]


@pytest.mark.parametrize("text,expected", [
    ("ventrue characters only", {"clans_only": ["clan:ventrue"]}),
    ("Bloodline, Hecata characters only", {"clans_only": ["clan:hecata"]}),
    ("Salubri or Tremere Only", {"clans_only": ["clan:salubri", "clan:tremere"]}),
    ("Tremere and Banu Haqim only", {"clans_only": ["clan:tremere", "clan:banu-haqim"]}),
    ("The Ministry only", {"clans_only": ["clan:ministry"]}),
    ("Thin-blooded characters only", {"thin_blood_only": True}),
    ("Thin-Blood Alchemists only", {"thin_blood_only": True, "disciplines_only": ["discipline:thin-blood-alchemy"]}),
    ("Blood Sorcery users only", {"disciplines_only": ["discipline:blood-sorcery"]}),
    ("Unavailable to Nosferatu characters", {"clans_excluded": ["clan:nosferatu"]}),
    ("Church of Set members", {}),
])
def test_structured_restriction(text, expected):
    base = {"clans_only": None, "disciplines_only": None, "thin_blood_only": False}
    assert loresheets.structured_restriction(text) == {**base, **expected}


def test_level_restriction_split():
    assert loresheets.split_level_restriction("Perception is Power (Banu Haqim characters only)") == (
        "Perception is Power", "Banu Haqim characters only")
    assert loresheets.split_level_restriction("Legendary Lineage (choose one)") == ("Legendary Lineage (choose one)", None)


def test_consolidate_loresheets_tier1_keeps_and_reprints_go_to_also_in():
    lv = [{"dots": d, "name": f"L{d}"} for d in range(1, 6)]
    recs = [
        {"id": "loresheet:x", "name": "X", "book": "v5-supp-b", "page": 9, "levels": lv, "clans_only": None},
        {"id": "loresheet:x", "name": "X", "book": "v5-core", "page": 400, "levels": lv, "clans_only": None},
        {"id": "loresheet:x", "name": "Old X", "book": "v5-supp-a", "page": 3,
         "levels": lv[:2] + [{"dots": 3, "name": "Other"}] + lv[3:], "clans_only": None},
        {"id": "loresheet:x", "name": "X", "book": "v5-online", "page": 5, "source": "online",
         "levels": [{"dots": d, "name": None} for d in range(1, 6)], "clans_only": ["clan:y"]},
    ]
    report = []
    out = merge.consolidate_loresheets(recs, {"v5-core": 10, "v5-supp-a": 40, "v5-supp-b": 40, "v5-online": 40},
                                       {"v5-supp-a": 2019, "v5-supp-b": 2025, "v5-online": 2019}, report)
    assert len(out) == 1 and (out[0]["book"], out[0]["page"]) == ("v5-core", 400)
    assert out[0]["also_in"] == [{"book": "v5-online", "page": 5}, {"book": "v5-supp-a", "page": 3},
                                 {"book": "v5-supp-b", "page": 9}]
    assert out[0]["aliases"] == ["Old X"]
    assert len(report) == 1 and "level 3 name differs" in report[0]  # null names and online facts are not conflicts


def test_loresheets_vs_wiki():
    wiki = """== Camarilla Loresheets ==
{| class="mildtable"
! Name !! Restrictions !! Description !! Source
|-
| '''Moon Court''' || Tremere only || invented || *Page 12
|-
| '''Sun Court''' || N/A || invented || *Page 14
|}
"""
    rows = crosscheck.wiki_loresheet_rows(wiki)
    assert [(r["book"], r["name"], r["page"]) for r in rows] == [("v5-camarilla", "Moon Court", 12),
                                                                ("v5-camarilla", "Sun Court", 14)]
    entries = [{"id": "loresheet:moon-court", "name": "Moon Court", "book": "v5-camarilla", "page": 13,
                "clans_only": None, "levels": [], "also_in": []},
               {"id": "loresheet:star-court", "name": "Star Court", "book": "v5-camarilla", "page": 20,
                "clans_only": None, "levels": [], "also_in": []}]
    out = crosscheck.loresheets_vs_wiki(entries, rows, common.slug)
    assert any("moon-court: wiki gives v5-camarilla p.12" in x for x in out)
    assert any("moon-court: wiki restriction 'Tremere only'" in x for x in out)
    assert any("'Sun Court'" in x and "not in the catalog" in x for x in out)
    assert any("star-court" in x and "not on the wiki" in x for x in out)


# --------------------------------------------------------------------------- supplement powers (part F2)

def _sup(text, h=12.0, page=40):
    return L(text, h=h, page=page)


def test_supplement_powers_parser_layouts():
    lines = [
        _sup("Invented chapter text runs on here.") for _ in range(6)
    ] + [
        _sup("New Moon", 38.6), _sup("Rituals", 38.6),          # two-line section heading
        _sup("THE SCENE", 252.0),                                  # big art caption: skipped, not a section end
        _sup("Level 1 Rituals", 19.3),
        _sup("S ilver T ide", 19.6),                               # small caps set as 'S ilver T ide'
        _sup("I ngredients : invented things"),                    # label with spaced capital and colon
        _sup("S ystem : invented effect"),
        _sup("Animalism", 19.5),                                   # a smaller Discipline heading
        _sup("Level 2 Power", 22.3),                               # 'Level N Power'
        _sup("Moon’sCall", 17.0),                                  # glued possessive
        _sup("Prerequisite: Feral Whispers (Players"),
        _sup("Guide, p. 9) or Sense the"),
        _sup("Beast"),
        _sup("Cost: One Rouse Check"),
        _sup("Pool: Charisma + Animalism"),
        _sup("System: invented"),
    ]
    recs, report = powers.parse(lines, supplement=True)
    assert [(r["kind"], r["discipline"], r["level"], r["name"]) for r in recs] == [
        ("ritual", "Blood Sorcery", 1, "Silver Tide"), ("power", "Animalism", 2, "Moon's Call")]
    call = recs[1]
    assert call["prerequisite_text"] == "Feral Whispers (Players Guide, p. 9) or Sense the Beast"
    assert (call["rouse_cost"], call["rouse_cost_conditional"], call["dice_pool"]) == (1, False, "Charisma + Animalism")
    # Tier-1 mode is unchanged: the small heading and 'Level 2 Power' are not read there
    assert powers.parse(lines)[0] == []


def test_supplement_start_section_and_prerequisite_references():
    lines = [_sup("Level 3", 28.6), _sup("Concoct Fog", 20.0), _sup("Ingredients: invented"),
             _sup("System: invented")]
    recs, _ = powers.parse(lines, supplement=True, start=("formula", "Thin-Blood Alchemy"))
    assert [(r["id"], r["level"]) for r in recs] == [("formula:concoct-fog", 3)]
    report = []
    ids = {"aura of decay": "power:oblivion:aura-of-decay", "necrotic plague": "power:oblivion:necrotic-plague",
           "where the shroud thins": "power:oblivion:where-the-veil-thins"}
    assert merge.resolve_prerequisite("Aura of Decay (Players Guide, p. 88) or Necrotic Plague (Players Guide, p. 89)",
                                      ids, report, "x") == {"any_of": ["power:oblivion:aura-of-decay",
                                                                        "power:oblivion:necrotic-plague"]}
    assert merge.resolve_prerequisite("Where the Shroud Th ins", ids, report, "x") == {
        "power_id": "power:oblivion:where-the-veil-thins"}
    assert report == []
