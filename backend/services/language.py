"""
Player language for Storyteller replies: 'en' or 'el'.

detect_language(text): share of Greek letters (U+0370-03FF, U+1F00-1FFF) among all letters.
>= 0.3 -> 'el'. Latin-script text is 'en' only when it is clearly English (common English
words outnumber common Greeklish ones); otherwise (Greeklish such as "Rixnw 5 zaria gia to
Dex", or too few words to tell) -> None. Too few letters (e.g. "ok", "+1", "5d10") -> None.
On None the caller falls back to the user's users.ui_language, then English.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

SUPPORTED = ("en", "el")
GREEK_RATIO = 0.3
MIN_LETTERS = 4  # fewer letters than this and no Greek -> undecided

LANGUAGE_NAMES = {"en": "English", "el": "Greek"}


def _is_greek(ch: str) -> bool:
    o = ord(ch)
    return 0x0370 <= o <= 0x03FF or 0x1F00 <= o <= 0x1FFF


def greek_ratio(text: str) -> float:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if _is_greek(c)) / len(letters)


# Small closed-class word lists; enough to tell English from Greeklish in chat lines.
ENGLISH_WORDS = frozenset("""
a an the i you he she it we they me my your his her its our their them him us this that these
those is are was were be been am do does did have has had will would can could should shall may
might must not no yes and or but if then so what who whom whose which when where why how to of
in on at by for with from into onto about over under after before up down out off than there
here hello hi please thanks thank just also all any some ok okay let lets what's i'm don't can't
""".split())
GREEKLISH_WORDS = frozenset("""
na kai ki gia sto sti stin ston sta tou tis ton tin ta mou sou tou mas sas tous pou ti tha den
dn min einai eimai eisai exw exo exei kanw kano kaneis kanei thelw thelo theleis mporw mporo
prepei pws pos giati otan ekei edw edo afto auto ayto ego egw esy esi emeis eseis apo alla oti
poso posa poios poia kati tipota ola ena enan mia nai oxi ok re lew leo pame pao paw
""".split())
_LATIN_WORD = re.compile(r"[a-z']+")


def _clearly_english(text: str) -> bool:
    words = _LATIN_WORD.findall((text or "").lower())
    en = sum(1 for w in words if w in ENGLISH_WORDS)
    gr = sum(1 for w in words if w in GREEKLISH_WORDS)
    return en >= 1 and en > gr


def detect_language(text: str) -> Optional[str]:
    letters = [c for c in (text or "") if c.isalpha()]
    greek = sum(1 for c in letters if _is_greek(c))
    if letters and greek / len(letters) >= GREEK_RATIO:
        return "el"
    if len(letters) < MIN_LETTERS:
        return None
    return "en" if _clearly_english(text) else None


def normalize_language(value) -> Optional[str]:
    v = str(value or "").strip().lower()[:2]
    return v if v in SUPPORTED else None


def user_ui_language(user_id) -> Optional[str]:
    """users.ui_language ('en' / 'el') or None; never raises."""
    if not user_id:
        return None
    try:
        from database import get_db

        conn = get_db()
        try:
            cur = conn.cursor()
            cur.execute("SELECT ui_language FROM users WHERE id = %s", (int(user_id),))
            row = cur.fetchone()
            return normalize_language((row or {}).get("ui_language") if isinstance(row, dict) else (row[0] if row else None))
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001 - language is a hint, never block a reply
        logger.debug("ui_language lookup failed for user %s: %s", user_id, e)
        return None


def resolve_reply_language(message: str, user_id=None) -> str:
    """Message language when clear, else the user's UI language, else English."""
    return detect_language(message) or user_ui_language(user_id) or "en"


def reply_language_instruction(lang: str, storyteller: bool = True) -> str:
    """Appended to the system prompt (Storyteller, or any other LLM call with storyteller=False)."""
    if not storyteller:
        if lang == "el":
            return (
                "LANGUAGE: Write the content in natural, modern Greek (Ελληνικά). Keep any required "
                "format, field names, keys and markup exactly as specified."
            )
        return "LANGUAGE: Write in English."
    if lang == "el":
        return (
            "LANGUAGE: The player writes in Greek. Write your entire reply in natural, modern Greek "
            "(Ελληνικά), addressing the player in the informal second person singular (εσύ). "
            "Keep game terms (clan names, Disciplines) as they are usually written. Do not switch to English."
        )
    return "LANGUAGE: Reply in English, the language the player writes in."
