"""Ghouls in the routes: POST /api/characters/ for a ghoul's sheet (no chronicle, the domitor's
owner, the ghoul check, overrides), the `retainers` / `domitor` fields of GET, who may read a
ghoul (its domitor's Storyteller), assign refused, POST /<id>/creation-override for a ghoul.
A Classic vampire's ghoul is a Classic sheet (bounds only, a Blood Pool), at the end."""

import copy
import json
import sqlite3
import sys
import types

import pytest

from tests.unit.test_creation_validation_routes import CASES_FILE, DOC, Conn
from tests.unit.test_v5_ghoul_chargen import MIRA, DARIUS

pytestmark = pytest.mark.skipif(CASES_FILE is None, reason="docs/rules/v5/tests not on disk")

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY, username TEXT, role TEXT, ui_language TEXT,
    allow_multi_campaign_play INTEGER DEFAULT 0
);
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY, name TEXT, game_system TEXT, rules_edition TEXT DEFAULT 'classic',
    created_by INTEGER, is_active INTEGER DEFAULT 1, creation_settings TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE campaign_players (
    id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER, role TEXT DEFAULT 'player',
    active_character_id INTEGER
);
CREATE TABLE characters (
    id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER, campaign_id INTEGER,
    system_type TEXT DEFAULT 'vampire', attributes TEXT DEFAULT '{}', skills TEXT DEFAULT '{}',
    background TEXT DEFAULT '', merits_flaws TEXT DEFAULT '{}', wod_meta TEXT DEFAULT '{}',
    portrait_url TEXT, is_active INTEGER DEFAULT 1, sheet_locked INTEGER DEFAULT 1,
    play_suspended INTEGER DEFAULT 0, play_suspension_reason_code TEXT,
    play_suspension_message TEXT, play_suspended_at TEXT, play_suspended_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    rules_edition TEXT DEFAULT 'classic'
);
INSERT INTO users (id, username, role) VALUES
    (1, 'admin', 'admin'), (2, 'st', 'player'), (3, 'adminator', 'player'), (4, 'other', 'player'),
    (5, 'helper', 'helper');
INSERT INTO campaigns (id, name, game_system, rules_edition, created_by) VALUES
    (10, 'Harbor Nights', 'vampire', 'v5', 2),
    (12, 'Constantinople', 'vampire', 'classic', 2);
