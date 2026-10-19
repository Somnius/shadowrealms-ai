"""The admin kill page's routes: list characters, kill (once), revive, the deaths log, and the death on
the player's own list and sheet (GET /api/characters/), with the sheet's permission. Plus the
script post-check of the death text (services/death_writeup.py)."""

import sqlite3
import sys
import types

import pytest

from tests.unit.chronicle_fixtures import Conn

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, allow_multi_campaign_play INTEGER DEFAULT 0);
CREATE TABLE campaigns (id INTEGER PRIMARY KEY, name TEXT, rules_edition TEXT DEFAULT 'classic', created_by INTEGER,
                        is_active INTEGER DEFAULT 1);
CREATE TABLE campaign_players (id INTEGER PRIMARY KEY, campaign_id INTEGER, user_id INTEGER, role TEXT DEFAULT 'player');
CREATE TABLE characters (
    id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER, campaign_id INTEGER,
    system_type TEXT DEFAULT 'vampire', attributes TEXT DEFAULT '{}', skills TEXT DEFAULT '{}',
    background TEXT DEFAULT '', merits_flaws TEXT DEFAULT '{}', wod_meta TEXT DEFAULT '{}',
    portrait_url TEXT, is_active INTEGER DEFAULT 1, is_npc INTEGER DEFAULT 0, sheet_locked INTEGER DEFAULT 1,
    play_suspended INTEGER DEFAULT 0, play_suspension_reason_code TEXT, play_suspension_message TEXT,
    play_suspended_at TEXT, play_suspended_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    rules_edition TEXT DEFAULT 'classic'
);
CREATE TABLE character_moderation (
    id INTEGER PRIMARY KEY, character_id INTEGER, action TEXT, death_type TEXT, death_description TEXT,
    moderated_by INTEGER, moderated_at TIMESTAMP
);
CREATE TABLE user_moderation_log (
    id INTEGER PRIMARY KEY, user_id INTEGER, admin_id INTEGER, action TEXT, details TEXT, created_at TIMESTAMP
);
INSERT INTO users (id, username, role) VALUES (1, 'admin', 'admin'), (2, 'st', 'player'), (3, 'eleni', 'player'),
    (4, 'other', 'player'), (5, 'helper', 'helper'), (6, 'tablemate', 'player');
INSERT INTO campaigns (id, name, rules_edition, created_by) VALUES (10, 'Harbor Nights', 'v5', 2);
INSERT INTO campaign_players (campaign_id, user_id) VALUES (10, 3), (10, 6);
INSERT INTO characters (id, name, user_id, campaign_id, rules_edition) VALUES
    (20, 'Kemal', 3, 10, 'v5'), (21, 'Theo', 6, 10, 'v5');
