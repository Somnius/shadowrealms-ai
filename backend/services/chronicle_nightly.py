"""
The nightly run of "The chronicle so far" (docs/CHRONICLE.md, phase 5).

At a quiet hour (CHRONICLE_NIGHTLY_AT in CHRONICLE_NIGHTLY_TZ, default 05:00 Europe/Athens; the
server's own clock stays UTC, as message times are) the first gunicorn worker
queues an Update for each chronicle whose nightly switch is on (Chronicle settings) and that has
new messages since its last run, one chronicle at a time: the next one is queued only when the
previous nightly job has ended. The jobs are ordinary Update jobs (requested_by NULL), so the same
rules hold: the job queue and its claim, the 10-minute quiet window, the busy marker and the limits
(one job per chronicle, Update every 5 minutes, the caps). Old job rows are pruned once a day here.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any, Dict, List, Optional, Tuple

from services import chronicle_jobs as cj
from services import chronicle_settings as cs

logger = logging.getLogger(__name__)

WINDOW_HOURS = 3  # nightly jobs are queued only in the 3 hours after the set time
TICK_S = 60
STUCK_MINUTES = 15  # a nightly job still queued/waiting this long no longer holds up the next chronicle


def nightly_zone():
    """CHRONICLE_NIGHTLY_TZ (default Europe/Athens), UTC when it isn't a known zone."""
    name = (os.environ.get("CHRONICLE_NIGHTLY_TZ") or "Europe/Athens").strip()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("CHRONICLE_NIGHTLY_TZ=%r is not a timezone; using UTC", name)
        return timezone.utc


def local_time(now: datetime) -> datetime:
    """Server time (naive, UTC like the message times) -> naive wall-clock time in the nightly zone."""
    return now.replace(tzinfo=timezone.utc).astimezone(nightly_zone()).replace(tzinfo=None)


def local_day_start(now: datetime) -> datetime:
    """The start of today in the nightly zone, as naive server (UTC) time."""
    zone = nightly_zone()
    loc = now.replace(tzinfo=timezone.utc).astimezone(zone)
    start = datetime(loc.year, loc.month, loc.day, tzinfo=zone)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


def nightly_at() -> Tuple[int, int]:
    """(hour, minute) from CHRONICLE_NIGHTLY_AT ('HH:MM' or 'HH'), else 05:00."""
    raw = (os.environ.get("CHRONICLE_NIGHTLY_AT") or "05:00").strip()
    try:
        h, _, m = raw.partition(":")
        h, m = int(h), int(m or 0)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except ValueError:
        pass
    logger.warning("CHRONICLE_NIGHTLY_AT=%r is not HH:MM; using 05:00", raw)
    return 5, 0


def window_day(now: datetime) -> Optional[date]:
    """The day of the nightly window server time `now` falls in (in the nightly zone), or None outside it."""
    now = local_time(now)
    h, m = nightly_at()
    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now < start:
        start -= timedelta(days=1)
    return start.date() if now - start < timedelta(hours=WINDOW_HOURS) else None


def has_new_messages(cursor, campaign_id: int) -> bool:
    """New messages since the last finished Update (a partial one still has nights to write)."""
    cursor.execute("SELECT MAX(created_at) AS last FROM messages WHERE campaign_id = %s", (campaign_id,))
    last_msg = cj._dt((cursor.fetchone() or {}).get("last"))
    if last_msg is None:
        return False
    cursor.execute(
        "SELECT status, created_at FROM chronicle_jobs WHERE campaign_id = %s AND scope IN ('update', 'all') "
        "AND status IN ('done', 'partial') ORDER BY id DESC LIMIT 1",
        (campaign_id,),
    )
    run = cursor.fetchone()
    if not run:
        # no finished run on record (e.g. pruned): new only if a message came after the stored nights
        try:
            cursor.execute("SELECT MAX(last_message_id) AS last FROM chronicle_chapters WHERE campaign_id = %s",
                           (campaign_id,))
            written = (cursor.fetchone() or {}).get("last")
            cursor.execute("SELECT MAX(id) AS last FROM messages WHERE campaign_id = %s", (campaign_id,))
            last_id = (cursor.fetchone() or {}).get("last")
        except Exception:  # noqa: BLE001
            cj._rollback(cursor)
            return True
        return not written or (last_id or 0) > int(written)
    if run["status"] == "partial":
        return True
    at = cj._dt(run["created_at"])
    return at is None or last_msg > at


