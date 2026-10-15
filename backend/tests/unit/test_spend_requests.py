"""Saved-point spends: routes/spend_requests.py with an in-memory SQLite stand-in for PostgreSQL."""

import json
import sqlite3
import sys
import types
from datetime import datetime

import pytest

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT);
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY, name TEXT, game_system TEXT, rules_edition TEXT DEFAULT 'classic',
    created_by INTEGER, is_active INTEGER DEFAULT 1, creation_settings TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE characters (
    id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER, campaign_id INTEGER,
    system_type TEXT DEFAULT 'vampire', attributes TEXT DEFAULT '{}', skills TEXT DEFAULT '{}',
    merits_flaws TEXT DEFAULT '{}', wod_meta TEXT DEFAULT '{}', rules_edition TEXT DEFAULT 'classic',
    sheet_locked INTEGER DEFAULT 1, updated_at TEXT
);
CREATE TABLE character_spend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL, campaign_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
    kind TEXT NOT NULL, payload TEXT NOT NULL, rule_check TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', approver TEXT, resolved_by INTEGER, resolved_at TIMESTAMP,
    reason TEXT, before_state TEXT, after_state TEXT, reversed_by INTEGER, reversed_at TIMESTAMP,
    reverse_reason TEXT, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO users (id, username, role) VALUES
    (1, 'admin', 'admin'), (2, 'st', 'player'), (3, 'eleni', 'player'), (4, 'other', 'player'),
    (5, 'st2', 'player');
INSERT INTO campaigns (id, name, game_system, rules_edition, created_by, creation_settings) VALUES
    (10, 'Athens by Night', 'vampire', 'v5', 2, '{"st_mode": "human"}'),
    (11, 'Self-run', 'vampire', 'v5', 2, '{"st_mode": "ai"}'),
    (12, 'Elsewhere', 'vampire', 'v5', 5, '{}'),
    (13, 'Classic', 'vampire', 'classic', 2, '{}');
