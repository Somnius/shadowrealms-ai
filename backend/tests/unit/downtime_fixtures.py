"""Shared fixture for the downtime route tests: routes/downtime.py on in-memory SQLite with the real
downtime DDL (database.ensure_downtime_tables). Generic example data only."""

import json
import sqlite3
import sys
import types
from datetime import datetime

import pytest

BASE = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT, active_character_id INTEGER);
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY, name TEXT, game_system TEXT, rules_edition TEXT DEFAULT 'classic',
    created_by INTEGER, is_active INTEGER DEFAULT 1
);
CREATE TABLE campaign_players (campaign_id INTEGER, user_id INTEGER, active_character_id INTEGER);
CREATE TABLE characters (
    id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER, campaign_id INTEGER, wod_meta TEXT DEFAULT '{}',
    play_suspended INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1
);
CREATE TABLE character_moderation (
    id INTEGER PRIMARY KEY, character_id INTEGER, action TEXT, death_type TEXT,
    death_description TEXT, moderated_at TEXT
);
CREATE TABLE locations (
    id INTEGER PRIMARY KEY, campaign_id INTEGER, name TEXT, is_active INTEGER DEFAULT 1,
    is_open INTEGER DEFAULT 1, dice_leniency_floor INTEGER, dice_leniency_v5 TEXT
);
CREATE TABLE dice_rolls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL, location_id INTEGER,
    user_id INTEGER NOT NULL, character_id INTEGER, roll_type TEXT NOT NULL,
    action_description TEXT NOT NULL, dice_pool INTEGER NOT NULL, difficulty INTEGER NOT NULL,
    results TEXT NOT NULL, successes INTEGER NOT NULL, is_botch INTEGER NOT NULL DEFAULT 0,
    is_critical INTEGER NOT NULL DEFAULT 0, modifiers TEXT, rolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO users (id, username, role) VALUES
    (1, 'admin', 'admin'), (2, 'st', 'player'), (3, 'alice', 'player'), (4, 'bob', 'player'),
    (5, 'helper', 'helper'), (6, 'outsider', 'player'), (7, 'paused', 'player'), (8, 'gone', 'player');
INSERT INTO campaigns (id, name, game_system, rules_edition, created_by) VALUES
    (10, 'Classic table', 'vampire', 'classic', 2), (11, 'V5 table', 'vampire', 'v5', 2);
INSERT INTO characters (id, name, user_id, campaign_id, play_suspended) VALUES
    (100, 'Anna', 3, 10, 0), (101, 'Bram', 4, 10, 0), (102, 'Cleo', 7, 10, 1), (103, 'Dov', 8, 10, 0),
    (110, 'Eva', 3, 11, 0);
INSERT INTO campaign_players VALUES (10, 3, 100), (10, 4, 101), (10, 7, 102), (10, 8, 103), (11, 3, 110);
INSERT INTO character_moderation (character_id, action, moderated_at) VALUES (103, 'kill', '2026-01-01');
INSERT INTO locations (id, campaign_id, name, is_open) VALUES
    (50, 10, 'The Harbour', 1), (51, 10, 'Sealed Vault', 0), (52, 11, 'Other table room', 1);
"""

USERS = (1, 2, 3, 4, 5, 6, 7, 8)


class Cur:
    def __init__(self, conn):
        self._c = conn.cursor()

    def execute(self, sql, params=()):
        params = tuple(p.isoformat(" ") if isinstance(p, datetime) else p for p in params)
        self._c.execute(sql.replace(" FOR UPDATE", "").replace("%s", "?"), params)

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
def dt(monkeypatch):
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    monkeypatch.delenv("DATABASE_TYPE", raising=False)
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    import database
    from routes import dice, downtime

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.execute("PRAGMA foreign_keys = ON")
    raw.executescript(BASE)
    database.ensure_downtime_tables(raw.cursor())
    raw.commit()
    monkeypatch.setattr(downtime, "get_db", lambda: Conn(raw))
    monkeypatch.setattr(dice, "get_db", lambda: Conn(raw))

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(downtime.downtime_bp, url_prefix="/api")
    app.register_blueprint(dice.dice_bp, url_prefix="/api")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in USERS}
    client = app.test_client()

    class Api:
        def call(self, method, url, uid, body=None):
            return client.open("/api" + url, method=method, json=body,
                               headers={"Authorization": f"Bearer {tokens[uid]}"})

        def get(self, url, uid):
            return self.call("GET", url, uid)

        def post(self, url, uid, body=None):
            return self.call("POST", url, uid, body if body is not None else {})

        def sql(self, q, params=()):
            cur = raw.execute(q, params)
            raw.commit()
            return cur.fetchall()

        def ok(self, resp, status=200):
            assert resp.status_code == status, resp.get_json()
            return resp.get_json()

        # Common steps
        def open_round(self, cid=10, title="Winter nights"):
            return self.ok(self.post(f"/campaigns/{cid}/downtime/rounds", 2, {"title": title}), 201)["round"]

        def project(self, uid=3, cid=10, title="Buy the old theatre", **extra):
            body = {"title": title, "goal": "Own a haven downtown", **extra}
            return self.ok(self.post(f"/campaigns/{cid}/downtime/projects", uid, body), 201)["project"]

        def declare(self, pid, uid=3, cid=10, action="Talk to the owner"):
            return self.ok(self.post(f"/campaigns/{cid}/downtime/projects/{pid}/phases", uid,
                                     {"action": action}), 201)["phase"]

        def ready(self, phid, cid=10, difficulty=None, hidden=False, version=1):
            body = {"version": version, "difficulty": difficulty, "difficulty_hidden": hidden}
            return self.ok(self.call("PUT", f"/campaigns/{cid}/downtime/phases/{phid}/setup", 2, body))["phase"]

    api = Api()
    api.raw = raw
    api.json = json
    return api
