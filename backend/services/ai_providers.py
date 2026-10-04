"""
Text-generation providers behind one interface: generate(messages, params) -> text.

messages: OpenAI-style [{"role": "system"|"user"|"assistant", "content": str}, ...]
params:   {"model": str, "max_tokens": int, "temperature": float, "timeout": int}

Providers raise ProviderError on any failure (HTTP error, timeout, empty answer, refusal),
so the caller (services/ai_roles.py) can fall back to the next provider in the chain.

- lm_studio: LM Studio's OpenAI-compatible /v1/chat/completions (local, default).
  Sends reasoning_effort when set (Qwen3.5 needs "none" or it spends the budget thinking).
- ollama: /api/chat (local).
- anthropic: Messages API (cloud, admin key). Some current models (e.g. claude-sonnet-5-5)
  reject a non-default temperature with 400; we leave it out for those, and on a 400 that
  names temperature we retry once without it.
- openai: Chat Completions (cloud, admin key). Sends max_completion_tokens, and
  reasoning_effort (OPENAI_REASONING_EFFORT, default "none") only to reasoning models
  (o-series, gpt-5 and later); a 400 that names reasoning is retried once without it.
  Same temperature retry.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

LOCAL_PROVIDERS = ("lm_studio", "ollama")
CLOUD_PROVIDERS = ("anthropic", "openai")
ALL_PROVIDERS = LOCAL_PROVIDERS + CLOUD_PROVIDERS

ANTHROPIC_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1"

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-6.1-sol",
    "ollama": "llama3.2:3b",
}

# Models known to reject a non-default temperature (400). Others get one retry without it.
_NO_TEMPERATURE = re.compile(r"^claude-(sonnet|opus|fable)-5", re.IGNORECASE)


class ProviderError(Exception):
    """A provider couldn't produce text; message is safe to log (never contains keys)."""


def _post(url: str, payload: dict, headers: dict, timeout: float) -> requests.Response:
    try:
        return requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        raise ProviderError(f"{type(e).__name__}: {e}") from e


def _short(resp: requests.Response, limit: int = 300) -> str:
    try:
        body = resp.text or ""
    except Exception:  # noqa: BLE001
        body = ""
    return f"HTTP {resp.status_code}: {body[:limit]}"


def _mentions_temperature(resp: requests.Response) -> bool:
    return resp.status_code == 400 and "temperature" in (resp.text or "").lower()


def _mentions_reasoning(resp: requests.Response) -> bool:
    return resp.status_code == 400 and "reasoning" in (resp.text or "").lower()


# OpenAI models that accept reasoning_effort: o1/o3/o4..., gpt-5 and later.
_OPENAI_REASONING_MODEL = re.compile(r"^(o\d|gpt-([5-9]|\d{2,}))", re.IGNORECASE)


def openai_supports_reasoning(model: str) -> bool:
    return bool(_OPENAI_REASONING_MODEL.match((model or "").strip()))


class Provider:
    name = "base"
    is_cloud = False

    def generate(self, messages: List[Dict[str, str]], params: Dict[str, Any]) -> str:
        raise NotImplementedError

    def test(self, model: Optional[str] = None) -> Dict[str, Any]:
        """Tiny real call; {'ok': bool, 'detail': str, 'model': str}."""
        model = model or self.default_model()
        try:
            text = self.generate(
                [{"role": "user", "content": "Reply with the single word: ready"}],
                {"model": model, "max_tokens": 16, "temperature": 0.0, "timeout": 30},
            )
            return {"ok": True, "detail": text.strip()[:80], "model": model}
        except ProviderError as e:
            return {"ok": False, "detail": str(e)[:300], "model": model}

    def default_model(self) -> str:
        return DEFAULT_MODELS.get(self.name, "")


