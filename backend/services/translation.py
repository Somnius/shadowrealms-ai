"""
Language override (docs/VOICE.md, voice phase 4): chat lines translated ahead of time.

After save_message commits, `schedule(message_id)` queues a background job (one worker thread,
never inside an audio request) that translates the line into each language some member of the
chronicle hears in (users.voice_settings.hear_lang). Results go to message_translations
(kind 'ai'); a player's own words before the write-in language was applied are kept there as
kind 'original'. The translator AI role (Krikri in LM Studio by default) does the work with a
game-term glossary and a few examples (phase 0 showed it once reversed a meaning).
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from services.voice_settings import normalize_user_voice_settings

logger = logging.getLogger(__name__)

LANGS = ("en", "el")
NAMES = {"en": "English", "el": "Greek"}
MAX_CHARS = 2000
MEMBERS_TTL_SEC = 60.0

_GLOSSARY_PATH = os.path.join(os.path.dirname(__file__), "translation_glossary.txt")

FEW_SHOT = {
    ("en", "el"): [
        ("Ilias misses by a hair, and the Prince sees it.", "Ο Ilias αστοχεί παρά τρίχα, και ο Πρίγκιπας το βλέπει."),
        ("Roll Wits + Awareness, difficulty 6.", "Ρίξε Wits + Awareness, δυσκολία 6."),
        ("*Eleni smiles* Nice try, Marcus.", "*Η Eleni χαμογελάει* Καλή προσπάθεια, Marcus."),
        ("Nikos and Dimitra wait in Elysium.", "Ο Nikos και η Dimitra περιμένουν στο Elysium."),
    ],
    ("el", "en"): [
        ("Ο Ηλίας αστοχεί παρά τρίχα και ο Πρίγκιπας το βλέπει.", "Ηλίας misses by a hair, and the Prince sees it."),
        ("Ρίχνω Wits + Awareness, δυσκολία 6.", "I roll Wits + Awareness, difficulty 6."),
        ("*Η Ελένη χαμογελάει* Ωραία προσπάθεια, Μάρκο.", "*Ελένη smiles* Nice try, Μάρκο."),
        ("Ο Νίκος και η Δήμητρα περιμένουν στο Elysium.", "Νίκος and Δήμητρα wait in Elysium."),
    ],
}


def guess_lang(text: Any) -> str:
    from services.voice_tts import guess_lang as g

    return g(text)


_glossary_cache: Optional[List[Tuple[str, str, Tuple[str, ...]]]] = None


def glossary() -> List[Tuple[str, str, Tuple[str, ...]]]:
    """[(english, greek or 'keep', greek words a player may say for a kept term)]."""
    global _glossary_cache
    if _glossary_cache is None:
        rows = []
        try:
            with open(_GLOSSARY_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "|" not in line:
                        continue
                    parts = [p.strip() for p in line.split("|")]
                    alts = tuple(a.strip() for a in parts[2].split(",") if a.strip()) if len(parts) > 2 else ()
                    rows.append((parts[0], parts[1], alts))
        except OSError:
            logger.warning("translation glossary missing")
        _glossary_cache = rows
    return _glossary_cache


def glossary_lines(text: str, src: str) -> List[str]:
    """The glossary entries whose term appears in text, as prompt lines for that direction."""
    low = text.lower()
    out = []
    for en, el, alts in glossary():
        if el == "keep":
            said = [a for a in alts if a.lower() in low]
            if en.lower() in low:
                out.append(f'- {en}: keep as "{en}"')
            for a in said:
                out.append(f'- {a} -> {en} (keep the English game term)')
        elif en.lower() in low or el.lower() in low:
            out.append(f"- {en} -> {el}" if src == "en" else f"- {el} -> {en}")
    return out


def build_messages(text: str, src: str, dst: str) -> List[Dict[str, str]]:
    rules = [
        f"You translate chat lines of a World of Darkness tabletop game from {NAMES[src]} to {NAMES[dst]}.",
        "Output only the translation: no notes, no explanations, no quotes around it.",
        "Translate faithfully, sentence by sentence; keep the exact meaning and every word's sense"
        " (\"misses by a hair\" means barely misses, never misses by a lot; blood stays blood).",
        "Never transliterate or translate personal names: copy them letter for letter in the alphabet"
        " they were written in (Ελένη stays Ελένη, Νίκος stays Νίκος, Eleni stays Eleni, Marcus stays Marcus).",
        "Keep dice notation, numbers, *actions*, markdown and the informal tone.",
        "Keep the game terms of the glossary as it says.",
    ]
    gl = glossary_lines(text, src)
    if gl:
        rules.append("Glossary:\n" + "\n".join(gl))
    msgs: List[Dict[str, str]] = [{"role": "system", "content": "\n".join(rules)}]
    for a, b in FEW_SHOT[(src, dst)]:
        msgs.append({"role": "user", "content": a})
        msgs.append({"role": "assistant", "content": b})
    msgs.append({"role": "user", "content": text})
    return msgs


_PREFIX = re.compile(r"^\s*(translation|μετάφραση)\s*[:：]\s*", re.I)
_NOTE = re.compile(r"^\s*\(?\s*(note|σημείωση|translator'?s note)\b", re.I)


def clean_output(out: str, source: str) -> Optional[str]:
    """The model's answer without labels, wrapping quotes or trailing notes; None when unusable."""
    s = _PREFIX.sub("", str(out or "").strip())
    lines = [ln for ln in s.split("\n")]
    while lines and _NOTE.match(lines[-1]):
        lines.pop()
    s = "\n".join(lines).strip()
    for q1, q2 in (('"', '"'), ("«", "»"), ("“", "”")):
        if len(s) > 1 and s.startswith(q1) and s.endswith(q2) and not source.strip().startswith(q1):
            s = s[1:-1].strip()
    if not s or len(s) > 3 * len(source) + 60:  # commentary, or a runaway answer
        return None
    return s


