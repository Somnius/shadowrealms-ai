"""
Transcript check (docs/VOICE.md, voice phase 6): Whisper's text, checked and fixed with context.

1. Whisper gets a short hint (initial_prompt): the chronicle's character, NPC and location names
   and a few World of Darkness words. It only biases spelling; it is not a word list.
2. The speech service asks Laya-words (somniusx/recmeets-laya-words) which of Whisper's words are
   probably misheard, and returns the words with those scores.
3. Here Krikri (LM Studio, temperature 0) gets the whole line with only the flagged spans marked,
   plus the names, and proposes a fix for each span: it may join split words («βλυχ άρα» ->
   «βλαχάρα») and writes slang and swearing as spoken. Nothing that was not flagged can change.
4. The recorder shows the result with each changed span marked; a tap puts Whisper's words back.

Never in the way: no flags, a slow (> TIMEOUT_S) or missing Krikri, or an unusable answer all
mean Whisper's text unchanged. Whisper's text always stays in voice_clips.transcript_raw.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

FLAG = 0.7          # Laya's chance of a mistake from which a word is sent to Krikri
TIMEOUT_S = 3.5     # one Krikri HTTP call; past it the player gets Whisper's text
# ai_roles skips an attempt with less than MIN_ATTEMPT_SEC (3 s) left, so the chain budget
# must sit above it or Krikri is never asked.
BUDGET_S = 4.5
NAME_MAX = 40       # one long free-text name must not eat the whole Whisper hint
PROMPT_MAX = 400    # characters of Whisper hint
MAX_SPANS = 8
NEIGHBOUR = 0.7     # a word next to a flagged one joins its span when Whisper was this unsure of it
ALIKE = 0.6         # a fix must sound like what Whisper wrote (letters compared, accents ignored)
PUNCT = ".,;:!?«»\"'()·;…-"

GLOSSARY = {
    "el": "Αφηγητής, Πρίγκιπας, Καμαρίλα, Σαμπάτ, Αναρχικοί, Ελύσιο, Θέληση, Πείνα, Ανθρωπιά, "
          "Οξύνοια, Επίγνωση, Βεντρού, Τορεαντόρ, Μαλκάβιαν, Νοσφεράτου, Μπρούχα, Γκανγκρέλ, Τρεμέρ.",
    "en": "Storyteller, Prince, Camarilla, Sabbat, Anarchs, Elysium, Willpower, Hunger, Humanity, "
          "Kindred, Masquerade, Ventrue, Toreador, Malkavian, Nosferatu, Brujah, Gangrel, Tremere.",
}


def model() -> str:
    return os.getenv("TRANSCRIPT_CHECK_MODEL", "llama-krikri-8b-instruct")


def enabled() -> bool:
    return os.getenv("VOICE_TRANSCRIPT_CHECK", "1").lower() not in ("0", "false", "off", "no")


# ------------------------------------------------------------------ names and the Whisper hint

def chronicle_names(cursor, campaign_id: int, limit: int = 40) -> List[str]:
    """Character, NPC and location names of the chronicle (most recent first), deduplicated."""
    names: List[str] = []
    for sql in (
        "SELECT name FROM characters WHERE campaign_id = %s ORDER BY id DESC LIMIT %s",
        "SELECT name FROM npcs WHERE campaign_id = %s ORDER BY id DESC LIMIT %s",
        "SELECT name FROM locations WHERE campaign_id = %s ORDER BY id DESC LIMIT %s",
    ):
        try:
            cursor.execute(sql, (campaign_id, limit))
            rows = cursor.fetchall() or []
        except Exception:  # noqa: BLE001 (a missing table only means fewer names)
            logger.warning("transcript check: names query failed")
            try:
                cursor.connection.rollback()
            except Exception:  # noqa: BLE001
                pass
            continue
        for r in rows:
            n = " ".join(str((r.get("name") if isinstance(r, dict) else r[0]) or "").split())
            if n and len(n) <= NAME_MAX and n.lower() not in {x.lower() for x in names}:
                names.append(n)
    return names[:limit]


def whisper_prompt(names: Sequence[str], lang: str) -> str:
    """Names first, then the glossary, cut at PROMPT_MAX characters on a comma."""
    out = ""
    for n in names:
        nxt = f"{out}, {n}" if out else n
        if len(nxt) > PROMPT_MAX - 60:
            break
        out = nxt
    gloss = GLOSSARY.get(lang, GLOSSARY["en"])
    text = f"{out}. {gloss}" if out else gloss
    return text[:PROMPT_MAX]


# ------------------------------------------------------------------ flagged spans

def spans(words: Sequence[str], suspects: Sequence[Dict[str, Any]], flag: float = FLAG,
          probs: Optional[Sequence[float]] = None) -> List[List[int]]:
    """[[first, last], …] word index ranges to check: flagged words, plus a neighbour Whisper was
    unsure of (a split word: «βλυχ άρα»), neighbours joined into one span."""
    hit = {int(s["i"]) for s in suspects or []
           if float(s.get("p_laya", 0)) >= flag and 0 <= int(s.get("i", -1)) < len(words)}
    if probs is not None and len(probs) == len(words):
        for i in list(hit):
            for j in (i - 1, i + 1):
                if 0 <= j < len(words) and probs[j] is not None and probs[j] < NEIGHBOUR and _core(words[j]):
                    hit.add(j)
    hit = sorted(hit)
    out: List[List[int]] = []
    for i in hit:
        if out and i == out[-1][1] + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out[:MAX_SPANS]


def build_messages(words: Sequence[str], sp: Sequence[Sequence[int]], lang: str,
                   names: Sequence[str]) -> List[Dict[str, str]]:
    marked = list(words)
    for k, (a, b) in enumerate(sp, 1):
        marked[a] = f"[{k}: " + marked[a]
        marked[b] = marked[b] + "]"
    language = "Greek" if lang == "el" else "English"
    system = (
        "You fix speech-recognition mistakes in a player's line from a World of Darkness tabletop "
        "role-playing chat. Only the numbered spans [n: …] may be wrong. For each span give the word(s) "
        "the speaker most likely said: it must SOUND like the span (a misheard spelling), never a "
        "synonym or a better word. A span may be one word split in pieces: join them. Players use slang, "
        "insults and swear words: write them as spoken, never soften or censor. Names are spelled as in "
        "the list. If the span is already a real word that fits, return it exactly as it is. Never "
        "rephrase, translate or add words. "
        'Answer only JSON: {"1": "…", "2": "…"}.'
    )
    user = (
        f"Language: {language}\n"
        f"Names: {', '.join(names[:40]) or '-'}\n"
        f"Line: {' '.join(marked)}"
    )
    shots = [
        ("Language: Greek\nNames: Μάρκος\nLine: [1: Γα μώτο], ο Μάρκος μας [2: έστεισε] πάλι.",
         '{"1": "Γαμώτο", "2": "έστησε"}'),
        ("Language: Greek\nNames: -\nLine: Λέει [1: σιγανά] ο πρίγκιπας, ρε [2: κωλόπαιδο].",
         '{"1": "σιγανά", "2": "κωλόπαιδο"}'),
        ("Language: English\nNames: -\nLine: The [1: candles] gutter in the [2: draft].",
         '{"1": "candles", "2": "draft"}'),
        ("Language: English\nNames: Dimitra\nLine: [1: Blot] is a debt, whispers [2: Demetra].",
         '{"1": "Blood", "2": "Dimitra"}'),
    ]
    msgs = [{"role": "system", "content": system}]
    for q, a in shots:
        msgs += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
    return msgs + [{"role": "user", "content": user}]


def _core(s: str) -> str:
    return s.strip(PUNCT)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if c.isalnum())


def alike(a: str, b: str) -> bool:
    """Whether a fix could be a mishearing of what Whisper wrote (not a synonym)."""
    fa, fb = _fold(a), _fold(b)
    return bool(fa and fb) and SequenceMatcher(None, fa, fb).ratio() >= ALIKE


def _keep_punct(orig_first: str, orig_last: str, new: str) -> str:
    """Whisper's punctuation around the span stays: «άρα,» -> «βλαχάρα,»."""
    lead = orig_first[: len(orig_first) - len(orig_first.lstrip(PUNCT))]
    trail = orig_last[len(orig_last.rstrip(PUNCT)):]
    return lead + _core(new) + trail


