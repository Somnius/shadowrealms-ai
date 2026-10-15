"""V5 creation check in the routes: POST /api/characters/ refuses sheets that break the creation
rules (unless the Storyteller overrides), POST /api/characters/<id>/creation-override, and the
server-owned wod_meta.creation record. Sheets come from the shared vectors
(docs/rules/v5/tests/creation-cases.json), checked against their catalog snapshot."""

import copy
import json
import sqlite3
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
CASES_FILE = next(
    (p for p in (REPO / "docs" / "rules" / "v5" / "tests" / "creation-cases.json",
                 Path("/app/project_docs/rules/v5/tests/creation-cases.json")) if p.is_file()),
    None,
)
pytestmark = pytest.mark.skipif(CASES_FILE is None, reason="docs/rules/v5/tests not on disk")
DOC = json.loads(CASES_FILE.read_text("utf-8")) if CASES_FILE else {"catalog": {}, "cases": []}

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY, username TEXT, role TEXT,
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
    (1, 'admin', 'admin'), (2, 'st', 'player'), (3, 'player', 'player'), (4, 'other', 'player'),
    (5, 'helper', 'helper');
INSERT INTO campaigns (id, name, game_system, rules_edition, created_by) VALUES
    (10, 'Athens by Night', 'vampire', 'v5', 2),
    (11, 'Thessaloniki', 'vampire', 'v5', 4),
    (12, 'Constantinople', 'vampire', 'classic', 2);
INSERT INTO campaign_players (campaign_id, user_id, role) VALUES
    (10, 2, 'owner'), (10, 3, 'player'), (10, 4, 'player'), (11, 4, 'owner'), (12, 2, 'owner'),
    (12, 3, 'player');
