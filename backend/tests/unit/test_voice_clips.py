"""Speaking (0.18): clip upload goes to the speech service and is recorded per player and room;
transcripts come back to their owner only; replay follows the message's visibility (an unsent
clip: its owner only); clips go with their message and with the chronicle."""

import io

import pytest

from tests.unit.test_creation_validation_routes import Conn
from tests.unit.test_voice_tts import api  # noqa: F401  (fixture)

CLIP = "c" * 32


class _VC:  # services.voice_clips, imported once the api fixture has stubbed psycopg2
    def __getattr__(self, name):
        from services import voice_clips as m
        return getattr(m, name)


voice_clips = _VC()


@pytest.fixture
def speech(api, monkeypatch):  # noqa: F811
    from services import speech_client

    state = {"uploads": [], "deleted": [], "job": {"id": "j" * 20, "status": "done", "clip": CLIP,
                                                    "text": "I open the door", "duration": 4.2}}

    def upload(path, fields, filename, data, mime, timeout=60):
        state["uploads"].append((path, fields, mime, len(data)))
        return 200, {"id": "j" * 20, "status": "queued", "clip": CLIP}

    base = speech_client.call_json

    def call_json(method, path, body=None):
        if path.startswith("/stt/"):
            return 200, dict(state["job"])
        if method == "DELETE" and path.startswith("/clips/"):
            state["deleted"].append(path[7:])
            return 200, {"ok": True}
        return base(method, path, body)

    monkeypatch.setattr(speech_client, "call_upload", upload)
    monkeypatch.setattr(speech_client, "call_json", call_json)
    return state


def post_clip(api, uid, data=b"OggS-data", mime="audio/mp4", **form):  # noqa: F811
    fields = {"campaign_id": "10", "location_id": "100", "lang": "en", **form}
    fields["audio"] = (io.BytesIO(data), "clip.m4a", mime)
    return api.client.post("/api/voice/clips", data=fields, content_type="multipart/form-data",
                           headers={"Authorization": f"Bearer {api.tokens[uid]}"})


def test_upload_checks(api, speech):  # noqa: F811
    assert post_clip(api, 4).status_code == 404  # not a member
    assert post_clip(api, 3, location_id="999").status_code == 404  # not a room of this chronicle
    assert post_clip(api, 3, lang="fr").status_code == 400
    assert post_clip(api, 3, mime="video/mp4").status_code == 400
    assert post_clip(api, 3, data=b"").status_code == 400
    assert post_clip(api, 3, data=b"x" * (voice_clips.max_clip_bytes() + 1)).status_code == 413
    assert speech["uploads"] == []
    r = post_clip(api, 3)
    assert r.status_code == 200 and r.get_json()["clip_id"] == CLIP
    assert speech["uploads"][0][:3] == ("/stt", {"lang": "en", "max_seconds": "180"}, "audio/mp4")
    row = api.raw.execute("SELECT user_id, campaign_id, location_id, message_id FROM voice_clips").fetchone()
    assert tuple(row) == (3, 10, 100, None)


def test_disk_cap(api, speech, monkeypatch):  # noqa: F811
    monkeypatch.setenv("VOICE_CLIPS_MAX_GB", "0")
    assert post_clip(api, 3).get_json()["error"] == "clips_disk_full"


def test_transcript_owner_only_and_stored(api, speech):  # noqa: F811
    post_clip(api, 3)
    assert api("GET", f"/api/voice/stt/jobs/{'j' * 20}", 5).status_code == 404  # someone else's
    r = api("GET", f"/api/voice/stt/jobs/{'j' * 20}", 3).get_json()
    assert r["state"] == "done" and r["text"] == "I open the door" and r["duration_ms"] == 4200
    raw = api.raw.execute("SELECT transcript_raw, duration_ms FROM voice_clips").fetchone()
    assert tuple(raw) == ("I open the door", 4200)


def test_replay_visibility(api, speech):  # noqa: F811
    post_clip(api, 3)
    assert api("GET", f"/api/voice/clips/{CLIP}/audio", 3).status_code == 200  # owner, unsent
    assert api("GET", f"/api/voice/clips/{CLIP}/audio", 5).status_code == 404  # unsent: not yet
    api.raw.execute("UPDATE voice_clips SET message_id = 1")
    assert api("GET", f"/api/voice/clips/{CLIP}/audio", 5).status_code == 200  # everyone in the room
    assert api("GET", f"/api/voice/clips/{CLIP}/audio", 4).status_code == 404  # not a member
    assert api("GET", f"/api/voice/clips/{CLIP}/audio?fmt=wav", 3).status_code == 404


def test_attach_rules(api):  # noqa: F811
    clip = {"user_id": 3, "campaign_id": 10, "location_id": 100, "message_id": None}
    assert voice_clips.attach_error(clip, 3, 10, 100) is None
    assert voice_clips.attach_error(None, 3, 10, 100) == "clip_not_found"
    assert voice_clips.attach_error(clip, 5, 10, 100) == "clip_not_found"
    assert voice_clips.attach_error(clip, 3, 10, 101) == "clip_wrong_room"
    assert voice_clips.attach_error({**clip, "message_id": 9}, 3, 10, 100) == "clip_already_sent"


def test_deleted_with_message_and_chronicle(api, speech):  # noqa: F811
    cur = Conn(api.raw).cursor()
    voice_clips.record(cur, "a" * 32, 10, 100, 3, "en")
    voice_clips.record(cur, "b" * 32, 10, 100, 3, "en")
    voice_clips.attach(cur, "a" * 32, 1)
    assert voice_clips.forget_message_clips(cur, [1]) == ["a" * 32]
    assert speech["deleted"] == ["a" * 32]
    assert voice_clips.forget_campaign_clips(cur, 10) == ["b" * 32]
    assert api.raw.execute("SELECT COUNT(*) FROM voice_clips").fetchone()[0] == 0


