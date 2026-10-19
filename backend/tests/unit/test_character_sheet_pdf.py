"""Fillable character sheet PDF: both editions, Greek, black ink only, and who may download it."""

import base64
import copy
import re
import sys
import types
import zlib

import pytest

pytest.importorskip("reportlab")

from services.character_sheet_pdf import (  # noqa: E402
    CINZEL_BOLD,
    SERIF,
    SERIF_ITALIC,
    SheetCanvas,
    _columns,
    _layout_reference,
    _ref_paragraph,
    build_sheet_pdf,
    safe_filename,
    v5_reference,
)

GREEK_NAME = "Κωνσταντίνος Κατακουζηνός"

V5_CHAR = {
    "id": 9, "name": GREEK_NAME, "system_type": "vampire", "rules_edition": "v5",
    "campaign_name": "Νύχτες της Θεσσαλονίκης",
    "attributes": {"strength": 1, "dexterity": 2, "stamina": 2, "charisma": 2, "manipulation": 3,
                   "composure": 3, "intelligence": 4, "wits": 2, "resolve": 3},
    "skills": {
        "physical": {"athletics": 0, "brawl": 0, "craft": 0, "drive": 0, "firearms": 0, "larceny": 0,
                     "melee": 0, "stealth": 0, "survival": 0},
        "social": {"animal_ken": 0, "etiquette": 3, "insight": 2, "intimidation": 0, "leadership": 0,
                   "performance": 0, "persuasion": 2, "streetwise": 2, "subterfuge": 1},
        "mental": {"academics": 4, "awareness": 1, "finance": 0, "investigation": 3, "medicine": 0,
                   "occult": 3, "politics": 0, "science": 0, "technology": 1},
        "specialties": [{"skill": "academics", "name": "Byzantine history"},
                        {"skill": "streetwise", "name": "Black Market", "source": "predator"}],
    },
    "merits_flaws": {"notes": "Bane Severity 2"},
    "background": "Ο Βυζαντινολόγος.\nTremere scholar.",
    "wod_meta": {
        "edition": "v5", "concept": "Byzantine scholar", "clan": "Tremere", "generation": 13,
        "predator_type": "Bagger", "ambition": "Secure the archive", "desire": "Find the forger",
        "hunger": 2, "humanity": 7, "stains": 1, "blood_potency": 1,
        "health": {"max": 5, "superficial": 1, "aggravated": 0},
        "willpower": {"max": 6, "superficial": 2, "aggravated": 1},
        "disciplines": [
            {"name": "Blood Sorcery", "level": 3, "powers": ["Corrosive Vitae", "A Taste for Blood", "Extinguish Vitae"]},
            {"name": "Dominate", "level": 2, "powers": ["Cloud Memory", "Mesmerize"]},
            {"name": "Auspex", "level": 1, "powers": ["Heightened Senses"]},
        ],
        "touchstones": [{"name": "Δήμητρα, a conservator", "conviction": "Never destroy knowledge."}],
        "chronicle_tenets": "Do not kill.",
        "advantages": [{"name": "Haven", "dots": 2, "kind": "background"}],
        "flaws": [{"name": "Enemy", "dots": 2, "kind": "flaw"}],
        "rituals": [{"name": "Ward against Ghouls", "level": 1}, {"name": "Θυρεός του Αίματος", "level": 2}],
        "experience": {"total": 25, "spent": 15, "unspent": 10,
                       "log": [{"date": "2026-09-20", "amount": 10, "note": "Session 1"}]},
    },
}

CLASSIC_CHAR = {
    "id": 8, "name": "Theodore Doukas", "system_type": "vampire", "rules_edition": "classic",
    "campaign_name": "Byzantium by Night",
    "attributes": {"strength": 2, "dexterity": 2, "stamina": 2, "charisma": 4, "manipulation": 4,
                   "appearance": 2, "perception": 3, "intelligence": 3, "wits": 2},
    "skills": {"talents": {"leadership": 3, "subterfuge": 3}, "skills": {"etiquette": 3},
               "knowledges": {"politics": 3},
               "custom": {"knowledges": [{"key": "theology", "label": "Θεολογία", "dots": 2}]}},
    "merits_flaws": {"entries": [{"name": "Eidetic Memory", "points": 2}], "notes": "Owes a boon."},
    "background": "A logothete of the imperial treasury.",
    "wod_meta": {"clan": "Ventrue", "generation": "12", "nature": "Architect", "demeanor": "Director",
                 "concept": "Imperial logothete",
                 "disciplines": [{"name": "Dominate", "dots": 2}, {"name": "Presence", "dots": 1}],
                 "backgrounds": [{"name": "Resources", "dots": 3}],
                 "virtues": {"conscience": 3, "self_control": 4, "courage": 3}, "humanity": 7, "willpower": 3},
}


# --- a small PDF reader (reportlab output only; no pypdf in the unit job) -----------------------

def _objects(pdf: bytes):
    return re.findall(rb"\n(\d+) 0 obj\s*(.*?)endobj", pdf, re.S)


def _decode_stream(header: bytes, data: bytes) -> bytes:
    for f in re.findall(rb"/(ASCII85Decode|FlateDecode)", header):
        if f == b"ASCII85Decode":
            data = data.strip()
            data = base64.a85decode(data[:-2] if data.endswith(b"~>") else data)
        else:
            data = zlib.decompress(data)
    return data


def _content_streams(pdf: bytes):
    for _, body in _objects(pdf):
        m = re.match(rb"(.*?)stream\r?\n(.*?)\r?\n?endstream", body, re.S)
        if not m or b"/Length1" in m.group(1) or b"/Image" in m.group(1) or b"CMap" in m.group(1):
            continue
        yield _decode_stream(m.group(1), m.group(2))


