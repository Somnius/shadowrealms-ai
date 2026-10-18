"""Phase 5 of "The chronicle so far" (docs/CHRONICLE.md): per-chronicle settings, caps, the nightly
run, writer health and the archive list. SQLite with a fake model; no LM Studio."""

import itertools
import json
from datetime import datetime, timedelta

import pytest

from services import chronicle_jobs as cj
from services import chronicle_nightly as cn
from services import chronicle_settings as cs
from services.request_validation import RequestValidationError
from tests.unit.chronicle_fixtures import Conn, FakeModel, build, db
from tests.unit.test_chronicle_routes import ADMIN, HELPER_IN, OUTSIDER, PLAYER, ST, api, write  # noqa: F401

OPTIONS = [{"provider": "lm_studio", "model": "krikri-8b", "cloud": False},
           {"provider": "anthropic", "model": "claude-x", "cloud": True}]


def setup(nights=3):
    rows, marks = build("el", nights)
    raw = db(rows, marks)
    return raw, Conn(raw)


def set_settings(raw, **kw):
    raw.execute("UPDATE campaigns SET chronicle_settings = ? WHERE id = 10", (json.dumps(cs.normalize(kw)),))
    raw.commit()


def run(conn, model=None, now=datetime(2020, 1, 1), **kw):
    cur = conn.cursor()
    jid = cj.create_job(cur, 10, 2, "update", now=now)
    cur.execute("UPDATE chronicle_jobs SET status = 'running', started_at = %s WHERE id = %s", (datetime.now(), jid))
    conn.commit()
    model = model or FakeModel()
    status = cj.run_job(conn, cj.get_job(cur, 10, jid), generate=model, sleep=lambda s: None, ctx_tokens=32768, **kw)
    return status, model


# -- settings -----------------------------------------------------------------------------------

def test_settings_defaults_and_bounds():
    assert cs.normalize(None) == {"v": 1, "gap_hours": 6, "table_talk": False, "nightly": False, "memory": True,
                                 "model": None}
    assert cs.normalize('{"gap_hours": 30, "nightly": "yes"}')["gap_hours"] == 6
    assert cs.normalize("not json")["nightly"] is False
    cur = cs.normalize({})
    assert cs.validate({"gap_hours": 2, "nightly": True}, cur, OPTIONS, False)["gap_hours"] == 2
    for bad in ({"gap_hours": 1}, {"gap_hours": 25}, {"gap_hours": "6"}, {"gap_hours": True}, {"nightly": 1},
                {"table_talk": "on"}, {"other": 1}, {"model": {"provider": "lm_studio", "model": "not-listed"}},
                {"model": "krikri-8b"}, []):
        with pytest.raises(RequestValidationError):
            cs.validate(bad, cur, OPTIONS, True)
    # a cloud writer only on purpose, by a site admin
    with pytest.raises(RequestValidationError):
        cs.validate({"model": {"provider": "anthropic", "model": "claude-x"}}, cur, OPTIONS, False)
    assert cs.validate({"model": {"provider": "anthropic", "model": "claude-x"}}, cur, OPTIONS, True)["model"]["provider"] == "anthropic"
    assert cs.validate({"model": None}, {"model": {"provider": "lm_studio", "model": "krikri-8b"}}, OPTIONS, False)["model"] is None


def test_caps_from_the_environment(monkeypatch):
    assert (cs.max_nights_per_job(), cs.max_seconds_per_job(), cs.job_keep_days()) == (40, 3600, 90)
    monkeypatch.setenv("CHRONICLE_MAX_NIGHTS_PER_JOB", "5")
    monkeypatch.setenv("CHRONICLE_MAX_SECONDS_PER_JOB", "10")  # at least a minute
    monkeypatch.setenv("CHRONICLE_JOB_KEEP_DAYS", "junk")
    assert (cs.max_nights_per_job(), cs.max_seconds_per_job(), cs.job_keep_days()) == (5, 60, 90)


