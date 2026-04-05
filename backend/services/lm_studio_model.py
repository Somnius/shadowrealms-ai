"""
Resolve which model id to send to LM Studio's OpenAI-compatible API.

If LM_STUDIO_MODEL is unset, empty, or a sentinel like "auto", we prefer the LLM that
LM Studio reports as *loaded* via native GET /api/v1/models (loaded_instances), so we do
not pass an arbitrary first entry from GET /v1/models (which can differ and may cause
LM Studio to load/switch models). Falls back to GET /v1/models data[0].id if needed.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

_CACHE_ID: Optional[str] = None
_CACHE_TS: float = 0.0
_CACHE_TTL_SEC = 15.0

# Stable router dict key (actual OpenAI model id comes from get_effective_lm_studio_model_id per request).
LM_STUDIO_ROUTE_KEY = "__lm_studio__"

# Env values meaning "do not pin a name — ask LM Studio what is available"
_AUTO_SENTINELS = frozenset(
    {
        "",
        "auto",
        "loaded",
        "default",
        "lmstudio",
        "lm_studio",
        "use_loaded",
        "first",
    }
)


def _normalize_base(base_url: str) -> str:
    return (base_url or "http://localhost:1234").rstrip("/")


def _auth_headers(api_key: Optional[str]) -> Dict[str, str]:
    if not (api_key or "").strip():
        return {}
    return {"Authorization": f"Bearer {api_key.strip()}"}


def _collect_loaded_llm_ids_native(base: str, api_key: Optional[str]) -> list[str]:
    """
    LM Studio REST: GET /api/v1/models — collect ids for LLMs with loaded_instances.
    Order follows the API document order (not guaranteed to match UI "active" model).
    """
    url = f"{base}/api/v1/models"
    try:
        r = requests.get(url, timeout=12, headers=_auth_headers(api_key))
        r.raise_for_status()
        body = r.json()
        models = body.get("models") or []
        out: list[str] = []
        seen: set[str] = set()
        for m in models:
            if m.get("type") != "llm":
                continue
            for inst in m.get("loaded_instances") or []:
                mid = inst.get("id") or m.get("key")
                if not mid:
                    continue
                s = str(mid)
                if s not in seen:
                    seen.add(s)
                    out.append(s)
        return out
    except Exception as e:
        logger.warning(
            "GET /api/v1/models failed (cannot prefer loaded model; will fall back to /v1/models): %s",
            e,
        )
        return []


def _pick_loaded_model_for_openai_compat(base: str, api_key: Optional[str], loaded_ids: list[str]) -> Optional[str]:
    """
    If several models report loaded_instances, prefer the id that appears first in
    GET /v1/models — that ordering usually matches LM Studio's server / dropdown.
    """
    if not loaded_ids:
        return None
    if len(loaded_ids) == 1:
        return loaded_ids[0]
    loaded_set = set(loaded_ids)
    try:
        r = requests.get(
            f"{base}/v1/models", timeout=12, headers=_auth_headers(api_key)
        )
        r.raise_for_status()
        for entry in r.json().get("data") or []:
            oid = entry.get("id")
            if oid and oid in loaded_set:
                return str(oid)
    except Exception as e:
        logger.warning("Could not cross-reference loaded models with GET /v1/models: %s", e)
    return loaded_ids[0]


def resolve_lm_studio_model_id(
    base_url: str, configured: Optional[str], api_key: Optional[str] = None
) -> str:
    """
    Return the model id to pass in chat/completions payloads.

    If `configured` is non-empty and not an auto sentinel, return it as-is.
    Otherwise GET {base}/v1/models and use data[0].id (refreshed every CACHE_TTL_SEC).
    """
    global _CACHE_ID, _CACHE_TS

    raw = (configured if configured is not None else os.environ.get("LM_STUDIO_MODEL", ""))
    raw = (raw or "").strip()
    if raw and raw.lower() not in _AUTO_SENTINELS:
        logger.info(
            "LM_STUDIO_MODEL is pinned to %r — remove it or set to 'auto' to use the model "
            "LM Studio reports as loaded via /api/v1/models.",
            raw,
        )
        return raw

    base = _normalize_base(base_url)
    now = time.time()
    if _CACHE_ID and (now - _CACHE_TS) < _CACHE_TTL_SEC:
        return _CACHE_ID

    # 1) Native API: which LLM(s) have loaded_instances, then match OpenAI /v1/models order
    loaded_ids = _collect_loaded_llm_ids_native(base, api_key)
    if loaded_ids:
        chosen = _pick_loaded_model_for_openai_compat(base, api_key, loaded_ids)
        if chosen:
            _CACHE_ID = chosen
            _CACHE_TS = now
            logger.info(
                "LM_STUDIO_MODEL is auto — using loaded LLM id (native + /v1/models order): %s "
                "(candidates: %s)",
                _CACHE_ID,
                loaded_ids,
            )
            return _CACHE_ID

    # 2) OpenAI-compat list (may list downloads; order is not guaranteed to be "loaded")
    url = f"{base}/v1/models"
    try:
        r = requests.get(url, timeout=12, headers=_auth_headers(api_key))
        r.raise_for_status()
        data = r.json().get("data") or []
        if not data:
            raise ValueError("LM Studio returned no models (load a model in LM Studio).")
        mid = data[0].get("id")
        if not mid:
            raise ValueError("LM Studio /v1/models entry missing id")
        _CACHE_ID = str(mid)
        _CACHE_TS = now
        logger.info(
            "LM_STUDIO_MODEL is auto — no loaded LLM in /api/v1/models; "
            "using first id from GET /v1/models: %s",
            _CACHE_ID,
        )
        return _CACHE_ID
    except Exception as e:
        logger.warning(
            "Could not resolve LM Studio model from /v1/models (%s). "
            "Set LM_STUDIO_MODEL to the exact id from LM Studio.",
            e,
        )
        # Last resort so router keys exist; prefer fixing LM Studio or set LM_STUDIO_MODEL explicitly.
        fallback = (os.environ.get("LM_STUDIO_MODEL_FALLBACK") or "").strip()
        if fallback:
            return fallback
        return "gemma-4-e2b-it"


def invalidate_lm_studio_model_cache() -> None:
    """Clear cached auto-resolved model id (e.g. after switching models in LM Studio)."""
    global _CACHE_ID, _CACHE_TS
    _CACHE_ID = None
    _CACHE_TS = 0.0


def get_effective_lm_studio_model_id(config: Dict[str, Any]) -> str:
    """
    Model id for each inference request: admin DB override (if set) else env + auto resolution.
    """
    from services.ai_runtime_settings import get_app_setting

    override = (get_app_setting("lm_studio_model") or "").strip()
    base = _normalize_base(config.get("LM_STUDIO_URL", "http://localhost:1234"))
    api_key = config.get("LM_STUDIO_API_KEY")
    env_model = config.get("LM_STUDIO_MODEL")
    if override:
        if override.lower() in _AUTO_SENTINELS:
            return resolve_lm_studio_model_id(base, "auto", api_key)
        return override
    return resolve_lm_studio_model_id(base, env_model, api_key)