def due(cursor) -> List[int]:
    """Chronicles with the nightly switch on and new messages, oldest id first."""
    try:
        cursor.execute("SELECT id, chronicle_settings FROM campaigns ORDER BY id")
        rows = cursor.fetchall()
    except Exception:  # noqa: BLE001 - before the column exists
        cj._rollback(cursor)
        return []
    out = []
    for r in rows:
        if cs.normalize(r.get("chronicle_settings"))["nightly"] and has_new_messages(cursor, int(r["id"])):
            out.append(int(r["id"]))
    return out


def nightly_running(cursor, now: datetime) -> bool:
    """A nightly job is writing, or was queued less than STUCK_MINUTES ago (one waiting longer for a
    chronicle still in play doesn't hold up the others)."""
    cursor.execute(
        "SELECT id FROM chronicle_jobs WHERE requested_by IS NULL AND (status = 'running' OR "
        "(status IN ('queued', 'waiting') AND created_at > %s)) LIMIT 1",
        (now - timedelta(minutes=STUCK_MINUTES),),
    )
    return cursor.fetchone() is not None


def cancel_leftovers(cursor, now: datetime) -> int:
    """Outside the window: nightly jobs still queued or waiting are cancelled, so they never start in
    the middle of the next session."""
    cursor.execute(
        "UPDATE chronicle_jobs SET status = 'cancelled', finished_at = %s, updated_at = %s "
        "WHERE requested_by IS NULL AND status IN ('queued', 'waiting')",
        (now, now),
    )
    return cursor.rowcount or 0


class Nightly:
    """State of the nightly run in this process: which chronicles were tried in which window."""

    def __init__(self):
        self.day: Optional[date] = None
        self.tried: set = set()
        self.queued: Dict[int, int] = {}  # chronicle -> its nightly job in this window
        self.pruned: Optional[date] = None

    def tick(self, conn, now: Optional[datetime] = None) -> Optional[int]:
        """Queue at most one nightly job; returns its id. Never raises for one bad chronicle."""
        now = now or datetime.now()
        cur = conn.cursor()
        if self.pruned != now.date():
            try:
                n = cj.prune_jobs(cur, now)
                conn.commit()
                self.pruned = now.date()
                if n:
                    logger.info("chronicle: pruned %s old job rows", n)
            except Exception as e:  # noqa: BLE001
                cj._safe_rollback(conn)
                logger.warning("chronicle: pruning old jobs failed: %s", e)
        day = window_day(now)
        if day is None:
            try:
                if cancel_leftovers(cur, now):
                    logger.info("chronicle: nightly jobs left waiting were cancelled")
                conn.commit()
            except Exception as e:  # noqa: BLE001
                cj._safe_rollback(conn)
                logger.warning("chronicle: cancelling nightly leftovers failed: %s", e)
            return None
        if day != self.day:
            self.day, self.tried, self.queued = day, set(), {}
        for cid, jid in list(self.queued.items()):  # a partial nightly job carries on at the next turn
            cur.execute("SELECT status FROM chronicle_jobs WHERE id = %s", (jid,))
            st = (cur.fetchone() or {}).get("status")
            if st in cj.ACTIVE:
                continue
            del self.queued[cid]
            if st == "partial":
                self.tried.discard(cid)
        if nightly_running(cur, now):  # one at a time
            conn.rollback()
            return None
        for cid in due(cur):
            if cid in self.tried:
                continue
            try:
                jid = cj.create_job(cur, cid, None, "update", now=now)
            except cj.JobRefused as e:
                conn.rollback()
                if e.code not in ("too_soon", "job_running"):  # those get another turn later tonight
                    self.tried.add(cid)
                logger.info("chronicle %s: nightly run skipped (%s)", cid, e.code)
                continue
            self.tried.add(cid)
            self.queued[cid] = jid
            conn.commit()
            logger.info("chronicle %s: nightly run queued (job %s)", cid, jid)
            return jid
        conn.rollback()
        return None


def _loop(state: Nightly):
    from database import get_db

    while True:
        conn = None
        try:
            conn = get_db()
            if state.tick(conn):
                cj.ensure_worker()
        except Exception as e:  # noqa: BLE001
            logger.warning("chronicle nightly: %s", e)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
        time.sleep(TICK_S)


_started = False
_lock = threading.Lock()


def start() -> bool:
    """Start the nightly thread once (PostgreSQL only). Called from main.start_background_jobs, which
    gunicorn runs in the first worker only (gunicorn.conf.py post_fork)."""
    global _started
    if not cj._pg():
        return False
    with _lock:
        if _started:
            return True
        threading.Thread(target=_loop, args=(Nightly(),), name="chronicle-nightly", daemon=True).start()
        _started = True
    return True


def status() -> Dict[str, Any]:
    h, m = nightly_at()
    zone = nightly_zone()
    return {"at": f"{h:02d}:{m:02d}", "tz": getattr(zone, "key", "UTC"), "window_hours": WINDOW_HOURS}
