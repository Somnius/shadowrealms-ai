"""Synthetic chronicles for "The chronicle so far" tests (Greek, English, mixed; any number of nights),
an in-memory SQLite database in the shape the routes read, and a fake model."""

import json
import re
import sqlite3
import sys
import types
from datetime import datetime, timedelta

try:  # database.py imports psycopg2; the unit job doesn't install it
    import psycopg2  # noqa: F401
except ImportError:  # pragma: no cover - depends on the environment
    _pg = types.ModuleType("psycopg2")
    _pg.extras = types.ModuleType("psycopg2.extras")
    sys.modules.setdefault("psycopg2", _pg)
    sys.modules.setdefault("psycopg2.extras", _pg.extras)

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role TEXT);
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY, name TEXT, created_by INTEGER, rules_edition TEXT DEFAULT 'v5',
    language TEXT, is_active INTEGER DEFAULT 1
);
CREATE TABLE campaign_players (campaign_id INTEGER, user_id INTEGER, role TEXT DEFAULT 'player');
CREATE TABLE locations (
    id INTEGER PRIMARY KEY, campaign_id INTEGER, name TEXT, type TEXT DEFAULT 'custom', description TEXT,
    is_open INTEGER DEFAULT 1, is_active INTEGER DEFAULT 1
);
CREATE TABLE characters (id INTEGER PRIMARY KEY, name TEXT, user_id INTEGER, campaign_id INTEGER, wod_meta TEXT DEFAULT '{}');
CREATE TABLE npcs (id INTEGER PRIMARY KEY, campaign_id INTEGER, name TEXT, type TEXT, faction TEXT);
CREATE TABLE messages (
    id INTEGER PRIMARY KEY, campaign_id INTEGER, location_id INTEGER, user_id INTEGER, character_id INTEGER,
    message_type TEXT DEFAULT 'ic', content TEXT, role TEXT DEFAULT 'user', created_at TIMESTAMP,
    ai_message_kind TEXT, speaker_mode TEXT, lang TEXT
);
INSERT INTO users (id, username, role) VALUES
    (1, 'siteadmin', 'admin'), (2, 'storyteller_lef', 'player'), (3, 'eleni_player', 'player'),
    (4, 'outsider', 'player'), (5, 'helper_in', 'helper'), (6, 'helper_out', 'helper'), (7, 'nikos_player', 'player');
INSERT INTO campaigns (id, name, created_by) VALUES (10, 'Athens: Blood and Concrete', 2);
INSERT INTO campaign_players (campaign_id, user_id) VALUES (10, 3), (10, 5), (10, 7);
INSERT INTO locations (id, campaign_id, name, type, description, is_open) VALUES
    (100, 10, 'Out of Character Lobby', 'ooc', 'Table talk', 1),
    (101, 10, 'The Echoing Basement', 'custom', 'Under the old block of flats', 1),
    (102, 10, 'Elysium', 'custom', 'The Prince''s hall', 1),
    (103, 10, 'The Crypt', 'custom', 'Sealed by the Storyteller', 0);
INSERT INTO characters (id, name, user_id, campaign_id, wod_meta) VALUES
    (20, 'Κωνσταντίνος Κατακουζηνός', 3, 10, '{"clan": "Tremere"}'),
    (21, 'Marcus Vell', 7, 10, '{"clan": "Brujah"}');