def translate(text: str, src: str, dst: str, generate: Optional[Callable] = None) -> Tuple[str, str]:
    """(translated text, model). Raises ValueError / ProviderError when it cannot."""
    if src not in LANGS or dst not in LANGS or src == dst:
        raise ValueError("bad language pair")
    text = str(text or "").strip()[:MAX_CHARS]
    if not text:
        raise ValueError("empty text")
    if generate is None:
        from services.ai_roles import generate_for_role

        generate = generate_for_role
    res = generate("translator", build_messages(text, src, dst),
                   {"temperature": 0, "max_tokens": min(1500, 40 + len(text) * 2), "timeout": 30})
    out = clean_output(res.get("text") or "", text)
    if out is None:
        raise ValueError("unusable translation")
    return out, str(res.get("model") or "")


# ---------------------------------------------------------------------------------------------
# Storage

def get_rows(cursor, message_ids: Iterable[int]) -> Dict[int, Dict[str, Dict[str, str]]]:
    """{message_id: {lang: {'text', 'kind'}}}."""
    ids = [int(i) for i in message_ids]
    if not ids:
        return {}
    marks = ",".join(["%s"] * len(ids))
    cursor.execute(
        f"SELECT message_id, lang, text, kind FROM message_translations WHERE message_id IN ({marks})", ids
    )
    out: Dict[int, Dict[str, Dict[str, str]]] = {}
    for r in cursor.fetchall():
        out.setdefault(int(r["message_id"]), {})[r["lang"]] = {"text": r["text"], "kind": r["kind"]}
    return out


def store(cursor, message_id: int, lang: str, text: str, kind: str = "ai", model: str = "") -> None:
    cursor.execute("DELETE FROM message_translations WHERE message_id = %s AND lang = %s", (message_id, lang))
    cursor.execute(
        "INSERT INTO message_translations (message_id, lang, text, kind, model) VALUES (%s, %s, %s, %s, %s)",
        (message_id, lang, text, kind, model or None),
    )


# ---------------------------------------------------------------------------------------------
# Who needs which language

_members: Dict[int, Tuple[float, Set[str]]] = {}
_members_lock = threading.Lock()


def hear_langs(settings_rows: Iterable[Any]) -> Set[str]:
    out = set()
    for raw in settings_rows:
        hl = normalize_user_voice_settings(raw).get("hear_lang")
        if hl in LANGS:
            out.add(hl)
    return out