"""

META = {
    "edition": "v5",
    "clan": "Toreador",
    "hunger": 1,
    "advantages": [
        {"name": "Resources", "dots": 3, "kind": "background"},
        {"name": "Herd", "dots": 2, "kind": "predator"},
    ],
    "saved": {"advantage_dots": 2, "specialty": 1},
}
SKILLS = {"social": {"persuasion": 3}, "mental": {"occult": 1}, "specialties": [{"skill": "occult", "name": "Vampires"}]}
MF = {"entries": [{"name": "Resources", "points": 3, "note": "background"}]}


class Cur:
    def __init__(self, conn):
        self._c = conn.cursor()

    def execute(self, sql, params=()):
        # PostgreSQL row locks have no SQLite form; one connection serialises anyway.
        params = tuple(p.isoformat(" ") if isinstance(p, datetime) else p for p in params)
        self._c.execute(sql.replace(" FOR UPDATE", "").replace("%s", "?"), params)

    def _row(self, r):
        return None if r is None else {k[0]: v for k, v in zip(self._c.description, r)}

    def fetchone(self):
        return self._row(self._c.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._c.fetchall()]

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

    from routes import spend_requests

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.executescript(SCHEMA)
    for cid, campaign in ((100, 10), (101, 11), (102, None)):
        raw.execute(
            "INSERT INTO characters (id, name, user_id, campaign_id, rules_edition, wod_meta, skills, merits_flaws) "
            "VALUES (?, ?, 3, ?, 'v5', ?, ?, ?)",
            (cid, f"Eleni {cid}", campaign, json.dumps(META), json.dumps(SKILLS), json.dumps(MF)),
        )
    raw.execute(
        "INSERT INTO characters (id, name, user_id, campaign_id, rules_edition) VALUES (103, 'Old', 3, 13, 'classic')"
    )
    raw.commit()
    catalog = {}
    readable = {"ok": True}
    monkeypatch.setattr(spend_requests, "get_db", lambda: Conn(raw))
    monkeypatch.setattr(spend_requests, "_ensure", lambda cursor: None)
    monkeypatch.setattr(spend_requests, "_spend_catalog", lambda: (catalog, readable["ok"]))

    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(spend_requests.spend_requests_bp, url_prefix="/api")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in (1, 2, 3, 4, 5)}
    c = app.test_client()

    def call(method, url, uid, body=None):
        return c.open(url, method=method, json=body, headers={"Authorization": f"Bearer {tokens[uid]}"})

    def sql(q, params=()):
        cur = raw.execute(q, params)
        raw.commit()
        return cur.fetchall()

    def sheet(cid):
        (row,) = sql("SELECT wod_meta, skills, merits_flaws FROM characters WHERE id = ?", (cid,))
        return {k: json.loads(v) for k, v in zip(("wod_meta", "skills", "merits_flaws"), row)}

    return types.SimpleNamespace(call=call, sql=sql, sheet=sheet, catalog=catalog, readable=readable)


RESOURCES = {"kind": "saved_advantage", "items": [{"name": "Resources", "dots": 1, "kind": "background"}]}


def spend(api, cid, body=RESOURCES, uid=3):
    return api.call("POST", f"/api/characters/{cid}/spend-requests", uid, body)


def patch(api, campaign, rid, uid, action, reason=None, confirm=False):
    body = {"action": action}
    if reason is not None:
        body["reason"] = reason
    if confirm:
        body["confirm_house_rule"] = True
    return api.call("PATCH", f"/api/campaigns/{campaign}/spend-requests/{rid}", uid, body)


# ---------- AI mode ----------

def test_ai_mode_applies_a_rule_following_spend_at_once(api):
    r = spend(api, 101)
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["applied"] is True
    req = body["request"]
    assert req["status"] == "approved" and req["approver"] == "ai" and req["resolved_by"] is None
    assert req["rule_check"] == {"ok": True, "problems": [], "house_rule": False}
    assert req["changes"] == [{"name": "Resources", "kind": "background", "from": 3, "to": 4}]
    assert req["character_name"] == "Eleni 101" and req["username"] == "eleni"
    s = api.sheet(101)
    assert s["wod_meta"]["advantages"][0] == {"name": "Resources", "dots": 4, "kind": "background", "saved_dots": 1}
    assert s["wod_meta"]["saved"] == {"advantage_dots": 1, "specialty": 1}
    assert s["merits_flaws"]["entries"] == [{"name": "Resources", "points": 4, "note": "background"}]


def test_ai_mode_never_approves_a_house_rule(api):
    r = spend(api, 101, {"kind": "saved_advantage", "items": [{"name": "Allies", "dots": 3}]})
    assert r.status_code == 201
    req = r.get_json()["request"]
    assert r.get_json()["applied"] is False
    assert req["status"] == "pending" and req["approver"] is None
    assert req["rule_check"]["house_rule"] is True
    assert [p["code"] for p in req["rule_check"]["problems"]] == ["saved_short"]
    assert api.sheet(101)["wod_meta"] == META


def test_ai_mode_checks_the_catalog_when_there_is_one(api):
    api.catalog["advantages"] = [{"id": "background:resources", "name": "Resources", "kind": "background", "dots": {"min": 1, "max": 5}}]
    made_up = spend(api, 101, {"kind": "saved_advantage", "items": [{"name": "Made Up", "dots": 1}]}).get_json()
    assert made_up["applied"] is False
    assert made_up["request"]["rule_check"]["problems"] == [{"code": "adv_unknown", "params": {"name": "Made Up"}}]
    assert spend(api, 101).get_json()["applied"] is True


def test_an_unreadable_catalog_makes_every_advantage_spend_a_house_rule(api):
    api.readable["ok"] = False
    req = spend(api, 101).get_json()
    assert req["applied"] is False
    assert req["request"]["rule_check"]["problems"] == [{"code": "catalog_error", "params": {}}]
    # the specialty doesn't need the catalog
    body = {"kind": "saved_specialty", "skill": "persuasion", "name": "Bargaining"}
    assert spend(api, 101, body).get_json()["applied"] is True


def test_ai_mode_specialty(api):
    body = {"kind": "saved_specialty", "skill": "persuasion", "name": "Bargaining"}
    req = spend(api, 101, body).get_json()["request"]
    assert req["status"] == "approved" and req["approver"] == "ai"
    s = api.sheet(101)
    assert {"skill": "persuasion", "name": "Bargaining", "source": "saved"} in s["skills"]["specialties"]
    assert s["wod_meta"]["saved"]["specialty"] == 0
    # nothing saved any more: the same spend again waits for the Storyteller
    again = spend(api, 101, {"kind": "saved_specialty", "skill": "persuasion", "name": "Haggling"}).get_json()
    assert again["applied"] is False
    assert [p["code"] for p in again["request"]["rule_check"]["problems"]] == ["no_saved_specialty"]


# ---------- human Storyteller ----------

def test_human_mode_waits_for_the_storyteller(api):
    r = spend(api, 100)
    assert r.status_code == 201
    req = r.get_json()["request"]
    assert req["status"] == "pending" and r.get_json()["applied"] is False
    assert req["rule_check"]["ok"] is True
    assert api.sheet(100)["wod_meta"] == META
    # the player, another player and another chronicle's Storyteller can't decide (and get the
    # same 404 as for a chronicle that doesn't exist)
    for uid in (3, 4, 5):
        r = patch(api, 10, req["id"], uid, "approve")
        assert r.status_code == 404 and r.get_json()["error"] == "Chronicle not found or access denied"
    assert patch(api, 12, req["id"], 5, "approve").status_code == 404
    assert api.sheet(100)["wod_meta"] == META
    ok = patch(api, 10, req["id"], 2, "approve", "Fair, you earned it.")
    assert ok.status_code == 200, ok.get_json()
    done = ok.get_json()["request"]
    assert done["status"] == "approved" and done["approver"] == "user"
    assert done["resolved_by"] == 2 and done["resolved_by_name"] == "st" and done["reason"] == "Fair, you earned it."
    assert api.sheet(100)["wod_meta"]["advantages"][0]["dots"] == 4


def test_approve_twice_applies_once(api):
    rid = spend(api, 100).get_json()["request"]["id"]
    assert patch(api, 10, rid, 2, "approve").status_code == 200
    again = patch(api, 10, rid, 1, "approve")
    assert again.status_code == 409 and again.get_json()["error_code"] == "not_pending"
    s = api.sheet(100)
    assert s["wod_meta"]["advantages"][0]["dots"] == 4
    assert s["wod_meta"]["saved"]["advantage_dots"] == 1
    assert patch(api, 10, rid, 2, "reject").status_code == 409


def test_the_storyteller_may_approve_a_house_rule(api):
    body = {"kind": "saved_advantage", "items": [{"name": "Allies", "dots": 4, "kind": "background"}]}
    rid = spend(api, 100, body).get_json()["request"]["id"]
    # a house rule needs the Storyteller to confirm it
    r = patch(api, 10, rid, 2, "approve", "House rule: the war gave her friends.")
    assert r.status_code == 409 and r.get_json()["error_code"] == "now_house_rule"
    assert api.sheet(100)["wod_meta"] == META
    r = patch(api, 10, rid, 2, "approve", "House rule: the war gave her friends.", confirm=True)
    assert r.status_code == 200
    assert r.get_json()["request"]["rule_check"]["house_rule"] is True
    s = api.sheet(100)
    assert {"name": "Allies", "dots": 4, "kind": "background", "saved_dots": 4} in s["wod_meta"]["advantages"]
    assert s["wod_meta"]["saved"]["advantage_dots"] == 0


def test_reject_with_a_reason_changes_nothing(api):
    rid = spend(api, 100).get_json()["request"]["id"]
    r = patch(api, 10, rid, 2, "reject", "Not in this story.")
    assert r.status_code == 200
    req = r.get_json()["request"]
    assert req["status"] == "rejected" and req["reason"] == "Not in this story."
    assert api.sheet(100)["wod_meta"] == META
    assert patch(api, 10, rid, 2, "reverse").get_json()["error_code"] == "not_approved"


# ---------- reverse ----------

def test_reverse_restores_the_touched_keys_only(api):
    rid = spend(api, 101).get_json()["request"]["id"]
    s = api.sheet(101)
    s["wod_meta"]["hunger"] = 3  # a Rouse check after the spend
    api.sql("UPDATE characters SET wod_meta = ? WHERE id = 101", (json.dumps(s["wod_meta"]),))
    # the player can't reverse; the human creator of the AI-run chronicle and staff can
    assert patch(api, 11, rid, 3, "reverse").status_code == 404
    r = patch(api, 11, rid, 2, "reverse", "Too strong for this story.")
    assert r.status_code == 200, r.get_json()
    req = r.get_json()["request"]
    assert req["status"] == "reversed" and req["reversed_by"] == 2 and req["reversed_by_name"] == "st"
    assert req["reverse_reason"] == "Too strong for this story." and req["reason"] is None
    back = api.sheet(101)
    assert back["wod_meta"]["advantages"] == META["advantages"]
    assert back["wod_meta"]["saved"] == META["saved"]
    assert back["merits_flaws"] == MF
    assert back["wod_meta"]["hunger"] == 3
    assert patch(api, 11, rid, 2, "reverse").get_json()["error_code"] == "not_approved"


def test_reverse_needs_the_later_spends_reversed_first(api):
    first = spend(api, 101).get_json()["request"]["id"]
    second = spend(api, 101, {"kind": "saved_advantage", "items": [{"name": "Contacts", "dots": 1}]}).get_json()["request"]["id"]
    r = patch(api, 11, first, 1, "reverse")
    assert r.status_code == 409 and r.get_json()["error_code"] == "sheet_changed"
    assert patch(api, 11, second, 1, "reverse").status_code == 200
    assert patch(api, 11, first, 1, "reverse").status_code == 200
    assert api.sheet(101)["wod_meta"] == META


# ---------- lists and permissions ----------

def test_character_list_for_owner_storyteller_and_staff(api):
    spend(api, 100)
    for uid in (3, 2, 1):
        r = api.call("GET", "/api/characters/100/spend-requests", uid)
        assert r.status_code == 200, (uid, r.get_json())
        body = r.get_json()
        assert len(body["requests"]) == 1
        assert body["saved"] == {"advantage_dots": 2, "specialty": 1}
        assert body["settings"]["st_mode"] == "human"
        assert body["settings"]["allowed_books"] is None  # the picker offers every book
        assert body["can_spend"] is (uid == 3)
        assert body["can_review"] is (uid in (1, 2))
    assert api.call("GET", "/api/characters/100/spend-requests", 4).status_code == 403
    assert api.call("GET", "/api/characters/100/spend-requests", 5).status_code == 403
    assert api.call("GET", "/api/characters/999/spend-requests", 3).status_code == 404


def test_chronicle_list_for_its_storyteller_and_staff(api):
    spend(api, 100)
    rid = spend(api, 100, {"kind": "saved_specialty", "skill": "persuasion", "name": "Bargaining"}).get_json()["request"]["id"]
    patch(api, 10, rid, 2, "reject")
    r = api.call("GET", "/api/campaigns/10/spend-requests", 2)
    assert r.status_code == 200
    assert [x["status"] for x in r.get_json()["requests"]] == ["pending", "rejected"]
    assert r.get_json()["st_mode"] == "human"
    pending = api.call("GET", "/api/campaigns/10/spend-requests?status=pending", 1).get_json()["requests"]
    assert [x["kind"] for x in pending] == ["saved_advantage"]
    assert api.call("GET", "/api/campaigns/10/spend-requests?status=odd", 2).status_code == 400
    for uid in (3, 5):
        r = api.call("GET", "/api/campaigns/10/spend-requests", uid)
        assert r.status_code == 404 and r.get_json()["error"] == "Chronicle not found or access denied"
    assert api.call("GET", "/api/campaigns/99/spend-requests", 1).status_code == 404


def test_post_checks(api):
    assert spend(api, 100, uid=4).status_code == 403
    assert spend(api, 100, uid=2).status_code == 403  # the Storyteller can't spend a player's points
    assert spend(api, 999).status_code == 404
    assert spend(api, 100, {"kind": "xp"}).status_code == 400
    assert spend(api, 100, {"kind": "saved_advantage", "items": [{"name": "Resources", "dots": 9}]}).status_code == 400
    r = spend(api, 102)
    assert r.status_code == 400 and r.get_json()["error_code"] == "character_has_no_chronicle"
    r = spend(api, 103)
    assert r.status_code == 400 and r.get_json()["error_code"] == "not_v5"
    assert api.sql("SELECT COUNT(*) FROM character_spend_requests") == [(0,)]


def test_too_many_pending(api):
    for _ in range(10):
        assert spend(api, 100).status_code == 201
    r = spend(api, 100)
    assert r.status_code == 409 and r.get_json()["error_code"] == "too_many_pending"


def test_patch_checks(api):
    rid = spend(api, 100).get_json()["request"]["id"]
    assert patch(api, 10, rid, 2, "maybe").status_code == 400
    assert api.call("PATCH", f"/api/campaigns/10/spend-requests/{rid}", 2, {"action": "reject", "reason": "x" * 501}).status_code == 400
    assert patch(api, 10, 999, 2, "approve").status_code == 404
    assert patch(api, 99, rid, 1, "approve").status_code == 404


def test_approve_runs_the_check_again_on_todays_sheet(api):
    a = spend(api, 100, {"kind": "saved_advantage", "items": [{"name": "Contacts", "dots": 2}]}).get_json()["request"]
    b = spend(api, 100, {"kind": "saved_advantage", "items": [{"name": "Haven", "dots": 2}]}).get_json()["request"]
    assert a["rule_check"]["ok"] and b["rule_check"]["ok"]
    assert patch(api, 10, a["id"], 2, "approve").status_code == 200
    # the first one used the 2 saved dots: the second is a house rule now
    r = patch(api, 10, b["id"], 2, "approve")
    assert r.status_code == 409 and r.get_json()["error_code"] == "now_house_rule"
    assert r.get_json()["rule_check"]["problems"] == [{"code": "saved_short", "params": {"need": 2, "have": 0}}]
    assert r.get_json()["request"]["rule_check"]["house_rule"] is True  # stored for the list too
    assert api.sheet(100)["wod_meta"]["saved"]["advantage_dots"] == 0
    assert not any(row["name"] == "Haven" for row in api.sheet(100)["wod_meta"]["advantages"])
    ok = patch(api, 10, b["id"], 2, "approve", "Fine, one more.", confirm=True)
    assert ok.status_code == 200
    assert {"name": "Haven", "dots": 2, "kind": "merit", "saved_dots": 2} in api.sheet(100)["wod_meta"]["advantages"]


def test_reverse_keeps_the_approval_reason_apart(api):
    rid = spend(api, 100).get_json()["request"]["id"]
    patch(api, 10, rid, 2, "approve", "Earned it.")
    req = patch(api, 10, rid, 2, "reverse").get_json()["request"]
    assert req["status"] == "reversed" and req["reason"] == "Earned it." and req["reverse_reason"] is None


def test_a_damaged_sheet_column_is_refused_not_overwritten(api):
    api.sql("UPDATE characters SET merits_flaws = 'not json' WHERE id = 101")
    r = spend(api, 101)
    assert r.status_code == 500 and r.get_json()["error_code"] == "sheet_data_damaged"
    assert api.sql("SELECT merits_flaws FROM characters WHERE id = 101") == [("not json",)]
    assert api.sql("SELECT COUNT(*) FROM character_spend_requests") == [(0,)]
    api.sql("UPDATE characters SET merits_flaws = '[1, 2]' WHERE id = 101")
    assert spend(api, 101).status_code == 500


def test_only_the_touched_columns_are_written(api):
    odd = '{"social":{"persuasion":3},   "mental": {"occult": 1}, "specialties": []}'
    api.sql("UPDATE characters SET skills = ? WHERE id = 101", (odd,))
    assert spend(api, 101).get_json()["applied"] is True
    # an Advantage spend writes wod_meta and merits_flaws only: skills keep their exact text
    assert api.sql("SELECT skills FROM characters WHERE id = 101") == [(odd,)]


def test_no_catalog_installed_fails_closed(monkeypatch):
    if "psycopg2" not in sys.modules:
        pg = types.ModuleType("psycopg2")
        pg.extras = types.ModuleType("psycopg2.extras")
        monkeypatch.setitem(sys.modules, "psycopg2", pg)
        monkeypatch.setitem(sys.modules, "psycopg2.extras", pg.extras)
    from routes import spend_requests

    monkeypatch.setattr(spend_requests, "load_catalog", lambda: None)
    assert spend_requests._spend_catalog() == ({}, False)
    monkeypatch.setattr(spend_requests, "load_catalog", lambda: {"clans": []})
    assert spend_requests._spend_catalog() == ({"clans": []}, True)
