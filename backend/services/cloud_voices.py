"""
Cloud voices (docs/VOICE.md, 0.23): Google Gemini TTS, off unless the site admin turns it on and
a chronicle opts in. The speech service makes the call and holds the keys (GEMINI_API_KEY for the
free tier, GEMINI_API_KEY_PAID for the paid tier); this side only decides which lines ask for it.
Settings live in app_settings: cloud_voices_tier (off | free | paid) and cloud_voices_model.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from services.request_validation import RequestValidationError
from services.voice_settings import normalize_campaign_voice_settings

TIERS = ("off", "free", "paid")
MODELS = ("gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview",
          "gemini-2.5-flash-preview-tts", "gemini-2.5-pro-preview-tts")
DEFAULT_MODEL = MODELS[0]
SETTING_TIER = "cloud_voices_tier"
SETTING_MODEL = "cloud_voices_model"
PREFIX = "gemini-"


def read_config(get: Callable[[str], Optional[str]]) -> Dict[str, str]:
    """{tier, model} from a getter of app settings; anything unknown reads as off / the default."""
    tier = get(SETTING_TIER) or "off"
    model = get(SETTING_MODEL) or DEFAULT_MODEL
    return {"tier": tier if tier in TIERS else "off", "model": model if model in MODELS else DEFAULT_MODEL}


def validate_config(data: Any) -> Dict[str, str]:
    """A PUT body -> {tier, model}; strict."""
    if not isinstance(data, dict):
        raise RequestValidationError("cloud voice settings must be an object")
    unknown = set(data) - {"tier", "model"}
    if unknown:
        raise RequestValidationError(f"unknown setting: {sorted(unknown)[0]}"[:120])
    tier, model = data.get("tier"), data.get("model", DEFAULT_MODEL)
    if tier not in TIERS:
        raise RequestValidationError("tier must be one of: off, free, paid")
    if model not in MODELS:
        raise RequestValidationError("model must be one of the listed Gemini TTS models")
    return {"tier": tier, "model": model}


def is_cloud_voice(voice_id: Any) -> bool:
    return isinstance(voice_id, str) and voice_id.startswith(PREFIX)


def active_for(config: Dict[str, str], campaign_settings: Any) -> bool:
    return config.get("tier") in ("free", "paid") and bool(
        normalize_campaign_voice_settings(campaign_settings).get("cloud_voices"))


def apply(body: Dict[str, Any], config: Dict[str, str], campaign_settings: Any) -> Dict[str, Any]:
    """The POST /tts body for one line: asks for Gemini when the site and the chronicle allow it;
    otherwise a Gemini narrator pick is dropped so the local default speaks."""
    out = dict(body)
    if active_for(config, campaign_settings):
        out["cloud"] = {"tier": config["tier"], "model": config["model"]}
    elif is_cloud_voice(out.get("voice")):
        out.pop("voice")
    return out
