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
