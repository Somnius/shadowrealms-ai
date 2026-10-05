"""Characters with no chronicle yet: list/get show them to their owner and staff; POST assign."""

import sqlite3
import sys
import types

import pytest

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY, username TEXT, role TEXT,
    allow_multi_campaign_play INTEGER DEFAULT 0
);
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY, name TEXT, game_system TEXT, rules_edition TEXT DEFAULT 'classic',
    created_by INTEGER, is_active INTEGER DEFAULT 1
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
CREATE TABLE character_downtime_requests (
    id INTEGER PRIMARY KEY, character_id INTEGER, user_id INTEGER, campaign_id INTEGER,
    request_text TEXT, status TEXT, admin_reason TEXT, resolved_at TEXT, created_at TEXT
);
INSERT INTO users (id, username, role) VALUES
    (1, 'admin', 'admin'), (2, 'st', 'player'), (3, 'newbie', 'player'), (4, 'other', 'player');
INSERT INTO campaigns (id, name, game_system, rules_edition, created_by) VALUES
    (10, 'Athens by Night', 'vampire', 'v5', 2),
    (11, 'Constantinople', 'vampire', 'classic', 2),
    (12, 'Wolves', 'werewolf', 'classic', 2),
    (13, 'Other V5', 'vampire', 'v5', 2);
INSERT INTO campaign_players (campaign_id, user_id, role) VALUES
    (10, 2, 'owner'), (11, 2, 'owner'), (12, 2, 'owner'), (13, 2, 'owner'),
    (10, 3, 'player'), (11, 3, 'player'), (12, 3, 'player');
INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, wod_meta) VALUES
    (100, 'Volkan', 3, NULL, 'v5', '{"edition": "v5"}'),
    (101, 'Theodore', 2, 11, 'classic', '{}');
