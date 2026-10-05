"""Fillable character sheet PDF: both editions, Greek, black ink only, and who may download it."""

import base64
import copy
import re
import sys
import types
import zlib

import pytest

pytest.importorskip("reportlab")

from services.character_sheet_pdf import FORM_CODES, build_sheet_pdf, safe_filename  # noqa: E402

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


def test_tabs_become_spaces():
    ch = copy.deepcopy(V5_CHAR)
    ch["background"] = "Sire\tΘεόδωρος"
    assert _fields(build_sheet_pdf(ch))["background"] == "Sire Θεόδωρος"


def test_fields_are_editable(v5_pdf):
    for w in _widgets(v5_pdf):
        ff = re.search(rb"/Ff (\d+)", w)
        assert not ff or not int(ff.group(1)) & 1, "read-only field"
        if b"/FT /Btn" in w:  # toggles between an empty and a marked appearance
            assert re.search(rb"/N <<\s*/Off \d+ 0 R /Yes \d+ 0 R", w)
        else:
            assert b"/DA (/SRG " in w  # edits redraw with the embedded Latin + Greek font


def test_form_font_covers_greek(v5_pdf):
    for ch in "ΑΩαωςάώΐΰ€éüñ":
        assert ord(ch) in FORM_CODES
    assert b"/Font << /SRG " in v5_pdf
    assert b"/Differences [" in v5_pdf and b"/uni03A9" in v5_pdf


def test_black_and_white_only(v5_pdf, classic_pdf):
    ops = re.compile(rb"((?:-?\d*\.?\d+\s+){1,4})(rg|RG|k|K|g|G|sc|SC|scn|SCN)(?=\s)")
    seen = 0
    for pdf in (v5_pdf, classic_pdf):
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
            if "FROM users" in self.sql:
                return {"role": roles[str(self.args[0])]}
            if "FROM campaigns" in self.sql:
                return {"created_by": 3}
            raise AssertionError(self.sql)

        def close(self):
            pass

    class Conn:
        def cursor(self):
            return Cur()

        def close(self):
            pass

    monkeypatch.setattr(characters, "get_db", lambda: Conn())
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
