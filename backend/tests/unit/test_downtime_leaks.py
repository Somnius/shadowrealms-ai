"""Nothing Storyteller-only reaches a player: raw response text of every player call, before and
after release, plus scene rooms and account deletion."""

import sqlite3

import pytest

from tests.unit.downtime_fixtures import dt  # noqa: F401 - pytest fixture

SECRETS = ("ZZINDNAME", "ZZVARNAME", "ZZVARNOTE", "ZZSTNOTE", "424242", "919191", "ZZBOBPLAN", "Sealed Vault")


def _assert_clean(resp, also=()):
    text = resp.get_data(as_text=True)
    for s in SECRETS + tuple(also):
        assert s not in text, (s, resp.request.path, text)


@pytest.fixture
def scene(dt):
    """Anna (user 3) and Bob (user 4) each have a phase; the ST adds secret indicator/variable data."""
    rnd = dt.open_round()
    anna = dt.project()
    phases = [dt.declare(anna["id"])]
    scene_proj = dt.project(title="Meet the harbour master")
    phases.append(dt.declare(scene_proj["id"], action="Arrange a meeting"))
    vault_proj = dt.project(title="Break in")
    phases.append(dt.declare(vault_proj["id"], action="Pick the lock"))
    bob = dt.project(uid=4, title="ZZBOBPLAN")
    bob_phase = dt.declare(bob["id"], uid=4, action="ZZBOBPLAN action")
    ind = dt.ok(dt.post(f"/campaigns/10/downtime/projects/{anna['id']}/indicators", 2,
                        {"name": "ZZINDNAME", "value": 424242}), 201)["indicator"]
    var = dt.ok(dt.post("/campaigns/10/downtime/variables", 2,
                        {"name": "ZZVARNAME", "value": 919191, "note": "ZZVARNOTE"}), 201)["variable"]
    dt.ready(phases[0]["id"], difficulty=9, hidden=True)
    dt.ready(phases[1]["id"])
    return dict(rnd=rnd, anna=anna, phases=phases, bob_phase=bob_phase, ind=ind, var=var)