def test_settings_route_is_for_the_storyteller_and_admins(api, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cs, "model_options", lambda: OPTIONS)
    url = "/api/campaigns/10/chronicle/settings"
    assert api("GET", url, OUTSIDER).status_code == 404
    assert api("GET", url, PLAYER).status_code == 403
    assert api("GET", url, HELPER_IN).status_code == 403  # helpers read and export only
    r = api("GET", url, ST).get_json()
    assert r["settings"]["gap_hours"] == 6 and r["gap_range"] == [2, 24]
    assert [m["provider"] for m in r["models"]] == ["lm_studio"]  # no cloud writers for a Storyteller
    assert [m["provider"] for m in api("GET", url, ADMIN).get_json()["models"]] == ["lm_studio", "anthropic"]
    assert api("PUT", url, HELPER_IN, {"nightly": True}).status_code == 403
    assert api("PUT", url, ST, {"gap_hours": 99}).status_code == 400
    r = api("PUT", url, ST, {"gap_hours": 4, "nightly": True, "table_talk": True,
                             "model": {"provider": "lm_studio", "model": "krikri-8b"}})
    assert r.status_code == 200 and r.get_json()["settings"]["nightly"] is True
    stored = json.loads(api.raw.execute("SELECT chronicle_settings FROM campaigns WHERE id = 10").fetchone()[0])
    assert stored["gap_hours"] == 4 and stored["model"] == {"provider": "lm_studio", "model": "krikri-8b"}
    # a partial PUT keeps the rest
    assert api("PUT", url, ADMIN, {"nightly": False}).get_json()["settings"]["gap_hours"] == 4
    body = api("GET", "/api/campaigns/10/chronicle", HELPER_IN).get_json()
    assert body["settings"] == {"table_talk": True} and body["can_settings"] is False  # no writer model for helpers
    assert api("GET", "/api/campaigns/10/chronicle", ST).get_json()["can_settings"] is True


def test_a_new_gap_makes_only_the_affected_nights_stale():
    raw, conn = setup(3)
    run(conn)
    assert cj.plan(conn.cursor(), 10)["stale"] == []
    set_settings(raw, gap_hours=2)
    assert cj.plan(conn.cursor(), 10)["stale"] == []  # no pause over 2 hours: the same nights
    # a line 3 hours after the last night in that room (night 3)
    raw.execute("INSERT INTO messages (id, campaign_id, location_id, user_id, character_id, content, created_at, lang) "
                "SELECT 5000, 10, 101, 3, 20, 'Μετά από ώρες.', datetime(MAX(created_at), '+3 hours'), 'el' "
                "FROM messages WHERE location_id = 101")
    raw.commit()
    p2 = cj.plan(conn.cursor(), 10)
    assert len(p2["stale"]) == 1 and p2["stale"][0]["first_id"] == 5000  # a night of its own; night 3 unchanged
    set_settings(raw, gap_hours=6)
    p6 = cj.plan(conn.cursor(), 10)
    assert len(p6["stale"]) == 1 and p6["stale"][0]["first_id"] != 5000  # night 3 grew instead


def test_the_writer_model_override_is_tried_first(monkeypatch):
    raw, conn = setup(1)
    monkeypatch.setattr(cs, "model_options", lambda: OPTIONS)
    import services.ai_roles as ar
    monkeypatch.setattr(ar, "fallback_chain", lambda role, cfg=None: [("lm_studio", "krikri-default")])
    set_settings(raw, model={"provider": "lm_studio", "model": "krikri-8b"})
    _s, model = run(conn)
    assert model.calls and all(c["kw"]["chain"] == [("lm_studio", "krikri-8b"), ("lm_studio", "krikri-default")]
                               for c in model.calls if c["role"].startswith("chronicler"))
    # no longer listed in the admin panel: the chronicler role's own chain
    monkeypatch.setattr(cs, "model_options", lambda: OPTIONS[1:])
    _s, model = run(conn, FakeModel(), now=datetime(2020, 1, 2))
    assert all("chain" not in c["kw"] for c in model.calls)


def test_nights_and_seconds_caps(monkeypatch):
    raw, conn = setup(5)
    monkeypatch.setenv("CHRONICLE_MAX_NIGHTS_PER_JOB", "2")
    status, _m = run(conn)
    assert status == "partial"
    assert raw.execute("SELECT nights, nights_done FROM chronicle_jobs").fetchone() == (2, 2)
    assert cj.estimate(conn.cursor(), 10)["max_nights"] == 2
    monkeypatch.delenv("CHRONICLE_MAX_NIGHTS_PER_JOB")
    monkeypatch.setenv("CHRONICLE_MAX_SECONDS_PER_JOB", "60")
    ticks = itertools.count(0, 50)  # each clock read is 50 s later
    status, _m = run(conn, now=datetime(2020, 1, 2), clock=lambda: float(next(ticks)))
    assert status == "partial"
    done = raw.execute("SELECT nights, nights_done FROM chronicle_jobs ORDER BY id DESC").fetchone()
    assert done[0] == done[1] and 1 <= done[1] < 4  # stopped after the night that crossed 60 s


