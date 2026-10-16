"""Server voices (0.17): read-out kinds and voices, the TTS routes (404 both ways, like reading
messages), the shared cache key, audio removed with its message, and the gender field."""

import sqlite3
import sys
import types

import pytest

from services import voice_tts as vt
from tests.unit.test_creation_validation_routes import Conn


def row(**kw):
    base = {"role": "user", "message_type": "ic", "content": "Hello there", "username": "lef",
            "speaker_mode": "character", "character_id": 5, "character_name": "Mira"}
    base.update(kw)
    return base


@pytest.mark.parametrize("r,kind", [
    (row(), "ic"),
    (row(speaker_mode="player", character_id=None), "ooc"),
    (row(role="assistant"), "storyteller"),
    (row(role="assistant", ai_message_kind="slash_assistant"), None),
    (row(ai_message_kind="dice_roll:ab"), "dice"),
    (row(ai_message_kind="dice_animation:ab"), None),
    (row(message_type="system"), None),
    (row(message_type="action"), "actions"),
    (row(speaker_mode="staff", staff_kind="storyteller"), "storyteller"),
    (row(speaker_mode="staff", staff_kind="admin"), "ooc"),
])
def test_readout_kind(r, kind):
    assert vt.readout_kind(r) == kind


def test_text_prep():
    assert vt.plain_text("**Run** to [the door](http://x) 🩸 now") == "Run to the door now"
    assert vt.spoken_text(row(content="*waves* Hi"), "ic") == "Mira: waves Hi"
    dice = row(content="lef rolled 5 dice: 3 successes\nmore lines", ai_message_kind="dice_roll:a",
               speaker_mode="player", character_id=None)
    assert vt.spoken_text(dice, "dice") == "lef rolled 5 dice: 3 successes"
    assert vt.guess_lang("Καλησπέρα σας") == "el" and vt.guess_lang("Good evening") == "en"


def test_voice_mapping():
    camp = {"narrator_voice_en": "en_US-ryan-high", "narrator_voice_en_gb": "en_GB-alan-medium",
            "narrator_voice_el": "el-spyros"}
    gb = {"en_accent": "gb"}
    assert vt.tts_request(row(), "female", {}, {}) == {
        "text": "Mira: Hello there", "lang": "en", "accent": "us", "gender": "female"}
    assert vt.tts_request(row(), None, {}, {})["gender"] == "neutral"  # unset speaks neutral
    assert vt.tts_request(row(speaker_mode="player", character_id=None), "male", {}, {})["gender"] == "neutral"
    st = vt.tts_request(row(role="assistant"), None, gb, camp)
    assert st["role"] == "narrator" and st["voice"] == "en_GB-alan-medium" and st["accent"] == "gb"
    assert vt.tts_request(row(role="assistant"), None, {}, camp)["voice"] == "en_US-ryan-high"
    el = vt.tts_request(row(role="assistant", content="Η νύχτα"), None, gb, camp)
    assert el["lang"] == "el" and el["voice"] == "el-spyros" and el["accent"] == "gr"
    act = vt.tts_request(row(message_type="action"), "female", {}, {})
    assert act["role"] == "narrator" and "voice" not in act and "gender" not in act
    assert vt.tts_request(row(message_type="system"), None, {}, {}) is None


SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT);
CREATE TABLE campaigns (id INTEGER PRIMARY KEY, created_by INTEGER);
CREATE TABLE campaign_players (campaign_id INTEGER, user_id INTEGER);
CREATE TABLE locations (id INTEGER PRIMARY KEY, campaign_id INTEGER, is_open INTEGER DEFAULT 1,
    closure_reason TEXT);
CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER);
CREATE TABLE messages (id INTEGER PRIMARY KEY, campaign_id INTEGER, location_id INTEGER,
    user_id INTEGER, character_id INTEGER, message_type TEXT DEFAULT 'ic', content TEXT,
    role TEXT DEFAULT 'user', created_at TEXT DEFAULT CURRENT_TIMESTAMP);
INSERT INTO users VALUES (1, 'admin', 'admin'), (2, 'st', 'player'), (3, 'pl', 'player'),
    (4, 'out', 'player'), (5, 'pl2', 'player');
INSERT INTO campaigns VALUES (10, 2);
INSERT INTO campaign_players VALUES (10, 3), (10, 5);
INSERT INTO locations VALUES (100, 10, 1, NULL), (101, 10, 0, 'closed');
INSERT INTO characters VALUES (7, 'Mira', 3);
INSERT INTO messages (id, campaign_id, location_id, user_id, character_id, content) VALUES
    (1, 10, 100, 3, 7, 'Good evening'), (2, 10, 101, 2, NULL, 'In the closed room');
