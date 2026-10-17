"""Routes of "The chronicle so far" (routes/chronicle.py): who may read, update and export; the player
view holds no usernames and no Storyteller keys; rooms are checked again when read; archives."""

import json
import os
from datetime import datetime, timedelta

import pytest

from services import chronicle_jobs as cj
from tests.unit.chronicle_fixtures import Conn, FakeModel, build, db

ADMIN, ST, PLAYER, OUTSIDER, HELPER_IN, HELPER_OUT = 1, 2, 3, 4, 5, 6
USERNAMES = ("siteadmin", "storyteller_lef", "eleni_player", "nikos_player", "helper_in", "outsider")


@pytest.fixture
def api(monkeypatch, tmp_path):
    from flask import Flask
    from flask_jwt_extended import JWTManager, create_access_token

    from routes import chronicle

    rows, marks = build("el", 3)
    raw = db(rows, marks)
    monkeypatch.setattr(chronicle, "get_db", lambda: Conn(raw))
    monkeypatch.setattr(cj, "ensure_worker", lambda: False)
    monkeypatch.setenv("CHRONICLE_ARCHIVE_DIR", str(tmp_path))
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(chronicle.chronicle_bp, url_prefix="/api")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in range(1, 8)}
    c = app.test_client()

    def call(method, url, uid, body=None):
        return c.open(url, method=method, json=body, headers={"Authorization": f"Bearer {tokens[uid]}"})

    call.raw = raw
    call.tmp = tmp_path
    return call


def write(api):
    conn = Conn(api.raw)
    cur = conn.cursor()
    jid = cj.create_job(cur, 10, ST, "update", now=datetime(2020, 1, 1))
    cur.execute("UPDATE chronicle_jobs SET status = 'running' WHERE id = %s", (jid,))
    conn.commit()
    assert cj.run_job(conn, cj.get_job(cur, 10, jid), generate=FakeModel(), sleep=lambda s: None, ctx_tokens=32768) == "done"


URLS = ["/api/campaigns/10/chronicle", "/api/campaigns/10/chronicle/chapters", "/api/campaigns/10/chronicle/estimate",
        "/api/campaigns/10/chronicle.md", "/api/campaigns/10/chronicle/minutes.md"]


def test_who_may_read_and_export(api):
    write(api)
    for url in URLS:
        assert api("GET", url, OUTSIDER).status_code == 404, url
        assert api("GET", url, HELPER_OUT).status_code == 404, url  # a helper who can't open the chronicle
        assert api("GET", url, PLAYER).status_code == 403, url
        for uid in (ST, ADMIN, HELPER_IN):
            assert api("GET", url, uid).status_code == 200, (url, uid)
    assert api("GET", "/api/campaigns/99/chronicle", ADMIN).status_code == 404


def test_update_permissions_and_limits(api):
    assert api("POST", "/api/campaigns/10/chronicle/jobs", PLAYER, {}).status_code == 403
    assert api("POST", "/api/campaigns/10/chronicle/jobs", OUTSIDER, {}).status_code == 404
    assert api("POST", "/api/campaigns/10/chronicle/jobs", HELPER_IN, {"scope": "all"}).status_code == 403
    r = api("POST", "/api/campaigns/10/chronicle/jobs", HELPER_IN, {})
    assert r.status_code == 202
    job = r.get_json()["job"]
    assert job["status"] == "queued" and "requested_by" not in job
    assert api("POST", "/api/campaigns/10/chronicle/jobs", ST, {}).status_code == 409
    got = api("GET", f"/api/campaigns/10/chronicle/jobs/{job['id']}", ST).get_json()["job"]
    assert got["id"] == job["id"]
    assert api("GET", f"/api/campaigns/10/chronicle/jobs/{job['id']}", PLAYER).status_code == 403
    r = api("DELETE", f"/api/campaigns/10/chronicle/jobs/{job['id']}", ST)
    assert r.status_code == 200 and r.get_json()["job"]["status"] == "cancelled"
    r = api("POST", "/api/campaigns/10/chronicle/jobs", ST, {})
    assert r.status_code == 429 and r.get_json()["retry_after"] > 0
    assert api("GET", "/api/campaigns/10/chronicle/jobs/9999", ST).status_code == 404


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


def test_player_view_has_no_usernames_and_no_storyteller_keys(api):
    write(api)
    st = api("GET", "/api/campaigns/10/chronicle", ST).get_json()
    assert any(c["visibility"] == "st" for c in st["chapters"])
    assert st["digest"]["st_so_far"]
    p = api("GET", "/api/campaigns/10/chronicle?view=player", ST).get_json()
    text = json.dumps(p, ensure_ascii=False)
    assert not any(u in text for u in USERNAMES)
    assert not any(str(k).startswith("st_") for k in _walk_keys(p))
    assert "ids" not in set(_walk_keys(p["chapters"]))
    assert len(p["chapters"]) == 3 and p["digest"]["so_far"]
    md = api("GET", "/api/campaigns/10/chronicle.md?view=player", ST).get_data(as_text=True)
    assert not any(u.replace("_", "\\_") in md or u in md for u in USERNAMES)
    assert "Μόνο για τον Storyteller" not in md and "The Crypt" not in md
    st_md = api("GET", "/api/campaigns/10/chronicle.md", ST).get_data(as_text=True)
    assert "Μόνο για τον Storyteller" in st_md and "eleni\\_player" in st_md


