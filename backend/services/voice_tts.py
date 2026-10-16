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

SPOKEN_MAX = 4000  # a whole Storyteller reply; it is spoken in chunks (0.22)
CHUNK_MAX = 220
DICE_MAX = 200
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
    text = plain_text(strip_roll_tags(row.get("content")))
    if kind == "dice":
        first = plain_text(str(row.get("content") or "").split("\n")[0])
        who = speaker_name(row)
        line = first if first.lower().startswith(who.lower()) else f"{who}: {first}"
        return line[:DICE_MAX]
    if kind in ("ic", "ooc"):
        return f"{speaker_name(row)}: {text}"[:SPOKEN_MAX]
    return text[:SPOKEN_MAX]


# ---------------------------------------------------------------------------------------------
# Read along (0.22): roll requests and dice said in the listener's language, text in chunks.

ROLL_TAG_RE = re.compile(r"\[\[roll:\s*([^\]\n]+?)\s*\]\]")

WORDS = {
    "en": {"roll": "Roll", "plus": "plus", "die": "die", "dice": "dice", "hunger": "Hunger",
           "difficulty": "difficulty", "specialty": "specialty", "success": "success",
           "successes": "successes", "critical": "critical win", "messy": "messy critical",
           "bestial": "bestial failure", "total": "total failure", "botch": "botch",
           "win": "success", "fail": "failure", "reroll": "Willpower reroll"},
    "el": {"roll": "Ρίψη", "plus": "συν", "die": "ζάρι", "dice": "ζάρια", "hunger": "Πείνα",
           "difficulty": "δυσκολία", "specialty": "ειδίκευση", "success": "επιτυχία",
           "successes": "επιτυχίες", "critical": "κρίσιμη επιτυχία",
           "messy": "κρίσιμη επιτυχία με Πείνα", "bestial": "κτηνώδης αποτυχία",
           "total": "ολική αποτυχία", "botch": "καταστροφική αποτυχία", "win": "επιτυχία",
           "fail": "αποτυχία", "reroll": "νέα ρίψη με Willpower"},
}


def parse_roll_tag(body: str) -> Optional[Dict[str, Any]]:
    """A canonical tag body (services/dice_pools.apply_roll_tags) -> request, as the app's
    rollRequests.js parseRollTag; None when it is not a resolved one."""
    parts = [p.strip() for p in str(body or "").split("|") if p.strip()]
    if len(parts) < 2:
        return None
    req: Dict[str, Any] = {"label": parts[0], "pool": None, "hunger": None, "difficulty": None, "specialty": None}
    for p in parts[1:]:
        m = re.match(r"^(\d+) dice$", p, re.I)
        if m:
            req["pool"] = int(m.group(1))
            continue
        m = re.match(r"^(\d+) hunger$", p, re.I)
        if m:
            req["hunger"] = int(m.group(1))
            continue
        m = re.match(r"^difficulty (\d+)$", p, re.I)
        if m:
            req["difficulty"] = int(m.group(1))
            continue
        m = re.match(r"^specialty (.+)$", p, re.I)
        if m:
            req["specialty"] = m.group(1)
    if req["pool"] is None:
        return None
    return req


def roll_requests(text: Any) -> list:
    out = []
    for m in ROLL_TAG_RE.finditer(str(text or "")):
        r = parse_roll_tag(m.group(1))
        if r:
            out.append(r)
    return out


def strip_roll_tags(text: Any) -> str:
    """Each resolved tag becomes its label (the prose still reads); unresolved tags go."""
    def repl(m):
        r = parse_roll_tag(m.group(1))
        return f"**{r['label']}**" if r else ""
    return ROLL_TAG_RE.sub(repl, str(text or ""))


def _w(lang: str) -> Dict[str, str]:
    return WORDS["el" if lang == "el" else "en"]


def _say_label(label: Any, lang: str) -> str:
    """Trait names stay English (game terms, frontend/src/i18n/glossary.jsx); '+' is said."""
    return re.sub(r"\s*\+\s*", f" {_w(lang)['plus']} ", plain_text(label)).strip()


def _dice(n: int, lang: str) -> str:
    w = _w(lang)
    return f"{n} {w['die'] if n == 1 else w['dice']}"


def roll_request_sentence(req: Dict[str, Any], lang: str) -> str:
    """'Roll: Intelligence plus Investigation, 7 dice, 1 Hunger, difficulty 2.' in `lang`."""
    w = _w(lang)
    bits = [f"{w['roll']}: {_say_label(req.get('label'), lang)}"]
    if req.get("specialty"):
        bits.append(f"{w['specialty']} {plain_text(req['specialty'])}")
    bits.append(_dice(int(req.get("pool") or 0), lang))
    if req.get("hunger"):
        bits.append(f"{int(req['hunger'])} {w['hunger']}")
    if req.get("difficulty") is not None:
        bits.append(f"{w['difficulty']} {int(req['difficulty'])}")
    return ", ".join(bits) + "."


def roll_reason(content: Any) -> tuple:
    """(reason, reroll) from the server's roll line ('… rolls (V5) for **Brawl**')."""
    first = str(content or "").split("\n")[0]
    m = re.search(r"\bfor \*\*(.+?)\*\*\s*$", first)
    reason = m.group(1).strip() if m else ""
    reroll = bool(re.search(r"\s*\(Willpower reroll\)$", reason))
    reason = re.sub(r"\s*\(Willpower reroll\)$", "", reason).strip()
    return ("" if reason == "Dice roll" else reason), reroll