"""


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

    from routes import voice
    from services import speech_client

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.executescript(SCHEMA)
    monkeypatch.setattr(voice, "get_db", lambda: Conn(raw))
    speech = {"calls": [], "files": set()}

    def fake_json(method, path, body=None):
        speech["calls"].append((method, path, body))
        if method == "POST" and path == "/tts":
            key = "k" + str(abs(hash((body["text"], body.get("voice"), body.get("gender")))))[:12]
            done = key in speech["files"]
            speech["files"].add(key)
            return 200, {"id": "job" + key, "status": "done" if done else "queued", "key": key,
                         "voice": body.get("voice") or "v"}
        if method == "DELETE":
            speech["files"].discard(path.rsplit("/", 1)[1])
            return 200, {"ok": True}
        if path.startswith("/tts/"):
            return 200, {"id": path[5:], "status": "done", "key": path[8:]}
        return 404, {}

    monkeypatch.setattr(speech_client, "call_json", fake_json)
    monkeypatch.setattr(speech_client, "call_bytes", lambda path: (200, b"OggS", "audio/ogg"))
    app = Flask(__name__)
    app.config.update(JWT_SECRET_KEY="unit-test-secret-key-of-enough-length", TESTING=True)
    JWTManager(app)
    app.register_blueprint(voice.voice_bp, url_prefix="/api")
    with app.app_context():
        tokens = {uid: create_access_token(identity=str(uid)) for uid in (1, 2, 3, 4, 5)}
    c = app.test_client()

    def call(method, url, uid, body=None):
        return c.open(url, method=method, json=body, headers={"Authorization": f"Bearer {tokens[uid]}"})

    call.raw, call.speech, call.client, call.tokens = raw, speech, c, tokens
    return call


def test_tts_job_visibility_404_both_ways(api):
    assert api("POST", "/api/voice/tts/jobs", 4, {"message_id": 1}).status_code == 404  # not a member
    assert api("POST", "/api/voice/tts/jobs", 3, {"message_id": 999}).status_code == 404  # missing
    assert api("POST", "/api/voice/tts/jobs", 3, {"message_id": 2}).status_code == 404  # closed room
    assert api("POST", "/api/voice/tts/jobs", 2, {"message_id": 2}).status_code == 200  # its Storyteller
    assert api("POST", "/api/voice/tts/jobs", 3, {"message_id": "1"}).status_code == 400


def test_gender_and_shared_cache(api):
    from database import ensure_characters_gender_column

    ensure_characters_gender_column(Conn(api.raw).cursor())
    api.raw.execute("UPDATE characters SET gender = 'female' WHERE id = 7")
    a = api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1}).get_json()
    sent = [b for m, p, b in api.speech["calls"] if p == "/tts"][-1]
    assert sent["gender"] == "female" and sent["text"] == "Mira: Good evening"
    b = api("POST", "/api/voice/tts/jobs", 2, {"message_id": 1}).get_json()
    assert a["key"] == b["key"] and b["state"] == "done"  # two listeners, one file
    assert api.raw.execute("SELECT COUNT(*) FROM voice_audio").fetchone()[0] == 1
    assert api("GET", f"/api/voice/audio/{a['key']}", 5).status_code == 200
    assert api("GET", f"/api/voice/audio/{a['key']}", 4).status_code == 404
    assert api("GET", f"/api/voice/audio/{a['key']}?fmt=wav", 5).status_code == 404
    assert api("GET", f"/api/voice/tts/jobs/{a['job_id']}", 5).get_json()["state"] == "done"


def test_message_delete_removes_audio(api):
    from routes.messages import visible_message  # noqa: F401  (the helper the route uses)
    from services.voice_audio import forget_message_audio

    key = api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1}).get_json()["key"]
    assert key in api.speech["files"]
    cur = Conn(api.raw).cursor()
    assert forget_message_audio(cur, [1]) == [key]
    assert key not in api.speech["files"]
    assert api("GET", f"/api/voice/audio/{key}", 5).status_code == 404


def test_preview(api):
    r = api("POST", "/api/voice/tts/preview", 4, {"voice_id": "el-eleni", "lang": "el"})
    assert r.status_code == 200
    assert api("GET", f"/api/voice/audio/{r.get_json()['key']}", 4).status_code == 200
    assert api("POST", "/api/voice/tts/preview", 4, {"voice_id": "x", "lang": "fr"}).status_code == 400


def test_gender_validation():
    from routes.characters import _gender_error

    assert _gender_error({}) is None and _gender_error({"gender": None}) is None
    assert _gender_error({"gender": "male"}) is None and _gender_error({"gender": ""}) is None
    assert _gender_error({"gender": "other"})


def test_voice_override_wins_when_language_matches():
    from services import voice_tts as vt
    en = vt.tts_request(row(), "male", {}, {}, "en_GB-alan-medium")
    assert en["voice"] == "en_GB-alan-medium" and en["gender"] == "male"
    el = vt.tts_request(row(content="Καλησπέρα σας"), "female", {}, {}, "en_GB-alan-medium")
    assert "voice" not in el and el["gender"] == "female"  # an English pick does not speak Greek
    assert vt.tts_request(row(content="Καλησπέρα"), None, {}, {}, "el-kostas")["voice"] == "el-kostas"
    assert "voice" not in vt.tts_request(row(speaker_mode="player", character_id=None), None, {}, {}, "el-kostas")


def test_voice_override_validation():
    from services.voice_tts import voice_override_error as err
    cat = {"el-kostas", "en_US-ryan-high"}
    assert err(None, None) is None and err("", cat) is None
    assert err("el-kostas", cat) is None
    assert err("el-nobody", cat) == "unknown voice"
    assert err("fr-x", cat) and err(5, cat) and err("el-kostas; drop", cat)
    assert err("el-kostas", None) == "speech_unavailable"
