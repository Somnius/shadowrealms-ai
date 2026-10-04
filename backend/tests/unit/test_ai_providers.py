"""Provider payloads, cloud quirks, and the role fallback chain (no real HTTP)."""

import pytest

from services import ai_providers as ap
from services import ai_roles


class FakeResp:
    def __init__(self, status, body=None, text=None):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = text if text is not None else str(self._body)
        self.headers = {}

    def json(self):
        return self._body


class FakeHTTP:
    """Replaces the `requests` module inside services.ai_providers."""

    RequestException = Exception

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": dict(json or {}), "headers": headers})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def http(monkeypatch):
    def install(*responses):
        fake = FakeHTTP(responses)
        monkeypatch.setattr(ap, "requests", fake)
        return fake
    return install


MSGS = [
    {"role": "system", "content": "You are the Storyteller."},
    {"role": "system", "content": "Campaign Context: Athens by night"},
    {"role": "user", "content": "I enter Elysium."},
]


def test_anthropic_payload_headers_and_no_temperature_for_sonnet_55(http):
    fake = http(FakeResp(200, {"content": [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "The doors open."}],
                               "stop_reason": "end_turn"}))
    p = ap.AnthropicProvider("sk-ant-test")
    out = p.generate(MSGS, {"model": "claude-sonnet-5-5", "max_tokens": 300, "temperature": 0.8})
    assert out == "The doors open."
    call = fake.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages"
    assert call["headers"]["x-api-key"] == "sk-ant-test"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    body = call["json"]
    assert "temperature" not in body
    assert body["system"] == "You are the Storyteller.\n\nCampaign Context: Athens by night"
    assert body["messages"] == [{"role": "user", "content": "I enter Elysium."}]


def test_anthropic_retries_without_temperature_on_400(http):
    fake = http(
        FakeResp(400, text='{"error":{"message":"temperature is not supported for this model"}}'),
        FakeResp(200, {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}),
    )
    assert ap.AnthropicProvider("k").generate(MSGS, {"model": "claude-haiku-4-5", "temperature": 0.5}) == "ok"
    assert "temperature" in fake.calls[0]["json"]
    assert "temperature" not in fake.calls[1]["json"]


def test_anthropic_refusal_and_auth_errors_raise(http):
    http(FakeResp(200, {"content": [], "stop_reason": "refusal"}))
    with pytest.raises(ap.ProviderError, match="refused"):
        ap.AnthropicProvider("k").generate(MSGS, {"model": "claude-sonnet-5-5"})
    http(FakeResp(401, text='{"error":{"type":"authentication_error"}}'))
    with pytest.raises(ap.ProviderError, match="401"):
        ap.AnthropicProvider("bad").generate(MSGS, {"model": "claude-sonnet-5-5"})
    with pytest.raises(ap.ProviderError, match="not set"):
        ap.AnthropicProvider("").generate(MSGS, {})


def test_openai_payload(http):
    fake = http(FakeResp(200, {"choices": [{"message": {"content": "Hi"}, "finish_reason": "stop"}]}))
    assert ap.OpenAIProvider("sk-o").generate(MSGS, {"model": "gpt-6.1-sol", "max_tokens": 50, "temperature": 0.7}) == "Hi"
    body = fake.calls[0]["json"]
    assert fake.calls[0]["url"] == "https://api.openai.com/v1/chat/completions"
    assert fake.calls[0]["headers"]["Authorization"] == "Bearer sk-o"
    assert body["reasoning_effort"] == "none" and body["max_completion_tokens"] == 50


def test_lm_studio_sends_reasoning_effort_and_rejects_empty(http):
    fake = http(FakeResp(200, {"choices": [{"message": {"content": ""}}]}))
    p = ap.LMStudioProvider("http://lm:1234", reasoning_effort="none")
    with pytest.raises(ap.ProviderError, match="empty"):
        p.generate(MSGS, {"model": "qwen/qwen3.5-9b"})
    assert fake.calls[0]["json"]["reasoning_effort"] == "none"
    assert fake.calls[0]["json"]["model"] == "qwen/qwen3.5-9b"


# --- roles + fallback ----------------------------------------------------------------------


@pytest.fixture
def roles_env(app_settings, monkeypatch):
    monkeypatch.setattr(ai_roles, "effective_lm_studio_model", lambda: "google/gemma-4-e2b")
    for k in ("STORYTELLER_EL_MODEL", "UTILITY_PROVIDER", "UTILITY_MODEL"):
        monkeypatch.delenv(k, raising=False)
    return app_settings


def test_default_chains(roles_env):
    assert ai_roles.fallback_chain("storyteller_en") == [
        ("lm_studio", "google/gemma-4-e2b"), ("ollama", "llama3.2:3b")]
    # Greek: Krikri, then whatever LM Studio has loaded (VRAM-safe), then Ollama
    assert ai_roles.fallback_chain("storyteller_el") == [
        ("lm_studio", "llama-krikri-8b-instruct"), ("lm_studio", "google/gemma-4-e2b"), ("ollama", "llama3.2:3b")]
    assert ai_roles.fallback_chain("utility") == [("ollama", "llama3.2:3b"), ("lm_studio", "google/gemma-4-e2b")]
    # The moderation classifier never falls back to the small Ollama model (it flags everything)
    assert ai_roles.fallback_chain("classifier") == [("lm_studio", "google/gemma-4-e2b")]