def test_old_job_rows_are_pruned():
    raw, conn = setup(1)
    cur = conn.cursor()

    def add(status, at):
        cur.execute("INSERT INTO chronicle_jobs (campaign_id, scope, status, created_at, finished_at) "
                    "VALUES (10, 'update', %s, %s, %s) RETURNING id", (status, at, at if status != "queued" else None))
        return cur.fetchone()["id"]

    add("done", datetime(2020, 1, 1))
    live = add("queued", datetime(2020, 1, 1))  # still queued: kept
    recent = add("failed", datetime(2026, 10, 16))
    conn.commit()
    assert cj.prune_jobs(cur, now=datetime(2026, 10, 17)) == 1
    assert {r[0] for r in raw.execute("SELECT id FROM chronicle_jobs")} == {live, recent}


# -- the nightly run --------------------------------------------------------------------------

NIGHT = datetime(2026, 10, 17, 5, 1)


@pytest.fixture(autouse=True)
def utc_nights(monkeypatch):
    """The nightly tests below read NIGHT as 05:01 in the nightly zone; one test checks Athens."""
    monkeypatch.setenv("CHRONICLE_NIGHTLY_TZ", "UTC")


def test_nightly_window(monkeypatch):
    assert cn.window_day(NIGHT) == NIGHT.date()
    assert cn.window_day(datetime(2026, 10, 17, 4, 59)) is None
    assert cn.window_day(datetime(2026, 10, 17, 8, 1)) is None  # three hours after
    monkeypatch.setenv("CHRONICLE_NIGHTLY_AT", "23:30")
    assert cn.window_day(datetime(2026, 10, 18, 1, 0)) == datetime(2026, 10, 17).date()  # across midnight
    monkeypatch.setenv("CHRONICLE_NIGHTLY_AT", "25:00")
    assert cn.nightly_at() == (5, 0)


def test_switch_off_means_no_job():
    raw, conn = setup(2)
    assert cn.Nightly().tick(conn, NIGHT) is None
    assert raw.execute("SELECT COUNT(*) FROM chronicle_jobs").fetchone()[0] == 0


def test_no_new_messages_means_no_job():
    raw, conn = setup(2)
    run(conn, now=datetime(2026, 10, 16))  # written: nothing new since
    set_settings(raw, nightly=True)
    assert cn.has_new_messages(conn.cursor(), 10) is False
    assert cn.Nightly().tick(conn, NIGHT) is None
    assert raw.execute("SELECT COUNT(*) FROM chronicle_jobs").fetchone()[0] == 1


def test_nightly_queues_one_update_at_a_time():
    raw, conn = setup(2)
    raw.executescript("""
        INSERT INTO campaigns (id, name, created_by, chronicle_settings) VALUES (11, 'Second table', 2, '{"nightly": true}');
        INSERT INTO locations (id, campaign_id, name) VALUES (201, 11, 'Bar');
        INSERT INTO messages (id, campaign_id, location_id, user_id, content, created_at) VALUES (9001, 11, 201, 2, 'hi', '2026-10-10 22:00:00');
    """)
    set_settings(raw, nightly=True)
    n = cn.Nightly()
    assert n.tick(conn, datetime(2026, 10, 17, 4, 0)) is None  # before the hour
    first = n.tick(conn, NIGHT)
    job = raw.execute("SELECT campaign_id, scope, status, requested_by FROM chronicle_jobs WHERE id = ?", (first,)).fetchone()
    assert job == (10, "update", "queued", None)
    assert n.tick(conn, NIGHT + timedelta(minutes=1)) is None  # one at a time
    raw.execute("UPDATE chronicle_jobs SET status = 'done' WHERE id = ?", (first,))
    raw.commit()
    second = n.tick(conn, NIGHT + timedelta(minutes=2))
    assert raw.execute("SELECT campaign_id FROM chronicle_jobs WHERE id = ?", (second,)).fetchone()[0] == 11
    raw.execute("UPDATE chronicle_jobs SET status = 'done' WHERE id = ?", (second,))
    raw.commit()
    assert n.tick(conn, NIGHT + timedelta(minutes=3)) is None  # each chronicle once a night
    assert n.tick(conn, NIGHT + timedelta(days=1, minutes=3)) is None  # nothing new since the run


