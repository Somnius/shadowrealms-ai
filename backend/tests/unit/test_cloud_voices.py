"""Cloud voices (0.23): the site setting, the chronicle opt-in, and what goes to the speech service.
The Gemini call itself lives in the speech service (speech/tests/test_gemini.py); here it is mocked."""

import pytest

from services import cloud_voices
from services.request_validation import RequestValidationError
from services.voice_settings import validate_campaign_voice_settings
from tests.unit.test_voice_tts import api  # noqa: F401  (fixture)

ON = {"tier": "free", "model": cloud_voices.DEFAULT_MODEL}
OFF = {"tier": "off", "model": cloud_voices.DEFAULT_MODEL}


def test_read_config_defaults_and_junk():
    assert cloud_voices.read_config(lambda k: None) == OFF
    assert cloud_voices.read_config({"cloud_voices_tier": "paid", "cloud_voices_model": "x"}.get) == {
        "tier": "paid", "model": cloud_voices.DEFAULT_MODEL}
    assert cloud_voices.read_config({"cloud_voices_tier": "maybe"}.get)["tier"] == "off"


@pytest.mark.parametrize("body", [None, {"tier": "on"}, {"tier": "free", "model": "gpt"}, {"tier": "free", "x": 1}])
def test_validate_config_rejects(body):
    with pytest.raises(RequestValidationError):
        cloud_voices.validate_config(body)


def test_chronicle_opt_in_validated():
    assert validate_campaign_voice_settings({"cloud_voices": True})["cloud_voices"] is True
    with pytest.raises(RequestValidationError):
        validate_campaign_voice_settings({"cloud_voices": "yes"})


def test_apply_needs_site_and_chronicle():
    body = {"text": "Hi", "lang": "en", "role": "narrator", "voice": "gemini-Puck"}
    assert cloud_voices.apply(body, ON, {"cloud_voices": True})["cloud"] == ON
    off_site = cloud_voices.apply(body, OFF, {"cloud_voices": True})
    off_chron = cloud_voices.apply(body, ON, {"cloud_voices": False})
    for out in (off_site, off_chron):  # no cloud, and the Gemini narrator pick is dropped
        assert "cloud" not in out and "voice" not in out
    local = cloud_voices.apply({"text": "Hi", "voice": "en_US-ryan-high"}, OFF, None)
    assert local["voice"] == "en_US-ryan-high"
    # an explicit local pick (narrator slot or a character's own voice) stays local when opted in
    kept = cloud_voices.apply({"text": "Hi", "voice": "el-kostas", "gender": "male"}, ON, {"cloud_voices": True})
    assert "cloud" not in kept and kept["voice"] == "el-kostas"
    assert cloud_voices.apply({"text": "Hi", "gender": "male"}, ON, {"cloud_voices": True})["cloud"] == ON


def _settings(monkeypatch, store):
    from routes import voice
    monkeypatch.setattr(voice, "_get_setting", store.get)
    monkeypatch.setattr(voice, "_set_setting", lambda k, v: store.pop(k, None) if v is None else store.__setitem__(k, v))


def _health(monkeypatch, api, cloud):  # noqa: F811
    from services import speech_client
    base = speech_client.call_json

    def cj(method, path, body=None):
        if path == "/health":
            return 200, {"stt": {}, "tts": {}, "clips": {}, "cloud": cloud}
        return base(method, path, body)

    monkeypatch.setattr(speech_client, "call_json", cj)


def test_admin_settings_route(api, monkeypatch):  # noqa: F811
    store = {}
    _settings(monkeypatch, store)
    _health(monkeypatch, api, {"keys": {"free": True, "paid": False}})
    assert api("GET", "/api/voice/cloud-settings", 2).status_code == 403
    r = api("GET", "/api/voice/cloud-settings", 1).get_json()
    assert r["tier"] == "off" and r["keys"] == {"free": True, "paid": False}
    assert cloud_voices.DEFAULT_MODEL in r["models"]
    assert api("PUT", "/api/voice/cloud-settings", 1, {"tier": "nope"}).status_code == 400
    r = api("PUT", "/api/voice/cloud-settings", 1, {"tier": "paid", "model": "gemini-3.8-flash-tts"}).get_json()
    assert r["tier"] == "paid" and r["model"] == "gemini-3.8-flash-tts"
    assert store == {"cloud_voices_tier": "paid", "cloud_voices_model": "gemini-3.8-flash-tts"}
    api("PUT", "/api/voice/cloud-settings", 1, {"tier": "off"})
    assert store == {}


