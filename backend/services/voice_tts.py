"""
Server voices (docs/VOICE.md): what a chat row says and in which voice. Pure: no Flask, no DB.

The same read-out kinds as the app (frontend/src/features/voice/readout.js):
  storyteller  AI narration, or the chronicle's Storyteller speaking as staff -> narrator voice
  dice         a roll line, said as one sentence with the roller's name     -> narrator voice
  actions      /me emotes, Rouse checks                                     -> narrator voice
  ic           a character speaking: the character's (or NPC's) gender, unset = neutral
  ooc          a player or staff out of character                          -> neutral voice
The speech service turns (lang, accent, gender | role) into a voice id (speech/app/catalog.py);
a chronicle's narrator choice is sent as an explicit voice.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from services.voice_settings import normalize_campaign_voice_settings, normalize_user_voice_settings

SPOKEN_MAX = 600
GENDERS = ("female", "male", "neutral")
NARRATED = ("storyteller", "dice", "actions")

PREVIEW_TEXT = {
    "en": "The night is young, and the city is hungry.",
    "el": "Η νύχτα είναι νέα, και η πόλη πεινάει.",
}

_MARKER = ("dice_animation:", "dice_animation_hidden:")
_DICE = ("dice_roll:", "dice_roll_hidden:")


def readout_kind(row: Dict[str, Any]) -> Optional[str]:
    """The read-out kind of a message row, or None when it is never spoken."""
    k = str(row.get("ai_message_kind") or "").lower()
    if k.startswith(_MARKER):
        return None
    if k.startswith(_DICE):
        return "dice"
    if row.get("role") == "assistant":
        return None if k == "slash_assistant" else "storyteller"
    mt = str(row.get("message_type") or "").lower()
    if mt == "system":
        return None
    if mt == "action":
        return "actions"
    sm = row.get("speaker_mode") or ("character" if row.get("character_id") else "player")
    if sm == "staff":
        return "storyteller" if row.get("staff_kind") == "storyteller" else "ooc"
    return "ic" if sm == "character" else "ooc"


def plain_text(text: Any) -> str:
    """Markdown and emoji off, whitespace collapsed (the speech service cleans again per language)."""
    s = str(text or "")
    s = re.sub(r"```[\s\S]*?```", " ", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[*_`~>#|]+", "", s)
    s = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]️?", "", s)
    return re.sub(r"\s+", " ", s).strip()


def speaker_name(row: Dict[str, Any]) -> str:
    if row.get("role") == "assistant":
        return "Storyteller"
    if (row.get("speaker_mode") or "") == "character" or (not row.get("speaker_mode") and row.get("character_id")):
        if str(row.get("character_name") or "").strip():
            return str(row["character_name"]).strip()
    return str(row.get("username") or "").strip() or "Player"


def spoken_text(row: Dict[str, Any], kind: str) -> str:
    """The words: dice as one sentence with the roller's name; IC / OOC lines start with the speaker."""
    text = plain_text(row.get("content"))
    if kind == "dice":
        first = plain_text(str(row.get("content") or "").split("\n")[0])
        who = speaker_name(row)
        line = first if first.lower().startswith(who.lower()) else f"{who}: {first}"
        return line[:200]
    if kind in ("ic", "ooc"):
        return f"{speaker_name(row)}: {text}"[:SPOKEN_MAX]
    return text[:SPOKEN_MAX]


def guess_lang(text: Any) -> str:
    """'el' when the text is mostly Greek letters, else 'en' (same rule as the app)."""
    s = str(text or "")
    greek = len(re.findall(r"[Ͱ-Ͽἀ-῿]", s))
    latin = len(re.findall(r"[A-Za-z]", s))
    return "el" if greek > latin else "en"


def narrator_voice(campaign_settings: Any, lang: str, accent: str) -> Optional[str]:
    c = normalize_campaign_voice_settings(campaign_settings)
    if lang == "el":
        return c.get("narrator_voice_el")
    return c.get("narrator_voice_en_gb") if accent == "gb" else c.get("narrator_voice_en")


VOICE_ID = re.compile(r"^[A-Za-z0-9_.-]{2,80}$")


def voice_lang(voice_id: Any) -> Optional[str]:
    """'en' or 'el' from a catalog id ("en_GB-alan-medium", "el-kostas"), else None."""
    s = str(voice_id or "")
    return s[:2] if s[:2] in ("en", "el") and VOICE_ID.match(s) else None


def voice_override_error(value: Any, catalog_ids: Any) -> Optional[str]:
    """Why a character's voice pick is refused, or None. None/'' clears it. catalog_ids is the set
    of voice ids the speech service lists (None when it cannot be asked)."""
    if value in (None, ""):
        return None
    if not isinstance(value, str) or voice_lang(value) is None:
        return "voice_override must be a voice id"
    if catalog_ids is None:
        return "speech_unavailable"
    if value not in catalog_ids:
        return "unknown voice"
    return None


def tts_request(row: Dict[str, Any], gender: Any, user_settings: Any, campaign_settings: Any,
                voice_override: Any = None) -> Optional[Dict[str, Any]]:
    """The body for the speech service's POST /tts, or None when the row is never spoken."""
    kind = readout_kind(row)
    if not kind:
        return None
    text = spoken_text(row, kind)
    if not text:
        return None
    u = normalize_user_voice_settings(user_settings)
    lang = guess_lang(row.get("content"))
    accent = u["en_accent"] if lang == "en" else "gr"
    body: Dict[str, Any] = {"text": text, "lang": lang, "accent": accent}
    if kind in NARRATED:
        body["role"] = "narrator"
        chosen = narrator_voice(campaign_settings, lang, accent)
        if chosen:
            body["voice"] = chosen
    elif kind == "ic":
        body["gender"] = gender if gender in GENDERS else "neutral"
        if voice_lang(voice_override) == lang:  # the owner's pick, when it speaks this language
            body["voice"] = voice_override
    else:
        body["gender"] = "neutral"
    return body