def test_rooms_checked_again_when_read(api):
    write(api)
    api.raw.execute("UPDATE locations SET is_open = 0 WHERE id = 102")
    api.raw.commit()
    p = api("GET", "/api/campaigns/10/chronicle?view=player", ST).get_json()
    assert all(c["room"] != "Elysium" for c in p["chapters"])
    assert p["digest"] is None and p["withheld"] is True
    st = api("GET", "/api/campaigns/10/chronicle", ST).get_json()
    assert any(c["room"] == "Elysium" for c in st["chapters"])


def test_exports(api):
    write(api)
    r = api("GET", "/api/campaigns/10/chronicle.md", HELPER_IN)
    assert r.status_code == 200 and r.mimetype == "text/markdown"
    assert "filename*=UTF-8''" in r.headers["Content-Disposition"]
    body = r.get_data(as_text=True)
    assert body.startswith("# Athens: Blood and Concrete — Το χρονικό ως τώρα")
    assert "Good game tonight" not in body and "brb" not in body
    talk = api("GET", "/api/campaigns/10/chronicle.md?with_table_talk=1", ST).get_data(as_text=True)
    assert "Good game tonight" in talk and "brb, coffee" in talk
    m = api("GET", "/api/campaigns/10/chronicle/minutes.md?last=2", ST).get_data(as_text=True)
    assert "Οι τελευταίες 2 νύχτες" in m
    assert api("GET", "/api/campaigns/10/chronicle/minutes.md?last=x", ST).status_code == 400
    assert api("GET", "/api/campaigns/10/chronicle/minutes.md?last=0", ST).status_code == 400


def test_estimate_route(api):
    e = api("GET", "/api/campaigns/10/chronicle/estimate", ST).get_json()
    assert e["nights_to_write"] == 4 and e["seconds"] > 0 and e["lang"] == "el"


def test_archive_on_delete_and_downloads(api):
    from services import chronicle_archive as ca

    write(api)
    conn = Conn(api.raw)
    cur = conn.cursor()
    aid = ca.write_archive(cur, 10, ST, root=str(api.tmp), now=datetime(2026, 10, 17, 22, 0))
    conn.commit()
    row = cur.execute("SELECT * FROM chronicle_archives WHERE id = %s", (aid,)) or cur.fetchone()
    assert row["dir_name"].startswith("10-athens-blood-and-concrete-20261017-2200")
    folder = os.path.join(str(api.tmp), row["dir_name"])
    minutes = open(os.path.join(folder, "minutes.md"), encoding="utf-8").read()
    transcript = open(os.path.join(folder, "transcript.md"), encoding="utf-8").read()
    assert "Πρακτικά: 4 από 4 νύχτες" in minutes and "Τι δεν είδαν οι παίκτες" in minutes
    assert "[κρυφή ρίψη]" in transcript and "The Crypt" in transcript
    assert row["nights_written"] == 4 and row["storyteller_id"] == ST and row["deleted_by"] == ST
    # downloads: site admins always, the deleting Storyteller for 30 days, nobody else
    assert api("GET", f"/api/chronicle-archives/{aid}/minutes", ADMIN).status_code == 200
    assert api("GET", f"/api/chronicle-archives/{aid}/transcript", ST).status_code == 200
    assert api("GET", f"/api/chronicle-archives/{aid}/minutes", PLAYER).status_code == 404
    assert api("GET", f"/api/chronicle-archives/{aid}/minutes", HELPER_IN).status_code == 404
    assert api("GET", f"/api/chronicle-archives/{aid}/..%2f..%2fetc", ADMIN).status_code == 404
    assert [a["id"] for a in api("GET", "/api/chronicle-archives", ST).get_json()["archives"]] == [aid]
    assert api("GET", "/api/chronicle-archives", PLAYER).get_json()["archives"] == []
    assert ca.can_download(row, ST, "player", now=datetime.now() + timedelta(days=40)) is False
    assert ca.can_download(row, ADMIN, "admin", now=datetime.now() + timedelta(days=400)) is True
    # the path comes from the row: a tampered row can't leave the archive folder
    assert ca.archive_file({**row, "dir_name": "../../etc"}, "minutes", root=str(api.tmp)) is None


def test_archive_failure_raises(api, tmp_path):
    from services import chronicle_archive as ca

    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(Exception):
        ca.write_archive(Conn(api.raw).cursor(), 10, ST, root=str(blocker))
    assert api.raw.execute("SELECT COUNT(*) FROM chronicle_archives").fetchone()[0] == 0


def test_delete_campaign_archives_first():
    """delete_campaign writes the archive before any SQL delete and stops when it fails."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "..", "routes", "campaigns.py"), encoding="utf-8").read()
    body = src[src.index("def delete_campaign"):]
    body = body[:body.index("\n@campaigns_bp.route")]
    assert body.index("write_archive(cursor, campaign_id, user_id)") < body.index("DELETE FROM campaigns")
    assert body.index("write_archive(") < body.index("forget_message_audio")
    assert "'archive_failed'" in body
