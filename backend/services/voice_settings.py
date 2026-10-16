"""
Voice settings (docs/VOICE.md), stored as JSON text: users.voice_settings (the player's own
choices) and campaigns.voice_settings (the chronicle's read-out defaults). Pure: no Flask, no DB.

Read-out rule for one kind of message: the player's override when set (true/false), else the
chronicle default. `normalize_*` is lenient (a bad stored row falls back to defaults);
`validate_*` is strict (an unknown key or a bad value is a RequestValidationError -> 400).
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, Optional

from services.request_validation import RequestValidationError

READOUT_KINDS = ("storyteller", "ic", "ooc", "dice")
OVERRIDE_KINDS = READOUT_KINDS + ("actions",)
RATE_RANGE = (0.75, 2.0)
CLIP_SECONDS_RANGE = (10, 180)
VOICE_ID_MAX = 80

USER_CHOICES = {
    "tts_source": ("off", "phone", "server"),
    "stt_source": ("server", "phone"),
    "en_accent": ("us", "gb"),
    "hear_lang": ("written", "en", "el"),
    "speak_lang": ("auto", "en", "el"),
    "write_lang": ("same", "en", "el"),
}

USER_DEFAULTS: Dict[str, Any] = {
    "tts_source": "server",
    "stt_source": "server",
    "en_accent": "us",
    "hear_lang": "written",
    "speak_lang": "auto",
    "write_lang": "same",
    "rate": 1.0,
    "volume": 1.0,
    "overrides": {k: None for k in OVERRIDE_KINDS},
}

CAMPAIGN_DEFAULTS: Dict[str, Any] = {
    "narrator_voice_en": None,  # English, US accent
    "narrator_voice_en_gb": None,
    "narrator_voice_el": None,
    "defaults": {k: True for k in READOUT_KINDS},
    "max_clip_seconds": 180,
    "allow_phone_stt": True,
}


def _load(value: Any) -> Dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except (TypeError, ValueError):
            return {}
    return value if isinstance(value, dict) else {}


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _bad(msg: str):
    raise RequestValidationError(msg)


def _apply_user(out: Dict[str, Any], data: Dict[str, Any], strict: bool) -> None:
    for key, value in data.items():
        if key in USER_CHOICES:
            if value in USER_CHOICES[key]:
                out[key] = value
            elif strict:
                _bad(f"{key} must be one of: {', '.join(USER_CHOICES[key])}")
        elif key in ("rate", "volume"):
            lo, hi = RATE_RANGE if key == "rate" else (0.0, 1.0)
            num = _num(value)
            if num is not None and lo <= num <= hi:
                out[key] = round(num, 2)
            elif strict:
                _bad(f"{key} must be a number from {lo} to {hi}")
        elif key == "overrides":
            if not isinstance(value, dict):
                if strict:
                    _bad("overrides must be an object")
                continue
            for k, v in value.items():
                if k in OVERRIDE_KINDS and (v is None or isinstance(v, bool)):
                    out["overrides"][k] = v
                elif strict:
                    _bad(f"overrides.{k}: unknown kind or not true/false/null")
        elif strict:
            _bad(f"unknown voice setting: {key}"[:120])


def normalize_user_voice_settings(value: Any) -> Dict[str, Any]:
    out = copy.deepcopy(USER_DEFAULTS)
    _apply_user(out, _load(value), strict=False)
    return out


def validate_user_voice_settings(data: Any, current: Any = None) -> Dict[str, Any]:
    """A PUT body (partial) merged onto the current stored settings."""
    if not isinstance(data, dict):
        _bad("voice settings must be an object")
    out = normalize_user_voice_settings(current)
    _apply_user(out, data, strict=True)
    return out


def _apply_campaign(out: Dict[str, Any], data: Dict[str, Any], strict: bool) -> None:
    for key, value in data.items():
        if key in ("narrator_voice_en", "narrator_voice_en_gb", "narrator_voice_el"):
            if value is None or (isinstance(value, str) and 0 < len(value.strip()) <= VOICE_ID_MAX):
                out[key] = value.strip() if isinstance(value, str) else None
            elif strict:
                _bad(f"{key} must be a voice id or null")
        elif key == "defaults":
            if not isinstance(value, dict):
                if strict:
                    _bad("defaults must be an object")
                continue
            for k, v in value.items():
                if k in READOUT_KINDS and isinstance(v, bool):
                    out["defaults"][k] = v
                elif strict:
                    _bad(f"defaults.{k}: unknown kind or not true/false")
        elif key == "max_clip_seconds":
            lo, hi = CLIP_SECONDS_RANGE
            if isinstance(value, int) and not isinstance(value, bool) and lo <= value <= hi:
                out[key] = value
            elif strict:
                _bad(f"max_clip_seconds must be a whole number from {lo} to {hi}")
        elif key == "allow_phone_stt":
            if isinstance(value, bool):
                out[key] = value
            elif strict:
                _bad("allow_phone_stt must be true or false")
        elif strict:
            _bad(f"unknown voice setting: {key}"[:120])


def normalize_campaign_voice_settings(value: Any) -> Dict[str, Any]:
    out = copy.deepcopy(CAMPAIGN_DEFAULTS)
    _apply_campaign(out, _load(value), strict=False)
    return out


def validate_campaign_voice_settings(data: Any, current: Any = None) -> Dict[str, Any]:
    if not isinstance(data, dict):
        _bad("voice settings must be an object")
    out = normalize_campaign_voice_settings(current)
    _apply_campaign(out, data, strict=True)
    return out


def effective_readout(user: Any, campaign: Any) -> Dict[str, bool]:
    """Which kinds of message are read out for this player in this chronicle."""
    u = normalize_user_voice_settings(user)
    c = normalize_campaign_voice_settings(campaign)
    out = {}
    for kind in OVERRIDE_KINDS:
        ov = u["overrides"].get(kind)
        out[kind] = ov if ov is not None else c["defaults"].get(kind, True)
    return out