INSERT INTO npcs (id, campaign_id, name, type, faction) VALUES (30, 10, 'Μαρώ', 'mortal', 'tenants');
"""

TEXT = {
    "el": [
        "Κατεβαίνω στο υπόγειο και κοιτάζω τις σκιές.",
        "Η Μαρώ λέει ότι ο κλειδαράς ήρθε χθες το βράδυ.",
        "Ψάχνω το σημείωμα με τα αρχαία σύμβολα.",
        "Η πόρτα τρίζει και κάτι κινείται στο βάθος.",
        "Ρωτάω τη Μαρώ ποιος άλλος έχει κλειδί.",
    ],
    "en": [
        "I walk down into the basement and watch the shadows.",
        "Maro says the locksmith came last night.",
        "I search for the note with the old symbols.",
        "The door creaks and something moves at the back.",
        "I ask Maro who else has a key.",
    ],
}
NARRATION = {
    "el": "Ο αέρας μυρίζει υγρασία και παλιό χαρτί· κάποιος σε παρακολουθεί.",
    "en": "The air smells of damp and old paper; someone is watching you.",
}


def marker(anim, botch=False, critical=False):
    return json.dumps({"animation_id": anim, "roll_id": 1, "is_botch": botch, "is_critical": critical})


def build(lang="el", nights=3, start=datetime(2026, 10, 1, 21, 0), session_mark_night=None):
    """Messages for `nights` nights. 'mixed' alternates the language per night.
    Night 1 has a botch; night 2 a hidden roll; night 3 in-room OOC; every night some lobby talk;
    the closed room (The Crypt) gets a scene on night 2."""
    rows = []
    mid = 1000
    marks = []

    def add(**kw):
        nonlocal mid
        mid += 1
        row = {"id": mid, "campaign_id": 10, "user_id": 3, "character_id": None, "message_type": "ic",
               "role": "user", "ai_message_kind": None, "speaker_mode": "character", "lang": None}
        row.update(kw)
        rows.append(row)
        return mid

    for n in range(1, nights + 1):
        lg = ("el" if n % 2 else "en") if lang == "mixed" else lang
        t = start + timedelta(days=n - 1)
        room = 101 if n % 2 else 102
        for i, text in enumerate(TEXT[lg]):
            ch, uid = (20, 3) if i % 2 == 0 else (21, 7)
            add(location_id=room, user_id=uid, character_id=ch, content=text, created_at=t + timedelta(minutes=i * 3), lang=lg)
        add(location_id=room, user_id=2, role="assistant", speaker_mode=None, content=NARRATION[lg],
            created_at=t + timedelta(minutes=16), lang=lg)
        add(location_id=room, user_id=2, role="assistant", speaker_mode=None, content=NARRATION[lg] + " II",
            created_at=t + timedelta(minutes=16, seconds=30), lang=lg)
        hidden = n == 2
        anim = f"r{n}-abc"
        kind_m = ("dice_animation_hidden:" if hidden else "dice_animation:") + anim
        kind_r = ("dice_roll_hidden:" if hidden else "dice_roll:") + anim
        add(location_id=room, user_id=3, message_type="system", role="assistant", content=marker(anim, botch=n == 1),
            ai_message_kind=kind_m, speaker_mode=None, created_at=t + timedelta(minutes=17))
        add(location_id=room, user_id=3, character_id=20, message_type="action", content="Κωνσταντίνος rolled Wits + Awareness: 0 successes",
            ai_message_kind=kind_r, created_at=t + timedelta(minutes=17))
        last = add(location_id=room, user_id=7, character_id=21, content=TEXT[lg][0], created_at=t + timedelta(minutes=20), lang=lg)
        if n == 3:
            add(location_id=room, user_id=7, message_type="ooc", speaker_mode="player", content="brb, coffee",
                created_at=t + timedelta(minutes=21))
        if n == 2:
            for i in range(3):
                add(location_id=103, user_id=2, speaker_mode="staff", content=f"{NARRATION[lg]} ({i})",
                    created_at=t + timedelta(minutes=30 + i), lang=lg)
        add(location_id=100, user_id=3, message_type="ooc", speaker_mode="player", content="Good game tonight!",
            created_at=t + timedelta(minutes=40))
        if session_mark_night == n:
            marks.append(last)
            # same room, 30 minutes later: no gap, so only the mark splits it
            add(location_id=room, user_id=3, character_id=20, content=TEXT[lg][1], created_at=t + timedelta(minutes=50), lang=lg)
    return rows, marks


def db(rows=None, marks=(), language=None):
    from database import CHRONICLE_TABLES_SQL, sqlite_ddl

    raw = sqlite3.connect(":memory:", check_same_thread=False)
    raw.executescript(SCHEMA)
    for stmt in CHRONICLE_TABLES_SQL:
        raw.execute(sqlite_ddl(stmt))
    if language:
        raw.execute("UPDATE campaigns SET language = ?", (language,))
    for r in rows or []:
        raw.execute(
            "INSERT INTO messages (id, campaign_id, location_id, user_id, character_id, message_type, content, role, "
            "created_at, ai_message_kind, speaker_mode, lang) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (r["id"], r["campaign_id"], r["location_id"], r["user_id"], r["character_id"], r["message_type"],
             r["content"], r["role"], r["created_at"].isoformat(" "), r["ai_message_kind"], r["speaker_mode"], r["lang"]),
        )
    for m in marks:
        raw.execute("INSERT INTO chronicle_session_marks (message_id, campaign_id) VALUES (?, 10)", (m,))
    raw.commit()
    return raw


class Cur:
    def __init__(self, conn):
        self._c = conn.cursor()
        self.connection = conn

    def execute(self, sql, params=()):
        sql = sql.replace("%s", "?").replace(" FOR UPDATE SKIP LOCKED", "").replace(" FOR UPDATE", "")
        self._c.execute(sql, tuple(p.isoformat(" ") if isinstance(p, datetime) else p for p in params))

    def _row(self, r):
        return None if r is None else {k[0]: v for k, v in zip(self._c.description, r)}

    def fetchone(self):
        return self._row(self._c.fetchone())

    def fetchall(self):
        return [self._row(r) for r in self._c.fetchall()]

    @property
    def rowcount(self):
        return self._c.rowcount

    def close(self):
        pass


class Conn:
    def __init__(self, raw):
        self._raw = raw

    def cursor(self):
        return Cur(self._raw)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        pass


GREEK = {
    "title": "Η νύχτα στο υπόγειο",
    "p": "Ο Κωνσταντίνος κατέβηκε στο υπόγειο και βρήκε το σημείωμα με τα σύμβολα.",
    "event": "Ο Κωνσταντίνος έψαξε το υπόγειο και βρήκε ίχνη.",
}
ENGLISH = {
    "title": "A night in the basement",
    "p": "Konstantinos went down to the basement and found the note with the symbols.",
    "event": "Konstantinos searched the basement and found traces.",
}


class FakeModel:
    """Answers each kind of call (by response_format name) in the language of its instructions."""

    def __init__(self, wrong_language_first=False, overflow_once=False):
        self.calls = []
        self.wrong_language_first = wrong_language_first
        self.overflow_once = overflow_once

    def __call__(self, role, messages, params, **kw):
        from services.ai_providers import ProviderError

        name = params["response_format"]["json_schema"]["name"]
        self.calls.append({"role": role, "name": name, "messages": messages, "kw": kw})
        assert kw.get("shrink") is False
        if self.overflow_once and name == "chapter":
            self.overflow_once = False
            raise ProviderError("LM Studio HTTP 400: Context size has been exceeded.")
        el = role == "chronicler_el"
        w = GREEK if el else ENGLISH
        if self.wrong_language_first and name == "chapter":
            self.wrong_language_first = False
            w = ENGLISH if el else GREEK
        ids = [int(x) for x in re.findall(r"^M(\d+)", messages[1]["content"], re.M)]
        if name == "chapter":
            out = {"title": w["title"], "summary": [w["p"], w["p"]],
                   "events": [{"text": w["event"], "ids": ids[:2] + [999999]}, {"text": "uncited", "ids": []}],
                   "characters": [{"name": "Κωνσταντίνος", "note": w["event"]}, {"name": "Ventrue Prince", "note": "x"}],
                   "places": [{"name": "Σκουφά", "note": w["event"]}],
                   "threads_opened": [{"text": w["event"], "ids": ids[:1]}], "threads_closed": []}
        elif name == "notes":
            out = {"notes": [{"text": w["event"], "ids": ids[:1]}]}
        elif name == "era":
            out = {"so_far": [w["p"]], "threads_open": [{"text": w["event"], "nights": [1]}]}
        elif name == "digest":
            out = {"tldr": w["p"], "so_far": [w["p"], w["p"]], "threads_open": [{"text": w["event"], "nights": [1]}]}
        else:
            out = {"st_so_far": [w["p"]]}
        text = json.dumps(out, ensure_ascii=False)
        cb = params.get("on_token")
        n = 0
        if cb:
            for i in range(0, len(text), 20):
                n += 1
                if cb(text[i:i + 20], None) is False:
                    from services.ai_providers import Cancelled

                    raise Cancelled("cancelled")
            if cb("", {"completion_tokens": n}) is False:
                from services.ai_providers import Cancelled

                raise Cancelled("cancelled")
        return {"text": text, "model": "fake-model", "provider": "lm_studio"}
