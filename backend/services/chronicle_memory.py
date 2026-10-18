"""
The Storyteller's memory of the chronicle (docs/CHRONICLE.md, "The Storyteller's memory"): a block of the
Storyteller prompt built from the written chapters and the final digest of "The chronicle so far".

It is the Storyteller view on purpose (st_so_far, st_notes): the prompt never reaches players, and the
header tells the model never to quote it. Priority when the budget is short (lowest dropped first):
the story so far, the open threads, this room's last nights (newest first), one line per other room's
last night, the Storyteller-only paragraphs.

Read in the reply's language when a translation of the digest is already stored, else in the chronicle's
own. Never blocks a reply: no model calls, a few reads per minute, any error gives ''.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from services import storyteller_prompt as sp

logger = logging.getLogger(__name__)

TTL_SECONDS = 60
MAX_TOKENS = 1500
ROOM_CHAPTERS = 3
OTHER_ROOMS = 4
THREADS = 8
ST_SO_FAR = 2

HEADER = {
    "en": "Your private memory of this chronicle (never quote or list it to players):",
    "el": "Η ιδιωτική σου μνήμη για αυτό το χρονικό (ποτέ μην την παραθέτεις ή απαριθμείς στους παίκτες):",
}
LABELS = {
    "en": {"so_far": "The story so far", "threads": "Open threads", "room": "Last nights in this room",
           "others": "Elsewhere, last night", "st": "Only you know"},
    "el": {"so_far": "Η ιστορία ως τώρα", "threads": "Ανοιχτά νήματα", "room": "Οι τελευταίες νύχτες σε αυτό το δωμάτιο",
           "others": "Αλλού, την τελευταία νύχτα", "st": "Μόνο εσύ ξέρεις"},
}

# (campaign_id, wanted language) -> (checked_at, stamp, material); material = {lang, memory, digest, chapters}
_cache: Dict[Tuple[int, Optional[str]], Tuple[float, Any, Dict[str, Any]]] = {}
_lock = threading.Lock()


def forget(campaign_id: Optional[int] = None) -> None:
    """Drop the cached material (one chronicle, or all)."""
    with _lock:
        if campaign_id is None:
            _cache.clear()
        else:
            for k in [k for k in _cache if k[0] == campaign_id]:
                _cache.pop(k, None)


def _stamp(cursor, campaign_id: int, want: Optional[str]):
    """Everything the block depends on: the memory switch, the chronicle's language, the language used
    (a stored translation into `want` when one exists; never a new one), the digest's hash and the newest
    chapter. Re-read after the TTL, so a switch or language changed in the other worker sticks too."""
    from services import chronicle_jobs as cj
    from services import chronicle_settings as cs

    if not cs.load(cursor, campaign_id)["memory"]:
        return (False,)
    camp = cj.campaign_row(cursor, campaign_id)
    if not camp:
        return (False,)
    lang = cj.chronicle_lang(cursor, camp)
    use, translated = lang, False
    cursor.execute("SELECT source_hash, translated_from FROM chronicle_digests WHERE campaign_id = %s "
                   "AND kind = 'final' AND era = 0 AND lang = %s", (campaign_id, lang))
    d = cursor.fetchone() or {}
    if want and want != lang:
        cursor.execute("SELECT source_hash, translated_from FROM chronicle_digests WHERE campaign_id = %s "
                       "AND kind = 'final' AND era = 0 AND lang = %s", (campaign_id, want))
        t = cursor.fetchone()
        if t and t.get("translated_from"):
            use, translated, d = want, True, t
    cursor.execute("SELECT MAX(written_at) AS w FROM chronicle_chapters WHERE campaign_id = %s AND lang = %s",
                   (campaign_id, use))
    c = cursor.fetchone() or {}
    return (True, lang, use, translated, d.get("source_hash"), str(c.get("w")))


def _load(cursor, campaign_id: int, stamp) -> Dict[str, Any]:
    from services import chronicle_jobs as cj

    if not stamp[0]:
        return {"memory": False, "lang": "en", "digest": None, "chapters": []}
    _, lang, use, translated = stamp[:4]
    chapters = cj.stored_chapters(cursor, campaign_id, use)
    if translated and not chapters:  # only the digest was translated: the nights in their own language
        chapters = cj.stored_chapters(cursor, campaign_id, lang)
    return {"memory": True, "lang": use, "digest": cj.stored_digest(cursor, campaign_id, use, translated=translated),
            "chapters": chapters}


def material(cursor, campaign_id: int, want: Optional[str] = None,
             clock: Callable[[], float] = time.monotonic) -> Dict[str, Any]:
    """The chronicle's digest and chapters, cached TTL_SECONDS; after that the stamp is read again and
    the material only reloaded when it moved. `want` is the reply language."""
    key = (campaign_id, want)
    now = clock()
    with _lock:
        hit = _cache.get(key)
    if hit and now - hit[0] < TTL_SECONDS:
        return hit[2]
    stamp = _stamp(cursor, campaign_id, want)
    mat = hit[2] if hit and hit[1] == stamp else _load(cursor, campaign_id, stamp)
    with _lock:
        _cache[key] = (now, stamp, mat)
    return mat


def _text(x) -> str:
    return " ".join(str((x.get("text") if isinstance(x, dict) else x) or "").split())


def format_chapter(ch: Dict[str, Any], short: bool = False) -> str:
    """A night as the Storyteller remembers it: title, summary (first paragraph only when short), st_notes."""
    c = ch.get("chapter") or {}
    title = _text(c.get("title")) or ch.get("key") or ""
    summary = [_text(p) for p in c.get("summary") or [] if _text(p)]
    if short:
        room = ch.get("room") or ""
        return f"- {room}: {title}" + (f" — {summary[0]}" if summary else "")
    lines = [f"- {title}"] + [f"  {p}" for p in summary]
    lines += [f"  * {_text(n)}" for n in c.get("st_notes") or [] if _text(n)]
    return "\n".join(lines)


def build_block(mat: Dict[str, Any], location_id: Optional[int], history_oldest_id: Optional[int],
                max_tokens: int) -> Tuple[str, int]:
    """(block, chapters used) from the material; '' when there is nothing written or no room left."""
    from routes.chronicle import _so_far_short

    if not mat.get("memory"):
        return "", 0
    lang = mat["lang"] if mat.get("lang") in HEADER else "en"
    lab = LABELS[lang]
    digest = mat.get("digest") or {}
    chapters = [c for c in mat.get("chapters") or [] if c.get("kind", "story") == "story"]

    so_far = _so_far_short(digest) if digest else ""
    threads = [_text(t) for t in digest.get("threads_open") or [] if _text(t)][:THREADS]
    room = [c for c in chapters if location_id and c["location_id"] == location_id
            and not (history_oldest_id and c.get("last_id") and c["last_id"] >= history_oldest_id)]
    room = room[-ROOM_CHAPTERS:]
    others: Dict[int, Dict[str, Any]] = {}
    for c in chapters:
        if c["location_id"] != location_id:
            others[c["location_id"]] = c  # chapters come oldest first: the last one wins
    other = sorted(others.values(), key=lambda c: (str(c.get("started_at") or ""), c.get("first_id") or 0))
    other = other[-OTHER_ROOMS:]
    st = [_text(p) for p in digest.get("st_so_far") or [] if _text(p)][:ST_SO_FAR]

    # (priority, section, order, text): kept by priority, written in section order
    items: List[Tuple[int, str, int, str]] = []
    if so_far:
        items.append((0, "so_far", 0, so_far))
    for i, t in enumerate(threads):
        items.append((1 + i, "threads", i, f"- {t}"))
    for i, c in enumerate(room):  # newest first in priority, oldest first in the text
        items.append((100 + len(room) - i, "room", i, format_chapter(c)))
    for i, c in enumerate(other):
        items.append((200 + len(other) - i, "others", i, format_chapter(c, short=True)))
    for i, p in enumerate(st):
        items.append((300 + i, "st", i, p))
    if not items:
        return "", 0

    header = HEADER[lang]
    used = sp.estimate_tokens(header) + 20  # header plus the section titles
    kept = []
    for it in sorted(items):  # by priority; the first that doesn't fit is cut, and nothing after it goes in
        t = sp.estimate_tokens(it[3]) + 1
        if used + t <= max_tokens:
            used += t
            kept.append(it)
            continue
        if max_tokens - used >= 40:
            kept.append(it[:3] + (sp.truncate_to_tokens(it[3], max_tokens - used - 1),))
        break
    if not kept:
        return "", 0
    out = [header]
    for sec in ("so_far", "threads", "room", "others", "st"):
        part = sorted((o, t) for _, s, o, t in kept if s == sec)
        if part:
            out.append(f"## {lab[sec]}\n" + "\n".join(t for _, t in part))
    n = sum(1 for _, s, _, _ in kept if s in ("room", "others"))
    return sp.truncate_to_tokens("\n\n".join(out), max_tokens), n


def storyteller_block(get_db, campaign_id: int, location_id: Optional[int], history_oldest_id: Optional[int],
                      max_tokens: int, reply_lang: Optional[str] = None) -> Tuple[str, int]:
    """The block for one Storyteller reply, (text, chapters); ('', 0) when off, empty or on any error.
    reply_lang: the reply's language; a stored translation into it is used when there is one."""
    if not campaign_id or max_tokens <= 0:
        return "", 0
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        mat = material(cur, campaign_id, reply_lang)
        block, n = build_block(mat, location_id, history_oldest_id, min(max_tokens, MAX_TOKENS))
        if not block:
            logger.debug("chronicle memory: nothing for chronicle %s", campaign_id)
        return block, n
    except Exception as e:  # noqa: BLE001 - a reply without memory beats no reply
        logger.warning("chronicle memory unavailable for chronicle %s: %s", campaign_id, e)
        if conn is not None:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
        return "", 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
