"""POST /campaigns/<id>/roll (routes/dice.py manual_roll) against an in-memory SQLite stand-in.

Pins the route's responses so the roll core can move to services/dice_rolls.py unchanged.
"""

import json
import sqlite3
import sys
import types

import pytest

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, active_character_id INTEGER);
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY, name TEXT, game_system TEXT, rules_edition TEXT DEFAULT 'classic',
    created_by INTEGER, is_active INTEGER DEFAULT 1
);
CREATE TABLE campaign_players (campaign_id INTEGER, user_id INTEGER, active_character_id INTEGER);
CREATE TABLE characters (
    id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER, campaign_id INTEGER, wod_meta TEXT DEFAULT '{}'
);
CREATE TABLE dice_rolls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL, location_id INTEGER,
    user_id INTEGER NOT NULL, character_id INTEGER, roll_type TEXT NOT NULL,
    action_description TEXT NOT NULL, dice_pool INTEGER NOT NULL, difficulty INTEGER NOT NULL,
    results TEXT NOT NULL, successes INTEGER NOT NULL, is_botch INTEGER NOT NULL DEFAULT 0,
    is_critical INTEGER NOT NULL DEFAULT 0, modifiers TEXT, rolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE locations (
    id INTEGER PRIMARY KEY, campaign_id INTEGER, is_active INTEGER DEFAULT 1,
    dice_leniency_floor INTEGER, dice_leniency_v5 TEXT
);
INSERT INTO users (id, username, role) VALUES (1, 'admin', 'admin'), (2, 'st', 'player'),
    (3, 'player', 'player'), (4, 'outsider', 'player');
INSERT INTO campaigns (id, name, game_system, rules_edition, created_by) VALUES
    (10, 'Classic table', 'vampire', 'classic', 2), (11, 'V5 table', 'vampire', 'v5', 2);
INSERT INTO campaign_players VALUES (10, 3, 100), (11, 3, 101);
INSERT INTO characters (id, name, user_id, campaign_id, wod_meta) VALUES
    (100, 'Anna', 3, 10, '{}'), (101, 'Bram', 3, 11, '{"hunger": 2}');
"""


class Cur:
    def __init__(self, conn):
        self._c = conn.cursor()

    def execute(self, sql, params=()):
        self._c.execute(sql.replace(" FOR UPDATE", "").replace("%s", "?"), tuple(params))

    def _row(self, r):
        return None if r is None else {k[0]: v for k, v in zip(self._c.description, r)}

    def fetchone(self):
        return self._row(self._c.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._c.fetchall()]

    def close(self):
        pass

    @property
    def rowcount(self):
        return self._c.rowcount


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

    from routes import dice

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.executescript(SCHEMA)
    monkeypatch.setattr(dice, "get_db", lambda: Conn(raw))
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(dice.dice_bp, url_prefix="/api")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in (1, 2, 3, 4)}
    c = app.test_client()

    def call(campaign_id, uid, body):
        return c.post(f"/api/campaigns/{campaign_id}/roll", json=body,
                      headers={"Authorization": f"Bearer {tokens[uid]}"})

    call.raw = raw
    return call


def test_classic_roll_saved_and_answered(api):
    r = api(10, 3, {"pool_size": 5, "difficulty": 7, "character_id": 100, "action_description": "Climb"})
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["rules_edition"] == "classic"
    assert body["server_posted"] is False and body["message_ids"] == []
    assert body["roll_result"]["roll_id"] == body["roll_id"]
    assert len(body["roll_result"]["results"]) >= 5
    assert "Anna" in body["chat_message"]
    row = api.raw.execute(
        "SELECT roll_type, difficulty, dice_pool, location_id, character_id, modifiers FROM dice_rolls"
    ).fetchone()
    assert row[:5] == ("manual", 7, 5, None, 100)
    assert json.loads(row[5])["rules_edition"] == "classic"


def test_v5_roll_uses_sheet_hunger_and_can_reroll(api):
    r = api(11, 3, {"pool_expression": "3+2", "character_id": 101})
    assert r.status_code == 200, r.get_json()
    res = r.get_json()["roll_result"]
    assert res["hunger"] == 2 and len(res["hunger_dice"]) == 2 and len(res["normal_dice"]) == 3
    assert res["can_reroll"] is True
    assert api.raw.execute("SELECT difficulty FROM dice_rolls").fetchone()[0] == 1


@pytest.mark.parametrize("cid,uid,body,status,msg", [
    (10, 4, {"pool_size": 3}, 403, "Campaign not found or access denied"),
    (10, 3, {}, 400, "pool_size must be at least 1 (or send pool_expression)"),
    (10, 3, {"pool_size": 51}, 400, "pool_size must be at most 50"),
    (10, 3, {"pool_size": 3, "difficulty": 1}, 400, "difficulty must be between 2 and 10"),
    (11, 3, {"pool_size": 3, "difficulty": 11}, 400,
     "difficulty (successes needed) must be between 0 and 10 for V5"),
    (11, 3, {"pool_size": 3, "hunger": 6}, 400, "hunger must be between 0 and 5"),
    (10, 3, {"pool_size": 3, "character_id": 101}, 400, "Character not found or not yours in this campaign"),
    (10, 3, {"pool_size": 3, "location_id": 999}, 400, "Location not found in this campaign"),
    (10, 3, {"pool_size": True}, 400, None),
])
def test_refusals(api, cid, uid, body, status, msg):
    r = api(cid, uid, body)
    assert r.status_code == status
    if msg:
        assert r.get_json() == {"error": msg}
    assert api.raw.execute("SELECT COUNT(*) FROM dice_rolls").fetchone()[0] == 0


def test_refusal_rolls_the_connection_back(api, monkeypatch):
    calls = []
    monkeypatch.setattr(Conn, "rollback", lambda self: calls.append("rollback"))
    r = api(10, 3, {"pool_size": 3, "difficulty": 1})
    assert r.status_code == 400 and calls == ["rollback"]