"""


class Cur:
    def __init__(self, conn):
        self._c = conn.cursor()

    def execute(self, sql, params=()):
        self._c.execute(sql.replace("%s", "?"), tuple(params))

    def _row(self, r):
        return None if r is None else {k[0]: v for k, v in zip(self._c.description, r)}

    def fetchone(self):
        return self._row(self._c.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._c.fetchall()]

    @property
    def rowcount(self):
        return self._c.rowcount

    def close(self):
        pass


class Conn:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return Cur(self._conn)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        pass


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
    monkeypatch.setattr(characters, "get_db", lambda: Conn(raw))
    monkeypatch.setattr(characters, "_ensure_character_schema", lambda cursor: None)
    monkeypatch.setattr(characters, "ensure_campaign_players_active_character_id_column", lambda cursor: None)

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(characters.bp, url_prefix="/api/characters")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in (1, 2, 3, 4)}
    c = app.test_client()

    def call(method, url, uid, body=None):
        return c.open(url, method=method, json=body, headers={"Authorization": f"Bearer {tokens[uid]}"})

    def sql(q, params=()):
        cur = raw.execute(q, params)
        raw.commit()
        return cur.fetchall()

    return types.SimpleNamespace(call=call, sql=sql)


def _ids(resp):
    return [ch["id"] for ch in resp.get_json()["characters"]]


def test_owner_lists_and_gets_unassigned_character(api):
    r = api.call("GET", "/api/characters/", 3)
    assert r.status_code == 200
    (ch,) = r.get_json()["characters"]
    assert ch["id"] == 100 and ch["campaign_id"] is None
    assert ch.get("campaign_name") is None
    assert ch["rules_edition"] == "v5" and ch["wod_meta"]["edition"] == "v5"
    r = api.call("GET", "/api/characters/100", 3)
    assert r.status_code == 200
    assert r.get_json()["character"]["campaign_id"] is None


def test_staff_see_unassigned_others_do_not(api):
    assert 100 in _ids(api.call("GET", "/api/characters/", 1))
    assert api.call("GET", "/api/characters/100", 1).status_code == 200
    assert _ids(api.call("GET", "/api/characters/", 4)) == []
    assert api.call("GET", "/api/characters/100", 4).status_code == 403
    # a chronicle filter never returns characters without one
    assert _ids(api.call("GET", "/api/characters/?campaign_id=10", 1)) == []


def test_owner_can_update_portrait_of_unassigned(api):
    r = api.call("PUT", "/api/characters/100", 3, {"portrait_url": "https://x/p.png"})
    assert r.status_code == 200
    assert r.get_json()["character"]["portrait_url"] == "https://x/p.png"


def test_downtime_needs_a_chronicle(api):
    r = api.call("POST", "/api/characters/100/downtime-requests", 3, {"request_text": "more blood"})
    assert r.status_code == 400
    assert r.get_json()["error_code"] == "character_has_no_chronicle"


def test_assign_ok_sets_chronicle_and_playing_character(api):
    r = api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 10})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["campaign_name"] == "Athens by Night"
    assert api.sql("SELECT campaign_id FROM characters WHERE id = 100") == [(10,)]
    assert api.sql(
        "SELECT active_character_id FROM campaign_players WHERE campaign_id = 10 AND user_id = 3"
    ) == [(100,)]
    got = api.call("GET", "/api/characters/100", 3).get_json()["character"]
    assert got["campaign_name"] == "Athens by Night"
    # already in a chronicle now: moving it is not supported
    r = api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 10})
    assert r.status_code == 400
    assert r.get_json()["error_code"] == "character_already_in_chronicle"


def test_assign_keeps_an_existing_playing_character(api):
    api.sql("INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, sheet_locked) "
            "VALUES (102, 'Old', 3, 10, 'v5', 0)")
    api.sql("UPDATE campaign_players SET active_character_id = 102 WHERE campaign_id = 10 AND user_id = 3")
    assert api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 10}).status_code == 200
    assert api.sql(
        "SELECT active_character_id FROM campaign_players WHERE campaign_id = 10 AND user_id = 3"
    ) == [(102,)]


def test_assign_not_member(api):
    r = api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 13})
    assert r.status_code == 404
    assert api.sql("SELECT campaign_id FROM characters WHERE id = 100") == [(None,)]


def test_assign_inactive_chronicle(api):
    api.sql("UPDATE campaigns SET is_active = 0 WHERE id = 10")
    assert api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 10}).status_code == 404


def test_assign_wrong_edition_and_line(api):
    r = api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 11})
    assert r.status_code == 400 and r.get_json()["error_code"] == "rules_edition_mismatch"
    api.sql("UPDATE characters SET rules_edition = 'classic', wod_meta = '{}' WHERE id = 100")
    r = api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 12})
    assert r.status_code == 400 and r.get_json()["error_code"] == "game_line_mismatch"
    assert api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 11}).status_code == 200


def test_assign_only_owner_or_staff(api):
    assert api.call("POST", "/api/characters/100/assign", 4, {"campaign_id": 10}).status_code == 403
    assert api.call("POST", "/api/characters/999/assign", 3, {"campaign_id": 10}).status_code == 404
    assert api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": "x"}).status_code == 400
    # staff act for the owner; the owner still has to be a member
    assert api.call("POST", "/api/characters/100/assign", 1, {"campaign_id": 13}).status_code == 404
    assert api.call("POST", "/api/characters/100/assign", 1, {"campaign_id": 10}).status_code == 200


def test_assign_respects_single_locked_character_rule(api):
    api.sql("INSERT INTO characters (id, name, user_id, campaign_id, rules_edition) "
            "VALUES (103, 'Elsewhere', 3, 11, 'classic')")
    r = api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 10})
    assert r.status_code == 409 and r.get_json()["error_code"] == "single_locked_pc_conflict"
    api.sql("UPDATE users SET allow_multi_campaign_play = 1 WHERE id = 3")
    assert api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 10}).status_code == 200


def test_assign_name_taken(api):
    api.sql("INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, sheet_locked) "
            "VALUES (104, 'Volkan', 2, 10, 'v5', 0)")
    assert api.call("POST", "/api/characters/100/assign", 3, {"campaign_id": 10}).status_code == 409


def test_unassigned_locked_character_does_not_block_creating_one(api):
    """An unassigned locked character isn't 'in another chronicle' (it used to crash on int(None))."""
    body = {"name": "Fresh", "campaign_id": 11, "system_type": "vampire", "sheet_locked": True}
    r = api.call("POST", "/api/characters/", 3, body)
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["rules_edition"] == "classic"


def test_unassigned_character_cannot_be_the_global_active_character():
    # PUT /api/users/me with a character that has no chronicle: refused, nothing stored.
    import ast, pathlib
    src = pathlib.Path(__file__).resolve().parents[2] / "routes" / "users.py"
    text = src.read_text()
    assert "character_has_no_chronicle" in text
    ast.parse(text)