def parse_fixes(answer: str, sp: Sequence[Sequence[int]], words: Sequence[str]) -> Dict[int, str]:
    """{span number: replacement} for usable, real changes only."""
    m = re.search(r"\{.*\}", answer or "", re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except ValueError:
        # Krikri sometimes adds a remark inside the braces ({"1": "βλαχάρα", "βλυχ άρα" sounds…});
        # the numbered pairs are still usable, everything else is ignored.
        data = {k: v for k, v in re.findall(r'"(\d+)"\s*:\s*"([^"\n]*)"', m.group(0))}
    out: Dict[int, str] = {}
    for k, (a, b) in enumerate(sp, 1):
        v = data.get(str(k)) if isinstance(data, dict) else None
        if not isinstance(v, str):
            continue
        v = " ".join(v.replace("[", " ").replace("]", " ").split())
        v = re.sub(rf"^{k}\s*:\s*", "", v)
        n_old = b - a + 1
        if not _core(v) or len(v.split()) > n_old + 1 or len(v) > 4 * len(" ".join(words[a:b + 1])) + 8:
            continue  # empty, or a rewrite rather than a fix
        new = _keep_punct(words[a], words[b], v)
        old = " ".join(words[a:b + 1])
        if _fold(new) != _fold(old) and alike(new, old):
            out[k] = new
    return out


def segments(words: Sequence[str], sp: Sequence[Sequence[int]], fixes: Dict[int, str]) -> List[Dict[str, str]]:
    """[{"t": text}, {"t": fixed, "raw": Whisper's words}, …] in order; unchanged runs joined."""
    out: List[Dict[str, str]] = []
    plain: List[str] = []
    i = 0
    starts = {a: (k, b) for k, (a, b) in enumerate(sp, 1)}
    while i < len(words):
        if i in starts and starts[i][0] in fixes:
            k, b = starts[i]
            if plain:
                out.append({"t": " ".join(plain)})
                plain = []
            out.append({"t": fixes[k], "raw": " ".join(words[i:b + 1])})
            i = b + 1
            continue
        plain.append(words[i])
        i += 1
    if plain:
        out.append({"t": " ".join(plain)})
    return out


def text_of(segs: Sequence[Dict[str, str]]) -> str:
    return " ".join(s["t"] for s in segs).strip()


def check(words: Sequence[str], suspects: Sequence[Dict[str, Any]], lang: str, names: Sequence[str],
          generate: Optional[Callable] = None,
          probs: Optional[Sequence[float]] = None) -> Optional[List[Dict[str, str]]]:
    """Segments with Krikri's fixes, or None when nothing changed (or it could not be asked)."""
    sp = spans(words, suspects, probs=probs)
    if not sp or not enabled():
        return None
    if generate is None:
        from services.ai_roles import generate_for_role

        def generate(messages):
            # The role only picks the provider settings; the chain names Krikri explicitly,
            # so English clips go to the same model.
            return generate_for_role("storyteller_el", messages,
                                     {"temperature": 0, "max_tokens": 200, "timeout": TIMEOUT_S},
                                     chain=[("lm_studio", model())], budget_s=BUDGET_S)
    try:
        res = generate(build_messages(words, sp, lang, names))
    except Exception as e:  # noqa: BLE001 (Krikri down, slow or refusing: Whisper's text stays)
        logger.info("transcript check skipped: %s", type(e).__name__)
        return None
    fixes = parse_fixes((res or {}).get("text") or "", sp, words)
    if not fixes:
        return None
    return segments(words, sp, fixes)
