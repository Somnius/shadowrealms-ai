"""routes/downtime.py: rounds, projects and phases (SQLite stand-in with the real downtime DDL)."""

import pytest

from tests.unit.downtime_fixtures import dt  # noqa: F401 - pytest fixture


# ---------------------------------------------------------------- permissions


@pytest.mark.parametrize("uid,status,code", [
    (2, 201, None), (1, 201, None), (5, 201, None),
    (3, 403, "storyteller_only"), (6, 403, "storyteller_only"), (7, 403, "storyteller_only"),
])
def test_open_round_permissions(dt, uid, status, code):
    r = dt.post("/campaigns/10/downtime/rounds", uid, {"title": "Spring"})
    assert r.status_code == status
    if code:
        assert r.get_json()["code"] == code


@pytest.mark.parametrize("url", [
    "/campaigns/10/downtime/rounds/1/resolve", "/campaigns/10/downtime/rounds/1/reopen",
    "/campaigns/10/downtime/rounds/1/release",
])
@pytest.mark.parametrize("uid", [3, 4, 6, 7, 8])
def test_round_moves_are_storyteller_only(dt, url, uid):
    dt.open_round()
    r = dt.post(url, uid)
    assert r.status_code == 403 and r.get_json()["code"] == "storyteller_only"


@pytest.mark.parametrize("uid", [3, 6])
def test_round_list_is_storyteller_only(dt, uid):
    r = dt.get("/campaigns/10/downtime/rounds", uid)
    assert r.status_code == 403


def test_unknown_or_inactive_chronicle_is_404(dt):
    assert dt.get("/campaigns/999/downtime/rounds", 2).status_code == 404
    dt.sql("UPDATE campaigns SET is_active = 0 WHERE id = 10")
    assert dt.get("/campaigns/10/downtime", 3).status_code == 404


@pytest.mark.parametrize("uid,code", [
    (6, "not_a_member"), (7, "character_suspended"), (8, "character_fallen"), (2, "not_a_member"),
])
def test_players_without_a_playable_character_cannot_file(dt, uid, code):
    r = dt.post("/campaigns/10/downtime/projects", uid, {"title": "x"})
    assert r.status_code == 403 and r.get_json()["code"] == code


def test_player_view_for_non_members_and_storyteller(dt):
    assert dt.get("/campaigns/10/downtime", 6).status_code == 403
    st = dt.ok(dt.get("/campaigns/10/downtime", 2))
    assert st["is_storyteller"] is True and st["can_play"] is False and st["projects"] == []
    paused = dt.ok(dt.get("/campaigns/10/downtime", 7))
    assert paused["can_play"] is False and paused["player_problem"] == "character_suspended"


# ---------------------------------------------------------------- rounds