def test_nightly_follows_the_update_limits():
    raw, conn = setup(2)
    set_settings(raw, nightly=True)
    cur = conn.cursor()
    cj.create_job(cur, 10, 2, "update", now=NIGHT - timedelta(minutes=2))  # pressed a moment ago, still running
    cur.execute("UPDATE chronicle_jobs SET status = 'running'")
    conn.commit()
    assert cn.Nightly().tick(conn, NIGHT) is None
    cur.execute("UPDATE chronicle_jobs SET status = 'cancelled'")
    conn.commit()
    raw.execute("INSERT INTO messages (id, campaign_id, location_id, user_id, content, created_at) VALUES "
                "(9100, 10, 101, 3, 'x', '2026-10-17 04:59:00')")
    raw.commit()
    assert cn.Nightly().tick(conn, NIGHT) is not None


# -- admin --------------------------------------------------------------------------------------

def test_writer_health_for_site_admins(api):  # noqa: F811
    write(api)
    conn = Conn(api.raw)
    cur = conn.cursor()
    jid = cj.create_job(cur, 10, None, "update", now=datetime.now())
    cur.execute("INSERT INTO chronicle_jobs (campaign_id, scope, status, error, created_at, finished_at) "
                "VALUES (10, 'update', 'failed', 'context', %s, %s)", (datetime.now(), datetime.now()))
    conn.commit()
    assert api("GET", "/api/chronicle-health", ST).status_code == 403
    assert api("GET", "/api/chronicle-health", HELPER_IN).status_code == 403
    h = api("GET", "/api/chronicle-health", ADMIN).get_json()
    assert h["failures_today"] == 1 and h["last_error"]["code"] == "context"
    assert h["seconds_per_night"] > 0 and h["nightly_at"] == "05:00"
    assert [(j["id"], j["nightly"], j["campaign_name"]) for j in h["jobs"]] == [(jid, True, "Athens: Blood and Concrete")]


def test_archive_list_has_names_size_and_nights(api):  # noqa: F811
    from services import chronicle_archive as ca

    write(api)
    conn = Conn(api.raw)
    aid = ca.write_archive(conn.cursor(), 10, ADMIN, root=str(api.tmp), now=datetime.now())
    conn.commit()
    a = api("GET", "/api/chronicle-archives", ADMIN).get_json()
    row = a["archives"][0]
    assert row["id"] == aid and row["storyteller"] == "storyteller_lef" and row["deleted_by"] == "siteadmin"
    assert row["size"] > 0 and row["nights_written"] == 4 and a["st_days"] == 30
    assert api("GET", "/api/chronicle-archives", ST).get_json()["archives"][0]["id"] == aid


def test_a_storyteller_keeps_an_admins_cloud_writer():
    cloud = {"provider": "anthropic", "model": "claude-x"}
    cur = cs.normalize({"model": cloud})
    # unchanged: saved as it is, even when the panel no longer lists it
    assert cs.validate({"model": dict(cloud), "nightly": True}, cur, OPTIONS[:1], False)["model"] == cloud
    assert cs.validate({"nightly": True}, cur, OPTIONS, False)["model"] == cloud
    for change in ({"model": None}, {"model": {"provider": "lm_studio", "model": "krikri-8b"}}):
        with pytest.raises(RequestValidationError):
            cs.validate(change, cur, OPTIONS, False)
    assert cs.validate({"model": None}, cur, OPTIONS, True)["model"] is None  # an admin can