INSERT INTO campaign_players (campaign_id, user_id, role) VALUES (10, 2, 'owner'), (10, 3, 'player');
"""

DOMINATE = json.dumps({"edition": "v5", "clan": "Ventrue", "disciplines": [
    {"name": "Dominate", "level": 2, "powers": ["Cloud Memory", "Mesmerize"]}]})
# Theo: a Classic Ventrue of the 12th generation, as the Classic wizard saves him
THEO = json.dumps({"concept": "Banker", "clan": "Ventrue", "generation": "12", "humanity": 7, "willpower": 4,
                   "virtues": {"conscience": 3, "self_control": 3, "courage": 4},
                   "disciplines": [{"name": "Dominate", "dots": 2}, {"name": "Fortitude", "dots": 1}],
                   "backgrounds": [{"name": "Resources", "dots": 3}]})


@pytest.fixture
def api(monkeypatch):
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    monkeypatch.delenv("DATABASE_TYPE", raising=False)
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    from routes import characters

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.executescript(SCHEMA)
    # Darius: no chronicle; Kemal: a V5 vampire in the chronicle of user 2
    raw.execute(
        "INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, wod_meta) VALUES (?, ?, ?, ?, ?, ?)",
        (17, DARIUS["name"], 3, None, "v5", DARIUS["wod_meta"]))
    raw.execute(
        "INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, wod_meta) VALUES (?, ?, ?, ?, ?, ?)",
        (20, "Kemal", 3, 10, "v5", DOMINATE))
    raw.execute("INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, wod_meta) "
                "VALUES (21, 'Theo', 3, 12, 'classic', ?)", (THEO,))
    raw.execute("INSERT INTO characters (id, name, user_id, campaign_id, system_type, rules_edition) "
                "VALUES (22, 'Ines', 3, 12, 'mage', 'classic')")
    raw.commit()
    monkeypatch.setattr(characters, "get_db", lambda: Conn(raw))
    monkeypatch.setattr(characters, "_ensure_character_schema", lambda cursor: None)
    monkeypatch.setattr(characters, "ensure_campaign_players_active_character_id_column", lambda cursor: None)
    catalog = {"value": copy.deepcopy(DOC["catalog"])}
    monkeypatch.setattr(characters, "load_catalog", lambda: catalog["value"])

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(characters.bp, url_prefix="/api/characters")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in (1, 2, 3, 4, 5)}
    c = app.test_client()

    def call(method, url, uid, body=None):
        return c.open(url, method=method, json=body, headers={"Authorization": f"Bearer {tokens[uid]}"})

    def sql(q, params=()):
        cur = raw.execute(q, params)
        raw.commit()
        return cur.fetchall()

    def row(character_id):
        cur = raw.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        return dict(zip([d[0] for d in cur.description], cur.fetchone()))

    return types.SimpleNamespace(call=call, sql=sql, row=row, catalog=catalog)


def ghoul_body(domitor=17, name="Mira Tanis", **extra):
    out = {"name": name, "campaign_id": None, "system_type": "vampire", "sheet_locked": True, "is_active": True,
           **copy.deepcopy(MIRA), "background": "Former television executive."}
    m = out["wod_meta"]
    m["ghoul"]["domitor"] = {"character_id": domitor, "name": "whatever the client says", "clan": "Toreador"}
    m["ghoul"]["bonds"][0]["character_id"] = domitor
    out.update(extra)
    return out


def kemal_ghoul(name="Ayla", **extra):
    """A ghoul of Kemal (in chronicle 10): Cloud Memory is one of his powers."""
    return ghoul_body(domitor=20, name=name, **extra)


# ---------- POST ----------

def test_mira_is_created_without_a_chronicle(api):
    r = api.call("POST", "/api/characters/", 3, ghoul_body())
    assert r.status_code == 201, r.get_json()
    out = r.get_json()
    assert out["sheet_kind"] == "ghoul" and out["domitor_id"] == 17 and out["rules_edition"] == "v5"
    row = api.row(out["character_id"])
    assert row["campaign_id"] is None and row["user_id"] == 3 and row["rules_edition"] == "v5"
    meta = json.loads(row["wod_meta"])
    assert meta["creation"]["validated"] is True and meta["creation"]["rules"] == "ghoul-v1"
    # the server's copy of the domitor, not the client's
    assert meta["ghoul"]["domitor"] == {"character_id": 17, "name": "Darius Vale", "clan": "Ventrue"}
    assert meta["sheet_kind"] == "ghoul" and row["background"] == "Former television executive."


def test_a_ghoul_has_no_chronicle(api):
    r = api.call("POST", "/api/characters/", 3, ghoul_body(campaign_id=10))
    assert r.status_code == 400 and r.get_json()["error_code"] == "ghoul_has_no_chronicle"
    r = api.call("POST", "/api/characters/", 3, ghoul_body(system_type="werewolf"))
    assert r.status_code == 400 and r.get_json()["error_code"] == "ghoul_not_vampire_line"


def test_the_domitor_must_be_yours_staff_keep_the_owner(api):
    r = api.call("POST", "/api/characters/", 4, ghoul_body())
    assert r.status_code == 403 and r.get_json()["error_code"] == "ghoul_domitor_not_yours"
    r = api.call("POST", "/api/characters/", 1, ghoul_body())
    assert r.status_code == 201
    assert api.row(r.get_json()["character_id"])["user_id"] == 3


def test_domitors_that_cannot_have_ghouls(api):
    r = api.call("POST", "/api/characters/", 3, ghoul_body(domitor=22))  # a mage
    assert r.status_code == 400 and r.get_json()["error_code"] == "ghoul_domitor_not_vampire"
    # Theo is a Classic vampire: his ghoul is a Classic sheet, so a V5 one is out of bounds
    r = api.call("POST", "/api/characters/", 3, ghoul_body(domitor=21))
    assert r.status_code == 400 and r.get_json()["error_code"] == "classic_ghoul_bounds"
    first = api.call("POST", "/api/characters/", 3, ghoul_body()).get_json()["character_id"]
    r = api.call("POST", "/api/characters/", 3, ghoul_body(domitor=first, name="Second"))  # a ghoul
    assert r.status_code == 400 and r.get_json()["error_code"] == "ghoul_domitor_not_vampire"
    r = api.call("POST", "/api/characters/", 3, ghoul_body(domitor=999))
    assert r.status_code == 404 and r.get_json()["error_code"] == "ghoul_domitor_not_found"
    b = ghoul_body()
    del b["wod_meta"]["ghoul"]["domitor"]
    r = api.call("POST", "/api/characters/", 3, b)
    assert r.status_code == 400 and r.get_json()["error_code"] == "ghoul_domitor_missing"


def test_a_sheet_that_breaks_the_rules_is_refused_with_codes(api):
    b = ghoul_body()
    b["wod_meta"]["advantages"].append({"id": "background:herd", "name": "Herd", "dots": 1, "kind": "background"})
    r = api.call("POST", "/api/characters/", 3, b)
    assert r.status_code == 400
    out = r.get_json()
    assert out["error_code"] == "creation_invalid"
    assert out["problems"] == [{"code": "adv_over", "params": {"max": 10, "have": 11}},
                               {"code": "ghoul_adv_restricted", "params": {"name": "Herd", "why": "herd"}}]
    assert api.sql("SELECT COUNT(*) FROM characters") == [(4,)]


def test_bounds_come_first(api):
    b = ghoul_body()
    b["wod_meta"]["disciplines"][0]["level"] = 2
    r = api.call("POST", "/api/characters/", 3, b)
    assert r.status_code == 400 and "a ghoul" in r.get_json()["error"]


def test_overrides_by_staff_or_the_domitors_storyteller(api):
    bad = ghoul_body()
    bad["wod_meta"]["disciplines"][0]["powers"] = ["Compel"]
    bad["creation_override"] = {"reason": "Darius taught her Compel"}
    # Darius has no chronicle: as for any sheet without one, only a site admin may override
    assert api.call("POST", "/api/characters/", 3, bad).status_code == 403
    assert api.call("POST", "/api/characters/", 5, bad).status_code == 403  # a helper
    r = api.call("POST", "/api/characters/", 1, bad)
    assert r.status_code == 201
    creation = json.loads(api.row(r.get_json()["character_id"])["wod_meta"])["creation"]
    assert creation["validated"] is False and creation["rules"] == "ghoul-v1"
    assert creation["override"]["by"] == 1 and creation["problems"][0]["code"] == "ghoul_power_not_domitors"
    # Kemal is in chronicle 10: its Storyteller may override a ghoul of his
    bad2 = kemal_ghoul(creation_override={"reason": "house rule"})
    bad2["wod_meta"]["advantages"].append({"id": "background:resources", "name": "Resources", "dots": 1,
                                           "kind": "background"})
    assert api.call("POST", "/api/characters/", 4, bad2).status_code == 403
    r = api.call("POST", "/api/characters/", 2, bad2)
    assert r.status_code == 201
    assert api.row(r.get_json()["character_id"])["user_id"] == 3  # Kemal's player owns it
    assert api.call("POST", "/api/characters/", 5, kemal_ghoul(name="Helper's", creation_override={"reason": "x"})).status_code == 201


def test_a_storyteller_makes_a_players_ghoul_only_to_approve_an_exception(api):
    # a legal ghoul of Kemal's, posted by the chronicle's Storyteller without an override: not theirs to make
    r = api.call("POST", "/api/characters/", 2, kemal_ghoul())
    assert r.status_code == 403 and r.get_json()["error_code"] == "ghoul_domitor_not_yours"
    r = api.call("POST", "/api/characters/", 2, kemal_ghoul(creation_override={"reason": "set up for the player"}))
    assert r.status_code == 201
    assert json.loads(api.row(r.get_json()["character_id"])["wod_meta"])["creation"]["validated"] is True


def test_a_players_sheets_are_locked_at_creation(api):
    r = api.call("POST", "/api/characters/", 3, ghoul_body(sheet_locked=False))
    assert r.status_code == 201 and api.row(r.get_json()["character_id"])["sheet_locked"] == 1
    r = api.call("POST", "/api/characters/", 1, ghoul_body(name="Draft", sheet_locked=False))
    assert r.status_code == 201 and api.row(r.get_json()["character_id"])["sheet_locked"] == 0  # staff may
    # the same for a vampire in a chronicle (user 2's Classic one, no creation check)
    r = api.call("POST", "/api/characters/", 2, {"name": "Theo II", "campaign_id": 12, "system_type": "vampire",
                                                 "sheet_locked": False})
    assert r.status_code == 201 and api.row(r.get_json()["character_id"])["sheet_locked"] == 1


def test_the_chronicles_settings_of_the_domitor_apply(api):
    api.sql("""UPDATE campaigns SET creation_settings = '{"allowed_books": ["v5-corebook"]}' WHERE id = 10""")
    r = api.call("POST", "/api/characters/", 3, kemal_ghoul())
    assert r.status_code == 400
    assert [p["code"] for p in r.get_json()["problems"]] == ["book_not_allowed"]  # Two Masters
    assert api.call("POST", "/api/characters/", 3, ghoul_body()).status_code == 201  # Darius: no chronicle


def test_a_locked_character_elsewhere_does_not_stop_a_ghoul(api):
    # user 3 has Kemal locked in chronicle 10; the ghoul has no chronicle, so the one-locked-PC rule doesn't apply
    assert api.call("POST", "/api/characters/", 3, ghoul_body()).status_code == 201
    assert api.call("POST", "/api/characters/", 3, kemal_ghoul()).status_code == 201


def test_names_are_unique_among_characters_without_a_chronicle(api):
    assert api.call("POST", "/api/characters/", 3, ghoul_body()).status_code == 201
    assert api.call("POST", "/api/characters/", 3, ghoul_body()).status_code == 409


# ---------- GET, who may read, assign ----------

def test_get_links_both_ways(api):
    gid = api.call("POST", "/api/characters/", 3, ghoul_body()).get_json()["character_id"]
    darius = api.call("GET", "/api/characters/17", 3).get_json()["character"]
    assert darius["sheet_kind"] is None
    assert darius["retainers"] == [{"id": gid, "name": "Mira Tanis", "portrait_url": None, "template": "gifted",
                                    "kind": None, "retainer_dots": 3, "rules_edition": "v5", "is_active": True}]
    mira = api.call("GET", f"/api/characters/{gid}", 3).get_json()["character"]
    assert mira["sheet_kind"] == "ghoul" and "retainers" not in mira
    assert mira["domitor"] == {"id": 17, "name": "Darius Vale", "clan": "Ventrue", "generation": None,
                                "campaign_id": None, "campaign_name": None, "exists": True}
    listed = api.call("GET", "/api/characters/", 3).get_json()["characters"]
    assert {c["id"]: c["sheet_kind"] for c in listed}[gid] == "ghoul"
    # the domitor's row is gone: the stored name stays
    api.sql("DELETE FROM characters WHERE id = 17")
    mira = api.call("GET", f"/api/characters/{gid}", 3).get_json()["character"]
    assert mira["domitor"]["exists"] is False and mira["domitor"]["name"] == "Darius Vale"


def test_the_domitors_storyteller_may_read_the_ghoul(api):
    gid = api.call("POST", "/api/characters/", 3, kemal_ghoul()).get_json()["character_id"]
    for uid, status in ((3, 200), (2, 200), (1, 200), (5, 200), (4, 403)):
        assert api.call("GET", f"/api/characters/{gid}", uid).status_code == status, uid
    pdf = api.call("GET", f"/api/characters/{gid}/sheet.pdf", 2)
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF-")
    assert api.call("GET", f"/api/characters/{gid}/sheet.pdf", 4).status_code == 404
    # Darius's ghoul: no chronicle, so no Storyteller but staff
    cid = api.call("POST", "/api/characters/", 3, ghoul_body()).get_json()["character_id"]
    assert api.call("GET", f"/api/characters/{cid}", 2).status_code == 403


def test_a_ghoul_is_never_brought_into_a_chronicle(api):
    gid = api.call("POST", "/api/characters/", 3, ghoul_body()).get_json()["character_id"]
    r = api.call("POST", f"/api/characters/{gid}/assign", 3, {"campaign_id": 10})
    assert r.status_code == 400 and r.get_json()["error_code"] == "ghoul_follows_domitor"
    assert api.row(gid)["campaign_id"] is None


# ---------- POST /<id>/creation-override ----------

def _insert_ghoul(api, character_id, domitor):
    b = kemal_ghoul() if domitor == 20 else ghoul_body()
    b["wod_meta"]["disciplines"][0]["powers"] = ["Compel"]  # neither Darius nor Kemal has it
    api.sql(
        "INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, attributes, skills, wod_meta) "
        "VALUES (?, ?, 3, NULL, 'v5', ?, ?, ?)",
        (character_id, f"Ghoul {character_id}", json.dumps(b["attributes"]), json.dumps(b["skills"]),
         json.dumps(b["wod_meta"])))


def test_override_route_for_a_ghoul(api):
    _insert_ghoul(api, 50, 20)
    assert api.call("POST", "/api/characters/50/creation-override", 4, {"reason": "x"}).status_code == 403
    assert api.call("POST", "/api/characters/50/creation-override", 3, {"reason": "x"}).status_code == 403
    r = api.call("POST", "/api/characters/50/creation-override", 2, {"reason": "taught by another"})
    assert r.status_code == 200, r.get_json()
    creation = r.get_json()["creation"]
    assert creation["rules"] == "ghoul-v1" and creation["override"]["by"] == 2
    assert [p["code"] for p in creation["problems"]] == ["ghoul_power_not_domitors"]
    assert api.call("POST", "/api/characters/50/creation-override", 5, {"reason": "staff"}).status_code == 200
    _insert_ghoul(api, 51, 17)  # Darius's (no chronicle): a site admin only, as for any such sheet
    assert api.call("POST", "/api/characters/51/creation-override", 2, {"reason": "x"}).status_code == 403
    assert api.call("POST", "/api/characters/51/creation-override", 5, {"reason": "x"}).status_code == 403
    assert api.call("POST", "/api/characters/51/creation-override", 1, {"reason": "x"}).status_code == 200


def test_staff_edits_keep_the_ghoul_bounds(api):
    gid = api.call("POST", "/api/characters/", 3, ghoul_body()).get_json()["character_id"]
    meta = json.loads(api.row(gid)["wod_meta"])
    meta["ghoul"]["bonds"][0]["strength"] = 6
    assert api.call("PUT", f"/api/characters/{gid}", 1, {"wod_meta": meta}).status_code == 200
    assert json.loads(api.row(gid)["wod_meta"])["ghoul"]["bonds"][0]["strength"] == 6
    meta["ghoul"]["bonds"][0]["strength"] = 7
    assert api.call("PUT", f"/api/characters/{gid}", 1, {"wod_meta": meta}).status_code == 400


# ---------- Classic ghouls (a Classic vampire's) ----------

def classic_body(name="Marta Ionescu", kind="vassal", **extra):
    """A Classic ghoul of Theo's as the Classic ghoul forge sends it (Fatal Addiction's budgets)."""
    out = {
        "name": name, "campaign_id": None, "system_type": "vampire", "sheet_locked": True, "is_active": True,
        "attributes": {"strength": 3, "dexterity": 3, "stamina": 2, "charisma": 2, "manipulation": 3,
                       "appearance": 2, "perception": 3, "intelligence": 3, "wits": 2},
        "skills": {"talents": {"alertness": 2, "brawl": 2, "subterfuge": 1},
                   "skills": {"drive": 2, "etiquette": 2, "firearms": 1, "security": 2},
                   "knowledges": {"finance": 2, "law": 1, "investigation": 1}},
        "background": "Theo's driver since 1998.",
        "merits_flaws": {"merits": [], "flaws": []},
        "wod_meta": {
            "sheet_kind": "ghoul", "concept": "Driver", "nature": "Caregiver", "demeanor": "Conformist",
            "ghoul": {"kind": kind, "domitor": {"character_id": 21, "name": "whatever", "clan": "Toreador"},
                      "duties": "Drives, keeps the house", "ghouled_since": "1998", "age": 51, "apparent_age": 38,
                      "bond": {"stage": 3, "note": ""}, "feeding": {"last": "", "note": ""}, "overdosing": ""},
            "blood_pool": {"max": 10, "current": 6, "per_turn": 1},
            "disciplines": [{"name": "Potence", "dots": 1}, {"name": "Fortitude", "dots": 1}],
            "backgrounds": [{"name": "Domitor", "dots": 1}, {"name": "Resources", "dots": 2},
                            {"name": "Contacts", "dots": 2}],
            "virtues": {"conscience": 3, "self_control": 3, "courage": 2},
            "humanity": 6, "willpower": 2, "willpower_current": 2, "health_damage": 0,
        },
    }
    out.update(extra)
    return out


def test_a_classic_vampires_ghoul_is_a_classic_sheet_with_a_blood_pool(api):
    r = api.call("POST", "/api/characters/", 3, classic_body())
    assert r.status_code == 201, r.get_json()
    out = r.get_json()
    assert out["rules_edition"] == "classic" and out["sheet_kind"] == "ghoul" and out["domitor_id"] == 21
    row = api.row(out["character_id"])
    assert row["rules_edition"] == "classic" and row["campaign_id"] is None and row["user_id"] == 3
    meta = json.loads(row["wod_meta"])
    assert set(meta["creation"]) == {"rules", "checked", "at"}
    assert meta["creation"]["rules"] == "classic-ghoul-v1" and meta["creation"]["checked"] == "bounds"
    # the server's copy of the domitor (generation as a number, for the PDF and the AI prompt)
    assert meta["ghoul"]["domitor"] == {"character_id": 21, "name": "Theo", "clan": "Ventrue", "generation": 12}
    assert meta["blood_pool"] == {"max": 10, "current": 6, "per_turn": 1}
    assert "edition" not in meta and "hunger" not in meta


@pytest.mark.parametrize("change", [
    lambda m: m["blood_pool"].update(max=21),
    lambda m: m["blood_pool"].update(current=11),
    lambda m: m.update(disciplines=[{"name": "Dominate", "dots": 1}]),  # no Potence
    lambda m: m["backgrounds"].append({"name": "Generation", "dots": 1}),
    lambda m: m.update(hunger=1),
    lambda m: m.update(edition="v5"),
    lambda m: m["ghoul"].update(kind="thrall"),
    lambda m: m["ghoul"]["bond"].update(stage=4),
])
def test_a_classic_ghoul_out_of_bounds_is_refused(api, change):
    b = classic_body()
    change(b["wod_meta"])
    r = api.call("POST", "/api/characters/", 3, b)
    assert r.status_code == 400 and r.get_json()["error_code"] == "classic_ghoul_bounds", r.get_json()
    assert r.get_json()["problems"]


def test_a_classic_ghoul_is_the_domitors_players(api):
    assert api.call("POST", "/api/characters/", 4, classic_body()).status_code == 403
    # Theo's Storyteller (user 2, chronicle 12) makes it only with an override, recorded not checked
    r = api.call("POST", "/api/characters/", 2, classic_body())
    assert r.status_code == 403 and r.get_json()["error_code"] == "ghoul_domitor_not_yours"
    r = api.call("POST", "/api/characters/", 2, classic_body(creation_override={"reason": "a revenant cousin"}))
    assert r.status_code == 201
    row = api.row(r.get_json()["character_id"])
    creation = json.loads(row["wod_meta"])["creation"]
    assert row["user_id"] == 3 and creation["checked"] == "bounds" and creation["override"]["by"] == 2


def test_classic_links_both_ways_and_the_pdf(api):
    gid = api.call("POST", "/api/characters/", 3, classic_body()).get_json()["character_id"]
    theo = api.call("GET", "/api/characters/21", 3).get_json()["character"]
    assert theo["retainers"] == [{"id": gid, "name": "Marta Ionescu", "portrait_url": None, "template": None,
                                  "kind": "vassal", "retainer_dots": None, "rules_edition": "classic",
                                  "is_active": True}]
    marta = api.call("GET", f"/api/characters/{gid}", 3).get_json()["character"]
    assert marta["sheet_kind"] == "ghoul" and marta["rules_edition"] == "classic"
    assert marta["domitor"] == {"id": 21, "name": "Theo", "clan": "Ventrue", "generation": 12, "campaign_id": 12,
                                "campaign_name": "Constantinople", "exists": True}
    assert api.call("GET", f"/api/characters/{gid}", 2).status_code == 200  # Theo's Storyteller
    assert api.call("GET", f"/api/characters/{gid}", 4).status_code == 403
    pdf = api.call("GET", f"/api/characters/{gid}/sheet.pdf", 3)
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF-")
    r = api.call("POST", f"/api/characters/{gid}/assign", 3, {"campaign_id": 12})
    assert r.status_code == 400 and r.get_json()["error_code"] == "ghoul_follows_domitor"
    # Classic sheets have no creation rules to override
    r = api.call("POST", f"/api/characters/{gid}/creation-override", 1, {"reason": "x"})
    assert r.status_code == 400 and r.get_json()["error_code"] == "not_v5"


def test_staff_edits_keep_the_classic_bounds_and_the_record(api):
    gid = api.call("POST", "/api/characters/", 3, classic_body()).get_json()["character_id"]
    meta = json.loads(api.row(gid)["wod_meta"])
    meta["blood_pool"]["current"] = 11
    r = api.call("PUT", f"/api/characters/{gid}", 1, {"wod_meta": meta})
    assert r.status_code == 400 and r.get_json()["error_code"] == "classic_ghoul_bounds"
    meta["blood_pool"]["current"] = 3
    meta["creation"] = {"rules": "made up"}
    assert api.call("PUT", f"/api/characters/{gid}", 1, {"wod_meta": meta}).status_code == 200
    stored = json.loads(api.row(gid)["wod_meta"])
    assert stored["blood_pool"]["current"] == 3 and stored["creation"]["rules"] == "classic-ghoul-v1"
    r = api.call("PUT", f"/api/characters/{gid}", 1, {"attributes": {"strength": 6}})
    assert r.status_code == 400 and r.get_json()["error_code"] == "classic_ghoul_bounds"


@pytest.mark.parametrize("body", [ghoul_body, classic_body], ids=["v5", "classic"])
@pytest.mark.parametrize("ghoul", ["missing", None, [], "vassal", 3])
def test_a_ghoul_sheet_without_a_ghoul_block_is_a_400(api, body, ghoul):
    b = body()
    if ghoul == "missing":
        del b["wod_meta"]["ghoul"]
    else:
        b["wod_meta"]["ghoul"] = ghoul
    r = api.call("POST", "/api/characters/", 3, b)
    assert r.status_code == 400 and r.get_json()["error_code"] == "ghoul_domitor_missing", r.get_json()