"""


class Cur:
    def __init__(self, conn):
        self._c = conn.cursor()

    def execute(self, sql, params=()):
        # SQLite has no row locks; production (PostgreSQL) keeps FOR UPDATE.
        self._c.execute(sql.replace("%s", "?").replace(" FOR UPDATE", ""), tuple(params))

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

    def meta(character_id):
        return json.loads(sql("SELECT wod_meta FROM characters WHERE id = ?", (character_id,))[0][0])

    return types.SimpleNamespace(call=call, sql=sql, meta=meta, catalog=catalog)


def body(case_name, name="Ada", campaign_id=10, **extra):
    c = next(c for c in DOC["cases"] if c["name"] == case_name)
    out = {"name": name, "campaign_id": campaign_id, **copy.deepcopy(c["payload"]), "sheet_locked": True}
    out.update(extra)
    return out


VALID = "valid: Brujah Alleycat neonate with 13 XP spent"
OVER = "advantages: 8 dots of your own"


def test_a_valid_sheet_is_stored_as_validated(api):
    r = api.call("POST", "/api/characters/", 3, body(VALID))
    assert r.status_code == 201, r.get_json()
    creation = api.meta(r.get_json()["character_id"])["creation"]
    assert creation["validated"] is True and creation["rules"] == "v2"
    assert creation["at"].endswith("Z")


def test_a_sheet_over_budget_is_refused_with_codes(api):
    r = api.call("POST", "/api/characters/", 3, body(OVER))
    assert r.status_code == 400
    out = r.get_json()
    assert out["error_code"] == "creation_invalid"
    assert out["problems"] == [{"code": "adv_over", "params": {"max": 7, "have": 8}}]
    assert "adv_over" in out["error"]
    assert api.sql("SELECT COUNT(*) FROM characters") == [(0,)]


def test_the_client_cannot_send_its_own_creation_record(api):
    forged = {"validated": True, "at": "2026-01-01T00:00:00Z", "rules": "v2"}
    b = body(OVER)
    b["wod_meta"]["creation"] = forged
    assert api.call("POST", "/api/characters/", 3, b).status_code == 400
    b = body(VALID)
    b["wod_meta"]["creation"] = {"validated": False, "override": {"by": 1, "reason": "x"}}
    r = api.call("POST", "/api/characters/", 3, b)
    assert r.status_code == 201
    assert api.meta(r.get_json()["character_id"])["creation"]["validated"] is True


def test_the_storyteller_overrides_with_a_reason(api):
    r = api.call("POST", "/api/characters/", 2, body(OVER, creation_override={"reason": "  ex-Camarilla favour  "}))
    assert r.status_code == 201, r.get_json()
    creation = api.meta(r.get_json()["character_id"])["creation"]
    assert creation["validated"] is False
    assert creation["override"]["by"] == 2 and creation["override"]["reason"] == "ex-Camarilla favour"
    assert creation["problems"] == [{"code": "adv_over", "params": {"max": 7, "have": 8}}]


def test_staff_may_override_players_may_not(api):
    r = api.call("POST", "/api/characters/", 3, body(OVER, creation_override={"reason": "please"}))
    assert r.status_code == 403 and r.get_json()["error_code"] == "creation_override_forbidden"
    # even on a sheet that would pass: an override request is the Storyteller's
    r = api.call("POST", "/api/characters/", 3, body(VALID, creation_override={"reason": "please"}))
    assert r.status_code == 403
    assert api.sql("SELECT COUNT(*) FROM characters") == [(0,)]
    assert api.call("POST", "/api/characters/", 1, body(OVER, creation_override={"reason": "import"})).status_code == 201


def test_an_override_needs_a_reason(api):
    for bad in ({}, {"reason": "   "}, {"reason": "x" * 501}, "text", None):
        b = body(OVER)
        b["creation_override"] = bad
        if bad is None:
            continue  # no override at all: the normal 400
        r = api.call("POST", "/api/characters/", 2, b)
        assert r.status_code == 400 and r.get_json()["error_code"] == "creation_override_reason", bad


def test_an_override_on_a_valid_sheet_records_it_as_validated(api):
    r = api.call("POST", "/api/characters/", 2, body(VALID, creation_override={"reason": "just in case"}))
    assert r.status_code == 201
    assert api.meta(r.get_json()["character_id"])["creation"]["validated"] is True


def test_chronicle_settings_are_overridable_by_the_storyteller(api):
    api.sql("""UPDATE campaigns SET creation_settings = '{"allowed_clans": ["Tremere"]}' WHERE id = 10""")
    r = api.call("POST", "/api/characters/", 3, body(VALID))
    assert r.status_code == 400
    assert r.get_json()["problems"] == ["The Storyteller doesn't allow Brujah in this chronicle."]
    r = api.call("POST", "/api/characters/", 2, body(VALID, creation_override={"reason": "guest Brujah"}))
    assert r.status_code == 201
    creation = api.meta(r.get_json()["character_id"])["creation"]
    assert creation["problems"] == [{"code": "clan_not_allowed", "params": {"clan": "Brujah"}}]


def test_without_a_catalog_the_sheet_goes_in_unchecked(api):
    api.catalog["value"] = None
    r = api.call("POST", "/api/characters/", 3, body(OVER))
    assert r.status_code == 201
    creation = api.meta(r.get_json()["character_id"])["creation"]
    assert creation == {"validated": False, "at": creation["at"], "rules": "v2", "reason": "catalog_missing"}


def test_bounds_errors_still_come_first(api):
    b = body(VALID)
    b["wod_meta"]["hunger"] = 9
    r = api.call("POST", "/api/characters/", 2, {**b, "creation_override": {"reason": "x"}})
    assert r.status_code == 400 and "hunger" in r.get_json()["error"]


def test_classic_chronicles_are_not_checked(api):
    r = api.call("POST", "/api/characters/", 3, {"name": "Theo", "campaign_id": 12, "system_type": "vampire"})
    assert r.status_code == 201


# ---------- POST /api/characters/<id>/creation-override ----------

def _insert(api, character_id, campaign_id, user_id=3, edition="v5", case_name=OVER):
    c = next(c for c in DOC["cases"] if c["name"] == case_name)
    p = c["payload"]
    api.sql(
        "INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, attributes, skills, wod_meta) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (character_id, f"PC {character_id}", user_id, campaign_id, edition,
         json.dumps(p["attributes"]), json.dumps(p["skills"]), json.dumps(p["wod_meta"])),
    )


def test_override_route_by_the_chronicles_storyteller(api):
    _insert(api, 100, 10)
    r = api.call("POST", "/api/characters/100/creation-override", 2, {"reason": "imported from Roll20"})
    assert r.status_code == 200, r.get_json()
    creation = api.meta(100)["creation"]
    assert r.get_json()["creation"] == creation
    assert creation["validated"] is False and creation["override"]["by"] == 2
    assert creation["problems"] == [{"code": "adv_over", "params": {"max": 7, "have": 8}}]
    # the rest of the sheet is untouched
    assert api.meta(100)["advantages"] == next(c for c in DOC["cases"] if c["name"] == OVER)["payload"]["wod_meta"]["advantages"]


def test_override_route_permissions(api):
    _insert(api, 100, 10)
    assert api.call("POST", "/api/characters/100/creation-override", 3, {"reason": "mine"}).status_code == 403
    # the Storyteller of another chronicle
    assert api.call("POST", "/api/characters/100/creation-override", 4, {"reason": "x"}).status_code == 403
    assert api.call("POST", "/api/characters/100/creation-override", 5, {"reason": "x"}).status_code == 200
    assert "creation" in api.meta(100)
    assert api.call("POST", "/api/characters/999/creation-override", 1, {"reason": "x"}).status_code == 404


def test_override_route_for_a_sheet_without_chronicle_is_admin_only(api):
    _insert(api, 101, None)
    for uid in (2, 3, 5):
        assert api.call("POST", "/api/characters/101/creation-override", uid, {"reason": "x"}).status_code == 403
    r = api.call("POST", "/api/characters/101/creation-override", 1, {"reason": "imported sheet"})
    assert r.status_code == 200
    assert api.meta(101)["creation"]["override"] == {"by": 1, "reason": "imported sheet", "at": api.meta(101)["creation"]["at"]}


def test_override_route_refuses_bad_requests(api):
    _insert(api, 102, 12, edition="classic")
    assert api.call("POST", "/api/characters/102/creation-override", 2, {"reason": "x"}).get_json()["error_code"] == "not_v5"
    _insert(api, 103, 10)
    for b in ({}, {"reason": ""}, {"reason": "y" * 501}):
        r = api.call("POST", "/api/characters/103/creation-override", 2, b)
        assert r.status_code == 400 and r.get_json()["error_code"] == "creation_override_reason"
    assert "creation" not in api.meta(103)


def test_override_route_uses_the_chronicle_settings(api):
    api.sql("""UPDATE campaigns SET creation_settings = '{"allowed_ages": ["childer"]}' WHERE id = 10""")
    _insert(api, 104, 10, case_name=VALID)
    r = api.call("POST", "/api/characters/104/creation-override", 2, {"reason": "veteran"})
    assert r.get_json()["creation"]["problems"] == [{"code": "age_not_allowed", "params": {"age": "neonate"}}]


# ---------- the record is the server's ----------

def test_staff_edits_keep_the_creation_record(api):
    r = api.call("POST", "/api/characters/", 3, body(VALID))
    cid = r.get_json()["character_id"]
    stored = api.meta(cid)["creation"]
    meta = api.meta(cid)
    meta.pop("creation")
    meta["hunger"] = 3
    assert api.call("PUT", f"/api/characters/{cid}", 1, {"wod_meta": meta}).status_code == 200
    assert api.meta(cid)["hunger"] == 3 and api.meta(cid)["creation"] == stored
    meta["creation"] = {"validated": True, "override": {"by": 1, "reason": "forged"}}
    assert api.call("PUT", f"/api/characters/{cid}", 1, {"wod_meta": meta}).status_code == 200
    assert api.meta(cid)["creation"] == stored
