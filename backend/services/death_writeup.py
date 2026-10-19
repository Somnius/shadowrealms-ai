"""
The death description when an admin kills a character (POST /api/admin/characters/<id>/kill).

One call to the chronicler role in the chronicle's language, from the character's name and clan,
the story so far and the character's last nights in the chapters. The text is stored for players, so
only the player view goes in (no closed rooms, no Storyteller-only keys, no digest kept back by a room
closed since it was written). Backgrounds stay out (same rule as the chronicle writer). Any failure,
timeout, empty answer, wrong language or mixed script (also a Latin word in a Greek text that the
material doesn't have) gives the canned sentence.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEATH_TYPES = ("soft", "mid", "horrible")
TIMEOUT_S = 25.0
LAST_CHAPTERS = 2
MAX_TOKENS = 220

FALLBACK = {
    "en": {
        "soft": "Your character fades peacefully into the shadows, their story complete.",
        "mid": "In a moment of sacrifice, your character falls to save others.",
        "horrible": "The darkness claims your character in a brutal and terrifying end.",
    },
    "el": {
        "soft": "Ο χαρακτήρας σου σβήνει ήσυχα μέσα στις σκιές· η ιστορία του ολοκληρώθηκε.",
        "mid": "Σε μια στιγμή θυσίας, ο χαρακτήρας σου πέφτει για να σώσει τους άλλους.",
        "horrible": "Το σκοτάδι παίρνει τον χαρακτήρα σου σε ένα βίαιο και τρομακτικό τέλος.",
    },
}

TONE = {
    "en": {"soft": "quiet and peaceful", "mid": "a sacrifice, bittersweet", "horrible": "brutal and terrifying"},
    "el": {"soft": "ήσυχος και γαλήνιος", "mid": "θυσία, γλυκόπικρος", "horrible": "βίαιος και τρομακτικός"},
}

SYSTEM = {
    "en": ("You write the death of a character in a Vampire: The Masquerade chronicle. Write 2 to 4 sentences "
           "in English, second person (\"you\"), tone: {tone}. Use only facts that are in the material below: "
           "its names, clan, places and events. Invent nothing: no new names, clans, titles, ranks, places, "
           "sects or lore. If the material is thin, keep the death plain rather than add details. "
           "Answer with the text only, no title."),
    "el": ("Γράφεις τον θάνατο ενός χαρακτήρα σε ένα χρονικό του Vampire: The Masquerade. Γράψε 2 έως 4 "
           "προτάσεις στα ελληνικά, σε δεύτερο πρόσωπο (\"εσύ\"), ύφος: {tone}. Χρησιμοποίησε μόνο ό,τι υπάρχει "
           "στο υλικό παρακάτω: τα ονόματα, τον κλάνο, τους τόπους και τα γεγονότα του. Μην επινοείς τίποτα: "
           "ούτε ονόματα, κλάνους, τίτλους, αξιώματα, τόπους, σέκτες ή μύθους. Αν το υλικό είναι λίγο, κράτα τον "
           "θάνατο απλό αντί να προσθέσεις λεπτομέρειες. Γράψε μόνο με ελληνικά γράμματα· λατινικά μόνο για ονόματα "
           "που είναι γραμμένα έτσι στο υλικό. Απάντησε μόνο με το κείμενο, χωρίς τίτλο."),
}

LABELS = {
    "en": {"name": "Character", "clan": "Clan", "so_far": "The story so far", "nights": "Their last nights"},
    "el": {"name": "Χαρακτήρας", "clan": "Κλάνος", "so_far": "Η ιστορία ως τώρα", "nights": "Οι τελευταίες νύχτες του"},
}


def fallback(lang: str, death_type: str) -> str:
    return FALLBACK.get(lang, FALLBACK["en"])[death_type]


_LATIN_WORD = re.compile(r"[A-Za-z]+")


def script_problems(text: str, lang: str, mat: Dict[str, Any]) -> List[str]:
    """Why the answer can't be shown: 'language' (mostly the wrong language), 'mixed_script' (a word
    mixing Greek and Latin letters, or letters of another script), 'latin_word' (a Greek text with a
    Latin word the material doesn't have, e.g. an invented English clan or title)."""
    from services import chronicle_digest as cd

    probs = cd.language_problems(text, lang)
    if lang == "el":
        known = set(_tokens(json.dumps(mat, ensure_ascii=False, default=str)))
        if any(t not in known for w in _LATIN_WORD.findall(text) for t in _tokens(w)):
            probs.append("latin_word")
    return probs


def _tokens(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", str(text or "").lower()) if t]


def _named(ch: Dict[str, Any], name: str) -> bool:
    """The chapter's cast names the character: one cast name's words are all whole words of the
    character's name (the chapters often use the first name only; Ann never matches Anastasia)."""
    own = set(_tokens(name))
    for c in (ch.get("chapter") or {}).get("characters") or []:
        words = _tokens(c.get("name") if isinstance(c, dict) else c)
        if own and words and all(w in own for w in words):
            return True
    return False


def material(cursor, character_id: int) -> Optional[Dict[str, Any]]:
    """name, clan, lang, so_far and the character's last chapters, player view; None when the character is gone."""
    from services import chronicle_digest as cd
    from services import chronicle_jobs as cj
    from routes.chronicle import _readable_for_players, _so_far_short

    cursor.execute("SELECT id, name, campaign_id, wod_meta FROM characters WHERE id = %s", (character_id,))
    row = cursor.fetchone()
    if not row:
        return None
    try:
        meta = json.loads(row.get("wod_meta") or "{}") if isinstance(row.get("wod_meta"), str) else (row.get("wod_meta") or {})
    except ValueError:
        meta = {}
    cid = row["campaign_id"]
    camp = cj.campaign_row(cursor, cid) or {"id": cid}
    lang = cj.chronicle_lang(cursor, camp)
    readable = _readable_for_players(cursor, cid)
    digest = cj.stored_digest(cursor, cid, lang)
    if digest and any(int(r) not in readable for r in digest.get("rooms") or []):
        digest = None  # a room closed since the digest was written keeps it back (as in the recap)
    visible = cd.visible_chapters(cj.stored_chapters(cursor, cid, lang), "player", readable)
    chapters = [cd.player_chapter(c) for c in visible if _named(c, row["name"] or "")]
    return {"name": row["name"] or "", "clan": str(meta.get("clan") or ""), "lang": lang,
            "so_far": _so_far_short(cd.player_digest(digest)) if digest else "",
            "chapters": chapters[-LAST_CHAPTERS:]}


def messages(mat: Dict[str, Any], death_type: str) -> List[Dict[str, str]]:
    lang = mat["lang"] if mat["lang"] in FALLBACK else "en"
    lab = LABELS[lang]
    parts = [f"{lab['name']}: {mat['name']}"]
    if mat.get("clan"):
        parts.append(f"{lab['clan']}: {mat['clan']}")
    if mat.get("so_far"):
        parts.append(f"{lab['so_far']}:\n{mat['so_far']}")
    nights = []
    for ch in mat.get("chapters") or []:
        c = ch.get("chapter") or {}
        summary = " ".join(str(p).strip() for p in c.get("summary") or [] if str(p).strip())
        if summary:
            nights.append(f"- {str(c.get('title') or '').strip()}: {summary}".replace("- : ", "- "))
    if nights:
        parts.append(f"{lab['nights']}:\n" + "\n".join(nights))
    return [{"role": "system", "content": SYSTEM[lang].format(tone=TONE[lang][death_type])},
            {"role": "user", "content": "\n\n".join(parts)}]


def _read(get_db, character_id: int) -> Optional[Dict[str, Any]]:
    """The material on a connection of its own, closed before the model call."""
    conn = get_db()
    try:
        return material(conn.cursor(), character_id)
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001 - a dead connection must not lose the kill
            pass


def write(get_db, character_id: int, death_type: str, generate=None,
          timeout: float = TIMEOUT_S) -> Tuple[str, bool]:
    """(text, generated). Never raises: any problem gives the canned sentence and generated=False."""
    lang = "en"
    try:
        mat = _read(get_db, character_id)
        if not mat:
            return fallback(lang, death_type), False
        lang = mat["lang"] if mat["lang"] in FALLBACK else "en"
        if generate is None:
            from services.ai_roles import generate_for_role as generate
        out = generate(f"chronicler_{lang}", messages(mat, death_type),
                       {"max_tokens": MAX_TOKENS, "temperature": 0.8, "timeout": timeout}, budget_s=timeout)
        text = str((out or {}).get("text") or "").strip()
        probs = script_problems(text, lang, mat) if text else ["empty"]
        if probs:
            logger.info("death description for character %s: unusable answer (%s), canned sentence used",
                        character_id, ",".join(probs))
            return fallback(lang, death_type), False
        return text, True
    except Exception as e:
        logger.warning("death description for character %s failed: %s", character_id, e)
        return fallback(lang, death_type), False
