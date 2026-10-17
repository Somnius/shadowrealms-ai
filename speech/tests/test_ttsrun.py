"""Cloud lines and their local fallback (0.23), with stub engines and converters (no models, no ffmpeg)."""
import os
import sys
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import audio, config, gemini, ttsrun  # noqa: E402
from app.limits import Refused  # noqa: E402

LOCAL = "en_US-ryan-high"


class Engine:
    def __init__(self):
        self.calls = []

    def synth(self, vid, text, wav):
        self.calls.append((vid, text))
        open(wav, "wb").write(b"RIFFlocal")


@pytest.fixture
def run(tmp_path, monkeypatch):
    def copy(src, dst, *a, **k):
        open(dst, "wb").write(open(src, "rb").read())

    monkeypatch.setattr(audio, "to_opus", copy)
    monkeypatch.setattr(audio, "to_m4a", copy)
    monkeypatch.setattr(audio, "duration", lambda p: 1.0)
    monkeypatch.setattr(audio, "_ff", lambda args, timeout=120: open(args[-1], "wb").write(b"RIFFcat"))
    (tmp_path / "tmp").mkdir()
    eng = Engine()
    stats = gemini.Stats()
    r = ttsrun.Runner(str(tmp_path / "tts"), str(tmp_path / "tmp"), lambda vid: eng, stats)
    r.eng, r.stats = eng, stats
    return r


def cloud_job(**kw):
    p = dict(voice="gemini-Kore", key="gemkey", text="Hello there.",
             cloud=dict(tier="free", model=gemini.DEFAULT_MODEL, name="Kore"),
             fallback=dict(voice=LOCAL, key="localkey"))
    p.update(kw)
    return p


def test_cloud_failure_falls_back_to_local(run, monkeypatch):
    def fail(*a, **k):
        raise gemini.CloudError("rate_limited")

    monkeypatch.setattr(gemini, "synth", fail)
    out = run.run_cloud(cloud_job())
    assert out["key"] == "localkey" and out["provider"] == "local" and out["cloud_error"] == "rate_limited"
    assert os.path.exists(run.paths("localkey")[0])
    assert not os.path.exists(run.paths("gemkey")[0]) and not os.path.exists(run.paths("gemkey")[1])
    assert run.stats.snapshot()["errors_today"] == 1
    assert run.eng.calls == [(LOCAL, "Hello there.")]


def test_cloud_success_writes_only_the_cloud_key(run, monkeypatch):
    monkeypatch.setattr(gemini, "synth", lambda text, name, model, tier, wav, **k: open(wav, "wb").write(b"RIFFg"))
    out = run.run_cloud(cloud_job())
    assert out["key"] == "gemkey" and out["provider"] == "gemini"
    assert open(run.paths("gemkey")[0], "rb").read() == b"RIFFg"
    assert not os.path.exists(run.paths("localkey")[0]) and run.eng.calls == []
    assert run.stats.snapshot()["errors_today"] == 0


def test_whole_line_deadline(run, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_TIMEOUT", 0.3)
    monkeypatch.setattr(config, "TEXT_PART_CHARS", 10)  # several parts
    calls = []

    def slow(text, name, model, tier, wav, **k):
        calls.append(text)
        time.sleep(0.2)
        open(wav, "wb").write(b"RIFFg")

    monkeypatch.setattr(gemini, "synth", slow)
    t0 = time.monotonic()
    out = run.run_cloud(cloud_job(text="One two three. Four five six. Seven eight nine. Ten eleven."))
    assert time.monotonic() - t0 < 1.0
    assert out["provider"] == "local" and out["cloud_error"] == "timeout"
    assert len(calls) <= 2  # the parts after the deadline are never asked for
    assert not os.path.exists(run.paths("gemkey")[0])


def test_hung_call_is_cut_at_the_deadline(run, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_TIMEOUT", 0.2)
    monkeypatch.setattr(gemini, "synth", lambda *a, **k: time.sleep(5))
    t0 = time.monotonic()
    assert run.run_cloud(cloud_job())["cloud_error"] == "timeout"
    assert time.monotonic() - t0 < 1.0


@pytest.mark.parametrize("fallback", [None, dict(voice="nope", key="k"), dict(voice=LOCAL)])
def test_missing_or_unknown_fallback_is_a_clear_error(run, fallback):
    with pytest.raises(Refused) as e:
        run.run_cloud(cloud_job(fallback=fallback))
    assert e.value.code == "no_fallback"


def test_unknown_local_voice_is_a_clear_error(run):
    with pytest.raises(Refused) as e:
        run.run_local(dict(voice="nope", key="k", text="x"))
    assert e.value.code == "unknown_voice"


def test_opener_has_no_proxy_and_no_redirects():
    handlers = gemini._OPENER.handlers
    proxies = [h for h in handlers if isinstance(h, urllib.request.ProxyHandler)]
    assert all(not h.proxies for h in proxies)  # no env proxy handler was added
    assert any(isinstance(h, gemini._NoRedirect) for h in handlers)
    assert gemini._NoRedirect().redirect_request(None, None, 302, "", {}, "http://x") is None
