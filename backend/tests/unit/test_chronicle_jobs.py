"""Writer jobs of "The chronicle so far" (services/chronicle_jobs.py) on SQLite with a fake model."""

import json
from datetime import datetime, timedelta

import pytest

from services import chronicle_jobs as cj
from tests.unit.chronicle_fixtures import Conn, FakeModel, build, db


def setup(lang="el", nights=3, marks_night=None):
    rows, marks = build(lang, nights, session_mark_night=marks_night)
    raw = db(rows, marks)
    return raw, Conn(raw)


_T = [datetime(2020, 1, 1)]


def new_job(conn, scope="update", now=None):
    cur = conn.cursor()
    _T[0] += timedelta(hours=2)  # past the Update and Rewrite limits
    jid = cj.create_job(cur, 10, 2, scope, now=now or _T[0])
    cur.execute("UPDATE chronicle_jobs SET status = 'running', started_at = %s WHERE id = %s", (datetime.now(), jid))
    conn.commit()
    return cj.get_job(cur, 10, jid)


def run(conn, model=None, **kw):
    model = model or FakeModel()
    status = cj.run_job(conn, new_job(conn, kw.pop("scope", "update")), generate=model, sleep=lambda s: None,
                        ctx_tokens=kw.pop("ctx", 32768), **kw)
    return status, model


def chapters(raw):
    return [(r[0], json.loads(r[1])) for r in raw.execute(
        "SELECT chapter_key, chapter FROM chronicle_chapters WHERE kind = 'story' ORDER BY started_at")]


def test_greek_chronicle_written_end_to_end():
    raw, conn = setup("el", 3)
    status, model = run(conn)
    assert status == "done"
    chs = chapters(raw)
    assert len(chs) == 4  # 3 nights + the closed room's night
    assert {c["visibility"] for _, c in chs} == {"all", "st"}
    n1 = chs[0][1]
    assert n1["title"] == "Η νύχτα στο υπόγειο" and len(n1["summary"]) == 2
    assert all(999999 not in e["ids"] for e in n1["events"])  # unknown id dropped
    assert [c["name"] for c in n1["characters"]] == ["Κωνσταντίνος"]  # invented title dropped
    assert any(e.get("fixed") and e["text"].startswith("Καταστροφική αποτυχία") for e in n1["events"])
    with_notes = [c for _, c in chs if c.get("st_notes")]
    assert len(with_notes) == 1  # only night 2 has a hidden roll
    assert any(o["text"] == "brb, coffee" for _, c in chs for o in c.get("ooc") or [])
    roles = {c["role"] for c in model.calls}
    assert roles == {"chronicler_el"}
    sys0 = model.calls[0]["messages"][0]["content"]
    assert "ΓΡΑΨΕ ΤΑ ΠΑΝΤΑ ΣΤΑ ΕΛΛΗΝΙΚΑ" in sys0
    names = [c["name"] for c in model.calls]
    assert names.count("chapter") == 4 and names.count("notes") == 1 and "era" in names and "digest" in names
    digest = json.loads(raw.execute("SELECT digest FROM chronicle_digests WHERE kind = 'final'").fetchone()[0])
    assert digest["tldr"] and digest["st_so_far"] and digest["nights_total"] == 4 and digest["rooms"] == [101, 102]
    job = raw.execute("SELECT status, nights, nights_done, tokens_total, seconds_per_night FROM chronicle_jobs").fetchone()
    assert job[0] == "done" and job[1] == job[2] == 4 and job[3] > 0 and job[4] is not None
    # lobby talk is stored without a model call
    assert raw.execute("SELECT COUNT(*) FROM chronicle_chapters WHERE kind = 'lobby'").fetchone()[0] == 3


def test_english_chronicle_uses_the_english_role_and_prompt():
    raw, conn = setup("en", 2)
    _s, model = run(conn)
    assert {c["role"] for c in model.calls} == {"chronicler_en"}
    assert "Write everything in ENGLISH" in model.calls[0]["messages"][0]["content"]