def _outcome(marker: Dict[str, Any]) -> str:
    v5 = str(marker.get("rules_edition") or "").lower() == "v5"
    succ = int(marker.get("successes") or 0)
    if v5:
        if marker.get("is_messy_critical"):
            return "messy"
        if marker.get("is_critical") or marker.get("isCritical"):
            return "critical"
        if marker.get("is_bestial_failure"):
            return "bestial"
        if marker.get("is_total_failure"):
            return "total"
        diff = marker.get("difficulty")
        return "win" if succ >= int(diff if diff not in (None, "") else 1) and succ > 0 else "fail"
    if marker.get("is_botch") or marker.get("isBotch"):
        return "botch"
    return "win" if succ > 0 else "fail"


def dice_sentence(who: str, content: Any, marker: Dict[str, Any], lang: str) -> str:
    """'Mira: Roll Brawl, 7 dice, 4 successes, critical win.' in `lang`, from the roll's marker."""
    w = _w(lang)
    reason, reroll = roll_reason(content)
    dice_list = marker.get("dice_preview") or marker.get("diceFinal") or []
    pool = int(marker.get("pool_size") or marker.get("poolSize") or len(dice_list) or 0)
    succ = int(marker.get("successes") or 0)
    head = f"{who}: {w['roll']}" + (f" {_say_label(reason, lang)}" if reason else "")
    bits = [head]
    if reroll:
        bits.append(w["reroll"])
    bits.append(_dice(pool, lang))
    bits.append(f"{succ} {w['success'] if succ == 1 else w['successes']}")
    bits.append(w[_outcome(marker)])
    return ", ".join(bits)[:DICE_MAX] + "."


_SPLIT = re.compile(r"([.!?…;·\u037e]+[\"'”»’)\]]*)\s+|\n+")
SHORT = 60


def split_chunks(text: Any, cap: int = CHUNK_MAX) -> list:
    """Sentences (Greek and English punctuation, closing quotes kept), short ones joined up to
    SHORT chars, long ones cut at a comma or a space; every chunk at most `cap` chars."""
    s = str(text or "").strip()
    sents, cur = [], ""
    pos = 0
    for m in _SPLIT.finditer(s):
        piece = s[pos:m.start()] + (m.group(1) or "")
        pos = m.end()
        if piece.strip():
            sents.append(piece.strip())
    if s[pos:].strip():
        sents.append(s[pos:].strip())
    out = []
    for sent in sents:
        while len(sent) > cap:
            cut = sent.rfind(", ", 0, cap)
            cut = cut + 1 if cut > cap // 3 else sent.rfind(" ", 0, cap)
            cut = cut if cut > 0 else cap
            if cur:
                out.append(cur)
                cur = ""
            out.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if cur and (len(cur) >= SHORT or len(cur) + 1 + len(sent) > cap):
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def spoken_parts(row: Dict[str, Any], kind: str, listen_lang: str = "en",
                 marker: Optional[Dict[str, Any]] = None, roll_source: Any = None) -> list:
    """[{text, lang}] in reading order: the message in chunks in its own language, then each roll
    the Storyteller asks for, and dice lines, in the listener's language (never English chip text
    in the Greek voice). roll_source: the text the roll tags come from (the original when `row`
    carries a translation)."""
    ll = "el" if listen_lang == "el" else "en"
    if kind == "dice":
        if isinstance(marker, dict):
            return [{"text": dice_sentence(speaker_name(row), row.get("content"), marker, ll), "lang": ll}]
        text = spoken_text(row, kind)
        return [{"text": text, "lang": guess_lang(text)}] if text else []
    lang = guess_lang(ROLL_TAG_RE.sub(" ", str(row.get("content") or "")))  # the tags are English
    parts = [{"text": c, "lang": lang} for c in split_chunks(spoken_text(row, kind))]
    if kind == "storyteller":
        src = row.get("content") if roll_source is None else roll_source
        parts += [{"text": roll_request_sentence(r, ll), "lang": ll} for r in roll_requests(src)]
    return parts


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
                voice_override: Any = None, chunk: int = 0, **kw) -> Optional[Dict[str, Any]]:
    """The body for the speech service's POST /tts for one chunk, or None (never spoken / no such chunk)."""
    bodies = tts_bodies(row, gender, user_settings, campaign_settings, voice_override, **kw)
    return bodies[chunk] if 0 <= chunk < len(bodies) else None


def tts_bodies(row: Dict[str, Any], gender: Any, user_settings: Any, campaign_settings: Any,
               voice_override: Any = None, listen_lang: str = "en", marker: Any = None,
               roll_source: Any = None) -> list:
    """One POST /tts body per chunk (each in its own language's voice); [] when never spoken."""
    kind = readout_kind(row)
    if not kind:
        return []
    return [_body(kind, p["text"], p["lang"], gender, user_settings, campaign_settings, voice_override)
            for p in spoken_parts(row, kind, listen_lang, marker, roll_source) if p["text"]]


def _body(kind, text, lang, gender, user_settings, campaign_settings, voice_override):
    u = normalize_user_voice_settings(user_settings)
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