def test_one_live_round_and_the_flow(dt):
    rnd = dt.open_round()
    assert rnd["status"] == "open"
    r = dt.post("/campaigns/10/downtime/rounds", 2, {"title": "Again"})
    assert r.status_code == 409 and r.get_json()["code"] == "round_already_live"
    # another chronicle has its own round
    dt.open_round(cid=11)
    moved = dt.ok(dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/resolve", 2))["round"]
    assert moved["status"] == "resolving" and moved["resolving_at"]
    r = dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/resolve", 2)
    assert r.status_code == 409 and r.get_json()["code"] == "round_wrong_status"
    assert dt.ok(dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/reopen", 2))["round"]["status"] == "open"
    rounds = dt.ok(dt.get("/campaigns/10/downtime/rounds", 2))["rounds"]
    assert [x["id"] for x in rounds] == [rnd["id"]]


def test_round_of_another_chronicle_is_404(dt):
    other = dt.open_round(cid=11)
    r = dt.post(f"/campaigns/10/downtime/rounds/{other['id']}/resolve", 2)
    assert r.status_code == 404 and r.get_json()["code"] == "round_not_found"


# ---------------------------------------------------------------- projects and phases


def test_project_validation(dt):
    r = dt.post("/campaigns/10/downtime/projects", 3, {"title": "  "})
    assert r.status_code == 400 and r.get_json()["code"] == "title_required"
    r = dt.post("/campaigns/10/downtime/projects", 3, {"title": "x" * 201})
    assert r.status_code == 400 and r.get_json()["code"] == "title_too_long"
    r = dt.post("/campaigns/10/downtime/projects", 3, {"title": "x", "parent_id": "a"})
    assert r.status_code == 400 and r.get_json()["code"] == "invalid_input"


def test_parent_must_be_own_project(dt):
    mine = dt.project()
    child = dt.project(title="Find the deed", parent_id=mine["id"])
    assert child["parent_id"] == mine["id"] and child["parent_title"] == "Buy the old theatre"
    bobs = dt.project(uid=4, title="Bob's plan")
    r = dt.post("/campaigns/10/downtime/projects", 3, {"title": "Steal", "parent_id": bobs["id"]})
    assert r.status_code == 400 and r.get_json()["code"] == "invalid_parent"
    # a project of mine in another chronicle is not a parent here either
    other = dt.project(cid=11, title="Elsewhere")
    r = dt.post("/campaigns/10/downtime/projects", 3, {"title": "x", "parent_id": other["id"]})
    assert r.get_json()["code"] == "invalid_parent"


def test_declare_needs_an_open_round(dt):
    p = dt.project()
    r = dt.post(f"/campaigns/10/downtime/projects/{p['id']}/phases", 3, {"action": "Ask"})
    assert r.status_code == 409 and r.get_json()["code"] == "no_open_round"
    rnd = dt.open_round()
    ph = dt.declare(p["id"])
    assert ph["status"] == "declared" and ph["round_id"] == rnd["id"] and ph["roll"] is None
    r = dt.post(f"/campaigns/10/downtime/projects/{p['id']}/phases", 3, {"action": "Twice"})
    assert r.status_code == 409 and r.get_json()["code"] == "phase_exists"
    dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/resolve", 2)
    p2 = dt.project(title="Second")
    r = dt.post(f"/campaigns/10/downtime/projects/{p2['id']}/phases", 3, {"action": "Late"})
    assert r.status_code == 409 and r.get_json()["code"] == "round_locked"


def test_cannot_declare_on_someone_elses_project(dt):
    dt.open_round()
    bobs = dt.project(uid=4, title="Bob's plan")
    r = dt.post(f"/campaigns/10/downtime/projects/{bobs['id']}/phases", 3, {"action": "Meddle"})
    assert r.status_code == 404 and r.get_json()["code"] == "project_not_found"


def test_player_sees_only_own_projects(dt):
    dt.open_round()
    mine = dt.project()
    dt.declare(mine["id"])
    dt.project(uid=4, title="Bob's secret plan")
    view = dt.ok(dt.get("/campaigns/10/downtime", 3))
    assert view["character"] == {"id": 100, "name": "Anna"}
    assert view["round"]["status"] == "open"
    assert [p["title"] for p in view["projects"]] == ["Buy the old theatre"]
    assert len(view["projects"][0]["phases"]) == 1
    assert "Bob's secret plan" not in dt.get("/campaigns/10/downtime", 3).get_data(as_text=True)


# ---------------------------------------------------------------- phase roll


def _roll(dt, phid, uid=3, cid=10, **body):
    return dt.post(f"/campaigns/{cid}/downtime/phases/{phid}/roll", uid, body or {"pool_size": 5})


def test_roll_saves_a_downtime_roll_with_the_phase_difficulty(dt):
    dt.open_round()
    ph = dt.declare(dt.project()["id"])
    dt.ready(ph["id"], difficulty=8)
    out = dt.ok(_roll(dt, ph["id"], pool_size=4, difficulty=3))["phase"]
    assert out["status"] == "rolled"
    roll = out["roll"]
    assert roll["difficulty"] == 8 and roll["outcome_hidden"] is False
    assert len(roll["results"]) >= 4 and "successes" in roll
    row = dt.sql("SELECT roll_type, difficulty, location_id, character_id, dice_pool FROM dice_rolls")
    assert row == [("downtime", 8, None, 100, 4)]
    assert dt.sql("SELECT dice_roll_id, version FROM downtime_phases")[0] == (roll["id"], 3)


def test_roll_uses_the_edition_default_when_unset(dt):
    dt.open_round(cid=11)
    ph = dt.declare(dt.project(cid=11)["id"], cid=11)
    dt.ready(ph["id"], cid=11)
    roll = dt.ok(_roll(dt, ph["id"], cid=11, pool_expression="3+1", hunger=4))["phase"]["roll"]
    assert roll["hunger"] == 0  # client hunger ignored; the sheet has none
    assert roll["rules_edition"] == "v5" and roll["difficulty"] == 1
    assert len(roll["normal_dice"]) + len(roll["hunger_dice"]) == 4


def test_second_roll_is_409_and_nothing_saved(dt):
    dt.open_round()
    ph = dt.declare(dt.project()["id"])
    dt.ready(ph["id"])
    dt.ok(_roll(dt, ph["id"]))
    r = _roll(dt, ph["id"])
    assert r.status_code == 409 and r.get_json()["code"] == "already_rolled"
    assert dt.sql("SELECT COUNT(*) FROM dice_rolls")[0][0] == 1


def test_roll_only_own_phase_and_only_while_open(dt):
    rnd = dt.open_round()
    ph = dt.declare(dt.project()["id"])
    dt.ready(ph["id"])
    r = _roll(dt, ph["id"], uid=4)
    assert r.status_code == 404 and r.get_json()["code"] == "phase_not_found"
    r = _roll(dt, ph["id"], uid=2)
    assert r.status_code == 403
    dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/resolve", 2)
    r = _roll(dt, ph["id"])
    assert r.status_code == 409 and r.get_json()["code"] == "round_locked"
    assert dt.sql("SELECT COUNT(*) FROM dice_rolls")[0][0] == 0


@pytest.mark.parametrize("body,code", [
    ({}, "pool_required"), ({"pool_size": 51}, "pool_too_big"), 
    ({"pool_expression": "x"}, "invalid_input"), ({"pool_size": True}, "invalid_input"),
])
def test_roll_input_refusals(dt, body, code):
    dt.open_round()
    ph = dt.declare(dt.project()["id"])
    r = dt.post(f"/campaigns/10/downtime/phases/{ph['id']}/roll", 3, body)
    assert r.status_code == 400 and r.get_json()["code"] == code


def test_hidden_difficulty_gives_faces_only(dt):
    dt.open_round()
    ph = dt.declare(dt.project()["id"])
    dt.ready(ph["id"], difficulty=9, hidden=True)
    out = dt.ok(_roll(dt, ph["id"], pool_size=6))["phase"]
    assert out["difficulty"] is None and out["difficulty_hidden"] is True
    roll = out["roll"]
    assert roll["outcome_hidden"] is True and len(roll["results"]) >= 6
    for key in ("difficulty", "successes", "is_botch", "is_critical"):
        assert key not in roll
    view = dt.ok(dt.get("/campaigns/10/downtime", 3))
    shown = view["projects"][0]["phases"][0]
    assert shown["difficulty"] is None and "successes" not in shown["roll"]


def test_downtime_roll_cannot_be_willpower_rerolled(dt):
    dt.open_round(cid=11)
    ph = dt.declare(dt.project(cid=11)["id"], cid=11)
    dt.ready(ph["id"], cid=11)
    roll = dt.ok(_roll(dt, ph["id"], cid=11, pool_size=5))["phase"]["roll"]
    r = dt.post(f"/campaigns/11/roll/{roll['id']}/reroll", 3, {"indices": [0], "location_id": 52})
    assert r.status_code == 400 and r.get_json()["error"] == "Only V5 manual rolls can be rerolled"
    assert dt.sql("SELECT COUNT(*) FROM dice_rolls")[0][0] == 1
    assert '"rerolled": false' in dt.sql("SELECT modifiers FROM dice_rolls")[0][0]


# ---------------------------------------------------------------- Storyteller: setup, inbox, resolve


def _setup_round(dt, cid=10):
    """Open round, Anna's project with one declared phase, an indicator and a variable."""
    rnd = dt.open_round(cid=cid)
    proj = dt.project(cid=cid)
    ph = dt.declare(proj["id"], cid=cid)
    ind = dt.ok(dt.post(f"/campaigns/{cid}/downtime/projects/{proj['id']}/indicators", 2,
                        {"name": "Pressure", "value": 2}), 201)["indicator"]
    var = dt.ok(dt.post(f"/campaigns/{cid}/downtime/variables", 2,
                        {"name": "Harbour unrest", "value": 5, "note": "rises with violence"}), 201)["variable"]
    return rnd, proj, ph, ind, var


def _resolve(dt, phid, version, uid=2, cid=10, **body):
    payload = {"version": version, "result_kind": "result", "result_text": "The owner agrees.", **body}
    return dt.post(f"/campaigns/{cid}/downtime/phases/{phid}/resolve", uid, payload)


def _to_resolving(dt, rnd, cid=10):
    dt.ok(dt.post(f"/campaigns/{cid}/downtime/rounds/{rnd['id']}/resolve", 2))


def _inbox_phase(dt, phid, cid=10):
    inbox = dt.ok(dt.get(f"/campaigns/{cid}/downtime/inbox", 2))
    return next(p for p in inbox["phases"] if p["id"] == phid)


def test_setup_sets_difficulty_before_the_roll_only(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    r = _roll(dt, ph["id"])
    assert r.status_code == 409 and r.get_json()["code"] == "difficulty_not_set"
    assert dt.ok(dt.get("/campaigns/10/downtime", 3))["projects"][0]["phases"][0]["ready"] is False
    out = dt.ready(ph["id"], difficulty=7, hidden=True)
    assert out["difficulty"] == 7 and out["difficulty_hidden"] is True and out["version"] == 2 and out["ready"]
    r = dt.call("PUT", f"/campaigns/10/downtime/phases/{ph['id']}/setup", 2, {"version": 1, "difficulty": 6})
    assert r.status_code == 409 and r.get_json()["code"] == "version_conflict"
    r = dt.call("PUT", f"/campaigns/10/downtime/phases/{ph['id']}/setup", 2, {"version": 2, "difficulty": 11})
    assert r.get_json()["code"] == "invalid_difficulty"
    r = dt.call("PUT", f"/campaigns/10/downtime/phases/{ph['id']}/setup", 2, {"difficulty": 5})
    assert r.get_json()["code"] == "version_required"
    r = dt.call("PUT", f"/campaigns/10/downtime/phases/{ph['id']}/setup", 3, {"version": 2, "difficulty": 5})
    assert r.status_code == 403
    dt.ok(_roll(dt, ph["id"]))
    r = dt.call("PUT", f"/campaigns/10/downtime/phases/{ph['id']}/setup", 2, {"version": 3, "difficulty": 5})
    assert r.status_code == 409 and r.get_json()["code"] == "already_rolled"
    assert dt.sql("SELECT difficulty FROM dice_rolls")[0][0] == 7


def test_inbox_shows_unrolled_phase_and_everything_for_the_st(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    inbox = dt.ok(dt.get("/campaigns/10/downtime/inbox", 2))
    assert inbox["round"]["id"] == rnd["id"]
    p = inbox["phases"][0]
    assert p["no_roll"] is True and p["roll"] is None and p["resolved"] is False
    assert inbox["projects"][0]["indicators"][0]["name"] == "Pressure"
    assert inbox["projects"][0]["character_name"] == "Anna"
    assert inbox["variables"][0]["name"] == "Harbour unrest"
    assert {loc["name"] for loc in inbox["locations"]} == {"The Harbour", "Sealed Vault"}
    for uid in (3, 4, 6):
        assert dt.get("/campaigns/10/downtime/inbox", uid).status_code == 403


def test_resolve_needs_resolving_and_applies_deltas(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    r = _resolve(dt, ph["id"], 1)
    assert r.status_code == 409 and r.get_json()["code"] == "round_not_resolving"
    _to_resolving(dt, rnd)
    deltas = [{"target_kind": "indicator", "target_id": ind["id"], "delta": 3},
              {"target_kind": "variable", "target_id": var["id"], "delta": -2}]
    out = dt.ok(_resolve(dt, ph["id"], 1, deltas=deltas, st_note="Owner is a ghoul"))["phase"]
    assert out["resolved"] and out["version"] == 2 and out["st_note"] == "Owner is a ghoul"
    assert sorted((c["target_kind"], c["old_value"], c["new_value"]) for c in out["changes"]) == [
        ("indicator", 2, 5), ("variable", 5, 3)]
    assert dt.sql("SELECT value FROM downtime_indicators")[0][0] == 5
    assert dt.sql("SELECT value FROM chronicle_variables")[0][0] == 3
    # unresolved filter
    inbox = dt.ok(dt.get("/campaigns/10/downtime/inbox?unresolved=1", 2))
    assert inbox["phases"] == []


def test_amend_applies_only_the_difference(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    _to_resolving(dt, rnd)
    dt.ok(_resolve(dt, ph["id"], 1, deltas=[{"target_kind": "indicator", "target_id": ind["id"], "delta": 3}]))
    out = dt.ok(_resolve(dt, ph["id"], 2, deltas=[{"target_kind": "variable", "target_id": var["id"], "delta": 1}]))
    assert dt.sql("SELECT value FROM downtime_indicators")[0][0] == 2  # reversed
    assert dt.sql("SELECT value FROM chronicle_variables")[0][0] == 6
    assert [c["delta"] for c in out["phase"]["changes"]] == [3, -3, 1]
    # text-only amend keeps the deltas (no deltas key)
    dt.ok(_resolve(dt, ph["id"], 3, result_text="Changed my mind on wording"))
    assert dt.sql("SELECT value FROM chronicle_variables")[0][0] == 6


def test_version_conflict(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    _to_resolving(dt, rnd)
    dt.ok(_resolve(dt, ph["id"], 1))
    r = _resolve(dt, ph["id"], 1, result_text="stale form")
    assert r.status_code == 409 and r.get_json()["code"] == "version_conflict"
    assert r.get_json()["current_version"] == 2


def test_bad_delta_rolls_everything_back(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    other = dt.project(uid=4, title="Bob's plan")
    other_ind = dt.ok(dt.post(f"/campaigns/10/downtime/projects/{other['id']}/indicators", 2,
                              {"name": "Momentum"}), 201)["indicator"]
    _to_resolving(dt, rnd)
    deltas = [{"target_kind": "variable", "target_id": var["id"], "delta": 4},
              {"target_kind": "indicator", "target_id": other_ind["id"], "delta": 1}]
    r = _resolve(dt, ph["id"], 1, deltas=deltas)
    assert r.status_code == 400 and r.get_json()["code"] == "invalid_target"
    assert dt.sql("SELECT value FROM chronicle_variables")[0][0] == 5
    assert dt.sql("SELECT COUNT(*) FROM downtime_changes")[0][0] == 0
    assert dt.sql("SELECT resolved_at, version FROM downtime_phases WHERE id = ?", (ph["id"],))[0] == (None, 1)
    # a variable of another chronicle is refused too
    other_var = dt.ok(dt.post("/campaigns/11/downtime/variables", 2, {"name": "Elsewhere"}), 201)["variable"]
    r = _resolve(dt, ph["id"], 1, deltas=[{"target_kind": "variable", "target_id": other_var["id"], "delta": 1}])
    assert r.get_json()["code"] == "invalid_target"


@pytest.mark.parametrize("body,code", [
    ({"result_kind": "maybe"}, "invalid_result_kind"),
    ({"deltas": "x"}, "invalid_deltas"),
    ({"deltas": [{"target_kind": "x", "target_id": 1, "delta": 1}]}, "invalid_deltas"),
    ({"deltas": [{"target_kind": "variable", "target_id": 1, "delta": 5000}]}, "invalid_deltas"),
    ({"result_kind": "scene", "result_location_id": 52}, "invalid_location"),
    ({"version": "missing"}, "version_required"),
])
def test_resolve_refusals(dt, body, code):
    rnd, proj, ph, ind, var = _setup_round(dt)
    _to_resolving(dt, rnd)
    if body.get("version") == "missing":
        r = dt.post(f"/campaigns/10/downtime/phases/{ph['id']}/resolve", 2, {"result_kind": "result"})
    else:
        r = _resolve(dt, ph["id"], 1, **body)
    assert r.status_code == 400 and r.get_json()["code"] == code


def test_resolve_is_storyteller_only(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    _to_resolving(dt, rnd)
    for uid in (3, 4, 6, 7):
        assert _resolve(dt, ph["id"], 1, uid=uid).status_code == 403
    assert dt.ok(_resolve(dt, ph["id"], 1, uid=5))["phase"]["resolved"]  # helper


def test_release_and_after_release_rules(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    second = dt.declare(dt.project(title="Second")["id"])
    _to_resolving(dt, rnd)
    dt.ok(_resolve(dt, ph["id"], 1, deltas=[{"target_kind": "variable", "target_id": var["id"], "delta": 1}]))
    r = dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/release", 2)
    assert r.status_code == 409 and r.get_json() == {
        "error": "Some phases have no result yet", "code": "unresolved_phases", "count": 1}
    dt.ok(_resolve(dt, second["id"], 1, result_kind="skip", result_text=""))
    assert dt.ok(dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/release", 2))["round"]["status"] == "released"
    # results are final once released
    r = _resolve(dt, ph["id"], 2, result_text="Typo fixed")
    assert r.status_code == 409 and r.get_json()["code"] == "round_released"
    # the next round can open
    assert dt.open_round(title="Spring")["status"] == "open"


def test_release_with_force_and_unrolled_phase(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    _to_resolving(dt, rnd)
    dt.ok(dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/release", 2, {"force": True}))
    view = dt.ok(dt.get("/campaigns/10/downtime", 3))
    assert view["projects"][0]["phases"][0]["status"] == "unresolved"


def test_indicator_and_variable_editing_keeps_history(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    out = dt.ok(dt.call("PATCH", f"/campaigns/10/downtime/indicators/{ind['id']}", 2, {"value": 7, "version": 1}))
    assert out["indicator"]["value"] == 7 and out["indicator"]["version"] == 2
    r = dt.call("PATCH", f"/campaigns/10/downtime/indicators/{ind['id']}", 2, {"value": 9, "version": 1})
    assert r.status_code == 409 and r.get_json()["code"] == "version_conflict"
    r = dt.call("PATCH", f"/campaigns/10/downtime/variables/{var['id']}", 2, {"value": 9})
    assert r.status_code == 400 and r.get_json()["code"] == "version_required"
    dt.ok(dt.call("PATCH", f"/campaigns/10/downtime/variables/{var['id']}", 2,
                  {"note": "calmer", "value": 4, "version": 1}))
    ch = dt.ok(dt.get("/campaigns/10/downtime/changes", 2))["changes"]
    assert [(c["target_kind"], c["old_value"], c["new_value"], c["phase_id"]) for c in ch] == [
        ("variable", 5, 4, None), ("indicator", 2, 7, None)]
    r = dt.post(f"/campaigns/10/downtime/projects/{proj['id']}/indicators", 2, {"name": "Pressure"})
    assert r.status_code == 409 and r.get_json()["code"] == "name_taken"
    for uid in (3, 6):
        assert dt.call("PATCH", f"/campaigns/10/downtime/indicators/{ind['id']}", uid, {"value": 1}).status_code == 403
        assert dt.get("/campaigns/10/downtime/variables", uid).status_code == 403
        assert dt.get("/campaigns/10/downtime/changes", uid).status_code == 403
    # another chronicle's ST view can't reach this indicator
    assert dt.call("PATCH", f"/campaigns/11/downtime/indicators/{ind['id']}", 2, {"value": 1}).status_code == 404
    dt.ok(dt.call("DELETE", f"/campaigns/10/downtime/indicators/{ind['id']}", 2))


def test_project_status_by_st(dt):
    proj = dt.project()
    dt.ok(dt.call("PATCH", f"/campaigns/10/downtime/projects/{proj['id']}", 2, {"status": "done"}))
    assert dt.call("PATCH", f"/campaigns/10/downtime/projects/{proj['id']}", 3, {"status": "active"}).status_code == 403
    dt.open_round()
    r = dt.post(f"/campaigns/10/downtime/projects/{proj['id']}/phases", 3, {"action": "More"})
    assert r.status_code == 409 and r.get_json()["code"] == "project_closed"


# ---------------------------------------------------------------- review fixes


def test_roll_refused_on_resolved_phase_after_reopen(dt):
    rnd = dt.open_round()
    ph = dt.declare(dt.project()["id"])
    dt.ready(ph["id"])
    _to_resolving(dt, rnd)
    dt.ok(_resolve(dt, ph["id"], 2, result_kind="skip"))
    dt.ok(dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/reopen", 2))
    r = _roll(dt, ph["id"])
    assert r.status_code == 409 and r.get_json()["code"] == "phase_resolved"


def test_roll_refused_on_closed_project(dt):
    dt.open_round()
    proj = dt.project()
    ph = dt.declare(proj["id"])
    dt.ready(ph["id"])
    dt.ok(dt.call("PATCH", f"/campaigns/10/downtime/projects/{proj['id']}", 2, {"status": "abandoned"}))
    r = _roll(dt, ph["id"])
    assert r.status_code == 409 and r.get_json()["code"] == "project_closed"


def test_suspended_player_keeps_a_read_only_view(dt):
    rnd = dt.open_round()
    ph = dt.declare(dt.project()["id"])
    dt.ready(ph["id"])
    _to_resolving(dt, rnd)
    dt.ok(_resolve(dt, ph["id"], 2, result_text="You got the keys."))
    dt.ok(dt.post(f"/campaigns/10/downtime/rounds/{rnd['id']}/release", 2))
    dt.sql("UPDATE characters SET play_suspended = 1 WHERE id = 100")
    view = dt.ok(dt.get("/campaigns/10/downtime", 3))
    assert view["can_play"] is False and view["player_problem"] == "character_suspended"
    assert view["projects"][0]["phases"][0]["result_text"] == "You got the keys."
    r = dt.post("/campaigns/10/downtime/projects", 3, {"title": "New"})
    assert r.status_code == 403 and r.get_json()["code"] == "character_suspended"
    dt.sql("UPDATE characters SET play_suspended = 0 WHERE id = 100")
    dt.sql("INSERT INTO character_moderation (character_id, action, moderated_at) VALUES (100, 'kill', '2026-02-01')")
    view = dt.ok(dt.get("/campaigns/10/downtime", 3))
    assert view["player_problem"] == "character_fallen" and len(view["projects"]) == 1


def test_net_delta_cap(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    _to_resolving(dt, rnd)
    deltas = [{"target_kind": "variable", "target_id": var["id"], "delta": 1000}] * 2
    r = _resolve(dt, ph["id"], 1, deltas=deltas)
    assert r.status_code == 400 and r.get_json()["code"] == "invalid_deltas"
    assert dt.sql("SELECT value FROM chronicle_variables")[0][0] == 5


def test_two_phases_on_one_variable_and_a_patch_between_resolve_and_amend(dt):
    rnd, proj, ph, ind, var = _setup_round(dt)
    ph2 = dt.declare(dt.project(uid=4, title="Bob's plan")["id"], uid=4)
    _to_resolving(dt, rnd)
    up = lambda n: [{"target_kind": "variable", "target_id": var["id"], "delta": n}]  # noqa: E731
    dt.ok(_resolve(dt, ph["id"], 1, deltas=up(2)))   # 5 -> 7
    dt.ok(_resolve(dt, ph2["id"], 1, deltas=up(3)))  # 7 -> 10
    assert dt.sql("SELECT value, version FROM chronicle_variables")[0] == (10, 3)
    dt.ok(dt.call("PATCH", f"/campaigns/10/downtime/variables/{var['id']}", 2, {"value": 20, "version": 3}))
    dt.ok(_resolve(dt, ph["id"], 2, deltas=up(-1)))  # amend: -3 more -> 17
    assert dt.sql("SELECT value FROM chronicle_variables")[0][0] == 17
    rows = dt.sql("SELECT old_value, new_value, delta FROM downtime_changes ORDER BY id")
    assert rows == [(5, 7, 2), (7, 10, 3), (10, 20, 10), (20, 17, -3)]
