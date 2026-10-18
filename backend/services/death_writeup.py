"""
The death description when an admin kills a character (POST /api/admin/characters/<id>/kill).

One call to the chronicler role in the chronicle's language, from the character's name and clan,
the story so far and the character's last nights in the chapters. Backgrounds stay out (same rule as
the chronicle writer). Any failure, timeout, empty answer or wrong language gives the canned sentence.
"""

from __future__ import annotations

import json
import logging
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
           "in English, second person (\"you\"), tone: {tone}. Use only the names, clans and events in the "
           "material; invent no new names. Answer with the text only."),
    "el": ("Γράφεις τον θάνατο ενός χαρακτήρα σε ένα χρονικό του Vampire: The Masquerade. Γράψε 2 έως 4 "
           "προτάσεις στα ελληνικά, σε δεύτερο πρόσωπο (\"εσύ\"), ύφος: {tone}. Χρησιμοποίησε μόνο τα ονόματα, "
           "τους κλάνους και τα γεγονότα του υλικού· μην επινοείς νέα ονόματα. Απάντησε μόνο με το κείμενο."),
}

LABELS = {
    "en": {"name": "Character", "clan": "Clan", "so_far": "The story so far", "nights": "Their last nights"},
    "el": {"name": "Χαρακτήρας", "clan": "Κλάνος", "so_far": "Η ιστορία ως τώρα", "nights": "Οι τελευταίες νύχτες του"},
}


def fallback(lang: str, death_type: str) -> str:
    return FALLBACK.get(lang, FALLBACK["en"])[death_type]


def _named(ch: Dict[str, Any], name: str) -> bool:
    low = name.strip().lower()
    for c in (ch.get("chapter") or {}).get("characters") or []:
        n = c.get("name") if isinstance(c, dict) else c
        n = str(n or "").strip().lower()
        if n and low and (n in low or low in n):  # the chapters often use the first name only
            return True
    return False


def material(cursor, character_id: int) -> Optional[Dict[str, Any]]:
    """name, clan, lang, so_far and the character's last chapters; None when the character is gone."""
    from services import chronicle_jobs as cj
    from routes.chronicle import _so_far_short

    cursor.execute("SELECT id, name, campaign_id, wod_meta FROM characters WHERE id = %s", (character_id,))
    row = cursor.fetchone()
    if not row:
        return None
    try:
        meta = json.loads(row.get("wod_meta") or "{}") if isinstance(row.get("wod_meta"), str) else (row.get("wod_meta") or {})
    except ValueError:
        meta = {}
    camp = cj.campaign_row(cursor, row["campaign_id"]) or {"id": row["campaign_id"]}
    lang = cj.chronicle_lang(cursor, camp)
    digest = cj.stored_digest(cursor, row["campaign_id"], lang)
    chapters = [c for c in cj.stored_chapters(cursor, row["campaign_id"], lang) if _named(c, row["name"] or "")]
    return {"name": row["name"] or "", "clan": str(meta.get("clan") or ""), "lang": lang,
            "so_far": _so_far_short(digest) if digest else "", "chapters": chapters[-LAST_CHAPTERS:]}


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


def write(cursor, character_id: int, death_type: str, generate=None,
          timeout: float = TIMEOUT_S) -> Tuple[str, bool]:
    """(text, generated). Never raises: any problem gives the canned sentence and generated=False."""
    from services import chronicle_digest as cd

    lang = "en"
    try:
        mat = material(cursor, character_id)
        if not mat:
            return fallback(lang, death_type), False
        lang = mat["lang"] if mat["lang"] in FALLBACK else "en"
        if generate is None:
            from services.ai_roles import generate_for_role as generate
        out = generate(f"chronicler_{lang}", messages(mat, death_type),
                       {"max_tokens": MAX_TOKENS, "temperature": 0.8, "timeout": timeout}, budget_s=timeout)
        text = str((out or {}).get("text") or "").strip()
        if not text or "language" in cd.language_problems(text, lang):
            logger.info("death description for character %s: unusable answer, canned sentence used", character_id)
            return fallback(lang, death_type), False
        return text, True
    except Exception as e:
        logger.warning("death description for character %s failed: %s", character_id, e)
        return fallback(lang, death_type), False
