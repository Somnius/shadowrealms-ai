"""The chronicler roles (no fall through to the small Ollama model, never trimmed) and LM Studio
streaming with usage and cancel (services/ai_providers.py, services/ai_roles.py)."""

import json

import pytest

from services import ai_providers, ai_roles
from services.ai_providers import Cancelled, LMStudioProvider, ProviderError


class FakeStream:
    def __init__(self, lines, status=200):
        self.lines, self.status_code, self.closed, self.text = lines, status, False, "error body"

    def iter_lines(self):
        for ln in self.lines:
            if self.closed:
                return
            yield ln.encode("utf-8")  # the wire is UTF-8 bytes; requests would guess Latin-1 for SSE

    def close(self):
        self.closed = True


def sse(*chunks):
    return [f"data: {json.dumps(c, ensure_ascii=False)}" for c in chunks] + ["data: [DONE]"]


def delta(text):
    return {"choices": [{"delta": {"content": text}}]}


def test_stream_sends_include_usage_and_reports_tokens(monkeypatch):
    sent = {}
    resp = FakeStream(sse(delta("Η "), delta("νύχτα"), {"choices": [], "usage": {"completion_tokens": 2, "prompt_tokens": 9}}))

    def post(url, json=None, headers=None, timeout=None, stream=False):
        sent.update(payload=json, stream=stream, timeout=timeout)
        return resp

    monkeypatch.setattr(ai_providers.requests, "post", post)
    seen = []
    text = LMStudioProvider("http://lm").generate(
        [{"role": "user", "content": "x"}],
        {"model": "m", "on_token": lambda d, u: seen.append((d, u)), "response_format": {"type": "json_schema"},
         "stream_idle_timeout": 20},
    )
    assert text == "Η νύχτα"
    assert sent["payload"]["stream"] is True and sent["payload"]["stream_options"] == {"include_usage": True}
    assert sent["payload"]["response_format"] == {"type": "json_schema"} and sent["stream"] is True
    assert sent["timeout"] == (10, 20.0)
    assert seen == [("Η ", None), ("νύχτα", None), ("", {"completion_tokens": 2, "prompt_tokens": 9})]
    assert resp.closed


def test_cancel_closes_the_stream(monkeypatch):
    resp = FakeStream(sse(delta("a"), delta("b"), delta("c")))
    monkeypatch.setattr(ai_providers.requests, "post", lambda *a, **k: resp)
    seen = []

    def on_token(d, u):
        seen.append(d)
        return len(seen) < 2

    with pytest.raises(Cancelled):
        LMStudioProvider("http://lm").generate([], {"on_token": on_token, "model": "m"})
    assert resp.closed and seen == ["a", "b"]


def test_stream_error_chunk_and_status(monkeypatch):
    monkeypatch.setattr(ai_providers.requests, "post",
                        lambda *a, **k: FakeStream(sse({"error": {"message": "Context size has been exceeded."}})))
    with pytest.raises(ProviderError, match="Context size"):
        LMStudioProvider("http://lm").generate([], {"on_token": lambda d, u: True, "model": "m"})
    monkeypatch.setattr(ai_providers.requests, "post", lambda *a, **k: FakeStream([], status=400))
    with pytest.raises(ProviderError, match="HTTP 400"):
        LMStudioProvider("http://lm").generate([], {"on_token": lambda d, u: True, "model": "m"})


def test_storyteller_path_stays_non_streaming(monkeypatch):
    sent = {}

    class R:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def post(url, json=None, headers=None, timeout=None):
        sent.update(json)
        return R()

    monkeypatch.setattr(ai_providers.requests, "post", post)
    assert LMStudioProvider("http://lm").generate([], {"model": "m"}) == "ok"
    assert sent["stream"] is False and "stream_options" not in sent


def test_chronicler_roles(app_settings, monkeypatch):
    monkeypatch.setattr(ai_roles, "effective_lm_studio_model", lambda: "loaded-model")
    assert "chronicler_el" in ai_roles.ROLES and "chronicler_en" in ai_roles.ROLES
    el = ai_roles.fallback_chain("chronicler_el")
    en = ai_roles.fallback_chain("chronicler_en")
    assert el[0] == ("lm_studio", "llama-krikri-8b-instruct")
    assert en[0] == ("lm_studio", "loaded-model")
    assert not any(p == "ollama" for p, _ in el + en)
    assert any(p == "ollama" for p, _ in ai_roles.fallback_chain("storyteller_en"))


def test_shrink_false_fails_on_overflow_instead_of_trimming(app_settings):
    calls = []

    class P:
        def generate(self, messages, params):
            calls.append(messages)
            raise ProviderError("HTTP 400: Context size has been exceeded")

    with pytest.raises(ProviderError, match="context overflow"):
        ai_roles.generate_for_role("chronicler_el", [{"role": "user", "content": "x" * 100}], {},
                                   chain=[("lm_studio", "m")], builder=lambda n: P(), shrink=False)
    assert len(calls) == 1


def test_cancel_is_never_retried(app_settings):
    calls = []

    class P:
        def generate(self, messages, params):
            calls.append(1)
            raise Cancelled("cancelled")

    with pytest.raises(Cancelled):
        ai_roles.generate_for_role("chronicler_el", [], {}, chain=[("lm_studio", "a"), ("lm_studio", "b")],
                                   builder=lambda n: P())
    assert calls == [1]


def test_finish_reason_length_is_its_own_error(monkeypatch):
    chunks = sse(delta('{"title": "x'), {"choices": [{"delta": {}, "finish_reason": "length"}]})
    monkeypatch.setattr(ai_providers.requests, "post", lambda *a, **k: FakeStream(chunks))
    with pytest.raises(ProviderError, match="finish_reason=length"):
        LMStudioProvider("http://lm").generate([], {"on_token": lambda d, u: True, "model": "m"})


def test_length_is_not_retried_on_another_model(app_settings):
    calls = []

    class P:
        def generate(self, messages, params):
            calls.append(1)
            raise ProviderError("LM Studio: finish_reason=length")

    with pytest.raises(ProviderError, match="length"):
        ai_roles.generate_for_role("chronicler_el", [], {}, chain=[("lm_studio", "a"), ("lm_studio", "b")],
                                   builder=lambda n: P(), shrink=False)
    assert calls == [1]