def member_langs(cursor, campaign_id: int) -> Set[str]:
    """The hear-in languages of the chronicle's members (creator + players), cached 60 s."""
    now = time.monotonic()
    with _members_lock:
        hit = _members.get(int(campaign_id))
        if hit and now - hit[0] < MEMBERS_TTL_SEC:
            return set(hit[1])
    cursor.execute(
        """
        SELECT u.voice_settings FROM users u
        WHERE u.id IN (SELECT created_by FROM campaigns WHERE id = %s)
           OR u.id IN (SELECT user_id FROM campaign_players WHERE campaign_id = %s)
        """,
        (campaign_id, campaign_id),
    )
    langs = hear_langs(r.get("voice_settings") for r in cursor.fetchall())
    with _members_lock:
        _members[int(campaign_id)] = (now, langs)
    return langs


def forget_members(campaign_id: Optional[int] = None) -> None:
    with _members_lock:
        if campaign_id is None:
            _members.clear()
        else:
            _members.pop(int(campaign_id), None)


def readout_skip(row: Dict[str, Any]) -> bool:
    """Rows never translated: dice lines and markers, slash commands, system lines."""
    k = str(row.get("ai_message_kind") or "").lower()
    return k.startswith(("dice_", "slash_")) or str(row.get("message_type") or "").lower() == "system"


def needed(msg_lang: str, wanted: Iterable[str], have: Iterable[str]) -> List[str]:
    return sorted(set(wanted) - {msg_lang} - set(have))


# ---------------------------------------------------------------------------------------------
# Background worker

_pool: Optional[ThreadPoolExecutor] = None
_pending: Set[Tuple[int, str]] = set()
_lock = threading.Lock()


def is_pending(message_id: int, lang: str) -> bool:
    with _lock:
        return (int(message_id), lang) in _pending


def _executor() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="translate")
    return _pool


def run_job(message_id: int, langs: Optional[List[str]] = None, *, get_db=None, generate=None) -> List[str]:
    """Translate one message into `langs` (default: what the members need). Returns langs done."""
    if get_db is None:
        from database import get_db
    from database import ensure_message_translations_table, ensure_messages_voice_columns

    done: List[str] = []
    conn = get_db()
    try:
        cursor = conn.cursor()
        ensure_messages_voice_columns(cursor)
        ensure_message_translations_table(cursor)
        cursor.execute("SELECT id, campaign_id, content, lang FROM messages WHERE id = %s", (message_id,))
        row = cursor.fetchone()
        if not row:
            return done
        src = row.get("lang") or guess_lang(row.get("content"))
        have = get_rows(cursor, [message_id]).get(int(message_id), {})
        wanted = langs if langs is not None else member_langs(cursor, row["campaign_id"])
        for dst in needed(src, wanted, have.keys()):
            try:
                text, model = translate(row["content"], src, dst, generate)
            except Exception as e:  # noqa: BLE001 - a missing caption, not an error for the player
                logger.warning("translation of message %s to %s failed: %s", message_id, dst, type(e).__name__)
                continue
            store(cursor, message_id, dst, text, "ai", model)
            conn.commit()
            done.append(dst)
        return done
    finally:
        conn.close()


def schedule(message_id: int, langs: Iterable[str]) -> None:
    """Queue a translation job (no-op for languages already queued)."""
    todo = []
    with _lock:
        for lang in langs:
            key = (int(message_id), lang)
            if key not in _pending:
                _pending.add(key)
                todo.append(lang)
    if not todo:
        return

    def job():
        try:
            run_job(message_id, todo)
        except Exception as e:  # noqa: BLE001
            logger.warning("translation job %s failed: %s", message_id, type(e).__name__)
        finally:
            with _lock:
                for lang in todo:
                    _pending.discard((int(message_id), lang))

    _executor().submit(job)


def after_save(cursor, message_id: int, campaign_id: int, content: str, lang: str) -> List[str]:
    """Called by save_message once committed: schedules what the members need. Returns those langs."""
    if not str(content or "").strip():
        return []
    try:
        langs = needed(lang, member_langs(cursor, campaign_id), ())
    except Exception as e:  # noqa: BLE001
        logger.warning("translation members lookup failed: %s", type(e).__name__)
        return []
    if langs:
        schedule(message_id, langs)
    return langs