def test_mixed_chronicle_follows_the_campaign_language_when_set():
    raw, conn = setup("mixed", 4)
    raw.execute("UPDATE campaigns SET language = 'en'")
    raw.commit()
    _s, model = run(conn)
    assert {c["role"] for c in model.calls} == {"chronicler_en"}


def test_sixty_nights_partial_then_continues_and_only_stale_rewritten():
    raw, conn = setup("el", 60)
    status, _m = run(conn)
    assert status == "partial"
    job = raw.execute("SELECT nights, nights_total, nights_done FROM chronicle_jobs ORDER BY id DESC").fetchone()
    assert job == (40, 61, 40)  # 60 nights + one closed-room night; 40 per run
    status, _m = run(conn)
    assert status == "done"
    assert len(chapters(raw)) == 61
    assert raw.execute("SELECT COUNT(*) FROM chronicle_digests WHERE kind = 'era'").fetchone()[0] == 7
    status, model = run(conn)  # nothing changed: no chapter calls, digests reused
    assert status == "done" and model.calls == []
    # a new message in the last night: that night only
    raw.execute("INSERT INTO messages (id, campaign_id, location_id, user_id, character_id, content, created_at, lang) "
                "SELECT (SELECT MAX(id) FROM messages) + 1, 10, location_id, 3, 20, 'Νέα γραμμή.', datetime(MAX(created_at), '+1 minute'), 'el' "
                "FROM messages WHERE location_id = (SELECT location_id FROM messages WHERE id = (SELECT MAX(id) FROM messages WHERE location_id != 100))")
    raw.commit()
    _s, model = run(conn)
    assert [c["name"] for c in model.calls].count("chapter") == 1


def test_session_mark_rewrites_and_removes_orphans():
    raw, conn = setup("el", 2)
    run(conn)
    before = {k for k, _ in chapters(raw)}
    rows, marks = build("el", 2, session_mark_night=1)
    # the same chronicle, now with a mark and one more line after it
    raw2 = db(rows, marks)
    conn2 = Conn(raw2)
    run(conn2)
    after = {k for k, _ in chapters(raw2)}
    assert len(after) == len(before) + 1
    # orphans: a deleted message that started a night removes that chapter's old key
    first_key = sorted(after)[0]
    lid, mid = first_key.split(":")
    raw2.execute("DELETE FROM messages WHERE id = ?", (int(mid),))
    raw2.commit()
    run(conn2)
    assert first_key not in {k for k, _ in chapters(raw2)}


def test_wrong_language_is_retried_once_with_the_reason():
    raw, conn = setup("el", 1)
    model = FakeModel(wrong_language_first=True)
    run(conn, model)
    chapter_calls = [c for c in model.calls if c["name"] == "chapter"]
    assert len(chapter_calls) == 2
    assert "Η απάντηση δεν ήταν στα ελληνικά" in chapter_calls[1]["messages"][-1]["content"]
    assert chapters(raw)[0][1]["title"] == "Η νύχτα στο υπόγειο"


def test_context_overflow_waits_and_splits_the_night():
    raw, conn = setup("el", 1)
    model = FakeModel(overflow_once=True)
    waits = []
    status = cj.run_job(conn, new_job(conn), generate=model, sleep=waits.append, ctx_tokens=32768)
    assert status == "done"
    chapter_calls = [c for c in model.calls if c["name"] == "chapter"]
    assert len(chapter_calls) == 3  # the failed call, then two halves
    assert chapters(raw)[0][1]["parts"] == 2
    assert sum(waits) >= 29  # waited about 30 s first


def test_small_context_splits_never_shrinks():
    raw, conn = setup("el", 1)
    model = FakeModel()
    run(conn, model, ctx=2000)
    assert all(c["kw"].get("shrink") is False for c in model.calls)


def test_cancel_stops_the_stream():
    raw, conn = setup("el", 3)

    class CancelAfterFirst(FakeModel):
        def __call__(self, role, messages, params, **kw):
            if len(self.calls) == 1:
                raw.execute("UPDATE chronicle_jobs SET cancel_requested = 1")
                raw.commit()
            return super().__call__(role, messages, params, **kw)

    clock = iter(range(0, 10_000, 2))
    status = cj.run_job(conn, new_job(conn), generate=CancelAfterFirst(), sleep=lambda s: None, ctx_tokens=32768,
                        clock=lambda: next(clock))
    assert status == "cancelled"
    assert raw.execute("SELECT status FROM chronicle_jobs").fetchone()[0] == "cancelled"
    assert len(chapters(raw)) == 1


