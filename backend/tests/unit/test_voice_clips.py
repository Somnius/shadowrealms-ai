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