def _pdf_string(raw: bytes) -> str:
    out = bytearray()
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == 0x5C:  # backslash
            nxt = raw[i + 1:i + 2]
            if nxt.isdigit():
                j = i + 1
                while j < len(raw) and j < i + 4 and raw[j:j + 1].isdigit():
                    j += 1
                out.append(int(raw[i + 1:j], 8))
                i = j
                continue
            out += {b"n": b"\n", b"r": b"\r", b"t": b"\t"}.get(nxt, nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    b = bytes(out)
    return b[2:].decode("utf-16-be") if b.startswith(b"\xfe\xff") else b.decode("latin-1")


_STR = rb"\(((?:\\.|[^\\)])*)\)"


def _fields(pdf: bytes):
    """{name: value} for every widget; checkboxes give 'Yes'/'Off'."""
    out = {}
    for _, body in _objects(pdf):
        if b"/Subtype /Widget" not in body:
            continue
        t = re.search(rb"/T " + _STR, body)
        v = re.search(rb"/V (?:" + _STR + rb"|/(\w+))", body)
        out[_pdf_string(t.group(1))] = _pdf_string(v.group(1)) if v.group(1) is not None else v.group(2).decode()
    return out


def _widgets(pdf: bytes):
    return [body for _, body in _objects(pdf) if b"/Subtype /Widget" in body]


def _long_text(f, key):
    """A Background or Notes field and its 'continued' parts (key.cont1, key.cont2...), one text."""
    parts = [f.get(key, "")]
    i = 1
    while f"{key}.cont{i}" in f:
        parts.append(f[f"{key}.cont{i}"])
        i += 1
    return " ".join(" ".join(parts).split())


# --- the document --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def v5_pdf():
    return build_sheet_pdf(V5_CHAR, player_name="lef")


@pytest.fixture(scope="module")
def classic_pdf():
    return build_sheet_pdf(CLASSIC_CHAR, player_name="lef")


def test_valid_two_page_pdfs(v5_pdf, classic_pdf):
    for pdf in (v5_pdf, classic_pdf):
        assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
        assert len(re.findall(rb"/Type /Page\b", pdf)) == 2
        assert b"/AcroForm" in pdf
        assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in pdf  # A4 by default


def test_letter_paper():
    pdf = build_sheet_pdf(V5_CHAR, paper="letter")
    assert b"/MediaBox [ 0 0 612 792 ]" in pdf


def test_v5_fields_prefilled(v5_pdf):
    f = _fields(v5_pdf)
    assert len(_widgets(v5_pdf)) == len(f) > 300  # every field has a unique name
    assert f["name"] == GREEK_NAME
    assert f["chronicle"] == "Νύχτες της Θεσσαλονίκης"
    assert f["clan"] == "Tremere" and f["predator_type"] == "Bagger" and f["generation"] == "13"
    assert f["touchstone1"] == "Δήμητρα, a conservator"
    assert f["skill.academics.specialty"] == "Byzantine history"
    # dots: Intelligence 4 of 5, Academics 4, Blood Sorcery 3
    assert [f[f"attr.intelligence.{i}"] for i in range(1, 6)] == ["Yes"] * 4 + ["Off"]
    assert [f[f"skill.academics.{i}"] for i in range(1, 6)] == ["Yes"] * 4 + ["Off"]
    assert f["disc1.name"] == "Blood Sorcery" and [f[f"disc1.{i}"] for i in range(1, 6)].count("Yes") == 3
    assert f["disc2.name"] == "Dominate" and f["disc3.name"] == "Auspex"
    assert f["disc1.power1"] == "Corrosive Vitae" and f["disc3.power1"] == "Heightened Senses"
    # trackers
    assert [f[f"humanity.{i}"] for i in range(1, 11)].count("Yes") == 7
    assert f["stains.10"] == "Yes" and f["stains.9"] == "Off"
    assert [f[f"hunger.{i}"] for i in range(1, 6)].count("Yes") == 2
    assert f["health.superficial.1"] == "Yes" and f["health.superficial.2"] == "Off"
    assert f["willpower.aggravated.1"] == "Yes"
    # rituals + XP
    assert f["ritual1.name"] == "Ward against Ghouls" and f["ritual2.name"] == "Θυρεός του Αίματος"
    assert [f[f"ritual2.{i}"] for i in range(1, 6)].count("Yes") == 2
    assert (f["xp.total"], f["xp.spent"], f["xp.unspent"]) == ("25", "15", "10")
    assert "Session 1" in f["xp.log"]
    assert f["background"].startswith("Ο Βυζαντινολόγος")


def test_v5_without_rituals_or_xp():
    ch = copy.deepcopy(V5_CHAR)
    del ch["wod_meta"]["rituals"], ch["wod_meta"]["experience"]
    f = _fields(build_sheet_pdf(ch))
    assert not any(k.startswith("ritual") for k in f)
    assert "xp.log" not in f
    assert f["xp.total"] == "" and f["xp.spent"] == ""


def test_classic_fields_prefilled(classic_pdf):
    f = _fields(classic_pdf)
    assert f["name"] == "Theodore Doukas" and f["player"] == "lef" and f["chronicle"] == "Byzantium by Night"
    assert f["clan"] == "Ventrue" and f["generation"] == "12" and f["nature"] == "Architect"
    assert [f[f"attr.charisma.{i}"] for i in range(1, 6)].count("Yes") == 4
    assert [f[f"talents.leadership.{i}"] for i in range(1, 6)].count("Yes") == 3
    assert f["knowledges.custom1.name"] == "Θεολογία"
    assert f["disc1.name"] == "Dominate" and f["bg1.name"] == "Resources"
    assert [f[f"virtue.self_control.{i}"] for i in range(1, 6)].count("Yes") == 4
    assert f["path.name"] == "Humanity" and [f[f"path.{i}"] for i in range(1, 11)].count("Yes") == 7
    assert [f[f"willpower.{i}"] for i in range(1, 11)].count("Yes") == 3
    # 12th generation: blood pool 11, 1 per turn
    assert f["blood.max"] == "11" and f["blood.per_turn"] == "1"
    assert [f[f"blood.r{r}.{i}"] for r in (1, 2) for i in range(1, 11)].count("Yes") == 11
    assert f["merit1.name"] == "Eidetic Memory" and f["merit1.cost"] == "+2"
    assert f["health.1"] == "Off"


@pytest.mark.parametrize("line,key", [("werewolf", "rage"), ("mage", "arete")])
def test_classic_other_lines(line, key):
    ch = {"name": "X", "system_type": line, "rules_edition": "classic",
          "wod_meta": {"rage": 3, "gnosis": 2, "arete": 1, "spheres": {"forces": 2}}}
    f = _fields(build_sheet_pdf(ch))
    assert f[f"{key}.1"] == "Yes"
    if line == "mage":
        assert f["sphere.forces.2"] == "Yes"


def _rects(pdf: bytes):
    for w in _widgets(pdf):
        m = re.search(rb"/Rect \[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]", w)
        yield [float(v) for v in m.groups()]


@pytest.mark.parametrize("paper,height", [("a4", 841.89), ("letter", 792.0)])
def test_v5_crowded_sheet_stays_on_two_pages(paper, height):
    """Long lists give up rows rather than run off the page; what has no row goes to Notes."""
    ch = copy.deepcopy(V5_CHAR)
    wm = ch["wod_meta"]
    wm["advantages"] = [{"name": f"Advantage {i}", "dots": 1 + i % 5} for i in range(15)]
    wm["flaws"] = [{"name": f"Flaw {i}", "dots": 1} for i in range(9)]
    wm["touchstones"] = [{"name": f"Touchstone {i}", "conviction": f"Conviction {i}"} for i in range(8)]
    wm["rituals"] = [{"name": f"Ritual {i}", "level": 1 + i % 5} for i in range(14)]
    wm["experience"]["log"] = [{"date": "2026-10-01", "amount": 3, "note": f"Session {i}"} for i in range(30)]
    wm["disciplines"] = [{"name": f"Discipline {i}", "level": 2, "powers": list("abcdefgh")} for i in range(8)]
    pdf = build_sheet_pdf(ch, paper=paper)
    assert len(re.findall(rb"/Type /Page\b", pdf)) == 2
    for x0, y0, x1, y1 in _rects(pdf):
        assert 24 <= y0 < y1 <= height - 24, (y0, y1)
    f = _fields(pdf)
    notes = f["notes"]
    shown_adv = sum(1 for k in f if re.fullmatch(r"adv\d+\.name", k))
    assert all(f"Advantage {i}" in notes for i in range(shown_adv, 15))
    assert "Touchstone 7" in notes
    rituals = {v for k, v in f.items() if re.fullmatch(r"ritual\d+\.name", k)}
    assert all(f"Ritual {i}" in rituals or f"Ritual {i} (" in notes for i in range(14))
    assert "Bane Severity 2" in notes
    # a discipline's extra powers share its last line
    last = max(int(m.group(1)) for k in f if (m := re.fullmatch(r"disc1\.power(\d+)", k)))
    assert f[f"disc1.power{last}"].endswith("; h")


# --- hostile or odd sheets never break the export -------------------------------------------

BAD_NUMBERS = [float("inf"), float("nan"), "1e400", 10 ** 400, -float("inf"), "x", None, [], {}]


def _numbers(ch):
    """Every number on the sheet replaced with something that isn't one."""
    def walk(v, i=[0]):
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            i[0] += 1
            return BAD_NUMBERS[i[0] % len(BAD_NUMBERS)]
        return v
    ch = walk(copy.deepcopy(ch))
    ch["wod_meta"]["experience"] = {"total": float("inf"), "spent": "1e400", "unspent": float("nan")}
    ch["wod_meta"]["generation"] = "1e400"
    return ch


def _text(ch):
    ch = copy.deepcopy(ch)
    bad = "Ζ\ud800ω\x00\x07\x1b\x7f\r\nend\udfff"
    ch["name"] = "Κων\ud83dσταντίνος\x00"
    ch["background"] = bad
    wm = ch["wod_meta"]
    wm["concept"] = bad
    wm["disciplines"] = [{"name": bad, "level": 2, "powers": [bad, {"name": bad, "level": "\x00"}]}]
    wm["touchstones"] = [{"name": bad, "conviction": bad}]
    wm["rituals"] = [{"name": bad, "level": 1}, bad]
    return ch


def _lists(ch):
    ch = copy.deepcopy(ch)
    wm = ch["wod_meta"]
    many = [{"name": f"Entry {i}", "dots": i % 6, "level": i % 6, "powers": [f"P{j}" for j in range(30)]}
            for i in range(3000)]
    for k in ("disciplines", "advantages", "flaws", "backgrounds", "rituals"):
        wm[k] = copy.deepcopy(many)
    wm["touchstones"] = [{"name": f"T{i}", "conviction": f"C{i}"} for i in range(3000)]
    wm["thin_blood_flaws"] = [f"Flaw {i}" for i in range(500)]
    wm["experience"] = {"total": 1, "log": [{"note": f"n{i}", "amount": 1} for i in range(3000)]}
    ch["merits_flaws"] = {"entries": [{"name": f"M{i}", "points": i % 7 - 3} for i in range(3000)]}
    ch["skills"] = dict(ch.get("skills") or {})
    ch["skills"]["specialties"] = [{"skill": "academics", "name": f"S{i}"} for i in range(3000)]
    ch["skills"]["custom"] = {c: [{"key": f"k{i}", "label": f"Custom {i}", "dots": 2} for i in range(500)]
                              for c in ("talents", "skills", "knowledges")}
    return ch


def _huge(ch):
    ch = copy.deepcopy(ch)
    big = ("Κείμενο με ελληνικά and English words. " * 30 + "\n") * 1000  # ~1.2 MB of UTF-8
    ch["background"] = big
    ch["name"] = "Κωνσταντίνος " * 800
    ch["merits_flaws"] = {"notes": big}
    ch["skills"] = dict(ch.get("skills") or {}, notes=big)
    wm = ch["wod_meta"]
    for k in ("concept", "ambition", "desire", "clan", "sire", "chronicle_tenets", "nature", "weakness"):
        wm[k] = big[:100000]
    return ch


@pytest.mark.parametrize("base", [V5_CHAR, CLASSIC_CHAR], ids=["v5", "classic"])
@pytest.mark.parametrize("mangle", [_numbers, _text, _lists, _huge], ids=lambda f: f.__name__.strip("_"))
@pytest.mark.parametrize("paper", ["a4", "letter"])
def test_never_raises(base, mangle, paper):
    import time

    ch = mangle(base)
    t = time.monotonic()
    pdf = build_sheet_pdf(ch, paper=paper)
    took = time.monotonic() - t
    # long Background / Notes go on over continuation pages
    assert pdf.startswith(b"%PDF-") and len(re.findall(rb"/Type /Page\b", pdf)) >= 2
    assert took < 2.0 and len(pdf) < 3_000_000, (took, len(pdf))
    height = 841.89 if paper == "a4" else 792.0
    for x0, y0, x1, y1 in _rects(pdf):
        assert 24 <= y0 < y1 <= height - 24
    f = _fields(pdf)
    for v in f.values():
        assert not re.search(r"[\x00-\x09\x0b-\x1f\x7f\ud800-\udfff]", v), repr(v[:80])
        assert len(v) <= 20000
    if mangle is _text:
        assert f["name"] == "Κων\ufffdσταντίνος" and f["background"] == "Ζ\ufffdω\nend\ufffd"
    if mangle is _huge:
        assert _long_text(f, "background").endswith("…") and len(f["name"]) <= 500
        assert len(_long_text(f, "background")) <= 40000


def test_classic_overflow_goes_to_notes():
    ch = copy.deepcopy(CLASSIC_CHAR)
    wm = ch["wod_meta"]
    wm["disciplines"] = [{"name": f"Disc {i}", "dots": 1} for i in range(12)]
    wm["backgrounds"] = [{"name": f"Bg {i}", "dots": 2} for i in range(11)]
    wm["rituals"] = [{"name": f"Rite {i}", "level": 1} for i in range(60)]
    ch["skills"]["custom"] = {"knowledges": [{"key": f"k{i}", "label": f"Lore {i}", "dots": 1} for i in range(6)]}
    ch["skills"]["notes"] = "Ability notes here"
    ch["merits_flaws"]["entries"] = [{"name": f"Merit {i}", "points": 1} for i in range(30)]
    for paper, height in (("a4", 841.89), ("letter", 792.0)):
        pdf = build_sheet_pdf(ch, paper=paper)
        for x0, y0, x1, y1 in _rects(pdf):
            assert 24 <= y0 < y1 <= height - 24
        f = _fields(pdf)
        notes = _long_text(f, "notes")
        assert "Owes a boon." in notes and "Ability notes here" in notes
        assert "More disciplines: Disc 9 (1); Disc 10 (1); Disc 11 (1)" in notes
        assert "Bg 10 (2)" in notes
        assert "Lore 5 (1)" in notes and f["knowledges.custom3.name"] == "Lore 2"
        shown = {v for k, v in f.items() if re.fullmatch(r"merit\d+\.name", k) and v}
        assert all(f"Merit {i}" in shown or f"Merit {i} (+1)" in notes for i in range(30))
        rites = {v for k, v in f.items() if re.fullmatch(r"ritual\d+\.name", k) and v}
        assert 2 <= len(rites) < 60
        assert all(f"Rite {i}" in rites or f"Rite {i} (1)" in notes for i in range(60))


def test_v5_age_player_and_thin_blood():
    ch = copy.deepcopy(V5_CHAR)
    ch["wod_meta"].update(age="neonate", clan="Thin-Blood", thin_blood_flaws=["Baby Teeth"],
                          thin_blood_merits=["Day Drinker"])
    f = _fields(build_sheet_pdf(ch, player_name="lef"))
    assert f["age"] == "neonate" and f["player"] == "lef"
    assert f["flaw2.name"] == "Baby Teeth (thin-blood)" and f["adv2.name"] == "Day Drinker (thin-blood)"


def test_v5_many_disciplines_listed_under_notes():
    ch = copy.deepcopy(V5_CHAR)
    ch["wod_meta"]["disciplines"] = [{"name": f"Disc {i}", "level": 1, "powers": [f"Power {i}"]} for i in range(11)]
    f = _fields(build_sheet_pdf(ch, paper="letter"))
    boxes = sum(1 for k in f if re.fullmatch(r"disc\d+\.name", k))
    assert boxes <= 9
    assert all(f"Disc {i} (1): Power {i}" in f["notes"] for i in range(boxes, 11))


def test_tabs_become_spaces():
    ch = copy.deepcopy(V5_CHAR)
    ch["background"] = "Sire\tΘεόδωρος"
    assert _fields(build_sheet_pdf(ch))["background"] == "Sire Θεόδωρος"


def test_form_resources_hold_both_fonts(v5_pdf):
    dr = re.search(rb"/DR << /Font << /Helv (\d+) 0 R /ZaDb \d+ 0 R >> >>", v5_pdf)
    assert dr, "one /Font dictionary with Helvetica and ZapfDingbats"
    helv = dict(_objects(v5_pdf))[dr.group(1)]
    assert b"/BaseFont /Helvetica" in helv and b"/WinAnsiEncoding" in helv and b"/Subtype /Type1" in helv
    assert b"/SRG" not in v5_pdf
    assert re.search(rb"/AcroForm.*?/DA \(/Helv 0 Tf 0 g\)", v5_pdf, re.S) or b"/DA (/Helv 0 Tf 0 g)" in v5_pdf
    assert b"/DA (/ZaDb 0 Tf 0 g)" in v5_pdf


def test_fields_are_editable(v5_pdf):
    for w in _widgets(v5_pdf):
        ff = re.search(rb"/Ff (\d+)", w)
        assert not ff or not int(ff.group(1)) & 1, "read-only field"
        if b"/FT /Btn" in w:  # toggles between an empty and a marked appearance
            assert re.search(rb"/N <<\s*/Off \d+ 0 R /Yes \d+ 0 R", w)
        else:
            assert b"/DA (/Helv " in w  # Acrobat can redraw edits with Helvetica, not with a custom-encoded TrueType


def test_black_and_white_only(v5_pdf, classic_pdf):
    ops = re.compile(rb"((?:-?\d*\.?\d+\s+){1,4})(rg|RG|k|K|g|G|sc|SC|scn|SCN)(?=\s)")
    seen = 0
    for pdf in (v5_pdf, classic_pdf, build_sheet_pdf(V5_CHAR, catalog=REF_CATALOG, lang="el")):
        for s in _content_streams(pdf):
            for m in ops.finditer(s):
                seen += 1
                vals = {float(x) for x in m.group(1).split()}
                assert vals <= {0.0, 1.0}, m.group(0)
                if m.group(2) in (b"rg", b"RG"):
                    assert len(set(m.group(1).split())) == 1, m.group(0)  # grey-free RGB: black or white
        for w in _widgets(pdf):
            assert b"/BG" not in w and b"/BC" not in w
    assert seen > 10


def test_greek_text_in_page_content(v5_pdf):
    # the footer is page text (not a field): drawn with EB Garamond and mapped back to Unicode
    assert v5_pdf.count(b"/ToUnicode") >= 2


def test_safe_filename():
    assert safe_filename(GREEK_NAME) == GREEK_NAME
    assert safe_filename('a/b\\c:"d"') == "a b c d"
    assert safe_filename("  ..  ") == "character"


# --- the V5 Reference page ------------------------------------------------------------------

def _d(en, el=None):
    return {"en": en, "el": el} if el else {"en": en}


# the shape of services/v5_catalog.load_catalog(); V5_CHAR matches most of it
REF_CATALOG = {
    "books": [{"book_id": "v5-corebook", "title": "Vampire: The Masquerade Corebook (2019)"},
              {"book_id": "v5-cults-of-the-blood-gods", "title": "Cults of the Blood Gods"}],
    "clans": [
        {"id": "clan:tremere", "name": "Tremere", "book": "v5-corebook", "page": 75,
         "desc": _d("Warlocks of a broken pyramid.", "Μάγοι μιας σπασμένης πυραμίδας."),
         "bane": {"name": "Deficient Blood", "page": 76, "desc": _d("Their Blood Bonds are weak.")},
         "compulsion": {"name": "Perfectionism", "book": "v5-corebook", "page": 77,
                        "desc": _d("Nothing but perfection will do.", "Μόνο το τέλειο αρκεί.")}},
        {"id": "clan:caitiff", "name": "Caitiff", "book": "v5-corebook", "page": 105, "desc": _d("Clanless."),
         "bane": None, "compulsion": None},
    ],
    "predator_types": [{"id": "predator:bagger", "name": "Bagger", "book": "v5-corebook", "page": 176,
                        "desc": _d("Feeds on bagged blood.", "Πίνει από σακούλες αίματος.")}],
    "disciplines": [
        {"id": "discipline:auspex", "name": "Auspex", "powers": [
            {"id": "power:auspex:heightened-senses", "name": "Heightened Senses", "level": 1,
             "book": "v5-corebook", "page": 249, "desc": _d("Sharper senses.", "Οξύτερες αισθήσεις.")}]},
        {"id": "discipline:blood-sorcery", "name": "Blood Sorcery", "powers": [
            {"id": "power:blood-sorcery:corrosive-vitae", "name": "Corrosive Vitae", "level": 1,
             "book": "v5-corebook", "page": 272,
             "desc": _d("Blood that eats through matter.", "Ψυχρό αίμα που ξεφτίζει την ύλη.")},
            {"id": "power:blood-sorcery:a-taste-for-blood", "name": "A Taste for Blood", "level": 1,
             "aliases": ["Taste for Blood"], "book": "v5-corebook", "page": 272, "desc": _d("Taste and know.")}]},
    ],
    "rituals": [{"id": "ritual:ward-against-ghouls", "name": "Ward against Ghouls", "level": 2,
                 "book": "v5-cults-of-the-blood-gods", "page": 9, "desc": _d("Wards a place against ghouls.")}],
    "ceremonies": [{"id": "ceremony:summon-spirit", "name": "Summon Spirit", "level": 1,
                    "book": "v5-players-guide", "page": 92, "desc": _d("Calls a wraith.")}],
    "formulae": [{"id": "formula:far-reach", "name": "Far Reach", "level": 1, "book": "v5-corebook",
                  "page": 284, "desc": _d("Telekinesis.")}],
}


def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type /Page\b", pdf))


def _entries(items):
    return [o for k, o in items if k == "entry"]


def test_reference_lists_matches_only():
    items = v5_reference(V5_CHAR, REF_CATALOG, "en")
    assert [(k, o if k != "entry" else o["name"]) for k, o in items] == [
        ("section", "Clan"), ("entry", "Tremere"), ("entry", "Deficient Blood"), ("entry", "Perfectionism"),
        ("section", "Predator Type"), ("entry", "Bagger"),
        ("section", "Discipline Powers"), ("group", "Blood Sorcery"), ("entry", "Corrosive Vitae"),
        ("entry", "A Taste for Blood"), ("group", "Auspex"), ("entry", "Heightened Senses"),
        ("section", "Rituals"), ("entry", "Ward against Ghouls"),
    ]  # no Extinguish Vitae, Cloud Memory, Mesmerize or Θυρεός του Αίματος: not in the catalog
    clan, bane, compulsion, _, corrosive = _entries(items)[:5]
    assert clan == {"name": "Tremere", "prefix": "", "level": 0, "desc": "Warlocks of a broken pyramid.",
                    "ref": "Corebook, p. 75", "credit": ""}
    assert bane["prefix"] == "Bane" and bane["ref"] == "Corebook, p. 76"  # the clan's book
    assert compulsion["prefix"] == "Compulsion" and compulsion["ref"] == "Corebook, p. 77"
    assert corrosive["level"] == 1 and corrosive["ref"] == "Corebook, p. 272"
    assert _entries(items)[-1]["ref"] == "Cults of the Blood Gods, p. 9"  # no short name: the title


def test_reference_language_falls_back_to_english():
    el = _entries(v5_reference(V5_CHAR, REF_CATALOG, "el"))
    assert el[0]["desc"] == "Μάγοι μιας σπασμένης πυραμίδας."
    assert el[1]["desc"] == "Their Blood Bonds are weak."  # no Greek text yet
    assert el[0]["name"] == "Tremere"  # names stay as in the books
    for lang in ("fr", "", None):
        assert _entries(v5_reference(V5_CHAR, REF_CATALOG, lang))[0]["desc"] == "Warlocks of a broken pyramid."


def test_reference_matches_ids_aliases_and_kinds():
    ch = copy.deepcopy(V5_CHAR)
    wm = ch["wod_meta"]
    wm.update(clan="Unknown", clan_id="clan:tremere", predator_type=" bagger ")
    wm["disciplines"] = [
        {"name": "Auspex", "level": 2, "powers": [
            {"id": "power:blood-sorcery:corrosive-vitae", "name": "Old name", "level": 1},  # by id
            "taste  FOR blood",  # alias, case and spaces ignored
            "Heightened Senses (1)",  # level written into the name
            "Heightened Senses",  # listed once
            "Homebrew Power", {"name": None}, 7, None]},
        {"name": "Not a Discipline", "powers": "Heightened Senses"},
    ]
    wm["rituals"] = ["Far Reach", {"name": "Summon Spirit", "kind": "ceremony"}, {"name": "Ward against Ghouls"},
                     {"name": "Nope", "kind": "ritual"}]
    items = v5_reference(ch, REF_CATALOG, "en")
    names = [o if k != "entry" else o["name"] for k, o in items]
    assert names == ["Clan", "Tremere", "Deficient Blood", "Perfectionism", "Predator Type", "Bagger",
                     "Discipline Powers", "Blood Sorcery", "Corrosive Vitae", "A Taste for Blood",
                     "Auspex", "Heightened Senses",
                     "Rituals", "Ward against Ghouls", "Ceremonies", "Summon Spirit", "Formulae", "Far Reach"]
    caitiff = copy.deepcopy(V5_CHAR)
    caitiff["wod_meta"].update(clan="caitiff", predator_type="", disciplines=[], rituals=[])
    assert [o["name"] for o in _entries(v5_reference(caitiff, REF_CATALOG))] == ["Caitiff"]  # no bane


def test_reference_page_after_the_sheet():
    plain = build_sheet_pdf(V5_CHAR, player_name="lef")
    pdf = build_sheet_pdf(V5_CHAR, player_name="lef", catalog=REF_CATALOG, lang="el")
    assert _pages(plain) == 2 and _pages(pdf) == 3
    assert _fields(pdf) == _fields(plain)  # page text only: no new fields
    for x0, y0, x1, y1 in _rects(pdf):
        assert 24 <= y0 < y1 <= 841.89 - 24


@pytest.mark.parametrize("catalog", [None, {}, {"clans": [], "disciplines": "x", "rituals": [None, 3]},
                                     {k: [] for k in REF_CATALOG}])
def test_no_reference_page_without_matches(catalog):
    pdf = build_sheet_pdf(V5_CHAR, catalog=catalog, lang="el")
    assert _pages(pdf) == 2
    nothing = copy.deepcopy(V5_CHAR)
    nothing["wod_meta"].update(clan="Homebrew", predator_type="Homebrew", disciplines=[{"name": "X", "powers": ["Y"]}],
                               rituals=["Z"])
    assert _pages(build_sheet_pdf(nothing, catalog=REF_CATALOG)) == 2
    assert v5_reference(nothing, REF_CATALOG) == []


def test_classic_sheet_never_gets_a_reference_page():
    ch = copy.deepcopy(CLASSIC_CHAR)
    ch["wod_meta"]["clan"] = "Tremere"
    assert _pages(build_sheet_pdf(ch, catalog=REF_CATALOG, lang="el")) == 2


def _embedded_chars(pdf: bytes, font: str) -> set:
    """Characters the subset ToUnicode maps of a font hold (what its page text can show)."""
    out = set()
    for _, body in _objects(pdf):
        m = re.match(rb"(.*?)stream\r?\n(.*?)\r?\n?endstream", body, re.S)
        if not m or b"/Length1" in m.group(1):
            continue
        data = _decode_stream(m.group(1), m.group(2))
        if b"begincmap" in data and re.search(rb"/Registry \(\w+\+" + font.encode() + rb"\)", data):
            out |= {chr(int(u, 16)) for u in re.findall(rb"<[0-9A-F]{2}> <([0-9A-F]{4})>", data)}
    return out


def test_reference_greek_is_embedded():
    from reportlab.pdfbase import pdfmetrics

    greek = set("Ψυχρό αίμα που ξεφτίζει την ύλη.") - set(" .")
    en = _embedded_chars(build_sheet_pdf(V5_CHAR, catalog=REF_CATALOG, lang="en"), "EBGaramond-Regular")
    el = _embedded_chars(build_sheet_pdf(V5_CHAR, catalog=REF_CATALOG, lang="el"), "EBGaramond-Regular")
    assert greek <= el  # every letter of the Greek description is drawn with the page font
    assert not {"Ψ", "ξ"} & en  # and those two come from the Reference page only
    assert all(ord(c) in pdfmetrics.getFont(SERIF).face.charToGlyph for c in greek)  # which has the glyphs


def test_installed_catalog_text_has_glyphs():
    """Every character of every description, name and book reference the catalog can put on the page."""
    from reportlab.pdfbase import pdfmetrics
    from services.v5_catalog import load_catalog

    catalog = load_catalog()
    if not catalog:
        pytest.skip("no V5 catalog installed")
    build_sheet_pdf(V5_CHAR)  # registers the fonts
    cover = {f: set(pdfmetrics.getFont(f).face.charToGlyph) for f in (SERIF, SERIF_ITALIC, CINZEL_BOLD)}
    seen = 0

    def check(e):
        nonlocal seen
        for text in (e.get("desc") or {}).values():
            assert not {c for c in text if ord(c) not in cover[SERIF]}, (e.get("id"), text)
            seen += 1
        assert not {c for c in e.get("name") or "" if ord(c) not in cover[CINZEL_BOLD]}, e.get("name")

    for kind in ("clans", "predator_types", "rituals", "ceremonies", "formulae", "disciplines", "advantages",
                 "loresheets"):
        for e in catalog[kind]:
            check(e)
            for sub in [e.get("bane"), e.get("compulsion"), *(e.get("powers") or []), *(e.get("levels") or [])]:
                if isinstance(sub, dict):
                    check(sub)
    for b in catalog["books"]:
        assert not {c for c in b["title"] + ", p. 0123456789()" if ord(c) not in cover[SERIF_ITALIC]}
    assert seen > 100


# Merits, Backgrounds, Flaws and loresheets (services/v5_catalog.py shape); V5_CHAR's Haven and Enemy
# are left out so the reference above stays as it is
BAHARI_LEVELS = ("Dangerous Reputation", "Ritual Scarification", "Sacrifice the Children", "The Womb's Blood",
                 "First-Cursed")
ADV_CATALOG = {
    **REF_CATALOG,
    "clans": [{**c, "caitiff": c["id"] == "clan:caitiff"} for c in REF_CATALOG["clans"]]
    + [{"id": "clan:thin-blood", "name": "Thin-blood", "thin_blood": True, "book": "v5-corebook", "page": 109,
        "desc": _d("Weak blood.")}],
    "advantages": [
        {"id": "background:allies", "name": "Allies", "kind": "background", "book": "v5-corebook", "page": 184,
         "desc": _d("Mortals who help you.", "Θνητοί που σε βοηθούν.")},
        {"id": "merit:iron-gullet", "name": "Iron Gullet", "kind": "merit", "book": "v5-corebook", "page": 179,
         "desc": _d("Drinks rancid blood.")},
        {"id": "flaw:suspect", "name": "Suspect", "kind": "flaw", "book": "v5-corebook", "page": 194,
         "desc": _d("Distrusted by the sect.")},
        {"id": "flaw:prey-exclusion", "name": "Prey Exclusion", "kind": "flaw", "book": "v5-corebook", "page": 179,
         "desc": _d("Won't feed on one group.")},
        {"id": "flaw:caitiff-clan-curse", "name": "Clan Curse", "kind": "flaw", "caitiff": True,
         "book": "v5-players-guide", "page": 105, "desc": _d("The Caitiff curse.")},
        {"id": "flaw:thin-blood-clan-curse", "name": "Clan Curse", "kind": "flaw", "thin_blood": True,
         "book": "v5-corebook", "page": 183, "desc": _d("The thin-blood curse.")},
        {"id": "merit:thin-blood-day-drinker", "name": "Day Drinker", "kind": "merit", "thin_blood": True,
         "book": "v5-corebook", "page": 182, "desc": _d("Walks in daylight.")},
    ],
    "loresheets": [{"id": "loresheet:the-bahari", "name": "The Bahari", "book": "v5-corebook", "page": 382,
                    "desc": _d("Followers of Lilith.", "Οπαδοί της Lilith."),
                    "levels": [{"dots": n, "name": nm, "desc": _d(f"Level {n} benefit.")}
                               for n, nm in enumerate(BAHARI_LEVELS, 1)]}],
}


def _advantage_sheet():
    ch = copy.deepcopy(V5_CHAR)
    ch["wod_meta"].update(
        clan="Thin-blood", predator_type="", disciplines=[], rituals=[],
        advantages=[{"id": "background:allies", "name": "Allies (police)", "dots": 2, "kind": "background"},
                    {"name": "Iron Gullet", "dots": 3, "kind": "merit"},
                    {"name": "Allies", "dots": 1, "kind": "background"},  # listed once
                    {"name": "Homebrew Patron", "dots": 1, "kind": "merit", "custom": True},
                    {"id": "loresheet:the-bahari", "name": "The Bahari", "dots": 4, "kind": "loresheet",
                     "levels": [3, 1]}],
        flaws=[{"id": "flaw:suspect", "name": "Suspect", "dots": 1, "kind": "flaw", "source": "clan"},
               {"name": "Prey Exclusion (locals)", "dots": 1, "kind": "predator"}],
        thin_blood_merits=["Day Drinker"], thin_blood_flaws=["Clan Curse"])
    return ch


def test_reference_advantages_and_loresheets():
    items = v5_reference(_advantage_sheet(), ADV_CATALOG, "el")
    start = items.index(("section", "Advantages"))
    names = [(k, o if k != "entry" else (o["prefix"], o["name"], o["level"])) for k, o in items[start:]]
    assert names == [
        ("section", "Advantages"), ("group", "Merits & Backgrounds"),
        ("entry", ("", "Allies", 0)), ("entry", ("", "Iron Gullet", 0)), ("entry", ("Thin-blood", "Day Drinker", 0)),
        ("group", "Flaws"),
        ("entry", ("", "Suspect", 0)), ("entry", ("", "Prey Exclusion", 0)), ("entry", ("Thin-blood", "Clan Curse", 0)),
        ("section", "Loresheets"),
        ("entry", ("", "The Bahari", 4)), ("entry", ("The Bahari", "Dangerous Reputation", 1)),
        ("entry", ("The Bahari", "Sacrifice the Children", 3)),
    ]  # no Homebrew Patron (custom), no levels 2, 4, 5
    by_name = {o["name"]: o for k, o in items if k == "entry"}
    assert by_name["Allies"]["desc"] == "Θνητοί που σε βοηθούν." and by_name["Allies"]["ref"] == "Corebook, p. 184"
    assert by_name["Clan Curse"]["desc"] == "The thin-blood curse."  # the thin-blood one, not the Caitiff one
    assert by_name["The Bahari"]["ref"] == "Corebook, p. 382"
    assert by_name["Sacrifice the Children"]["desc"] == "Level 3 benefit." and by_name["Sacrifice the Children"]["ref"] == ""


def test_reference_loresheet_levels_without_names():
    """An online-only sheet (the Anarch ones) has no English level names: the level reads "Level N"."""
    catalog = copy.deepcopy(ADV_CATALOG)
    catalog["loresheets"].append({"id": "loresheet:salvador-garcia", "name": "Salvador Garcia", "book": "v5-anarch",
                                  "page": 190, "levels": [{"dots": n, "name": None} for n in range(1, 6)]})
    ch = copy.deepcopy(V5_CHAR)
    ch["wod_meta"].update(advantages=[{"id": "loresheet:salvador-garcia", "name": "Salvador Garcia", "dots": 2,
                                       "kind": "loresheet", "levels": [2]}], flaws=[])
    entries = [(e["prefix"], e["name"], e["level"]) for e in _entries(v5_reference(ch, catalog))]
    assert ("Salvador Garcia", "Level 2", 2) in entries
    assert build_sheet_pdf(ch, catalog=catalog).startswith(b"%PDF-")


@pytest.mark.parametrize("lang,credit", [("en", "facts from vtm.paradoxwikis.com (CC BY-SA)"),
                                         ("el", "στοιχεία από το vtm.paradoxwikis.com (CC BY-SA)"),
                                         ("fr", "facts from vtm.paradoxwikis.com (CC BY-SA)")])
def test_reference_credits_wiki_facts(lang, credit):
    """An entry whose facts come from the Paradox wiki (source "online") credits it (CC BY-SA)."""
    catalog = copy.deepcopy(ADV_CATALOG)
    catalog["loresheets"].append({"id": "loresheet:salvador-garcia", "name": "Salvador Garcia", "book": "v5-anarch",
                                  "page": 190, "source": "online", "desc": _d("Ties to an Anarch."),
                                  "levels": [{"dots": n, "name": None} for n in range(1, 6)]})
    ch = copy.deepcopy(V5_CHAR)
    ch["wod_meta"].update(advantages=[
        {"id": "loresheet:salvador-garcia", "name": "Salvador Garcia", "dots": 2, "kind": "loresheet", "levels": [2]},
        {"id": "loresheet:the-bahari", "name": "The Bahari", "dots": 1, "kind": "loresheet", "levels": [1]}], flaws=[])
    by_name = {e["name"]: e for e in _entries(v5_reference(ch, catalog, lang))}
    assert by_name["Salvador Garcia"]["credit"] == credit
    assert by_name["The Bahari"]["credit"] == "" and by_name["Tremere"]["credit"] == ""  # book entries
    from reportlab.pdfbase import pdfmetrics

    assert build_sheet_pdf(ch, catalog=catalog, lang=lang).startswith(b"%PDF-")  # registers the fonts too
    assert credit in _ref_paragraph(by_name["Salvador Garcia"]).text
    assert "paradoxwikis" not in _ref_paragraph(by_name["The Bahari"]).text
    assert all(ord(c) in pdfmetrics.getFont(SERIF_ITALIC).face.charToGlyph for c in "· " + credit)


def test_reference_advantages_of_older_and_caitiff_sheets():
    ch = copy.deepcopy(V5_CHAR)
    ch["wod_meta"].update(clan="Caitiff", predator_type="", disciplines=[], rituals=[],
                          advantages=[{"name": "The Bahari", "dots": 3, "kind": "background"}],  # an imported sheet
                          flaws=[{"name": "Clan Curse", "dots": 2, "kind": "flaw"}])
    entries = _entries(v5_reference(ch, ADV_CATALOG))
    assert [(e["name"], e["level"], e["desc"]) for e in entries[1:]] == [
        ("Clan Curse", 0, "The Caitiff curse."), ("The Bahari", 0, "Followers of Lilith.")]  # no levels recorded


def test_reference_page_lists_advantages():
    ch = _advantage_sheet()
    assert _pages(build_sheet_pdf(ch)) == 2
    pdf = build_sheet_pdf(ch, catalog=ADV_CATALOG, lang="el")
    assert _pages(pdf) == 3
    assert set("Θνητοί που σε βοηθούν") - set(" ") <= _embedded_chars(pdf, "EBGaramond-Regular")


def _many_powers(n_disc=6, n_powers=12):
    catalog = copy.deepcopy(REF_CATALOG)
    long_el = "Μακροσκελής περιγραφή δύναμης με αρκετές λέξεις για να γεμίσει τη στήλη. " * 3
    catalog["disciplines"] = [
        {"id": f"discipline:d{i}", "name": f"Discipline {i}", "powers": [
            {"id": f"power:d{i}:p{j}", "name": f"Power {i}-{j}", "level": 1 + j % 5, "book": "v5-corebook",
             "page": 200 + j, "desc": _d(f"Long description {i}-{j}. " * 12, long_el)} for j in range(n_powers)]}
        for i in range(n_disc)]
    ch = copy.deepcopy(V5_CHAR)
    ch["wod_meta"]["disciplines"] = [{"name": f"Discipline {i}", "level": 5,
                                      "powers": [f"Power {i}-{j}" for j in range(n_powers)]} for i in range(n_disc)]
    return ch, catalog


@pytest.mark.parametrize("paper,height", [("a4", 841.89), ("letter", 792.0)])
def test_reference_overflows_onto_more_pages(paper, height):
    ch, catalog = _many_powers()
    sc = SheetCanvas(paper)
    items = v5_reference(ch, catalog, "el")
    pages = _layout_reference(sc, items)
    assert len(pages) >= 2
    pdf = build_sheet_pdf(ch, paper=paper, catalog=catalog, lang="el")
    assert _pages(pdf) == 2 + len(pages)
    top = sc.top - 38
    xs, cw = _columns(sc, 2, gap=22)
    for placed in pages:
        for kind, obj, x, y in placed:
            assert x in xs
            low = y - (obj.height if kind == "entry" else 15)
            assert sc.bottom - 0.01 <= low and y <= top + 0.01, (kind, y, low)
    # a section carried onto the next page says so, with its Discipline
    first = pages[1][:2]
    assert first[0][:2] == ("section", "Discipline Powers (cont.)") and first[1][0] == "group"
    # nothing lost or doubled: split parts add up to the whole entries, line for line
    want = sum(_ref_paragraph(e).wrap(cw, 10 ** 6)[1] for e in _entries(items))
    assert abs(sum(o.height for p in pages for k, o, _, _ in p if k == "entry") - want) < 0.01
    # the last page uses both columns, about evenly
    last = pages[-1]
    cols = {}
    for kind, obj, x, y in last:
        cols[x] = min(cols.get(x, top), y - (obj.height if kind == "entry" else 15))
    if len(last) > 4:
        assert len(cols) == 2 and abs(min(cols.values()) - max(cols.values())) < 120


@pytest.mark.parametrize("mangle", [_numbers, _text, _lists, _huge], ids=lambda f: f.__name__.strip("_"))
def test_reference_never_raises(mangle):
    import time

    ch = mangle(V5_CHAR)
    ch["wod_meta"]["disciplines"] = list(ch["wod_meta"].get("disciplines") or []) + [
        {"name": "Auspex", "powers": ["Heightened Senses"] * 2000}]
    bad = copy.deepcopy(REF_CATALOG)
    bad["clans"][0].update(page="1e400", book=None, desc=["x"], aliases="Tremere")
    bad["clans"][0]["bane"] = "Deficient Blood"
    bad["disciplines"].append({"name": None, "powers": [None, {"name": 5}, {"name": "X", "desc": {"el": 3}}]})
    bad["rituals"].append("Ward against Ghouls")
    t = time.monotonic()
    pdf = build_sheet_pdf(ch, catalog=bad, lang="el")
    assert time.monotonic() - t < 3.0
    assert pdf.startswith(b"%PDF-") and _pages(pdf) >= 2


# --- the route -----------------------------------------------------------------------------

@pytest.fixture
def api(monkeypatch):
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        pg.IntegrityError = type("IntegrityError", (Exception,), {})
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token
    from routes import characters

    roles = {"1": "admin", "2": "player", "3": "player", "4": "player"}  # 2 owns, 3 runs the chronicle
    langs = {"1": "EN", "2": "el", "3": None, "4": "el"}  # users.ui_language
    row = {
        "id": 9, "name": GREEK_NAME, "system_type": "vampire", "rules_edition": "v5",
        "attributes": "{}", "skills": "{}", "background": "", "merits_flaws": "{}",
        "wod_meta": '{"edition": "v5", "clan": "Tremere"}', "user_id": 2, "campaign_id": 5,
        "created_at": None, "updated_at": None, "owner_name": "lef", "campaign_name": "Νύχτες",
    }

    class Cur:
        def execute(self, sql, args):
            self.sql, self.args = sql, args

        def fetchone(self):
            if "FROM characters ch" in self.sql:
                return dict(row) if self.args[0] == 9 else None
            if "SELECT ui_language FROM users" in self.sql:
                return {"ui_language": langs[str(self.args[0])]}
            if "FROM users" in self.sql:
                return {"role": roles[str(self.args[0])]}
            if "FROM campaigns" in self.sql:
                return {"created_by": 3}
            if "sqlite_master" in self.sql:
                return None  # no character_moderation table: nobody has fallen
            raise AssertionError(self.sql)

        def close(self):
            pass

    class Conn:
        def cursor(self):
            return Cur()

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(characters, "get_db", lambda: Conn())
    monkeypatch.setattr(characters, "_ensure_character_schema", lambda cursor: None)
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(characters.bp, url_prefix="/api/characters")
    with app.app_context():
        tokens = {uid: create_access_token(identity=uid) for uid in roles}
    c = app.test_client()

    def get(url, uid):
        return c.get(url, headers={"Authorization": f"Bearer {tokens[uid]}"})

    return get


@pytest.mark.parametrize("uid", ["2", "3", "1"])  # owner, Storyteller, admin
def test_route_allows_owner_storyteller_admin(api, uid):
    r = api("/api/characters/9/sheet.pdf", uid)
    assert r.status_code == 200
    assert r.mimetype == "application/pdf" and r.data.startswith(b"%PDF-")
    cd = r.headers["Content-Disposition"]
    assert cd.startswith("attachment;") and "filename*=UTF-8''%CE%9A" in cd
    assert "no-store" in r.headers["Cache-Control"]


def test_route_hides_from_other_players(api):
    assert api("/api/characters/9/sheet.pdf", "4").status_code == 404
    assert api("/api/characters/77/sheet.pdf", "1").status_code == 404


def test_route_letter_paper(api):
    r = api("/api/characters/9/sheet.pdf?paper=letter", "2")
    assert b"/MediaBox [ 0 0 612 792 ]" in r.data
    r = api("/api/characters/9/sheet.pdf?paper=bogus", "2")
    assert b"/MediaBox [ 0 0 595.2756 841.8898 ]" in r.data


@pytest.mark.parametrize("uid,lang", [("2", "el"), ("3", "en"), ("1", "en")])  # unset -> en, 'EN' -> en
def test_route_reference_page_in_requester_language(api, monkeypatch, uid, lang):
    import services.character_sheet_pdf as pdf_mod
    from services import v5_catalog

    calls = []
    real = pdf_mod.build_sheet_pdf

    def spy(ch, **kw):
        calls.append(kw)
        return real(ch, **kw)

    monkeypatch.setattr(pdf_mod, "build_sheet_pdf", spy)
    monkeypatch.setattr(v5_catalog, "load_catalog", lambda: REF_CATALOG)
    r = api("/api/characters/9/sheet.pdf", uid)
    assert r.status_code == 200
    assert calls[-1]["lang"] == lang and calls[-1]["catalog"] is REF_CATALOG
    assert _pages(r.data) == 3  # the Tremere clan, bane and compulsion


@pytest.mark.parametrize("load", [lambda: None, lambda: (_ for _ in ()).throw(ValueError("bad catalog"))],
                         ids=["none", "broken"])
def test_route_without_catalog_keeps_two_pages(api, monkeypatch, load):
    from services import v5_catalog

    monkeypatch.setattr(v5_catalog, "load_catalog", load)
    r = api("/api/characters/9/sheet.pdf", "2")
    assert r.status_code == 200 and _pages(r.data) == 2


@pytest.mark.parametrize("uid,status", [("2", 200), ("3", 200), ("1", 200), ("4", 403)])
def test_sheet_json_follows_the_same_rule(api, uid, status):
    """GET /api/characters/<id>: owner, the chronicle's Storyteller and admins, like the PDF."""
    r = api("/api/characters/9", uid)
    assert r.status_code == status
    if status == 200:
        assert r.get_json()["character"]["name"] == GREEK_NAME


def test_can_view_character_sheet_rule():
    from services.playing_character import can_view_character_sheet

    class Cur:
        def execute(self, sql, args):
            self.sql, self.args = sql, args

        def fetchone(self):
            if "FROM users" in self.sql:
                return {"role": {1: "admin", 5: "helper"}.get(self.args[0], "player")}
            return {"created_by": 3} if self.args[0] == 7 else None

    ch = {"user_id": 2, "campaign_id": 7}
    assert [can_view_character_sheet(Cur(), u, ch) for u in (2, 3, 1, 5, 4)] == [True, True, True, True, False]
    assert not can_view_character_sheet(Cur(), 3, {"user_id": 2, "campaign_id": 8})  # not their chronicle
    assert not can_view_character_sheet(Cur(), 2, None)


# --- Background & Notes that run over their box -------------------------------------------

LONG_PARA = ("Darius filmed the raid from the roof across the street, then sold the footage before dawn. "
             "Ο Σερκάν τα κατέγραψε όλα από τη στέγη απέναντι. ") * 8


def _long_background(n=24):
    return "\n\n".join(f"{i}. {LONG_PARA}" for i in range(n))  # about 16 000 characters, like character 17's


@pytest.fixture
def page_text(monkeypatch):
    """Every string drawn as page text (labels upper-cased), in order."""
    seen = []
    real = SheetCanvas.text

    def spy(self, x, y, s, *a, **k):
        seen.append(s)
        return real(self, x, y, s, *a, **k)

    monkeypatch.setattr(SheetCanvas, "text", spy)
    return seen


@pytest.mark.parametrize("base", [V5_CHAR, CLASSIC_CHAR], ids=["v5", "classic"])
@pytest.mark.parametrize("paper,height", [("a4", 841.89), ("letter", 792.0)])
def test_a_long_background_goes_on_a_continued_page(base, paper, height, page_text):
    ch = copy.deepcopy(base)
    ch["background"] = _long_background()
    assert len(ch["background"]) > 15000
    pdf = build_sheet_pdf(ch, paper=paper)
    f = _fields(pdf)
    n = _pages(pdf)
    assert n >= 3
    # the box keeps the start, as a field; the rest is in background.cont1, .cont2...
    assert f["background"] and len(f["background"]) < 6000
    assert ch["background"].startswith(f["background"].split("\n")[0])
    assert "background.cont1" in f and "notes.cont1" not in f
    assert _long_text(f, "background") == " ".join(ch["background"].split())
    assert "BACKGROUND (CONTINUED ON P. 3)" in page_text
    assert "BACKGROUND & NOTES (CONTINUED)" in page_text and "BACKGROUND (CONTINUED)" in page_text
    assert f"2 / {n}" in page_text and f"{n} / {n}" in page_text
    for x0, y0, x1, y1 in _rects(pdf):
        assert 24 <= y0 < y1 <= height - 24


def test_long_notes_continue_after_the_background(page_text):
    ch = copy.deepcopy(V5_CHAR)
    ch["background"] = _long_background(12)
    ch["merits_flaws"]["notes"] = "Bane Severity 2.\n" + _long_background(10)
    f = _fields(build_sheet_pdf(ch))
    assert _long_text(f, "notes") == " ".join(ch["merits_flaws"]["notes"].split())
    assert _long_text(f, "background") == " ".join(ch["background"].split())
    assert any(t.startswith("NOTES (CONTINUED ON P. ") for t in page_text)


def test_text_that_fits_still_shrinks_into_the_box():
    ch = copy.deepcopy(V5_CHAR)
    ch["background"] = LONG_PARA[:500]  # fits, at a smaller size if need be
    pdf = build_sheet_pdf(ch)
    f = _fields(pdf)
    assert _pages(pdf) == 2 and "background.cont1" not in f
    assert f["background"] == " ".join(ch["background"].split()) or f["background"] == ch["background"].strip()


def test_continued_pages_come_before_the_reference(page_text):
    ch = copy.deepcopy(V5_CHAR)
    ch["background"] = _long_background()
    plain = _pages(build_sheet_pdf(ch))
    pdf = build_sheet_pdf(ch, catalog=REF_CATALOG)
    assert _pages(pdf) == plain + 1
    total = _pages(pdf)
    assert "REFERENCE" in page_text and f"{total} / {total}" in page_text
    assert page_text.count(f"1 / {total}") >= 1


def test_the_split_keeps_every_word():
    from services.character_sheet_pdf import _split_text

    text = "one two three\n\nfour five six seven eight nine ten " * 40
    head, tail = _split_text(text, 200, 60, 8.2)
    assert head and tail
    assert " ".join((head + " " + tail).split()) == " ".join(text.split())
    assert _split_text("short", 200, 60, 8.2) == ("short", "")


# --- a ghoul's sheet ----------------------------------------------------------------------

def _mira():
    from tests.unit.test_v5_ghoul_chargen import MIRA

    ch = {"id": 30, "name": "Mira Tanis", "system_type": "vampire", "rules_edition": "v5",
          **copy.deepcopy(MIRA), "background": "Πρώην στέλεχος της τηλεόρασης. Former television executive.",
          "merits_flaws": {"notes": "Resources 0: in debt."},
          "domitor": {"id": 17, "name": "Darius Vale", "clan": "Ventrue", "campaign_id": None,
                      "campaign_name": None, "exists": True}}
    return ch


def test_ghoul_sheet_fields(page_text):
    pdf = build_sheet_pdf(_mira(), player_name="adminator")
    assert _pages(pdf) == 2
    f = _fields(pdf)
    assert f["name"] == "Mira Tanis" and f["player"] == "adminator"
    assert f["ghoul.domitor"] == "Darius Vale" and f["ghoul.domitor_clan"] == "Ventrue"
    # '•' is 0x80 in a PDF text string (PDFDocEncoding); _pdf_string reads Latin-1
    assert f["ghoul.template"].replace("\x80", "•") == "Gifted mortal · Retainers •••" and f["ghoul.age"] == "55 / 53"
    assert f["power.discipline.name"] == "Dominate" and f["power.name"] == "Cloud Memory"
    assert [f[f"power.discipline.{i}"] for i in range(1, 6)] == ["Yes"] + ["Off"] * 4
    assert f["bond.regnant"] == "Darius Vale" and f["bond.flaws"] == "Bondslave · Two Masters"
    assert [f[f"bond.strength.{i}"] for i in range(1, 7)] == ["Off"] * 6  # not set
    assert "not set" in page_text
    assert "bond2.regnant" not in f and f["feeding.note"] == "About once a month" and f["feeding.last"] == ""
    assert not any(k.startswith("vitae") for k in f)
    assert "FEEDING" in page_text and "Ghoul Power  ·  Blood Bond & Feeding".upper() in page_text
    assert not any("Vitae" == t or "VITAE" == t for t in page_text)
    assert [f[f"attr.manipulation.{i}"] for i in range(1, 6)].count("Yes") == 4
    assert f["skill.persuasion.specialty"] == "Negotiation"
    assert f["adv1.name"] == "Beautiful" and f["flaw1.name"] == "Two Masters"
    assert [f[f"humanity.{i}"] for i in range(1, 11)].count("Yes") == 7
    assert f["health.superficial.1"] == "Off"
    assert not any(k.startswith(("hunger", "blood_potency", "disc1", "ritual", "predator")) for k in f)
    assert f["background"].startswith("Πρώην") and f["notes"] == "Resources 0: in debt."
    assert "GHOUL" in page_text and "Mira Tanis · Ghoul of Darius Vale" in page_text


def test_ghoul_with_two_bonds_and_no_humanity():
    ch = _mira()
    g = ch["wod_meta"]["ghoul"]
    g["bonds"][0]["strength"] = 4
    g["bonds"].append({"character_id": None, "name": "Leyla", "strength": 1, "note": "One taste, at the gallery"})
    del ch["wod_meta"]["humanity"]
    f = _fields(build_sheet_pdf(ch))
    assert [f[f"bond.strength.{i}"] for i in range(1, 7)].count("Yes") == 4
    assert f["bond2.regnant"] == "Leyla" and f["bond2.strength.1"] == "Yes" and f["bond2.strength.2"] == "Off"
    assert not any(k.startswith("humanity") for k in f)


def test_ghoul_reference_and_footer(page_text):
    from tests.unit.test_creation_validation_routes import DOC

    items = v5_reference(_mira(), DOC["catalog"], "en")
    names = [o["name"] for k, o in items if k == "entry"]
    assert items[:2] == [("section", "Ghoul"), ("entry", items[1][1])] and names[0] == "Retainers"
    assert {"Cloud Memory", "Beautiful", "Two Masters", "Bondslave", "Contacts"} <= set(names)
    pdf = build_sheet_pdf(_mira(), catalog=DOC["catalog"])
    assert _pages(pdf) == 3 and "Ghoul of Darius Vale" in page_text and "REFERENCE" in page_text


def test_ghoul_pdf_is_black_and_white_and_never_raises():
    ops = re.compile(rb"((?:-?\d*\.?\d+\s+){1,4})(rg|RG|k|K|g|G|sc|SC|scn|SCN)(?=\s)")
    pdf = build_sheet_pdf(_mira())
    for s in _content_streams(pdf):
        for m in ops.finditer(s):
            assert {float(x) for x in m.group(1).split()} <= {0.0, 1.0}
    for mangle in (_numbers, _text, _lists, _huge):
        ch = mangle(_mira())
        if mangle is _numbers:
            ch["wod_meta"]["ghoul"] = {"bonds": [{"strength": "x"}] * 5, "domitor": "y", "feeding": [1], "vitae": "z"}
        out = build_sheet_pdf(ch, paper="letter")
        assert out.startswith(b"%PDF-") and _pages(out) >= 2


def test_a_ghoul_sheet_from_before_the_rename_prints_its_feeding_note():
    ch = _mira()
    g = ch["wod_meta"]["ghoul"]
    g["vitae"] = {"last": "early October", "note": "old key"}
    del g["feeding"]
    f = _fields(build_sheet_pdf(ch))
    assert (f["feeding.last"], f["feeding.note"]) == ("early October", "old key")


@pytest.mark.parametrize("key", ["background", "notes"])
def test_a_long_unbroken_token_is_cut_and_continued(key):
    """A URL or a pasted line with no spaces is cut into pieces that fit, so nothing is clipped."""
    token = "https://example.org/" + "x" * 6000
    ch = copy.deepcopy(V5_CHAR)
    if key == "background":
        ch["background"] = "Start. " + token + " End."
    else:
        ch["merits_flaws"]["notes"] = "Start. " + token + " End."
    pdf = build_sheet_pdf(ch)
    f = _fields(pdf)
    assert _pages(pdf) >= 3 and f"{key}.cont1" in f
    assert _long_text(f, key).replace(" ", "") == ("Start." + token + "End.")
    for field in [k for k in f if k == key or k.startswith(f"{key}.cont")]:
        assert len(f[field]) <= 20000


# --- a Classic ghoul's sheet (the 1997 ghoul sheet's page 1) ----------------------------------

def _marta():
    from tests.unit.test_ghoul_routes import classic_body

    b = classic_body()
    g = b["wod_meta"]["ghoul"]
    g["domitor"] = {"character_id": 8, "name": "Theodore Doukas", "clan": "Ventrue", "generation": 12}
    g["bond"] = {"stage": 3, "note": "Third drink in 1998"}
    g["feeding"] = {"last": "Sunday", "note": "A point of Theodore's vitae each month"}
    g["overdosing"] = "Can cram 2 extra (Stamina 2)"
    b["merits_flaws"] = {"entries": [{"name": "Unbondable", "points": 3}]}
    return {"id": 40, **b, "rules_edition": "classic",
            "domitor": {"id": 8, "name": "Theodore Doukas", "clan": "Ventrue", "generation": 12,
                        "campaign_id": 12, "campaign_name": "Byzantium by Night", "exists": True}}


def test_classic_ghoul_sheet_fields(page_text):
    pdf = build_sheet_pdf(_marta(), player_name="lef", chronicle_name="Byzantium by Night", catalog=REF_CATALOG)
    assert _pages(pdf) == 2  # Classic: never a Reference page
    f = _fields(pdf)
    assert f["ghoul.domitor"] == "Theodore Doukas (Ventrue, 12th)" and f["ghoul.duties"] == "Drives, keeps the house"
    assert f["ghoul.kind"] == "Vassal"
    assert not any(k in f for k in ("clan", "generation", "sire", "weakness"))
    assert f["disc1.name"] == "Potence" and f["disc2.name"] == "Fortitude" and f["disc1.1"] == "Yes"
    assert f["bg1.name"] == "Domitor"
    # Blood Pool: one row of 10, 6 held, 1 per turn
    assert f["blood.max"] == "10" and f["blood.per_turn"] == "1"
    assert [f[f"blood.r1.{i}"] for i in range(1, 11)] == ["Yes"] * 6 + ["Off"] * 4
    assert not any(k.startswith("blood.r2") for k in f)
    assert f["bond"] == "3/3 drinks · Third drink in 1998" and f["overdosing"] == "Can cram 2 extra (Stamina 2)"
    assert f["path.name"] == "Humanity" and [f[f"path.{i}"] for i in range(1, 11)].count("Yes") == 6
    assert [f[f"willpower.{i}"] for i in range(1, 11)].count("Yes") == 2
    assert f["health.1"] == "Off" and f["merit1.name"] == "Unbondable"
    # page 2: its ages, when it was ghouled, its feeding
    assert f["desc.age"] == "51" and f["desc.apparent_age"] == "38" and f["desc.ghouled_since"] == "1998"
    assert "desc.rip" not in f and "poss.feeding_grounds" not in f
    assert f["poss.feeding"] == "Last fed: Sunday\nA point of Theodore's vitae each month"
    assert "GHOUL" in page_text and "Marta Ionescu · Ghoul of Theodore Doukas · Byzantium by Night" in page_text
    assert not any(t in ("Hunger", "HUNGER", "Rouse") for t in page_text)


def test_classic_ghoul_pool_potence_and_old_sheets():
    ch = _marta()
    m = ch["wod_meta"]
    m["blood_pool"] = {"max": 14, "current": 12}  # an old ghoul (staff edit)
    m["disciplines"] = [{"name": "Dominate", "dots": 1}, {"name": "potence", "dots": 2}]
    m["ghoul"].update(kind="revenant", family="Zantosa", bond={"stage": 1})
    del ch["domitor"]  # the domitor's row is gone: the stored copy stands in
    f = _fields(build_sheet_pdf(ch))
    assert f["blood.max"] == "14" and [f[f"blood.r2.{i}"] for i in range(1, 11)].count("Yes") == 2
    assert f["disc1.name"] == "potence" and f["disc1.2"] == "Yes" and f["disc2.name"] == "Dominate"
    assert f["ghoul.kind"] == "Revenant: Zantosa" and f["bond"] == "1/3 drinks"
    assert f["ghoul.domitor"] == "Theodore Doukas (Ventrue, 12th)"
    m["disciplines"] = []
    m.pop("blood_pool")
    m["ghoul"] = {"domitor": {"name": "Theo"}}
    f = _fields(build_sheet_pdf(ch))
    assert f["disc1.name"] == "Potence" and f["blood.max"] == "10" and f["blood.r1.1"] == "Off"
    assert f["ghoul.domitor"] == "Theo" and f["bond"] == "" and f["ghoul.kind"] == ""


def test_classic_ghoul_pdf_is_black_and_white_and_never_raises():
    ops = re.compile(rb"((?:-?\d*\.?\d+\s+){1,4})(rg|RG|k|K|g|G|sc|SC|scn|SCN)(?=\s)")
    pdf = build_sheet_pdf(_marta())
    for s in _content_streams(pdf):
        for m in ops.finditer(s):
            assert {float(x) for x in m.group(1).split()} <= {0.0, 1.0}
    for mangle in (_numbers, _text, _lists, _huge):
        ch = mangle(_marta())
        if mangle is _numbers:
            ch["wod_meta"]["ghoul"] = {"bond": {"stage": "x"}, "domitor": "y", "feeding": [1], "kind": 3}
            ch["wod_meta"]["blood_pool"] = {"max": "ten", "current": [1]}
        out = build_sheet_pdf(ch, paper="letter")
        assert out.startswith(b"%PDF-") and _pages(out) >= 2


@pytest.mark.parametrize("paper,height", [("a4", 841.89), ("letter", 792.0)])
def test_classic_ghoul_page_one_fits(paper, height):
    """The two extra lines in the Health column keep Experience above the band's last row."""
    pdf = build_sheet_pdf(_marta(), paper=paper)
    for x0, y0, x1, y1 in _rects(pdf):
        assert 0 <= y0 < y1 <= height
    rect = {}
    for w in _widgets(pdf):
        t = re.search(rb"/T " + _STR, w)
        r = re.search(rb"/Rect \[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]", w)
        rect[_pdf_string(t.group(1))] = [float(v) for v in r.groups()]
    lowest_merit = min(v[1] for k, v in rect.items() if k.startswith("merit") and k.endswith(".name"))
    assert rect["xp.unspent"][1] >= lowest_merit and rect["overdosing"][1] > rect["xp.total"][3]
    assert _pages(pdf) == 2


# --- print version (flat) and the form font's Latin Extended letters -----------------------------

TURKISH_NAME = "Nazlı Özdoğan İşçi Şahin"


@pytest.mark.parametrize("make", [
    lambda: copy.deepcopy(V5_CHAR),
    lambda: copy.deepcopy(CLASSIC_CHAR),
    lambda: _mira(),
    lambda: _marta(),
    lambda: {**copy.deepcopy(V5_CHAR), "background": _long_background(), "name": TURKISH_NAME},
    lambda: {**copy.deepcopy(CLASSIC_CHAR), "background": _long_background()},
], ids=["v5", "classic", "v5-ghoul", "classic-ghoul", "v5-long", "classic-long"])
def test_print_version_has_no_form_and_draws_every_value(make, page_text):
    ch = make()
    fillable = build_sheet_pdf(ch, player_name="adminator")
    values = _fields(fillable)
    page_text.clear()
    flat = build_sheet_pdf(ch, player_name="adminator", flat=True)
    assert flat.startswith(b"%PDF-") and _pages(flat) == _pages(fillable)
    assert b"/AcroForm" not in flat and b"/Widget" not in flat and b"/Annots" not in flat
    words = set(" ".join(page_text).split())
    for key, v in values.items():
        if v in ("Yes", "Off"):
            continue
        for w in v.replace("\x80", "•").split():  # '•' is 0x80 in a PDF text string
            assert w in words, (key, w)


def test_print_version_marks_are_page_content():
    flat = build_sheet_pdf(V5_CHAR, flat=True)
    # the 'Yes' marks are drawn inline: filled dots (curves) and squares in the page streams
    assert any(b" c f" in s and b"BT" in s for s in _content_streams(flat))
    assert b"SRap" not in flat  # no field appearance XObjects


def test_route_print_version(api):
    r = api("/api/characters/9/sheet.pdf?flat=1", "2")
    assert r.status_code == 200 and b"/AcroForm" not in r.data
    assert "%28print%29.pdf" in r.headers["Content-Disposition"]
    assert b"/AcroForm" in api("/api/characters/9/sheet.pdf", "2").data
    assert api("/api/characters/9/sheet.pdf?flat=1", "4").status_code == 404


def _content_streams_all(pdf: bytes):
    for _, body in _objects(pdf):
        m = re.match(rb"(.*?)stream\r?\n(.*?)\r?\n?endstream", body, re.S)
        if m:
            yield _decode_stream(m.group(1), m.group(2))