class LMStudioProvider(Provider):
    name = "lm_studio"

    def __init__(self, base_url: str, api_key: str = "", reasoning_effort: str = "", timeout: int = 120):
        self.base_url = (base_url or "http://localhost:1234").rstrip("/")
        self.api_key = (api_key or "").strip()
        self.reasoning_effort = (reasoning_effort or "").strip()
        self.timeout = timeout

    def default_model(self) -> str:
        from services.lm_studio_model import resolve_lm_studio_model_id

        return resolve_lm_studio_model_id(self.base_url, "auto", self.api_key)

    def generate(self, messages, params):
        payload = {
            "model": params.get("model") or self.default_model(),
            "messages": messages,
            "max_tokens": int(params.get("max_tokens") or 1024),
            "temperature": params.get("temperature", 0.7),
            "stream": False,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        r = _post(f"{self.base_url}/v1/chat/completions", payload, headers, params.get("timeout") or self.timeout)
        if r.status_code != 200:
            raise ProviderError(f"LM Studio {_short(r)}")
        try:
            text = r.json()["choices"][0]["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"LM Studio: unexpected response ({e})") from e
        if not text.strip():
            raise ProviderError("LM Studio returned empty content (reasoning model without reasoning_effort=none?)")
        return text


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.timeout = timeout

    def generate(self, messages, params):
        payload = {
            "model": params.get("model") or self.default_model(),
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": params.get("temperature", 0.7),
                "num_predict": int(params.get("max_tokens") or 512),
            },
        }
        r = _post(f"{self.base_url}/api/chat", payload, {"Content-Type": "application/json"},
                  params.get("timeout") or self.timeout)
        if r.status_code != 200:
            raise ProviderError(f"Ollama {_short(r)}")
        try:
            text = (r.json().get("message") or {}).get("content") or ""
        except ValueError as e:
            raise ProviderError(f"Ollama: unexpected response ({e})") from e
        if not text.strip():
            raise ProviderError("Ollama returned empty content")
        return text


class AnthropicProvider(Provider):
    name = "anthropic"
    is_cloud = True

    def __init__(self, api_key: str, base_url: str = ANTHROPIC_URL, timeout: int = 120):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def split_messages(messages: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
        """System messages -> one `system` string; the rest must alternate user/assistant."""
        system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system" and m.get("content"))
        convo: List[Dict[str, str]] = []
        for m in messages:
            role = m.get("role")
            if role not in ("user", "assistant") or not m.get("content"):
                continue
            if convo and convo[-1]["role"] == role:  # merge consecutive same-role turns
                convo[-1] = {"role": role, "content": convo[-1]["content"] + "\n\n" + m["content"]}
            else:
                convo.append({"role": role, "content": m["content"]})
        if not convo or convo[0]["role"] != "user":
            convo.insert(0, {"role": "user", "content": "(continue)"})
        if convo[-1]["role"] != "user":  # no assistant prefill on current models
            convo.append({"role": "user", "content": "(continue)"})
        return system, convo

    def generate(self, messages, params):
        if not self.api_key:
            raise ProviderError("Anthropic API key is not set")
        model = params.get("model") or self.default_model()
        system, convo = self.split_messages(messages)
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": int(params.get("max_tokens") or 1024),
            "messages": convo,
        }
        if system:
            payload["system"] = system
        if params.get("temperature") is not None and not _NO_TEMPERATURE.match(model):
            payload["temperature"] = params["temperature"]
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        url = f"{self.base_url}/v1/messages"
        timeout = params.get("timeout") or self.timeout
        r = _post(url, payload, headers, timeout)
        if _mentions_temperature(r) and "temperature" in payload:
            payload.pop("temperature")
            r = _post(url, payload, headers, timeout)
        if r.status_code != 200:
            raise ProviderError(f"Anthropic {_short(r)}")
        try:
            body = r.json()
        except ValueError as e:
            raise ProviderError(f"Anthropic: unexpected response ({e})") from e
        if body.get("stop_reason") == "refusal":
            raise ProviderError("Anthropic refused this request (stop_reason=refusal)")
        text = "".join(b.get("text", "") for b in body.get("content") or [] if b.get("type") == "text")
        if not text.strip():
            raise ProviderError(f"Anthropic returned no text (stop_reason={body.get('stop_reason')})")
        return text


class OpenAIProvider(Provider):
    name = "openai"
    is_cloud = True

    def __init__(self, api_key: str, base_url: str = OPENAI_URL, reasoning_effort: str = "none", timeout: int = 120):
        self.api_key = (api_key or "").strip()
        self.base_url = base_url.rstrip("/")
        self.reasoning_effort = (reasoning_effort or "").strip()
        self.timeout = timeout

    def generate(self, messages, params):
        if not self.api_key:
            raise ProviderError("OpenAI API key is not set")
        payload: Dict[str, Any] = {
            "model": params.get("model") or self.default_model(),
            "messages": [m for m in messages if m.get("content")],
            "max_completion_tokens": int(params.get("max_tokens") or 1024),
        }
        if self.reasoning_effort and openai_supports_reasoning(payload["model"]):
            payload["reasoning_effort"] = self.reasoning_effort
        if params.get("temperature") is not None:
            payload["temperature"] = params["temperature"]
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        url = f"{self.base_url}/chat/completions"
        timeout = params.get("timeout") or self.timeout
        r = _post(url, payload, headers, timeout)
        if _mentions_reasoning(r) and "reasoning_effort" in payload:
            payload.pop("reasoning_effort")
            r = _post(url, payload, headers, timeout)
        if _mentions_temperature(r) and "temperature" in payload:
            payload.pop("temperature")
            r = _post(url, payload, headers, timeout)
        if r.status_code != 200:
            raise ProviderError(f"OpenAI {_short(r)}")
        try:
            choice = r.json()["choices"][0]
            text = (choice.get("message") or {}).get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"OpenAI: unexpected response ({e})") from e
        if not text.strip():
            raise ProviderError(f"OpenAI returned no text (finish_reason={choice.get('finish_reason')})")
        return text