def test_cloud_role_falls_back_to_local(roles_env):
    ai_roles.set_role_config("storyteller_en", "anthropic", "claude-sonnet-5-5")
    chain = ai_roles.fallback_chain("storyteller_en")
    assert chain[0] == ("anthropic", "claude-sonnet-5-5")
    assert chain[1] == ("lm_studio", "google/gemma-4-e2b")

    class Failing:
        def generate(self, messages, params):
            raise ap.ProviderError("Anthropic HTTP 401")

    class Local:
        def generate(self, messages, params):
            return f"local reply from {params['model']}"

    res = ai_roles.generate_for_role("storyteller_en", MSGS, {"max_tokens": 10},
                                     builder=lambda n: Failing() if n == "anthropic" else Local())
    assert res["provider"] == "lm_studio" and res["text"] == "local reply from google/gemma-4-e2b"
    assert res["attempts"][0]["provider"] == "anthropic" and "401" in res["attempts"][0]["error"]


def test_all_fail_raises(roles_env):
    class Failing:
        def generate(self, m, p):
            raise ap.ProviderError("down")
    with pytest.raises(ap.ProviderError, match="all providers failed"):
        ai_roles.generate_for_role("utility", MSGS, {}, builder=lambda n: Failing())


def test_role_settings_validation(roles_env):
    with pytest.raises(ValueError):
        ai_roles.set_role_config("storyteller_en", "skynet", None)
    with pytest.raises(ValueError):
        ai_roles.set_role_config("narrator", "lm_studio", None)
    ai_roles.set_role_config("storyteller_el", None, "maistros-8b-instruct")
    assert ai_roles.get_role_config("storyteller_el") == {"provider": "lm_studio", "model": "maistros-8b-instruct"}
    ai_roles.set_role_config("storyteller_el", "", "")  # reset to defaults
    assert ai_roles.get_role_config("storyteller_el")["model"] == "llama-krikri-8b-instruct"


def test_snapshot_never_contains_plaintext_keys(roles_env, monkeypatch):
    from services import secret_store

    monkeypatch.setenv("FLASK_SECRET_KEY", "unit")
    secret_store.set_secret("anthropic_api_key", "sk-ant-SUPERSECRET-9876")
    snap = ai_roles.settings_snapshot()
    assert "SUPERSECRET" not in repr(snap)
    assert snap["cloud_keys"]["anthropic"] == {"set": True, "masked": "••••9876"}
    assert snap["cloud_keys"]["openai"] == {"set": False, "masked": ""}


def test_model_that_failed_to_load_is_skipped_for_a_while(roles_env, monkeypatch):
    monkeypatch.setattr(ai_roles, "_load_failed_until", {})
    calls = []

    class LM:
        def generate(self, messages, params):
            calls.append(params["model"])
            if params["model"] == "llama-krikri-8b-instruct":
                raise ap.ProviderError('LM Studio HTTP 400: {"error": {"message": "Failed to load model"}}')
            return "fallback text"

    for _ in range(2):
        res = ai_roles.generate_for_role("storyteller_el", MSGS, {}, builder=lambda n: LM())
        assert res["model"] == "google/gemma-4-e2b"
    assert calls == ["llama-krikri-8b-instruct", "google/gemma-4-e2b", "google/gemma-4-e2b"]
    assert "skipped" in res["attempts"][0]["error"]


def test_openai_reasoning_effort_only_for_reasoning_models(http):
    ok = {"choices": [{"message": {"content": "Hi"}, "finish_reason": "stop"}]}
    fake = http(FakeResp(200, ok), FakeResp(200, ok))
    ap.OpenAIProvider("k").generate(MSGS, {"model": "gpt-4.1-mini"})
    ap.OpenAIProvider("k").generate(MSGS, {"model": "o4-mini"})
    assert "reasoning_effort" not in fake.calls[0]["json"]
    assert fake.calls[1]["json"]["reasoning_effort"] == "none"


def test_openai_retries_once_without_reasoning_effort_on_400(http):
    fake = http(
        FakeResp(400, text='{"error":{"message":"Unsupported parameter: reasoning_effort"}}'),
        FakeResp(200, {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}),
    )
    assert ap.OpenAIProvider("k").generate(MSGS, {"model": "gpt-6.1-sol"}) == "ok"
    assert "reasoning_effort" in fake.calls[0]["json"]
    assert "reasoning_effort" not in fake.calls[1]["json"]


def test_chain_time_budget_caps_attempt_timeouts(monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(ai_roles.time, "monotonic", lambda: clock["t"])
    seen = []

    class Slow:
        def generate(self, messages, params):
            seen.append(params["timeout"])
            clock["t"] += params["timeout"]
            raise ap.ProviderError("timed out")

    chain = [("lm_studio", "a"), ("lm_studio", "b"), ("ollama", "c")]
    with pytest.raises(ap.ProviderError) as e:
        ai_roles.generate_for_role("storyteller_en", MSGS, {"timeout": 45}, chain=chain,
                                   builder=lambda n: Slow(), budget_s=55)
    assert seen == [45, 10]  # second attempt gets what is left; third is skipped
    assert "time budget" in str(e.value)


def test_storyteller_timeouts_env(monkeypatch):
    monkeypatch.delenv("STORYTELLER_ATTEMPT_TIMEOUT", raising=False)
    monkeypatch.delenv("STORYTELLER_TIME_BUDGET", raising=False)
    assert ai_roles.storyteller_timeouts() == (45.0, 55.0)
    monkeypatch.setenv("STORYTELLER_ATTEMPT_TIMEOUT", "30")
    monkeypatch.setenv("STORYTELLER_TIME_BUDGET", "bogus")
    assert ai_roles.storyteller_timeouts() == (30.0, 55.0)