def test_no_leaks_through_the_whole_round(dt, scene):
    rnd, phases, ind, var = scene["rnd"], scene["phases"], scene["ind"], scene["var"]
    hidden_phase = phases[0]
    calls = []

    r = dt.post(f"/campaigns/10/downtime/phases/{hidden_phase['id']}/roll", 3, {"pool_size": 6})
    calls.append(r)
    rolled = dt.ok(r)["phase"]
    assert rolled["difficulty"] is None and "successes" not in rolled["roll"]
    calls.append(dt.post(f"/campaigns/10/downtime/phases/{phases[1]['id']}/roll", 3, {"pool_size": 3}))
    calls.append(dt.post("/campaigns/10/downtime/projects", 3, {"title": "Another"}))
    calls.append(dt.get("/campaigns/10/downtime", 3))

    dt.ok(dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/resolve", 2))
    deltas = [{"target_kind": "indicator", "target_id": ind["id"], "delta": 1},
              {"target_kind": "variable", "target_id": var["id"], "delta": -1}]
    dt.ok(dt.post(f"/campaigns/10/downtime/phases/{phases[0]['id']}/resolve", 2, {
        "version": 3, "result_kind": "result", "result_text": "ZZRESULT one", "st_note": "ZZSTNOTE",
        "deltas": deltas}))
    dt.ok(dt.post(f"/campaigns/10/downtime/phases/{phases[1]['id']}/resolve", 2, {
        "version": 3, "result_kind": "scene", "result_text": "ZZRESULT two", "result_location_id": 50,
        "st_note": "ZZSTNOTE"}))
    dt.ok(dt.post(f"/campaigns/10/downtime/phases/{phases[2]['id']}/resolve", 2, {
        "version": 1, "result_kind": "scene", "result_text": "ZZRESULT three", "result_location_id": 51}))
    dt.ok(dt.post(f"/campaigns/10/downtime/phases/{scene['bob_phase']['id']}/resolve", 2, {
        "version": 1, "result_kind": "feedback", "result_text": "ZZBOBPLAN result"}))

    # resolving: players are locked out and see no results yet
    before = dt.get("/campaigns/10/downtime", 3)
    _assert_clean(before, also=("ZZRESULT",))
    assert all(p["status"] in ("rolled", "declared")
               for proj in before.get_json()["projects"] for p in proj["phases"])
    locked = dt.post(f"/campaigns/10/downtime/projects/{scene['anna']['id']}/phases", 3, {"action": "x"})
    assert locked.status_code == 409
    calls.append(locked)

    # every Storyteller endpoint refuses the player without echoing data
    st_calls = [
        ("GET", "/campaigns/10/downtime/inbox"), ("GET", "/campaigns/10/downtime/rounds"),
        ("GET", "/campaigns/10/downtime/variables"), ("GET", "/campaigns/10/downtime/changes"),
        ("POST", "/campaigns/10/downtime/variables"),
        ("PATCH", f"/campaigns/10/downtime/variables/{var['id']}"),
        ("DELETE", f"/campaigns/10/downtime/variables/{var['id']}"),
        ("PATCH", f"/campaigns/10/downtime/indicators/{ind['id']}"),
        ("DELETE", f"/campaigns/10/downtime/indicators/{ind['id']}"),
        ("POST", f"/campaigns/10/downtime/projects/{scene['anna']['id']}/indicators"),
        ("PATCH", f"/campaigns/10/downtime/projects/{scene['anna']['id']}"),
        ("PUT", f"/campaigns/10/downtime/phases/{phases[0]['id']}/setup"),
        ("POST", f"/campaigns/10/downtime/phases/{phases[0]['id']}/resolve"),
        ("POST", f"/campaigns/10/downtime/rounds/{rnd['id']}/release"),
        ("POST", "/campaigns/10/downtime/rounds"),
    ]
    for uid in (3, 4, 6, 7, 8):
        for method, url in st_calls:
            r = dt.call(method, url, uid, {"name": "x", "value": 1})
            assert r.status_code == 403, (uid, method, url, r.status_code)
            calls.append(r)

    dt.ok(dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/release", 2))
    after = dt.get("/campaigns/10/downtime", 3)
    calls.append(after)
    body = after.get_json()
    phases_out = {p["id"]: p for proj in body["projects"] for p in proj["phases"]}
    first = phases_out[phases[0]["id"]]
    assert first["status"] == "resolved" and first["result_text"] == "ZZRESULT one"
    assert first["difficulty"] == 9 and first["roll"]["difficulty"] == 9 and "successes" in first["roll"]
    second = phases_out[phases[1]["id"]]
    assert second["result_kind"] == "scene" and second["result_location"] == {"id": 50, "name": "The Harbour"}
    third = phases_out[phases[2]["id"]]
    assert third["result_kind"] == "scene" and third["result_location"] is None  # closed room
    for p in phases_out.values():
        assert "st_note" not in p and "changes" not in p and "version" not in p

    for r in calls:
        _assert_clean(r)
    # Bob sees his own result, not Anna's
    bob_view = dt.get("/campaigns/10/downtime", 4)
    assert "ZZRESULT" not in bob_view.get_data(as_text=True)
    assert "ZZBOBPLAN result" in bob_view.get_data(as_text=True)


def test_storyteller_sees_it_all(dt, scene):
    text = dt.get("/campaigns/10/downtime/inbox", 2).get_data(as_text=True)
    for s in ("ZZINDNAME", "ZZVARNAME", "ZZVARNOTE", "424242", "919191", "ZZBOBPLAN"):
        assert s in text


def test_player_error_bodies_carry_codes(dt, scene):
    r = dt.post("/campaigns/10/downtime/projects", 3, {"title": ""})
    assert set(r.get_json()) == {"error", "code"}
    r = dt.post(f"/campaigns/10/downtime/phases/{scene['bob_phase']['id']}/roll", 3, {"pool_size": 3})
    assert r.get_json()["code"] == "phase_not_found"


# ---------------------------------------------------------------- account deletion


ACCOUNT_SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, email TEXT, password_hash TEXT, role TEXT,
                    is_active INTEGER, active_character_id INTEGER);
CREATE TABLE campaigns (id INTEGER PRIMARY KEY, created_by INTEGER);
CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER);
CREATE TABLE campaign_players (campaign_id INTEGER, user_id INTEGER, active_character_id INTEGER);
CREATE TABLE messages (id INTEGER PRIMARY KEY, user_id INTEGER, character_id INTEGER);
CREATE TABLE locations (id INTEGER PRIMARY KEY);
CREATE TABLE dice_rolls (id INTEGER PRIMARY KEY, user_id INTEGER, character_id INTEGER);
INSERT INTO users (id, username, role) VALUES (1, 'admin', 'admin'), (2, 'st', 'player'), (3, 'alice', 'player');
INSERT INTO campaigns VALUES (10, 2);
INSERT INTO characters VALUES (100, 'Anna', 3);
"""


def test_account_delete_keeps_the_project_by_stored_name(monkeypatch):
    monkeypatch.delenv("DATABASE_TYPE", raising=False)
    import database
    from services.user_account_delete import delete_player_account_preserving_chats

    raw = sqlite3.connect(":memory:")  # no foreign key enforcement: the explicit updates must do it
    raw.executescript(ACCOUNT_SCHEMA)
    database.ensure_downtime_tables(raw.cursor())
    raw.execute("INSERT INTO downtime_rounds (id, campaign_id, opened_by) VALUES (1, 10, 2)")
    raw.execute("INSERT INTO downtime_projects (id, campaign_id, character_id, character_name, title) "
                "VALUES (5, 10, 100, 'Anna', 'Buy the old theatre')")
    raw.execute("INSERT INTO downtime_phases (project_id, round_id, action, resolved_by) VALUES (5, 1, 'Ask', 3)")
    raw.commit()
    ok, err, stats = delete_player_account_preserving_chats(raw, 3, 1)
    assert ok, err
    assert raw.execute("SELECT character_id, character_name, title FROM downtime_projects").fetchone() == (
        None, "Anna", "Buy the old theatre")
    assert raw.execute("SELECT resolved_by FROM downtime_phases").fetchone() == (None,)
    assert raw.execute("SELECT COUNT(*) FROM characters").fetchone()[0] == 0