def test_the_nightly_hour_is_in_the_nightly_zone(monkeypatch):
    from services import chronicle_nightly as nightly

    monkeypatch.setenv("CHRONICLE_NIGHTLY_TZ", "Europe/Athens")
    # server time is UTC: 02:01 UTC is 05:01 in Athens (summer time), 05:01 UTC is 08:01
    assert nightly.window_day(datetime(2026, 10, 17, 2, 1)) == datetime(2026, 10, 17).date()
    assert nightly.window_day(datetime(2026, 10, 17, 5, 1)) is None
    assert nightly.local_day_start(datetime(2026, 10, 17, 12)) == datetime(2026, 10, 16, 21)
    monkeypatch.setenv("CHRONICLE_NIGHTLY_TZ", "Not/AZone")
    assert nightly.window_day(datetime(2026, 10, 17, 5, 1)) == datetime(2026, 10, 17).date()  # UTC fallback


def test_a_waiting_nightly_job_does_not_block_and_is_cancelled_after_the_window():
    raw, conn = setup(2)
    raw.executescript("""
        INSERT INTO campaigns (id, name, created_by, chronicle_settings) VALUES (11, 'Second table', 2, '{"nightly": true}');
        INSERT INTO locations (id, campaign_id, name) VALUES (201, 11, 'Bar');
        INSERT INTO messages (id, campaign_id, location_id, user_id, content, created_at) VALUES (9001, 11, 201, 2, 'hi', '2026-10-10 22:00:00');
    """)
    set_settings(raw, nightly=True)
    n = cn.Nightly()
    first = n.tick(conn, NIGHT)
    raw.execute("UPDATE chronicle_jobs SET status = 'waiting' WHERE id = ?", (first,))  # that table is still playing
    raw.commit()
    assert n.tick(conn, NIGHT + timedelta(minutes=10)) is None  # still its turn
    second = n.tick(conn, NIGHT + timedelta(minutes=16))  # waiting over 15 minutes: the next chronicle goes
    assert second and raw.execute("SELECT campaign_id FROM chronicle_jobs WHERE id = ?", (second,)).fetchone()[0] == 11
    raw.execute("UPDATE chronicle_jobs SET status = 'queued' WHERE id = ?", (second,))
    raw.commit()
    assert n.tick(conn, NIGHT + timedelta(hours=4)) is None  # after the window
    assert {r[0] for r in raw.execute("SELECT status FROM chronicle_jobs")} == {"cancelled"}


def test_a_refused_chronicle_gets_another_turn_and_a_partial_one_continues():
    raw, conn = setup(2)
    set_settings(raw, nightly=True)
    cur = conn.cursor()
    jid = cj.create_job(cur, 10, 2, "update", now=NIGHT - timedelta(minutes=2))  # the Storyteller pressed Update
    cur.execute("UPDATE chronicle_jobs SET status = 'done' WHERE id = %s", (jid,))
    raw.execute("INSERT INTO messages (id, campaign_id, location_id, user_id, content, created_at) VALUES "
                "(9100, 10, 101, 3, 'x', '2026-10-17 05:00:00')")
    conn.commit()
    n = cn.Nightly()
    assert n.tick(conn, NIGHT) is None  # too soon: not burnt for the night
    first = n.tick(conn, NIGHT + timedelta(minutes=4))
    assert first is not None
    raw.execute("UPDATE chronicle_jobs SET status = 'partial' WHERE id = ?", (first,))
    raw.commit()
    assert n.tick(conn, NIGHT + timedelta(minutes=6)) is None  # partial: again, after the 5 minutes
    assert n.tick(conn, NIGHT + timedelta(minutes=10)) is not None


def test_no_job_after_pruning_when_nothing_is_new():
    raw, conn = setup(2)
    run(conn, now=datetime(2026, 10, 16))
    raw.execute("DELETE FROM chronicle_jobs")  # pruned
    raw.commit()
    assert cn.has_new_messages(conn.cursor(), 10) is False
    raw.execute("INSERT INTO messages (id, campaign_id, location_id, user_id, content, created_at) VALUES "
                "(9200, 10, 101, 3, 'new', '2026-10-17 01:00:00')")
    raw.commit()
    assert cn.has_new_messages(conn.cursor(), 10) is True


def test_writer_health_counts_runs_not_translations(api):  # noqa: F811
    conn = Conn(api.raw)
    cur = conn.cursor()
    for scope in ("update", "translate"):
        cur.execute("INSERT INTO chronicle_jobs (campaign_id, scope, status, created_at) VALUES (10, %s, 'done', %s)",
                    (scope, datetime.now()))
    conn.commit()
    assert api("GET", "/api/chronicle-health", ADMIN).get_json()["jobs_today"] == 1