def test_closed_room_refuses_upload(api, speech):  # noqa: F811
    api.raw.execute("UPDATE locations SET is_open = 0 WHERE id = 100")
    assert post_clip(api, 3).status_code == 404
    assert speech["uploads"] == []


def test_attach_once(api, speech):  # noqa: F811
    cur = Conn(api.raw).cursor()
    voice_clips.record(cur, "a" * 32, 10, 100, 3, "en")
    assert voice_clips.attach(cur, "a" * 32, 1) is True
    assert voice_clips.attach(cur, "a" * 32, 2) is False


def test_unmetered_clips_count(api, speech):  # noqa: F811
    cur = Conn(api.raw).cursor()
    voice_clips.record(cur, "a" * 32, 10, 100, 3, "en")
    assert voice_clips.used_bytes(cur) == voice_clips.UNMETERED_MS * 4


def test_health_admin_only(api, speech, monkeypatch):  # noqa: F811
    from services import speech_client
    base = speech_client.call_json

    def cj(method, path, body=None):
        if path == "/health":
            return 200, {"stt": {"loaded": True, "queue": 1, "vram_free_mb": 9000, "vram_needed_mb": 2150},
                         "tts": {"queue": 2, "cache_bytes": 10, "cache_cap_bytes": 99}, "clips": {"bytes": 5}}
        return base(method, path, body)

    monkeypatch.setattr(speech_client, "call_json", cj)
    post_clip(api, 3)
    api.raw.execute("UPDATE voice_clips SET duration_ms = 90000")
    for uid in (2, 3, 4):
        assert api("GET", "/api/voice/health", uid).status_code == 403
    r = api("GET", "/api/voice/health", 1).get_json()
    assert r["speech"]["up"] and r["queues"] == {"stt": 1, "tts": 2} and r["vram"]["free_mb"] == 9000
    assert r["disk"]["clips_bytes"] == 5 and r["disk"]["tts_cache_cap_bytes"] == 99
    assert r["minutes_today"][0]["user_id"] == 3 and r["minutes_today"][0]["minutes"] == 1.5


def test_health_speech_down(api, monkeypatch):  # noqa: F811
    from services import speech_client

    def down(*a, **k):
        raise speech_client.SpeechUnavailable("x")

    monkeypatch.setattr(speech_client, "call_json", down)
    r = api("GET", "/api/voice/health", 1)
    assert r.status_code == 200 and r.get_json()["speech"]["up"] is False


def test_orphan_sweep(api, speech):  # noqa: F811
    from datetime import datetime, timedelta
    post_clip(api, 3)
    api.raw.execute("INSERT INTO voice_clips (clip_id, campaign_id, user_id, message_id, created_at) "
                    "VALUES ('d', 10, 3, 1, '2000-01-01 00:00:00')")  # sent: kept
    from tests.unit.test_creation_validation_routes import Conn
    cur = Conn(api.raw).cursor()
    assert voice_clips.sweep_orphans(cur) == []  # fresh
    later = datetime.utcnow() + timedelta(hours=25)
    assert voice_clips.sweep_orphans(cur, now=later) == [CLIP]
    assert speech["deleted"] == [CLIP]
    assert [r[0] for r in api.raw.execute("SELECT clip_id FROM voice_clips")] == ["d"]


def test_orphan_sweep_keeps_rows_when_speech_down(api, monkeypatch):  # noqa: F811
    from datetime import datetime, timedelta

    from services import speech_client
    from tests.unit.test_creation_validation_routes import Conn
    voice_clips.ensure_voice_clips_table(Conn(api.raw).cursor())
    api.raw.execute("INSERT INTO voice_clips (clip_id, campaign_id, user_id, created_at) "
                    "VALUES ('e', 10, 3, '2000-01-01 00:00:00')")

    def down(*a, **k):
        raise speech_client.SpeechUnavailable("x")

    monkeypatch.setattr(speech_client, "call_json", down)
    from tests.unit.test_creation_validation_routes import Conn
    cur = Conn(api.raw).cursor()
    assert voice_clips.sweep_orphans(cur, now=datetime.utcnow() + timedelta(hours=1)) == []
    assert [r[0] for r in api.raw.execute("SELECT clip_id FROM voice_clips")] == ["e"]


def test_orphan_sweep_spares_a_clip_sent_meanwhile(api, speech, monkeypatch):  # noqa: F811
    from datetime import datetime, timedelta
    post_clip(api, 3)
    from tests.unit.test_creation_validation_routes import Conn
    cur = Conn(api.raw).cursor()
    real = voice_clips._drop_files
    seen = []

    def sent_first(ids):
        seen.append(list(ids))
        return real(ids)

    monkeypatch.setattr(voice_clips, "_drop_files", sent_first)
    real_exec = cur.execute
    state = {"done": False}

    def execute(sql, params=()):
        if sql.startswith("DELETE FROM voice_clips") and not state["done"]:
            state["done"] = True
            api.raw.execute("UPDATE voice_clips SET message_id = 1")  # a send lands just now
        return real_exec(sql, params)

    cur.execute = execute
    assert voice_clips.sweep_orphans(cur, now=datetime.utcnow() + timedelta(hours=25)) == []
    assert speech["deleted"] == [] and api.raw.execute("SELECT COUNT(*) FROM voice_clips").fetchone()[0] == 1
