"""
Which provider + model serves each AI role, and the fallback chain.

Roles:
- storyteller_en: Storyteller replies to players writing English (default: LM Studio, the
  model the admin/env/LM Studio picks today, see lm_studio_model.get_effective_lm_studio_model_id)
- storyteller_el: Storyteller replies to players writing Greek (default: LM Studio
  `llama-krikri-8b-instruct`, the only installed model that writes clean Greek)
- utility: short internal jobs (dice/combat quick answers when no role is given)
  (default: Ollama `llama3.2:3b`, as before)
- classifier: the LLM-prompt fallback of services/classifier.py (OOC check + intent)
  (default: LM Studio's loaded model). Measured 2026-10-04 on 12 labelled messages:
  llama3.2:3b called 7 of 7 OOC messages "in character" (useless, and warnings lead to bans);
  gemma-4-e2b got 12/12. So this role never falls back to the small Ollama model.

Settings live in app_settings (`ai_role:<role>:provider`, `ai_role:<role>:model`);
cloud keys in secret_store (`anthropic_api_key`, `openai_api_key`). A cloud provider is
only used when an admin has saved its key AND picked it for a role (off by default).

Fallback: cloud fails -> LM Studio (the role's local model); LM Studio with a model that
isn't the loaded one fails -> LM Studio's loaded model; LM Studio fails -> Ollama
utility model; Ollama fails -> LM Studio.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from services.ai_providers import (
    ALL_PROVIDERS,
    CLOUD_PROVIDERS,
    DEFAULT_MODELS,
    AnthropicProvider,
    LMStudioProvider,
    OllamaProvider,
    OpenAIProvider,
    Provider,
    ProviderError,
)

logger = logging.getLogger(__name__)

ROLES = ("storyteller_en", "storyteller_el", "utility", "classifier")
CLOUD_KEY_NAMES = {"anthropic": "anthropic_api_key", "openai": "openai_api_key"}


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def role_defaults() -> Dict[str, Dict[str, str]]:
    return {
        "storyteller_en": {"provider": "lm_studio", "model": ""},  # "" = effective LM Studio model
        "storyteller_el": {"provider": "lm_studio", "model": _env("STORYTELLER_EL_MODEL", "llama-krikri-8b-instruct")},
        "utility": {"provider": _env("UTILITY_PROVIDER", "ollama"), "model": _env("UTILITY_MODEL", "llama3.2:3b")},
        "classifier": {"provider": "lm_studio", "model": ""},  # "" = the loaded LM Studio model
    }


def _lm_studio_config() -> Dict[str, Any]:
    return {
        "LM_STUDIO_URL": _env("LM_STUDIO_URL", "http://localhost:1234"),
        "LM_STUDIO_API_KEY": _env("LM_STUDIO_API_KEY"),
        "LM_STUDIO_MODEL": _env("LM_STUDIO_MODEL"),
    }


def effective_lm_studio_model() -> str:
    from services.lm_studio_model import get_effective_lm_studio_model_id

    return get_effective_lm_studio_model_id(_lm_studio_config())


def get_role_config(role: str) -> Dict[str, str]:
    """{'provider', 'model'} as configured (admin setting, else default). model may be ''."""
    from services.ai_runtime_settings import get_app_setting

    if role not in ROLES:
        raise ValueError(f"unknown AI role {role!r}")
    d = role_defaults()[role]
    provider = (get_app_setting(f"ai_role:{role}:provider") or d["provider"]).strip()
    if provider not in ALL_PROVIDERS:
        provider = d["provider"]
    model = get_app_setting(f"ai_role:{role}:model")
    model = d["model"] if model is None else model.strip()
    return {"provider": provider, "model": model}


def set_role_config(role: str, provider: Optional[str], model: Optional[str]) -> None:
    """None/'' resets that field to the default."""
    from services.ai_runtime_settings import set_app_setting

    if role not in ROLES:
        raise ValueError(f"unknown AI role {role!r}")
    if provider is not None:
        p = provider.strip()
        if p and p not in ALL_PROVIDERS:
            raise ValueError(f"unknown provider {p!r}")
        set_app_setting(f"ai_role:{role}:provider", p or None)
    if model is not None:
        set_app_setting(f"ai_role:{role}:model", model.strip() or None)


def build_provider(name: str) -> Provider:
    if name == "lm_studio":
        return LMStudioProvider(
            _env("LM_STUDIO_URL", "http://localhost:1234"),
            _env("LM_STUDIO_API_KEY"),
            _env("LM_STUDIO_REASONING_EFFORT"),
            int(_env("LM_STUDIO_TIMEOUT", "120") or 120),
        )
    if name == "ollama":
        # Small local model; give it more than the old 30 s when it has to load first.
        return OllamaProvider(_env("OLLAMA_URL", "http://localhost:11434"), int(_env("OLLAMA_TIMEOUT", "60") or 60))
    if name in CLOUD_PROVIDERS:
        from services.secret_store import get_secret

        key = get_secret(CLOUD_KEY_NAMES[name]) or ""
        if name == "anthropic":
            return AnthropicProvider(key)
        return OpenAIProvider(key, reasoning_effort=_env("OPENAI_REASONING_EFFORT", "none"))
    raise ValueError(f"unknown provider {name!r}")


def _model_for(provider: str, model: str, role: str) -> str:
    """Concrete model id ('' means the provider's default for that role)."""
    if model:
        return model
    if provider == "lm_studio":
        if role == "storyteller_el":
            return role_defaults()["storyteller_el"]["model"]
        return effective_lm_studio_model()
    return DEFAULT_MODELS.get(provider, "")


def fallback_chain(role: str, cfg: Optional[Dict[str, str]] = None) -> List[Tuple[str, str]]:
    """Ordered (provider, model) attempts for a role, de-duplicated."""
    cfg = cfg or get_role_config(role)
    provider = cfg["provider"]
    chain: List[Tuple[str, str]] = [(provider, _model_for(provider, cfg["model"], role))]
    local_default = role_defaults()[role]
    if provider in CLOUD_PROVIDERS:
        lp = local_default["provider"]
        chain.append((lp, _model_for(lp, local_default["model"], role)))
    loaded = None
    for p, m in list(chain):
        if p == "lm_studio":
            loaded = loaded or effective_lm_studio_model()
            if m != loaded:
                chain.append(("lm_studio", loaded))
            break
    if not any(p == "ollama" for p, _ in chain) and role != "classifier":
        util = role_defaults()["utility"]
        chain.append(("ollama", util["model"] if util["provider"] == "ollama" else DEFAULT_MODELS["ollama"]))
    if not any(p == "lm_studio" for p, _ in chain):
        chain.append(("lm_studio", effective_lm_studio_model()))
    seen, out = set(), []
    for item in chain:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# LM Studio refuses to JIT-load a model that doesn't fit in VRAM ("Failed to load model"), which
# takes ~7 s each time. After such a failure that (provider, model) is skipped for a while so
# the next messages go straight to the fallback (the loaded model).
LOAD_FAILURE_COOLDOWN_SEC = 300

# Storyteller replies go through nginx, which gives /api requests 60 s (proxy_read_timeout
# default). Each LM Studio/Ollama attempt gets at most STORYTELLER_ATTEMPT_TIMEOUT seconds
# and the whole fallback chain STORYTELLER_TIME_BUDGET, so a failure still answers in time.
MIN_ATTEMPT_SEC = 3.0
# Context overflow: retry the same model with the prompt cut to SHRINK_FACTOR, at most this often.
MAX_SHRINK_RETRIES = 2
SHRINK_FACTOR = 0.6


_ctx_cache: Dict[str, Any] = {"at": 0.0, "value": None}


def _loaded_lm_studio_context() -> Optional[int]:
    """loaded_context_length of the model LM Studio has loaded (native /api/v0/models), cached 60 s."""
    now = time.monotonic()
    if now - _ctx_cache["at"] < 60:
        return _ctx_cache["value"]
    value = None
    try:
        import requests

        base = _env("LM_STUDIO_URL", "http://localhost:1234").rstrip("/")
        key = _env("LM_STUDIO_API_KEY")
        r = requests.get(f"{base}/api/v0/models", timeout=3,
                         headers={"Authorization": f"Bearer {key}"} if key else {})
        loaded = effective_lm_studio_model()
        for m in (r.json().get("data") or []) if r.status_code == 200 else []:
            if m.get("id") == loaded and m.get("loaded_context_length"):
                value = int(m["loaded_context_length"])
    except Exception as e:  # noqa: BLE001 - a hint only
        logger.debug("LM Studio context length lookup failed: %s", e)
    _ctx_cache.update(at=now, value=value)
    return value


def storyteller_context_tokens() -> int:
    """
    Context window to budget Storyteller prompts for: STORYTELLER_CONTEXT_TOKENS (default 8192),
    lowered to the loaded LM Studio model's context when that is smaller. A JIT-loaded or cloud
    model may differ; a context overflow is then trimmed and retried (generate_for_role).
    """
    try:
        cap = int(_env("STORYTELLER_CONTEXT_TOKENS", "8192") or 8192)
    except ValueError:
        cap = 8192
    loaded = _loaded_lm_studio_context()
    return min(cap, loaded) if loaded else cap


def storyteller_timeouts() -> Tuple[float, float]:
    """(per-attempt timeout, whole-chain budget) in seconds for storyteller roles."""
    def num(name: str, default: float) -> float:
        try:
            v = float(_env(name) or default)
            return v if v > 0 else default
        except ValueError:
            return default
    return num("STORYTELLER_ATTEMPT_TIMEOUT", 45.0), num("STORYTELLER_TIME_BUDGET", 55.0)
_load_failed_until: Dict[Tuple[str, str], float] = {}


def _is_load_failure(err: Exception) -> bool:
    return "failed to load model" in str(err).lower()


def generate_for_role(
    role: str,
    messages: List[Dict[str, str]],
    params: Dict[str, Any],
    *,
    chain: Optional[List[Tuple[str, str]]] = None,
    builder=build_provider,
    budget_s: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Try each (provider, model) in the role's chain until one returns text.

    budget_s: total seconds for the whole chain; each attempt's timeout is capped to what is
    left, and attempts are skipped once less than MIN_ATTEMPT_SEC remain.

    Returns {'text', 'provider', 'model', 'role', 'attempts': [{'provider','model','error'}], 'ms'}.
    Raises ProviderError when every attempt failed.
    """
    from services.storyteller_prompt import is_context_overflow, shrink_messages

    chain = chain or fallback_chain(role)
    attempts: List[Dict[str, str]] = []
    deadline = time.monotonic() + budget_s if budget_s else None
    overflowed = False
    for provider_name, model in chain:
        if overflowed and provider_name == "ollama":
            # Ollama's default context is smaller than LM Studio's: it would silently drop
            # the start of a prompt that was already too long.
            attempts.append({"provider": provider_name, "model": model,
                             "error": "skipped: prompt too long for its context"})
            continue
        until = _load_failed_until.get((provider_name, model), 0)
        if until > time.monotonic() and len(chain) > 1:
            attempts.append({"provider": provider_name, "model": model,
                             "error": f"skipped: failed to load less than {LOAD_FAILURE_COOLDOWN_SEC}s ago"})
            continue
        msgs = messages
        for shrink_round in range(MAX_SHRINK_RETRIES + 1):
            attempt_params = dict(params)
            if deadline is not None:
                left = deadline - time.monotonic()
                if left < MIN_ATTEMPT_SEC:
                    attempts.append({"provider": provider_name, "model": model,
                                     "error": f"skipped: time budget of {budget_s:g}s used up"})
                    break
                attempt_params["timeout"] = min(float(params.get("timeout") or left), left)
            t0 = time.monotonic()
            try:
                provider = builder(provider_name)
                text = provider.generate(msgs, {**attempt_params, "model": model})
                ms = int((time.monotonic() - t0) * 1000)
                if attempts:
                    logger.warning("AI role %s answered by fallback %s/%s after: %s", role, provider_name, model, attempts)
                return {"text": text, "provider": provider_name, "model": model, "role": role,
                        "attempts": attempts, "ms": ms, "trimmed": shrink_round}
            except (ProviderError, ValueError) as e:
                logger.warning("AI role %s: %s/%s failed: %s", role, provider_name, model, e)
                if _is_load_failure(e):
                    _load_failed_until[(provider_name, model)] = time.monotonic() + LOAD_FAILURE_COOLDOWN_SEC
                attempts.append({"provider": provider_name, "model": model, "error": str(e)[:300]})
                if not is_context_overflow(e):
                    break
                overflowed = True
                if shrink_round < MAX_SHRINK_RETRIES:
                    msgs = shrink_messages(msgs, SHRINK_FACTOR)
                    logger.warning("AI role %s: prompt too long for %s/%s, trimmed and retrying", role, provider_name, model)
    raise ProviderError(f"all providers failed for role {role}: {attempts}")


def test_provider(name: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Admin 'test connection': a tiny real request with the stored key; never raises."""
    if name not in ALL_PROVIDERS:
        return {"ok": False, "detail": f"unknown provider {name!r}"}
    try:
        p = build_provider(name)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)[:300]}
    t0 = time.monotonic()
    res = p.test(model or None)
    res["ms"] = int((time.monotonic() - t0) * 1000)
    res["provider"] = name
    return res


def settings_snapshot() -> Dict[str, Any]:
    """Admin view: roles + defaults + cloud key status (masked). No plaintext keys."""
    from services.secret_store import secret_status

    roles = {}
    for r in ROLES:
        cfg = get_role_config(r)
        try:
            chain = fallback_chain(r, cfg)
        except Exception as e:  # noqa: BLE001
            chain, cfg["error"] = [], str(e)
        roles[r] = {**cfg, "default": role_defaults()[r], "chain": [{"provider": p, "model": m} for p, m in chain]}
    return {
        "roles": roles,
        "providers": list(ALL_PROVIDERS),
        "cloud_keys": {p: secret_status(k) for p, k in CLOUD_KEY_NAMES.items()},
        "default_models": DEFAULT_MODELS,
    }
