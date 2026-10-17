import base64
import io
import json
import os
import sys
import urllib.error
import wave

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import gemini  # noqa: E402
from app.cachekeys import tts_key  # noqa: E402


def _wav(n=240):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * n)
    return buf.getvalue()


class _Resp:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "free-test-key")
    monkeypatch.delenv("GEMINI_API_KEY_PAID", raising=False)


def test_keys_present_and_valid_cloud(keys):
    assert gemini.keys_present() == {"free": True, "paid": False}
    assert gemini.valid_cloud({"tier": "free"}) == ("free", gemini.DEFAULT_MODEL)
    assert gemini.valid_cloud({"tier": "paid"}) is None  # no paid key
    assert gemini.valid_cloud({"tier": "free", "model": "nope"}) is None
    assert gemini.valid_cloud(None) is None


def test_pick_by_voice_role_gender():
    assert gemini.pick("gemini-Puck") == "Puck"
    assert gemini.pick("gemini-Nobody", gender="female") == "Kore"
    assert gemini.pick(None, gender="male") == "Charon"
    assert gemini.pick(None, gender=None) == "Schedar"
    assert gemini.pick("en_US-ryan-high", role="narrator") == "Charon"
    assert gemini.voice_name("el-kostas") is None


def test_listing_has_all_documented_voices():
    ids = {v["id"] for v in gemini.listing()}
    assert len(ids) == 30 and "gemini-Kore" in ids
    kore = next(v for v in gemini.listing() if v["id"] == "gemini-Kore")
    assert kore["gender"] == "female" and "female" in kore["default_for"]


def test_synth_writes_wav_and_sends_key_header(keys, tmp_path):
    seen = {}

    def opener(req, timeout):
        seen["key"] = req.get_header("X-goog-api-key")
        seen["url"] = req.full_url
        seen["body"] = json.loads(req.data)
        data = base64.b64encode(_wav()).decode()
        return _Resp(json.dumps({"candidates": [{"content": {"parts": [
            {"inlineData": {"mimeType": "audio/wav", "data": data}}]}}]}).encode())

    out = tmp_path / "a.wav"
    gemini.synth("Γεια", "Kore", gemini.DEFAULT_MODEL, "free", str(out), opener=opener)
    assert out.read_bytes()[:4] == b"RIFF"
    assert seen["key"] == "free-test-key"
    assert gemini.DEFAULT_MODEL + ":generateContent" in seen["url"]
    cfg = seen["body"]["generationConfig"]
    assert cfg["responseModalities"] == ["AUDIO"]
    assert cfg["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"


def test_raw_pcm_is_wrapped():
    raw = base64.b64encode(b"\0\0" * 100).decode()
    wav = gemini.wav_bytes({"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "audio/L16;codec=pcm;rate=24000", "data": raw}}]}}]})
    with wave.open(io.BytesIO(wav)) as w:
        assert w.getframerate() == 24000 and w.getnframes() == 100


@pytest.mark.parametrize("exc,code", [
    (urllib.error.HTTPError("u", 429, "x", {}, None), "rate_limited"),
    (urllib.error.HTTPError("u", 500, "x", {}, None), "http_500"),
    (TimeoutError("timed out"), "timeout"),
    (urllib.error.URLError("refused"), "network"),
])
def test_errors_become_cloud_errors_without_key(keys, tmp_path, exc, code):
    def opener(req, timeout):
        raise exc

    with pytest.raises(gemini.CloudError) as e:
        gemini.synth("x", "Kore", gemini.DEFAULT_MODEL, "free", str(tmp_path / "a.wav"), opener=opener)
    assert e.value.code == code
    assert "free-test-key" not in repr(e.value) + str(e.value.detail)


def test_bad_response_and_no_key(monkeypatch, tmp_path):
    with pytest.raises(gemini.CloudError):
        gemini.wav_bytes({"candidates": []})
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(gemini.CloudError) as e:
        gemini.synth("x", "Kore", gemini.DEFAULT_MODEL, "free", str(tmp_path / "a.wav"))
    assert e.value.code == "no_key"


def test_stats_count_today_and_roll_over(keys):
    day = ["2026-10-17"]
    s = gemini.Stats(today=lambda: day[0])
    s.error("rate_limited", gemini.DEFAULT_MODEL, "free")
    s.error("timeout", gemini.DEFAULT_MODEL, "free")
    snap = s.snapshot()
    assert snap["errors_today"] == 2 and snap["last_error"]["code"] == "timeout"
    assert snap["keys"] == {"free": True, "paid": False}
    day[0] = "2026-10-18"
    assert s.snapshot()["errors_today"] == 0
    assert s.snapshot()["last_error"]["code"] == "timeout"  # the last error stays visible


def test_cloud_cache_key_has_provider_and_model():
    a = tts_key("gemini", f"{gemini.MODELS[0]}/Kore", "Hello", "24k")
    assert a != tts_key("gemini", f"{gemini.MODELS[1]}/Kore", "Hello", "24k")
    assert a != tts_key("piper", "Kore", "Hello", "24k")