def test_failure_is_recorded():
    raw, conn = setup("el", 1)

    def broken(role, messages, params, **kw):
        from services.ai_providers import ProviderError

        raise ProviderError("all providers failed")

    status = cj.run_job(conn, new_job(conn), generate=broken, sleep=lambda s: None, ctx_tokens=32768)
    assert status == "failed"
    assert "all providers failed" in raw.execute("SELECT error FROM chronicle_jobs").fetchone()[0]


def test_too_few_story_messages_writes_nothing():
    raw, conn = setup("el", 1)
    raw.execute("DELETE FROM messages WHERE id > 1003")
    raw.commit()
    status, model = run(conn)
    assert status == "done" and model.calls == []


def test_job_limits():
    raw, conn = setup("el", 1)
    cur = conn.cursor()
    t = datetime(2026, 10, 17, 12)
    jid = cj.create_job(cur, 10, 2, "update", now=t)
    with pytest.raises(cj.JobRefused) as e:
        cj.create_job(cur, 10, 2, "update", now=t)
    assert e.value.status == 409
    raw.execute("UPDATE chronicle_jobs SET status = 'done'")
    with pytest.raises(cj.JobRefused) as e:
        cj.create_job(cur, 10, 2, "update", now=t + timedelta(minutes=4))
    assert e.value.status == 429 and e.value.retry_after > 0
    cj.create_job(cur, 10, 2, "all", now=t + timedelta(minutes=4))
    raw.execute("UPDATE chronicle_jobs SET status = 'done'")
    with pytest.raises(cj.JobRefused):
        cj.create_job(cur, 10, 2, "all", now=t + timedelta(minutes=40))
    assert cj.cancel_job(cur, 10, jid) is False  # already finished
    j2 = cj.create_job(cur, 10, 2, "update", now=t + timedelta(minutes=10))
    assert cj.cancel_job(cur, 10, j2) is True
    assert cj.get_job(cur, 10, j2)["status"] == "cancelled"


def test_estimate_falls_back_to_six_seconds_a_night():
    raw, conn = setup("el", 3)
    est = cj.estimate(conn.cursor(), 10)
    assert est["nights_to_write"] == 4 and est["seconds_per_night"] == 6.0
    assert est["seconds"] == 4 * 6 + 2 * 6 and est["capped"] is False and est["enough"] is True
    raw2, conn2 = setup("el", 50)
    est = cj.estimate(conn2.cursor(), 10)
    assert est["capped"] is True and est["nights_to_write"] == 40


def test_progress_written_at_most_every_one_and_a_half_seconds():
    raw, conn = setup("el", 1)
    job = new_job(conn)
    now = [0.0]
    p = cj.Progress(conn, job["id"], clock=lambda: now[0])
    writes = []
    orig = p.conn.cursor

    def counting_cursor():
        c = orig()
        real = c.execute

        def ex(sql, params=()):
            if sql.startswith("UPDATE chronicle_jobs"):
                writes.append(1)
            return real(sql, params)

        c.execute = ex
        return c

    p.conn = type("C", (), {"cursor": staticmethod(counting_cursor), "commit": conn.commit, "rollback": conn.rollback})()
    for _ in range(10):
        p.token()
        p.tick()
        now[0] += 0.5
    assert len(writes) == 4  # at 0, 1.5, 3.0, 4.5
    p.set_eta(100)
    p.set_eta(140)
    assert p.fields["eta_s"] == 100  # never jumps up
    assert 1.4 <= p.fields["tok_per_s"] <= 2.6


def test_job_json_has_no_requester():
    raw, conn = setup("el", 1)
    j = cj.job_json(new_job(conn))
    assert "requested_by" not in j and j["status"] == "running" and j["elapsed_s"] >= 0
