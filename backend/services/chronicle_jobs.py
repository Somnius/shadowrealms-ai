"""
"The chronicle so far" (docs/CHRONICLE.md): the database side and the writer jobs.

- Reading: rows per view, facts, stored chapters and digests.
- Jobs: created by Update, claimed by a daemon thread in any gunicorn worker with
  SELECT ... FOR UPDATE SKIP LOCKED plus a per-chronicle advisory lock, run one night at a time.
  The writer only starts after a quiet window (no message in that chronicle for
  CHRONICLE_QUIET_MINUTES, default 10) and waits while a Storyteller reply is being written.
- Progress lives in the job row, written at most every 1.5 s (and at each night and at the end),
  so the panel can poll it from either worker.
- Partial runs: at most MAX_NIGHTS_PER_RUN nights per job; the next Update carries on.

The model is called through ai_roles.generate_for_role with the chronicler role of the chronicle's
language, streaming (on_token) so the panel shows tokens as they come; a context overflow is never
trimmed: the night is split and written again.
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Set

from services import chronicle_digest as cd

logger = logging.getLogger(__name__)

MAX_NIGHTS_PER_RUN = 40
UPDATE_EVERY_S = 300
REWRITE_ALL_EVERY_S = 3600
PROGRESS_EVERY_S = 1.5
STALE_JOB_S = 60
FALLBACK_SECONDS_PER_NIGHT = 6.0
ACTIVE = ("queued", "waiting", "running")
ADVISORY_CLASS = 7317  # pg_advisory_lock(class, campaign_id): one writer per chronicle

_LOBBY_NAMES = ("out of character lobby", "ooc lobby", "ooc chat", "💬 ooc chat", "out of character")


def _envf(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name) or default)
    except ValueError:
        return default


def quiet_seconds() -> float:
    return _envf("CHRONICLE_QUIET_MINUTES", 10) * 60


def overflow_wait_seconds() -> float:
    return _envf("CHRONICLE_OVERFLOW_WAIT_S", 30)


def _pg() -> bool:
    return os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql"


def _dt(v) -> Optional[datetime]:
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", ""))
    except ValueError:
        return None


def _bool(v, default=True) -> bool:
    if v is None:
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("1", "t", "true", "yes")
    return bool(v)


# ---------------------------------------------------------------------------------------------
# Reading the chronicle

def campaign_row(cursor, campaign_id: int) -> Optional[Dict[str, Any]]:
    cursor.execute(
        "SELECT id, name, created_by, rules_edition, language FROM campaigns WHERE id = %s", (campaign_id,)
    )
    return cursor.fetchone()


def lobby_ids(cursor, campaign_id: int, rooms: Sequence[Dict[str, Any]]) -> Set[int]:
    out = set()
    for r in rooms:
        name = str(r.get("name") or "").strip().lower()
        if str(r.get("type") or "").strip().lower() == "ooc" or name in _LOBBY_NAMES or name.startswith("out of character"):
            out.add(int(r["id"]))
    return out


def load_rows(cursor, campaign_id: int) -> List[Dict[str, Any]]:
    """Every message of the chronicle as a chronicle_digest row (the Storyteller's view, flagged per player view)."""
    from services.location_access import readable_location_ids
    from services.message_actions import hidden_dice_sql_filter

    cursor.execute(
        'SELECT id, name, "type" AS type, description, is_open, is_active FROM locations WHERE campaign_id = %s',
        (campaign_id,),
    )
    rooms = cursor.fetchall()
    readable = readable_location_ids(rooms, False)
    lobby = lobby_ids(cursor, campaign_id, rooms)
    by_id = {int(r["id"]): r for r in rooms}
    cursor.execute(
        "SELECT m.id FROM messages m WHERE m.campaign_id = %s" + hidden_dice_sql_filter("m.ai_message_kind"),
        (campaign_id,),
    )
    shown = {int(r["id"]) for r in cursor.fetchall()}
    cursor.execute(
        """
        SELECT m.id, m.location_id, m.user_id, m.created_at, m.message_type, m.role, m.ai_message_kind,
               m.speaker_mode, m.content, m.lang, c.name AS character_name, camp.created_by
        FROM messages m
        JOIN campaigns camp ON camp.id = m.campaign_id
        LEFT JOIN characters c ON c.id = m.character_id
        WHERE m.campaign_id = %s
        ORDER BY m.id
        """,
        (campaign_id,),
    )
    out = []
    for r in cursor.fetchall():
        lid = int(r["location_id"])
        room = by_id.get(lid) or {}
        out.append({
            "id": int(r["id"]),
            "location_id": lid,
            "room": room.get("name") or "",
            "room_kind": "lobby" if lid in lobby else "story",
            "room_readable": lid in readable,
            "created_at": _dt(r.get("created_at")),
            "message_type": r.get("message_type"),
            "role": r.get("role"),
            "ai_message_kind": r.get("ai_message_kind"),
            "speaker_mode": r.get("speaker_mode"),
            "character_name": r.get("character_name"),
            "staff_kind": "storyteller" if str(r.get("user_id")) == str(r.get("created_by")) else "staff",
            "content": r.get("content"),
            "lang": r.get("lang"),
            "player_visible": int(r["id"]) in shown and lid in readable,
        })
    return out


def session_marks(cursor, campaign_id: int) -> Set[int]:
    try:
        cursor.execute("SELECT message_id FROM chronicle_session_marks WHERE campaign_id = %s", (campaign_id,))
        return {int(r["message_id"]) for r in cursor.fetchall()}
    except Exception:  # noqa: BLE001 - before the table exists
        _rollback(cursor)
        return set()


def _rollback(cursor):
    try:
        cursor.connection.rollback()
    except Exception:  # noqa: BLE001
        pass


def cast_names(cursor, campaign_id: int) -> List[str]:
    names = []
    for table in ("characters", "npcs"):
        try:
            cursor.execute(f"SELECT name FROM {table} WHERE campaign_id = %s", (campaign_id,))
            names += [str(r["name"]) for r in cursor.fetchall() if r.get("name")]
        except Exception:  # noqa: BLE001
            _rollback(cursor)
    return names


_TRANSLIT = str.maketrans({
    "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "i", "θ": "th", "ι": "i", "κ": "k",
    "λ": "l", "μ": "m", "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t",
    "υ": "y", "φ": "f", "χ": "ch", "ψ": "ps", "ω": "o",
})


def _latin_key(name: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFD", name.casefold())
    s = "".join(c for c in s if not unicodedata.combining(c)).translate(_TRANSLIT)
    s = s.replace("ou", "u").replace("y", "i").replace("h", "")
    return "".join(c for c in s if c.isalnum())


def spelling_names(cursor, campaign_id: int, lang: str) -> List[str]:
    """
    The exact spellings the writer must use: characters, NPCs and rooms (translation.chronicle_names).
    When the data holds one name in both alphabets ("Maro" and «Μαρώ»), only the form in the
    chronicle's language is kept.
    """
    from services.translation import chronicle_names

    names = list(dict.fromkeys(n.strip() for n in chronicle_names(cursor, campaign_id) + cast_names(cursor, campaign_id)
                               if n and n.strip()))
    groups: Dict[str, List[str]] = {}
    for n in names:
        groups.setdefault(_latin_key(n), []).append(n)
    out = []
    for n in names:
        same = groups.get(_latin_key(n)) or [n]
        if len(same) > 1:
            mine = [x for x in same if (cd.greek_share(x) >= 0.5) == (lang == "el")]
            if mine and n not in mine:
                continue
        out.append(n)
    return out


def room_names(cursor, campaign_id: int) -> List[str]:
    cursor.execute("SELECT name FROM locations WHERE campaign_id = %s", (campaign_id,))
    return [str(r["name"]) for r in cursor.fetchall() if r.get("name")]


def chronicle_lang(cursor, campaign: Dict[str, Any], rows: Optional[List[Dict[str, Any]]] = None) -> str:
    if campaign.get("language") in cd.LANGS:
        return campaign["language"]
    if rows is None:
        cursor.execute(
            "SELECT lang, content, message_type, role, ai_message_kind, speaker_mode FROM messages "
            "WHERE campaign_id = %s ORDER BY id DESC LIMIT 500",
            (campaign["id"],),
        )
        rows = cursor.fetchall()
    story = [r for r in rows if cd._kind({**r, "character_name": "x"}) == "story"]
    return cd.chronicle_language(None, story)


def edition_name(rules_edition: Optional[str]) -> str:
    return "Vampire: The Masquerade V5" if str(rules_edition or "").lower() == "v5" else "Vampire: The Masquerade (Revised)"


def facts(cursor, campaign: Dict[str, Any], view: str, readable_rooms: Optional[Set[int]] = None,
          chapters: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Heading facts from the database, never from the model. Usernames only in the Storyteller's view.
    Outside it, an NPC is listed only when a visible night names it (chapters), else not at all.
    """
    cid = campaign["id"]
    cast = []
    cursor.execute(
        """
        SELECT c.name, c.wod_meta, u.username FROM characters c LEFT JOIN users u ON u.id = c.user_id
        WHERE c.campaign_id = %s ORDER BY c.name
        """,
        (cid,),
    )
    for r in cursor.fetchall():
        clan = None
        try:
            meta = json.loads(r.get("wod_meta") or "{}")
            clan = meta.get("clan") if isinstance(meta, dict) else None
        except (TypeError, ValueError):
            pass
        entry = {"name": r["name"], "clan": clan}
        if view == "st":
            entry["player"] = r.get("username")
        cast.append(entry)
    try:
        cursor.execute("SELECT name, type, faction FROM npcs WHERE campaign_id = %s ORDER BY name", (cid,))
        named = [c["name"] for ch in chapters or [] for c in (ch.get("chapter") or {}).get("characters") or []]
        for r in cursor.fetchall():
            if view != "st" and not any(cd._name_ok(n, [r["name"]]) for n in named):
                continue
            note = ", ".join(x for x in (r.get("type"), r.get("faction")) if x)
            cast.append({"name": r["name"], "npc": True, "note": note})
    except Exception:  # noqa: BLE001
        _rollback(cursor)
    cursor.execute(
        'SELECT id, name, "type" AS type, description, is_open, is_active FROM locations WHERE campaign_id = %s ORDER BY id',
        (cid,),
    )
    rooms_all = cursor.fetchall()
    lobby = lobby_ids(cursor, cid, rooms_all)
    rooms = []
    for r in rooms_all:
        if int(r["id"]) in lobby:
            continue
        if view != "st" and readable_rooms is not None and int(r["id"]) not in readable_rooms:
            continue
        rooms.append({"name": r["name"], "description": (r.get("description") or "")[:300]})
    return {"name": campaign.get("name"), "edition": edition_name(campaign.get("rules_edition")),
            "cast": cast, "rooms": rooms}


def stored_chapters(cursor, campaign_id: int, lang: str) -> List[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT ch.id, ch.location_id, ch.chapter_key, ch.kind, ch.first_message_id, ch.last_message_id,
               ch.started_at, ch.ended_at, ch.chapter, ch.source_hash, ch.model, ch.written_at,
               l.name AS room
        FROM chronicle_chapters ch LEFT JOIN locations l ON l.id = ch.location_id
        WHERE ch.campaign_id = %s AND ch.lang = %s
        ORDER BY ch.started_at, ch.first_message_id
        """,
        (campaign_id, lang),
    )
    out = []
    for r in cursor.fetchall():
        try:
            chapter = json.loads(r["chapter"])
        except (TypeError, ValueError):
            chapter = {}
        out.append({
            "row_id": r["id"], "key": r["chapter_key"], "location_id": int(r["location_id"]),
            "kind": r.get("kind") or "story", "first_id": r["first_message_id"], "last_id": r["last_message_id"],
            "started_at": _dt(r.get("started_at")), "ended_at": _dt(r.get("ended_at")),
            "chapter": chapter, "visibility": chapter.get("visibility", "all"),
            "ooc": chapter.get("ooc") or [], "source_hash": r["source_hash"], "model": r.get("model"),
            "written_at": _dt(r.get("written_at")), "room": r.get("room") or chapter.get("room") or "",
        })
    return out


def stored_digest(cursor, campaign_id: int, lang: str, kind: str = "final", era: int = 0,
                  translated: bool = False) -> Optional[Dict[str, Any]]:
    """The written digest (translated=False) or the cached translation into `lang` (translated=True)."""
    cursor.execute(
        "SELECT digest, source_hash, written_at, model, edited_markdown, edited_by, edited_at, edited_from_hash, "
        "translated_from FROM chronicle_digests WHERE campaign_id = %s AND kind = %s AND era = %s AND lang = %s",
        (campaign_id, kind, era, lang),
    )
    r = cursor.fetchone()
    if not r or bool(r.get("translated_from")) != translated:
        return None
    try:
        d = json.loads(r["digest"])
    except (TypeError, ValueError):
        return None
    d["_hash"] = r["source_hash"]
    d["_written_at"] = _dt(r.get("written_at"))
    d["_edited_markdown"] = r.get("edited_markdown")
    d["_edited_at"] = _dt(r.get("edited_at"))
    d["_edited_from"] = r.get("edited_from_hash")
    d["_translated_from"] = r.get("translated_from")
    return d


# ---------------------------------------------------------------------------------------------
# The Storyteller's edit copy (one Markdown text on the final digest row; the generated text is never touched)

EDIT_MAX_CHARS = 200_000


def edit_state(digest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """{'edited', 'newer', 'edited_at'}: newer = the digest was written again after the edit was based on it."""
    if not digest or not digest.get("_edited_markdown"):
        return {"edited": False, "newer": False, "edited_at": None}
    at = digest.get("_edited_at")
    return {"edited": True, "newer": digest.get("_edited_from") != digest.get("_hash"),
            "edited_at": at.isoformat() if at else None}


def save_edit(cursor, campaign_id: int, lang: str, markdown: Optional[str], user_id: int,
              keep: bool = False) -> bool:
    """Save (markdown), keep the edit over a newer digest (keep=True), or drop it (markdown None).
    False when there is no written digest to edit."""
    cursor.execute(
        "SELECT id, source_hash FROM chronicle_digests WHERE campaign_id = %s AND kind = 'final' AND era = 0 "
        "AND lang = %s AND translated_from IS NULL", (campaign_id, lang))
    row = cursor.fetchone()
    if not row:
        return False
    if keep:
        cursor.execute("UPDATE chronicle_digests SET edited_from_hash = %s WHERE id = %s", (row["source_hash"], row["id"]))
    elif markdown is None:
        cursor.execute("UPDATE chronicle_digests SET edited_markdown = NULL, edited_by = NULL, edited_at = NULL, "
                       "edited_from_hash = NULL WHERE id = %s", (row["id"],))
    else:
        cursor.execute("UPDATE chronicle_digests SET edited_markdown = %s, edited_by = %s, edited_at = %s, "
                       "edited_from_hash = %s WHERE id = %s",
                       (markdown, user_id, datetime.now(), row["source_hash"], row["id"]))
    return True


def message_ids(cursor, campaign_id: int) -> Set[int]:
    cursor.execute("SELECT id FROM messages WHERE campaign_id = %s", (campaign_id,))
    return {int(r["id"]) for r in cursor.fetchall()}


# ---------------------------------------------------------------------------------------------
# Planning a run

def plan(cursor, campaign_id: int, scope: str = "update", gap_hours: float = cd.GAP_HOURS) -> Dict[str, Any]:
    """Fresh chapters with their hashes, and which story nights need writing (no model calls)."""
    camp = campaign_row(cursor, campaign_id)
    rows = load_rows(cursor, campaign_id)
    lang = chronicle_lang(cursor, camp, rows)
    names = spelling_names(cursor, campaign_id, lang)
    flags = cd.roll_flags(rows)
    chapters = cd.cut_chapters(rows, gap_hours, session_marks(cursor, campaign_id))
    stored = {c["key"]: c for c in stored_chapters(cursor, campaign_id, lang)}
    stale, story = [], []
    for ch in chapters:
        mat = cd.chapter_material(ch, lang, flags)
        ch["material"] = mat
        ch["hash"] = cd.chapter_hash(ch, mat, lang, names)
        if ch["kind"] != "story":
            continue
        if not mat["lines"]:
            ch["empty"] = True
            continue
        story.append(ch)
        old = stored.get(ch["key"])
        if scope == "all" or not old or old["source_hash"] != ch["hash"]:
            stale.append(ch)
    return {"campaign": camp, "lang": lang, "names": names, "rows": rows, "chapters": chapters,
            "story": story, "stale": stale, "stored": stored,
            "story_messages": cd.story_message_count(rows)}


def seconds_per_night(cursor) -> float:
    """Median of the last 10 finished jobs (any chronicle: it's the machine's speed), else 6 s."""
    try:
        cursor.execute(
            "SELECT seconds_per_night FROM chronicle_jobs WHERE seconds_per_night IS NOT NULL "
            "AND status IN ('done', 'partial') ORDER BY id DESC LIMIT 10"
        )
        vals = [float(r["seconds_per_night"]) for r in cursor.fetchall() if r.get("seconds_per_night")]
    except Exception:  # noqa: BLE001
        _rollback(cursor)
        vals = []
    return statistics.median(vals) if vals else FALLBACK_SECONDS_PER_NIGHT


def changed_eras(p: Dict[str, Any], todo: Sequence[Dict[str, Any]]) -> int:
    """Era digests the run rewrites: the eras that hold a night being written."""
    pos = {c["key"]: i for i, c in enumerate(p["story"])}
    return len({pos[c["key"]] // cd.ERA_SIZE for c in todo if c["key"] in pos})


def estimate_seconds(nights: int, eras: int, spn: float) -> int:
    """Nights to write, the eras that change and the final join, at spn seconds a call."""
    return int(round((nights + eras + 1) * spn)) if nights else 0


def estimate(cursor, campaign_id: int, scope: str = "update") -> Dict[str, Any]:
    p = plan(cursor, campaign_id, scope)
    stale = len(p["stale"])
    nights = min(stale, MAX_NIGHTS_PER_RUN)
    spn = seconds_per_night(cursor)
    return {
        "lang": p["lang"], "nights_to_write": nights, "nights_stale": stale, "nights_total": len(p["story"]),
        "capped": stale > MAX_NIGHTS_PER_RUN, "max_nights": MAX_NIGHTS_PER_RUN,
        "seconds": estimate_seconds(nights, changed_eras(p, p["stale"][:nights]), spn), "seconds_per_night": round(spn, 1),
        "quiet_minutes": round(quiet_seconds() / 60),
        "story_messages": p["story_messages"], "enough": p["story_messages"] >= cd.MIN_STORY_MESSAGES,
    }


# ---------------------------------------------------------------------------------------------
# Jobs: create, read, cancel

JOB_FIELDS = ("id", "campaign_id", "scope", "lang", "status", "phase", "night", "nights", "nights_total",
              "nights_done", "tokens_night", "tokens_total", "tok_per_s", "eta_s", "error", "created_at",
              "started_at", "updated_at", "finished_at", "cancel_requested")


def job_json(r: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not r:
        return None
    out = {k: r.get(k) for k in JOB_FIELDS}
    for k in ("created_at", "started_at", "updated_at", "finished_at"):
        v = _dt(out.get(k))
        out[k] = v.isoformat() if v else None
    out["cancel_requested"] = _bool(out.get("cancel_requested"), False)
    started = _dt(r.get("started_at"))
    end = _dt(r.get("finished_at")) or datetime.now()
    out["elapsed_s"] = int((end - started).total_seconds()) if started else 0
    return out


def get_job(cursor, campaign_id: int, job_id: int) -> Optional[Dict[str, Any]]:
    cursor.execute("SELECT * FROM chronicle_jobs WHERE id = %s AND campaign_id = %s", (job_id, campaign_id))
    return cursor.fetchone()


def latest_job(cursor, campaign_id: int) -> Optional[Dict[str, Any]]:
    cursor.execute("SELECT * FROM chronicle_jobs WHERE campaign_id = %s ORDER BY id DESC LIMIT 1", (campaign_id,))
    return cursor.fetchone()


class JobRefused(Exception):
    def __init__(self, code: str, status: int, retry_after: int = 0):
        super().__init__(code)
        self.code, self.status, self.retry_after = code, status, retry_after


def create_job(cursor, campaign_id: int, user_id: int, scope: str = "update",
               now: Optional[datetime] = None, lang: Optional[str] = None) -> int:
    """One job per chronicle; Update at most every 5 minutes, Rewrite everything once an hour, a
    translation (scope 'translate', into `lang`) at most every 5 minutes."""
    now = now or datetime.now()
    if scope not in ("update", "all", "translate"):
        raise JobRefused("bad_scope", 400)
    if scope == "translate" and lang not in cd.LANGS:
        raise JobRefused("bad_lang", 400)
    cursor.execute(
        "SELECT id FROM chronicle_jobs WHERE campaign_id = %s AND status IN ('queued', 'waiting', 'running')",
        (campaign_id,),
    )
    if cursor.fetchone():
        raise JobRefused("job_running", 409)
    every = REWRITE_ALL_EVERY_S if scope == "all" else UPDATE_EVERY_S
    cursor.execute(
        "SELECT created_at FROM chronicle_jobs WHERE campaign_id = %s AND (scope = %s OR %s = 'update') "
        "AND status NOT IN ('cancelled', 'failed') ORDER BY id DESC LIMIT 1",
        (campaign_id, scope, scope),
    )
    last = cursor.fetchone()
    if last and _dt(last["created_at"]):
        left = every - (now - _dt(last["created_at"])).total_seconds()
        if left > 0:
            raise JobRefused("too_soon", 429, int(left) + 1)
    cursor.execute(
        "INSERT INTO chronicle_jobs (campaign_id, requested_by, scope, lang, status, phase, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, 'queued', 'waiting', %s, %s) RETURNING id",
        (campaign_id, user_id, scope, lang if scope == "translate" else None, now, now),
    )
    return int(cursor.fetchone()["id"])


def cancel_job(cursor, campaign_id: int, job_id: int) -> bool:
    """Queued or waiting jobs end at once; a running one stops at the next token (the stream is closed)."""
    now = datetime.now()
    cursor.execute(
        "UPDATE chronicle_jobs SET status = 'cancelled', finished_at = %s, updated_at = %s "
        "WHERE id = %s AND campaign_id = %s AND status IN ('queued', 'waiting')",
        (now, now, job_id, campaign_id),
    )
    if cursor.rowcount:
        return True
    cursor.execute(
        "UPDATE chronicle_jobs SET cancel_requested = TRUE, updated_at = updated_at "
        "WHERE id = %s AND campaign_id = %s AND status = 'running'",
        (job_id, campaign_id),
    )
    return bool(cursor.rowcount)


# ---------------------------------------------------------------------------------------------
# Progress

class Progress:
    """In memory; written to the job row at most every PROGRESS_EVERY_S (forced at each night and at the end)."""

    def __init__(self, conn, job_id: int, clock: Callable[[], float] = time.monotonic):
        self.conn, self.job_id, self.clock = conn, job_id, clock
        self.fields: Dict[str, Any] = {"tokens_night": 0, "tokens_total": 0, "night": 0, "nights": 0}
        self.last_write = -1e9
        self.window: deque = deque()
        self.cancelled = False
        self.eta: Optional[int] = None

    def set(self, **kw):
        self.fields.update(kw)

    def set_eta(self, seconds: Optional[float]):
        """Refined after each night, never jumps up."""
        if seconds is None:
            return
        s = max(0, int(round(seconds)))
        self.eta = s if self.eta is None else min(self.eta, s)
        self.fields["eta_s"] = self.eta

    def token(self, n: int = 1):
        now = self.clock()
        self.fields["tokens_night"] += n
        self.fields["tokens_total"] += n
        self.window.append((now, n))
        while self.window and now - self.window[0][0] > 2.0:
            self.window.popleft()
        span = now - self.window[0][0] if len(self.window) > 1 else 0
        if span > 0.2:
            self.fields["tok_per_s"] = round(sum(k for _, k in self.window) / span, 1)

    def tick(self, force: bool = False) -> bool:
        """Writes when due; returns False once a cancel was asked for."""
        now = self.clock()
        if not force and now - self.last_write < PROGRESS_EVERY_S:
            return not self.cancelled
        self.last_write = now
        cols = [k for k in self.fields]
        sets = ", ".join(f"{k} = %s" for k in cols)
        cur = self.conn.cursor()
        try:
            cur.execute(
                f"UPDATE chronicle_jobs SET {sets}, updated_at = %s WHERE id = %s RETURNING cancel_requested, status",
                [self.fields[k] for k in cols] + [datetime.now(), self.job_id],
            )
            row = cur.fetchone()
            self.conn.commit()
        except Exception as e:  # noqa: BLE001
            logger.warning("chronicle job %s: progress write failed: %s", self.job_id, e)
            try:
                self.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            return not self.cancelled
        if row is None or _bool(row.get("cancel_requested"), False) or row.get("status") == "cancelled":
            self.cancelled = True
        return not self.cancelled


def is_length_cut(err) -> bool:
    """The answer stopped at max_tokens (finish_reason "length"): write the night in halves."""
    return "finish_reason=length" in str(err or "")


class JobCancelled(Exception):
    pass


class NightFailed(Exception):
    pass


# ---------------------------------------------------------------------------------------------
# Running a job

def default_generate(role, messages, params, **kw):
    from services.ai_roles import generate_for_role

    return generate_for_role(role, messages, params, **kw)


def context_tokens() -> int:
    """The chronicler's context: CHRONICLE_CONTEXT_TOKENS, else the loaded LM Studio model's, else 8192."""
    v = os.environ.get("CHRONICLE_CONTEXT_TOKENS")
    if v:
        try:
            return int(v)
        except ValueError:
            pass
    try:
        from services.ai_roles import _loaded_lm_studio_context

        return _loaded_lm_studio_context() or 8192
    except Exception:  # noqa: BLE001
        return 8192


def storyteller_reserve() -> int:
    try:
        return int(os.environ.get("STORYTELLER_CONTEXT_TOKENS") or 8192)
    except ValueError:
        return 8192


class Runner:
    """Writes one job. `generate` and `sleep` are injectable for tests (a fake model, no waiting)."""

    def __init__(self, conn, job: Dict[str, Any], generate=default_generate, sleep=time.sleep,
                 busy: Optional[Callable[[], bool]] = None, ctx_tokens: Optional[int] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.conn, self.job = conn, job
        self.cid = int(job["campaign_id"])
        self.generate, self.sleep, self.clock = generate, sleep, clock
        self.busy = busy or (lambda: False)
        self.ctx = ctx_tokens or context_tokens()
        self.progress = Progress(conn, int(job["id"]), clock)
        self.model = None

    # -- model calls ---------------------------------------------------------------------------

    def _call(self, messages, max_tokens, schema_name, schema):
        waited = 0.0
        while self.busy() and waited < 60:  # live play first
            self.progress.set(phase=self.progress.fields.get("phase") or "writing")
            if not self.progress.tick(force=True):
                raise JobCancelled()
            self.sleep(2)
            waited += 2

        def on_token(delta, usage):
            if usage is not None:
                if usage.get("completion_tokens"):
                    # exact count from the final usage chunk
                    diff = int(usage["completion_tokens"]) - self._night_stream
                    if diff:
                        self.progress.fields["tokens_night"] += diff
                        self.progress.fields["tokens_total"] += diff
                return self.progress.tick(force=True)
            self._night_stream += 1
            self.progress.token(1)
            return self.progress.tick()

        self._night_stream = 0
        role = "chronicler_el" if self.lang == "el" else "chronicler_en"
        params = {"max_tokens": max_tokens, "temperature": 0.1, "timeout": 300,
                  "response_format": cd.response_format(schema_name, schema), "on_token": on_token,
                  "stream_idle_timeout": 60}
        from services.ai_providers import Cancelled

        try:
            res = self.generate(role, messages, params, shrink=False)
        except Cancelled:
            raise JobCancelled()
        if self.progress.cancelled:
            raise JobCancelled()
        self.model = res.get("model") or self.model
        return res["text"]

    def _write_part(self, ch, lines, split_left=1):
        from services.ai_providers import ProviderError
        from services.storyteller_prompt import is_context_overflow

        msgs = cd.chapter_messages(self.lang, ch["room"], ch["started_at"], lines, self.names, self.edition)
        try:
            raw = self._call(msgs, cd.CHAPTER_MAX_TOKENS, "chapter", cd.CHAPTER_SCHEMA)
        except ProviderError as e:
            cut = is_length_cut(e)
            if not (cut or is_context_overflow(e)) or split_left <= 0 or len(lines) < 2:
                logger.warning("chronicle %s: night %s failed: %s", self.cid, ch["key"], e)
                raise NightFailed("context" if is_context_overflow(e) else "model_failed") from e
            if not cut:  # the context is full (maybe a live Storyteller prompt): wait, then smaller
                logger.warning("chronicle %s: context exceeded on %s; waiting, then splitting the night", self.cid, ch["key"])
                self._wait(overflow_wait_seconds())
            return cd.merge_parts([self._write_part(ch, h, split_left - 1) for h in cd.halve(lines)])
        ids = [ln["id"] for ln in lines]
        chapter, problems = cd.check_chapter(raw, ids, self.names, self.lang, self.places)
        if problems:
            again = self._call(cd.retry_messages(msgs, raw, problems, self.lang), cd.CHAPTER_MAX_TOKENS, "chapter", cd.CHAPTER_SCHEMA)
            chapter2, problems2 = cd.check_chapter(again, ids, self.names, self.lang, self.places)
            if chapter2 is not None and (chapter is None or len(problems2) <= len(problems)):
                chapter, problems = chapter2, problems2
        if chapter is None:
            raise NightFailed("no_json")
        if "mixed_script" in problems:
            chapter = cd.strip_foreign(chapter)
        if "language" in problems:
            chapter = self._translate(chapter)
        return chapter

    def _title(self, ch, chapter):
        """A title that is the room's name or in the wrong language is asked for once more, alone;
        then a fixed one in the chronicle's language."""
        title = chapter.get("title", "")
        if not cd.title_problem(title, ch["room"], self.lang, self.names):
            return title
        try:
            raw = self._call(cd.title_messages(self.lang, ch["room"], chapter.get("summary") or []), 60,
                             "title", cd.TITLE_SCHEMA)
            again = cd._str(cd.parse_json(raw).get("title"))
            if not cd.title_problem(again, ch["room"], self.lang, self.names):
                return again
        except JobCancelled:
            raise
        except Exception as e:  # noqa: BLE001 - the fixed title will do
            logger.info("chronicle %s: title retry failed: %s", self.cid, e)
        return cd.fallback_title(ch["room"], ch.get("started_at"), self.lang)

    def _translate(self, chapter):
        """The night is in the wrong language after the retry: the translator role puts it into the
        chronicle's language (names protected, services/translation.py). If that fails it is kept and flagged."""
        from services import translation

        src = "en" if self.lang == "el" else "el"
        out = dict(chapter)

        def tr(text):
            if not text or not cd.language_problems(text, self.lang).count("language"):
                return text
            return translation.translate(text, src, self.lang, generate=self.generate, names=self.names)[0]

        try:
            out["title"] = tr(chapter.get("title", ""))
            out["summary"] = [tr(x) for x in chapter.get("summary") or []]
            for key in ("events", "threads_opened", "threads_closed"):
                out[key] = [{**e, "text": tr(e["text"])} for e in chapter.get(key) or []]
            for key in ("characters", "places"):
                out[key] = [{**e, "note": tr(e.get("note", ""))} for e in chapter.get(key) or []]
        except Exception as e:  # noqa: BLE001 - kept as written, and flagged
            logger.warning("chronicle %s: translating a night failed: %s", self.cid, e)
            flagged = dict(chapter)
            flagged["check"] = ["language"]
            return flagged
        out["translated"] = True
        return out

    def _wait(self, seconds):
        """Sleep in short steps, keeping the job row fresh (not stale) and honouring Cancel."""
        left = float(seconds)
        while left > 0:
            if not self.progress.tick(force=True):
                raise JobCancelled()
            step = min(2.0, left)
            self.sleep(step)
            left -= step

    def write_night(self, ch):
        mat = ch["material"]
        budget = cd.prompt_budget(self.ctx, cd.CHAPTER_MAX_TOKENS, storyteller_reserve())
        parts = [self._write_part(ch, p) for p in cd.split_lines(mat["lines"], budget)]
        chapter = cd.merge_parts(parts)
        chapter["title"] = self._title(ch, chapter)
        chapter["events"] = cd.inject_rolls(chapter.get("events") or [], mat["lines"], self.lang)
        if mat["hidden"]:
            raw = self._call(cd.notes_messages(self.lang, mat["hidden"], self.names), cd.NOTES_MAX_TOKENS,
                             "notes", cd.NOTES_SCHEMA)
            notes = cd.check_notes(raw, [ln["id"] for ln in mat["hidden"]])
            chapter["st_notes"] = cd.inject_rolls(notes, mat["hidden"], self.lang)
        chapter["visibility"] = ch["visibility"]
        chapter["room"] = ch["room"]
        chapter["ooc"] = mat["ooc"]
        return chapter

    # -- storage -------------------------------------------------------------------------------

    def _save_chapter(self, ch, chapter):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM chronicle_chapters WHERE campaign_id = %s AND chapter_key = %s AND lang = %s",
                    (self.cid, ch["key"], self.lang))
        cur.execute(
            """
            INSERT INTO chronicle_chapters (campaign_id, location_id, chapter_key, lang, kind, first_message_id,
                last_message_id, started_at, ended_at, chapter, source_hash, model, written_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (self.cid, ch["location_id"], ch["key"], self.lang, ch["kind"], ch["first_id"], ch["last_id"],
             ch["started_at"], ch["ended_at"], json.dumps(chapter, ensure_ascii=False), ch["hash"], self.model,
             datetime.now()),
        )
        self.conn.commit()

    def _save_digest(self, kind, era, digest, h, lang=None, translated_from=None):
        """Replaces the row; the Storyteller's edit copy on it is kept (never on a translation)."""
        lang = lang or self.lang
        cur = self.conn.cursor()
        cur.execute("SELECT edited_markdown, edited_by, edited_at, edited_from_hash, translated_from FROM chronicle_digests "
                    "WHERE campaign_id = %s AND kind = %s AND era = %s AND lang = %s", (self.cid, kind, era, lang))
        old = cur.fetchone() or {}
        if old.get("translated_from") or translated_from:
            old = {}
        cur.execute("DELETE FROM chronicle_digests WHERE campaign_id = %s AND kind = %s AND era = %s AND lang = %s",
                    (self.cid, kind, era, lang))
        cur.execute(
            "INSERT INTO chronicle_digests (campaign_id, kind, era, lang, digest, source_hash, model, written_at, "
            "edited_markdown, edited_by, edited_at, edited_from_hash, translated_from) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (self.cid, kind, era, lang, json.dumps(digest, ensure_ascii=False), h, self.model, datetime.now(),
             old.get("edited_markdown"), old.get("edited_by"), old.get("edited_at"), old.get("edited_from_hash"),
             translated_from),
        )
        self.conn.commit()

    def _sync_unwritten(self, plan_):
        """Lobby chapters (table talk only, no model call), fresh table talk on written nights, orphans removed."""
        cur = self.conn.cursor()
        fresh = {c["key"] for c in plan_["chapters"] if c["kind"] == "lobby" or not c.get("empty")}
        for key, old in plan_["stored"].items():
            if key not in fresh:
                cur.execute("DELETE FROM chronicle_chapters WHERE id = %s", (old["row_id"],))
        for ch in plan_["chapters"]:
            if ch["kind"] == "lobby":
                if ch["material"]["ooc"]:
                    self._save_chapter(ch, {"visibility": "all", "room": ch["room"], "ooc": ch["material"]["ooc"]})
                continue
            old = plan_["stored"].get(ch["key"])
            if old and not ch.get("empty") and old["ooc"] != ch["material"]["ooc"]:
                c = dict(old["chapter"])
                c["ooc"] = ch["material"]["ooc"]
                cur.execute("UPDATE chronicle_chapters SET chapter = %s WHERE id = %s",
                            (json.dumps(c, ensure_ascii=False), old["row_id"]))
        self.conn.commit()

    # -- digests -------------------------------------------------------------------------------

    def write_digests(self, total_nights):
        cur = self.conn.cursor()
        stored = [c for c in stored_chapters(cur, self.cid, self.lang) if c["kind"] == "story"]
        eras = cd.eras_of(stored)
        hashes = []
        self.progress.set(phase="eras")
        self.progress.tick(force=True)
        era_digests = []
        for i, era in enumerate(eras):
            h = cd.era_hash(era, self.lang)
            hashes.append(h)
            old = stored_digest(cur, self.cid, self.lang, "era", i)
            if old and old.get("_hash") == h:
                era_digests.append(old)
                continue
            shown = [(s, c) for s, c in era if c.get("visibility") != "st"]
            d = {"so_far": [], "threads_open": []}
            if shown:
                raw = self._call(cd.era_messages(self.lang, shown, self.names, self.edition), cd.ERA_MAX_TOKENS,
                                 "era", cd.ERA_SCHEMA)
                d = cd.check_era(raw) or d
            mat = cd.st_material(era, self.lang)
            if mat:
                d["st_so_far"] = cd.check_st(self._call(cd.st_messages(self.lang, mat), cd.NOTES_MAX_TOKENS, "st", cd.ST_SCHEMA))
            self._save_digest("era", i, d, h)
            era_digests.append(d)
        cur.execute("DELETE FROM chronicle_digests WHERE campaign_id = %s AND kind = 'era' AND lang = %s AND era >= %s",
                    (self.cid, self.lang, len(eras)))
        self.conn.commit()
        fh = cd.final_hash(hashes, self.lang)
        old = stored_digest(cur, self.cid, self.lang)
        rooms = sorted({c["location_id"] for c in stored if c.get("visibility") != "st"})
        if old and old.get("_hash") == fh:
            if old.get("nights_total") != total_nights:
                old["nights_total"] = total_nights
                self._save_digest("final", 0, {k: v for k, v in old.items() if not k.startswith("_")}, fh)
            return
        self.progress.set(phase="joining")
        self.progress.tick(force=True)
        final = self._join([e for e in era_digests if e.get("so_far")])
        st = [p for e in era_digests for p in e.get("st_so_far") or []]
        if st and len(eras) > 1:
            st = cd.check_st(self._call(cd.st_messages(self.lang, st), cd.NOTES_MAX_TOKENS, "st", cd.ST_SCHEMA)) or st
        final["st_so_far"] = st
        final["rooms"] = rooms
        final["nights_total"] = total_nights
        self._save_digest("final", 0, final, fh)

    def _join(self, eras):
        if not eras:
            return {"tldr": "", "so_far": [], "threads_open": []}
        while len(eras) > cd.MAX_ERAS_PER_JOIN:
            groups = [eras[i:i + cd.MAX_ERAS_PER_JOIN] for i in range(0, len(eras), cd.MAX_ERAS_PER_JOIN)]
            eras = [self._join_once(g) for g in groups]
        return self._join_once(eras)

    def _join_once(self, eras):
        raw = self._call(cd.final_messages(self.lang, eras, self.names, self.edition), cd.JOIN_MAX_TOKENS,
                         "digest", cd.FINAL_SCHEMA)
        d = cd.check_era(raw)
        if not d:
            d = {"so_far": [p for e in eras for p in e["so_far"]],
                 "threads_open": [t for e in eras for t in e.get("threads_open") or []]}
        d.setdefault("tldr", "")
        return d

    # -- the run -------------------------------------------------------------------------------

    def run(self) -> str:
        cur = self.conn.cursor()
        scope = self.job.get("scope") or "update"
        if scope == "translate":
            return self.run_translate()
        p = plan(cur, self.cid, scope)
        self.lang, self.names = p["lang"], p["names"]
        self.places = room_names(cur, self.cid)
        self.edition = edition_name((p["campaign"] or {}).get("rules_edition"))
        todo = p["stale"][:MAX_NIGHTS_PER_RUN]
        spn = seconds_per_night(cur)
        self.progress.set(lang=self.lang, phase="writing", nights=len(todo), nights_total=len(p["stale"]),
                          nights_done=0, night=0)
        eras = changed_eras(p, todo)
        self.progress.set_eta(estimate_seconds(len(todo), eras, spn))
        self.progress.tick(force=True)
        if p["story_messages"] < cd.MIN_STORY_MESSAGES:
            self._sync_unwritten(p)
            return "done"
        if scope == "all":
            cur.execute("UPDATE chronicle_chapters SET source_hash = 'stale' WHERE campaign_id = %s", (self.cid,))
            self.conn.commit()
        t0 = self.clock()
        for n, ch in enumerate(todo, 1):
            self.progress.set(night=n, tokens_night=0, tok_per_s=None)
            if not self.progress.tick(force=True):
                raise JobCancelled()
            chapter = self.write_night(ch)
            self._save_chapter(ch, chapter)
            done_s = self.clock() - t0
            per = done_s / n
            self.progress.set(nights_done=n)
            self.progress.set_eta(estimate_seconds(len(todo) - n, eras, per) if n < len(todo) else (eras + 1) * per)
            self.progress.tick(force=True)
        if todo:
            self.progress.set(seconds_per_night=round((self.clock() - t0) / len(todo), 2))
        self._sync_unwritten(p)
        self.write_digests(len(p["story"]))
        return "partial" if len(p["stale"]) > len(todo) else "done"


    # -- translation of the finished digest (the translator role, names protected) --------------

    def run_translate(self) -> str:
        from services import translation

        cur = self.conn.cursor()
        camp = campaign_row(cur, self.cid)
        src = chronicle_lang(cur, camp)
        dst = self.job.get("lang")
        if dst not in cd.LANGS or dst == src:
            raise NightFailed("bad_lang")
        self.lang = src
        digest = stored_digest(cur, self.cid, src)
        if not digest:
            raise NightFailed("no_digest")
        chapters = [c for c in stored_chapters(cur, self.cid, src) if c["kind"] == "story"]
        texts = cd.translation_texts(digest, chapters)
        todo = [i for i, t in enumerate(texts) if t and t.strip()]
        names = translation.chronicle_names(cur, self.cid)
        self.progress.set(lang=dst, phase="translating", nights=len(todo), nights_total=len(todo), nights_done=0,
                          night=0)
        self.progress.set_eta(len(todo) * TRANSLATE_SECONDS_PER_TEXT)
        self.progress.tick(force=True)
        out = list(texts)
        failed = 0
        t0 = self.clock()
        for n, i in enumerate(todo, 1):
            self._wait_for_play()
            self.progress.set(night=n, tokens_night=0)
            if not self.progress.tick(force=True):
                raise JobCancelled()
            try:
                out[i], model = translation.translate(texts[i], src, dst, generate=self.generate, names=names)
                self.model = model or self.model
                self.progress.token(cd.estimate_tokens(out[i]))
            except (ValueError, KeyError) as e:  # an unusable answer: this text stays as written
                logger.info("chronicle %s: a text was not translated: %s", self.cid, e)
                failed += 1
            per = (self.clock() - t0) / n
            self.progress.set(nights_done=n)
            self.progress.set_eta((len(todo) - n) * per)
            if not self.progress.tick(force=True):
                raise JobCancelled()
        if todo and failed == len(todo):
            raise NightFailed("translate_failed")
        row = cd.apply_translation(digest, chapters, out)
        row["untranslated"] = failed
        self._save_digest("final", 0, row, cd.translation_hash(digest, chapters), lang=dst, translated_from=src)
        return "done"

    def _wait_for_play(self):
        waited = 0.0
        while self.busy() and waited < 60:  # live play first
            if not self.progress.tick(force=True):
                raise JobCancelled()
            self.sleep(2)
            waited += 2


TRANSLATE_SECONDS_PER_TEXT = 2.0


def translation_estimate(cursor, campaign_id: int) -> Dict[str, Any]:
    camp = campaign_row(cursor, campaign_id)
    src = chronicle_lang(cursor, camp)
    digest = stored_digest(cursor, campaign_id, src)
    chapters = [c for c in stored_chapters(cursor, campaign_id, src) if c["kind"] == "story"]
    n = sum(1 for t in cd.translation_texts(digest, chapters) if t and t.strip()) if digest else 0
    return {"texts": n, "seconds": int(n * TRANSLATE_SECONDS_PER_TEXT), "from": src}


def finish(conn, job_id: int, status: str, error: Optional[str] = None, fields: Optional[Dict[str, Any]] = None):
    fields = dict(fields or {})
    now = datetime.now()
    cols = ["status", "error", "finished_at", "updated_at"] + list(fields)
    vals = [status, error, now, now] + list(fields.values())
    cur = conn.cursor()
    cur.execute(f"UPDATE chronicle_jobs SET {', '.join(c + ' = %s' for c in cols)} WHERE id = %s", vals + [job_id])
    conn.commit()


def run_job(conn, job: Dict[str, Any], **kw) -> str:
    """Run a claimed job to its end state; never raises."""
    runner = Runner(conn, job, **kw)
    try:
        status = runner.run()
        finish(conn, job["id"], status, None, {**runner.progress.fields, "phase": None, "eta_s": 0})
        return status
    except JobCancelled:
        _safe_rollback(conn)
        finish(conn, job["id"], "cancelled", None, {**runner.progress.fields, "phase": None})
        return "cancelled"
    except Exception as e:  # noqa: BLE001
        logger.exception("chronicle job %s failed", job.get("id"))
        _safe_rollback(conn)
        from services.ai_providers import ProviderError

        # a short code for the panel; the provider's text (it can hold the LM Studio address) only in the log
        msg = str(e) if isinstance(e, NightFailed) else ("model_failed" if isinstance(e, ProviderError) else "internal")
        try:
            finish(conn, job["id"], "failed", msg, {**runner.progress.fields, "phase": None})
        except Exception:  # noqa: BLE001
            logger.exception("chronicle job %s: could not record the failure", job.get("id"))
        return "failed"


def _safe_rollback(conn):
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------------------------
# Claiming (PostgreSQL) and the worker thread

def is_quiet(cursor, campaign_id: int, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now()
    cursor.execute("SELECT MAX(created_at) AS last FROM messages WHERE campaign_id = %s", (campaign_id,))
    row = cursor.fetchone() or {}
    last = _dt(row.get("last"))
    return last is None or (now - last).total_seconds() >= quiet_seconds()


WAITING_RECHECK_S = 5


def claim(conn) -> Optional[Dict[str, Any]]:
    """
    The next job to run, or None. Candidates come queued first, then waiting ones, oldest first;
    a chronicle that isn't quiet yet is marked 'waiting' and skipped, so it never blocks the
    others. FOR UPDATE SKIP LOCKED skips rows another worker holds; the advisory lock (kept on this
    connection until it closes) means one chronicle never has two writers, even when a stale job
    is picked up again. While a Storyteller reply is being written nothing is claimed.
    """
    from services.ai_busy import is_busy

    cur = conn.cursor()
    if is_busy(cur):
        conn.rollback()
        return None
    now = datetime.now()
    cur.execute(
        """
        SELECT * FROM chronicle_jobs
        WHERE status = 'queued'
           OR (status = 'waiting' AND (updated_at IS NULL OR updated_at < %s))
           OR (status = 'running' AND updated_at < %s)
        ORDER BY (status = 'waiting'), id LIMIT 20 FOR UPDATE SKIP LOCKED
        """,
        (now - timedelta(seconds=WAITING_RECHECK_S), now - timedelta(seconds=STALE_JOB_S)),
    )
    for job in cur.fetchall():
        cid = int(job["campaign_id"])
        if not is_quiet(cur, cid, now):
            cur.execute("UPDATE chronicle_jobs SET status = 'waiting', phase = 'waiting', updated_at = %s WHERE id = %s",
                        (now, job["id"]))
            continue
        if not _try_lock(cur, cid):
            continue
        cur.execute(
            "UPDATE chronicle_jobs SET status = 'running', phase = 'writing', started_at = COALESCE(started_at, %s), "
            "updated_at = %s WHERE id = %s",
            (now, now, job["id"]),
        )
        conn.commit()
        job = dict(job)
        job["status"] = "running"
        return job
    conn.commit()
    return None


def _try_lock(cur, campaign_id: int) -> bool:
    if not _pg():
        return True
    cur.execute("SELECT pg_try_advisory_lock(%s, %s) AS ok", (ADVISORY_CLASS, int(campaign_id)))
    return bool((cur.fetchone() or {}).get("ok"))


_worker_lock = threading.Lock()
_worker: Optional[threading.Thread] = None


def _loop():
    from database import get_db
    from services.ai_busy import is_busy

    while True:
        ran = False
        conn = None
        try:
            conn = get_db()
            job = claim(conn)
            if job:
                ran = True

                def busy(c=conn):
                    try:
                        return is_busy(c.cursor())
                    except Exception:  # noqa: BLE001
                        return False

                run_job(conn, job, busy=busy)
        except Exception as e:  # noqa: BLE001
            logger.warning("chronicle worker: %s", e)
        finally:
            if conn is not None:
                try:
                    conn.close()  # releases the advisory lock
                except Exception:  # noqa: BLE001
                    pass
        time.sleep(0.5 if ran else 5)


def ensure_worker() -> bool:
    """Start this process's writer thread once (PostgreSQL only). Safe in every gunicorn worker."""
    global _worker
    if not _pg():
        return False
    with _worker_lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_loop, name="chronicle-writer", daemon=True)
            _worker.start()
    return True