INSERT INTO characters (id, name, user_id, campaign_id, is_npc) VALUES (22, 'Some NPC', 2, 10, 1);
"""

TEXT = "You fall in the harbor as the dawn comes."


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

    from routes import admin, characters
    from services import death_writeup

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.executescript(SCHEMA)
    raw.commit()
    for mod in (admin, characters):
        monkeypatch.setattr(mod, "get_db", lambda: Conn(raw))
    for name in ("ensure_characters_is_active_column", "ensure_characters_is_npc_column"):
        monkeypatch.setattr(admin, name, lambda cursor: None)
    monkeypatch.setattr(characters, "_ensure_character_schema", lambda cursor: None)
    calls = []

    def fake_write(get_db, character_id, death_type):
        calls.append((character_id, death_type))
        return TEXT, True

    monkeypatch.setattr(death_writeup, "write", fake_write)

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(admin.bp)
    app.register_blueprint(characters.bp, url_prefix="/api/characters")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in range(1, 7)}
    c = app.test_client()

    def call(method, url, uid, body=None):
        return c.open(url, method=method, json=body, headers={"Authorization": f"Bearer {tokens[uid]}"})

    call.raw = raw
    call.calls = calls
    return call


def test_only_admins(api):
    for method, url in (("GET", "/api/admin/characters"), ("GET", "/api/admin/character-deaths"),
                        ("POST", "/api/admin/characters/20/kill"), ("POST", "/api/admin/characters/20/revive")):
        for uid in (2, 3, 5):
            assert api(method, url, uid, {}).status_code == 403, (url, uid)
    assert api.calls == []


def test_kill_once_then_revive(api):
    rows = api("GET", "/api/admin/characters", 1).get_json()
    assert [r["name"] for r in rows] == ["Kemal", "Theo"]  # NPC rows stay out
    assert rows[0]["owner_name"] == "eleni" and rows[0]["campaign_name"] == "Harbor Nights"
    assert rows[0]["rules_edition"] == "v5" and rows[0]["death"] is None

    assert api("POST", "/api/admin/characters/20/kill", 1, {"death_type": "awful"}).status_code == 400
    assert api("POST", "/api/admin/characters/99/kill", 1, {"death_type": "soft"}).status_code == 404
    r = api("POST", "/api/admin/characters/20/kill", 1, {"death_type": "horrible"})
    assert r.status_code == 200 and r.get_json()["generated"] is True and r.get_json()["death_description"] == TEXT
    assert api("POST", "/api/admin/characters/20/kill", 1, {"death_type": "soft"}).status_code == 409
    assert api.calls == [(20, "horrible")]  # no model call for a refused kill

    row = next(r for r in api("GET", "/api/admin/characters", 1).get_json() if r["id"] == 20)
    assert row["is_active"] is False and row["death"]["death_type"] == "horrible"
    assert row["death"]["death_description"] == TEXT
    assert api.raw.execute("SELECT action FROM user_moderation_log").fetchall() == [("character_kill",)]

    assert api("POST", "/api/admin/characters/21/revive", 1).status_code == 409
    assert api("POST", "/api/admin/characters/20/revive", 1).status_code == 200
    row = next(r for r in api("GET", "/api/admin/characters", 1).get_json() if r["id"] == 20)
    assert row["is_active"] is True and row["death"] is None

    log = api("GET", "/api/admin/character-deaths", 1).get_json()
    assert [(e["action"], e["character_name"], e["admin_username"], e["owner_name"]) for e in log] == [
        ("revive", "Kemal", "admin", "eleni"), ("kill", "Kemal", "admin", "eleni")]
    assert log[1]["death_description"] == TEXT and log[1]["death_type"] == "horrible"


def test_players_see_the_death_on_their_list_and_sheet(api):
    api("POST", "/api/admin/characters/20/kill", 1, {"death_type": "soft"})
    mine = api("GET", "/api/characters/", 3).get_json()["characters"]
    assert [(c["id"], (c["death"] or {}).get("death_description")) for c in mine] == [(20, TEXT)]
    for uid in (3, 2, 1, 5):  # owner, Storyteller, admin, helper: the sheet's own rule
        r = api("GET", "/api/characters/20", uid)
        assert r.status_code == 200 and r.get_json()["character"]["death"]["death_type"] == "soft", uid
    for uid in (4, 6):  # outsider, another player at the table
        assert api("GET", "/api/characters/20", uid).status_code == 403, uid
    assert api("GET", "/api/characters/21", 6).get_json()["character"]["death"] is None


def test_only_an_admin_revive_brings_a_fallen_character_back(api):
    api("POST", "/api/admin/characters/20/kill", 1, {"death_type": "mid"})
    r = api("PUT", "/api/characters/20", 5, {"is_active": True})
    assert r.status_code == 409 and r.get_json()["error_code"] == "character_fallen"
    assert api.raw.execute("SELECT is_active FROM characters WHERE id = 20").fetchone() == (0,)


# --- the death text's script check -------------------------------------------------------------

MAT = {"name": "Κωνσταντίνος", "clan": "Tremere", "lang": "el", "so_far": "Το υπόγειο.", "chapters": []}


@pytest.mark.parametrize("text, ok", [
    ("Η αυγή σε βρίσκει στο υπόγειο, Κωνσταντίνε.", True),
    ("Ως Tremere, πέφτεις στο υπόγειο.", True),  # a name the material spells in Latin
    ("Ο Prince σε καταδικάζει στο υπόγειο.", False),  # an English title the material doesn't have
    ("Η αυγή σε βρίσκει στο υπόγειo.", False),  # a Latin o inside a Greek word
    ("Dawn finds you in the basement.", False),
])
def test_greek_script_check(text, ok):
    from services import death_writeup as dw

    assert (dw.script_problems(text, "el", MAT) == []) is ok


def test_a_mixed_script_answer_gives_the_canned_sentence(monkeypatch):
    from services import death_writeup as dw

    monkeypatch.setattr(dw, "_read", lambda get_db, cid: MAT)
    gen = lambda role, msgs, params, **kw: {"text": "Η αυγή σε βρίσκει στο υπόγειo."}  # noqa: E731
    assert dw.write(None, 1, "soft", generate=gen) == (dw.FALLBACK["el"]["soft"], False)
    gen_ok = lambda role, msgs, params, **kw: {"text": "Η αυγή σε βρίσκει στο υπόγειο."}  # noqa: E731
    assert dw.write(None, 1, "soft", generate=gen_ok) == ("Η αυγή σε βρίσκει στο υπόγειο.", True)


def test_the_prompt_forbids_invented_lore_and_latin_in_greek():
    from services import death_writeup as dw

    assert "Invent nothing" in dw.SYSTEM["en"] and "titles" in dw.SYSTEM["en"]
    assert "Μην επινοείς τίποτα" in dw.SYSTEM["el"] and "ελληνικά γράμματα" in dw.SYSTEM["el"]