def test_tts_job_sends_cloud_only_when_opted_in(api, monkeypatch):  # noqa: F811
    store = {"cloud_voices_tier": "free"}
    _settings(monkeypatch, store)
    api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1})
    sent = [b for m, p, b in api.speech["calls"] if p == "/tts"][-1]
    assert "cloud" not in sent  # the chronicle has not opted in
    assert api("PUT", "/api/campaigns/10/voice-settings", 2, {"cloud_voices": True}).status_code == 200
    api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1})
    sent = [b for m, p, b in api.speech["calls"] if p == "/tts"][-1]
    assert sent["cloud"] == {"tier": "free", "model": cloud_voices.DEFAULT_MODEL}
    got = api("GET", "/api/campaigns/10/voice-settings", 5).get_json()
    assert got["cloud_available"] is True and got["settings"]["cloud_voices"] is True
    store.clear()
    api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1})
    assert "cloud" not in [b for m, p, b in api.speech["calls"] if p == "/tts"][-1]


def test_fallback_key_is_remembered(api, monkeypatch):  # noqa: F811
    from services import speech_client

    def cj(method, path, body=None):
        if path == "/tts":
            return 200, {"id": "j1", "status": "queued", "key": "gemkey1", "voice": "gemini-Kore",
                         "fallback_key": "localkey1"}
        return 404, {}

    monkeypatch.setattr(speech_client, "call_json", cj)
    assert api("POST", "/api/voice/tts/jobs", 5, {"message_id": 1}).status_code == 200
    keys = {r[0] for r in api.raw.execute("SELECT audio_key FROM voice_audio WHERE message_id = 1")}
    assert keys == {"gemkey1", "localkey1"}
    assert api("GET", "/api/voice/audio/localkey1", 5).status_code == 200


def test_preview_of_cloud_voice(api, monkeypatch):  # noqa: F811
    store = {}
    _settings(monkeypatch, store)
    body = {"voice_id": "gemini-Kore", "lang": "el"}
    assert api("POST", "/api/voice/tts/preview", 5, body).get_json()["error"] == "cloud_voices_off"
    store["cloud_voices_tier"] = "paid"
    assert api("POST", "/api/voice/tts/preview", 5, body).status_code == 200  # a player: local sample
    assert "cloud" not in [b for m, p, b in api.speech["calls"] if p == "/tts"][-1]
    for uid in (1, 2):  # site admin, chronicle creator
        assert api("POST", "/api/voice/tts/preview", uid, body).status_code == 200
        assert [b for m, p, b in api.speech["calls"] if p == "/tts"][-1]["cloud"]["tier"] == "paid"


def test_voices_list_cloud_only_when_on(api, monkeypatch):  # noqa: F811
    from services import speech_client
    store = {}
    _settings(monkeypatch, store)
    monkeypatch.setattr(speech_client, "call_json", lambda m, p, b=None: (200, {
        "voices": [], "defaults": {}, "cloud_voices": [{"id": "gemini-Kore"}]}))
    assert api("GET", "/api/voice/voices", 5).get_json()["cloud_voices"] == []
    store["cloud_voices_tier"] = "free"
    assert api("GET", "/api/voice/voices", 5).get_json()["cloud_voices"] == [{"id": "gemini-Kore"}]


def test_health_shows_cloud_errors(api, monkeypatch):  # noqa: F811
    _settings(monkeypatch, {"cloud_voices_tier": "free"})
    _health(monkeypatch, api, {"keys": {"free": True, "paid": False}, "errors_today": 3,
                               "last_error": {"code": "rate_limited"}})
    c = api("GET", "/api/voice/health", 1).get_json()["cloud"]
    assert c["errors_today"] == 3 and c["last_error"]["code"] == "rate_limited" and c["tier"] == "free"
