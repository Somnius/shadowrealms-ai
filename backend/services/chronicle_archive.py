"""
Archive on delete (docs/CHRONICLE.md, docs/SECURITY_MODEL.md): before a chronicle is deleted, its
minutes (rendered from the chapters already written; no model call) and the raw transcript of
every room in the Storyteller's view (hidden rolls marked) are written to
data/chronicle_archive/<id>-<slug>-<time>/, with an index row in chronicle_archives. If that
fails, the delete stops.

Downloads: site admins always; the chronicle's Storyteller (its creator) for ARCHIVE_ST_DAYS days,
whoever pressed delete. The path
on disk always comes from the index row, never from the request.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from services import chronicle_digest as cd
from services import chronicle_jobs as cj

ARCHIVE_ST_DAYS = 30
FILES = {"minutes": "minutes.md", "transcript": "transcript.md"}

_HEADER = {
    "en": ("Archive of “{name}”, written on {date} when the chronicle was deleted.\n\n"
           "- Minutes: {written} of {total} nights, from the chapters already written (nothing new was written).\n"
           "- Transcript: every chat line of every room ({messages} messages; dice animations and system rows left out), as the Storyteller saw them; hidden rolls are marked.\n"),
    "el": ("Αρχείο του «{name}», γράφτηκε στις {date} όταν διαγράφηκε το χρονικό.\n\n"
           "- Πρακτικά: {written} από {total} νύχτες, από τα κεφάλαια που είχαν ήδη γραφτεί (δεν γράφτηκε τίποτα νέο).\n"
           "- Απομαγνητοφώνηση: κάθε γραμμή συνομιλίας κάθε αίθουσας ({messages} μηνύματα· χωρίς τα κινούμενα ζάρια και τις γραμμές συστήματος), όπως τα έβλεπε ο Storyteller· οι κρυφές ρίψεις σημειώνονται.\n"),
}


def archive_root() -> str:
    env = os.environ.get("CHRONICLE_ARCHIVE_DIR")
    if env:
        return env
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend, "data", "chronicle_archive")


def slug(name: str) -> str:
    s = re.sub(r"[^\w]+", "-", str(name or "").lower(), flags=re.UNICODE).strip("-_")
    return s[:40] or "chronicle"


def write_archive(cursor, campaign_id: int, actor_id: int, root: Optional[str] = None,
                  now: Optional[datetime] = None) -> int:
    """Write the two files and the index row; returns the row id. Raises on any failure."""
    now = now or datetime.now()
    camp = cj.campaign_row(cursor, campaign_id)
    if not camp:
        raise ValueError("no such chronicle")
    rows = cj.load_rows(cursor, campaign_id)
    lang = cj.chronicle_lang(cursor, camp, rows)
    try:
        chapters = cj.stored_chapters(cursor, campaign_id, lang)
    except Exception:  # noqa: BLE001 - no chapter table yet: nothing written
        cj._rollback(cursor)
        chapters = []
    from services.chronicle_settings import load as load_settings

    gap = load_settings(cursor, campaign_id)["gap_hours"]
    fresh = cd.cut_chapters(rows, gap, cj.session_marks(cursor, campaign_id))
    flags = cd.roll_flags(rows)
    total = sum(1 for c in fresh if c["kind"] == "story" and cd.chapter_material(c, lang, flags)["lines"])
    written = sum(1 for c in chapters if c["kind"] == "story")
    facts = cj.facts(cursor, camp, "st")
    facts["nights_total"] = max(total, written)
    existing = {int(r["id"]) for r in rows}
    minutes = cd.minutes_markdown(facts, chapters, lang, "st", existing_ids=existing, with_table_talk=True)
    header = _HEADER["el" if lang == "el" else "en"].format(
        name=camp["name"], date=now.strftime("%Y-%m-%d %H:%M"), written=written, total=facts["nights_total"],
        messages=len(rows))
    transcript = cd.transcript_markdown(facts, rows, lang)
    dir_name = f"{int(campaign_id)}-{slug(camp['name'])}-{now.strftime('%Y%m%d-%H%M%S')}"
    path = os.path.join(root or archive_root(), dir_name)
    os.makedirs(path, mode=0o700, exist_ok=False)
    for key, body in (("minutes", minutes), ("transcript", transcript)):
        with open(os.path.join(path, FILES[key]), "w", encoding="utf-8") as f:
            f.write(header + "\n" + body)
    cursor.execute(
        """
        INSERT INTO chronicle_archives (campaign_id, campaign_name, dir_name, deleted_by, storyteller_id, nights,
            nights_written, messages, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """,
        (campaign_id, camp["name"], dir_name, actor_id, camp.get("created_by"), facts["nights_total"], written,
         len(rows), now),
    )
    return int(cursor.fetchone()["id"])


def can_download(row: Dict[str, Any], user_id: Any, user_role: Optional[str], now: Optional[datetime] = None) -> bool:
    """Site admins always; the chronicle's Storyteller for ARCHIVE_ST_DAYS days, whoever deleted it."""
    if (user_role or "") == "admin":
        return True
    now = now or datetime.now()
    created = cj._dt(row.get("created_at"))
    return (row.get("storyteller_id") is not None and str(row["storyteller_id"]) == str(user_id)
            and created is not None and now - created <= timedelta(days=ARCHIVE_ST_DAYS))


def remove_archive(cursor, archive_id: int, root: Optional[str] = None) -> None:
    """Undo write_archive when the delete fails after it, so a retry doesn't leave two copies."""
    import shutil

    cursor.execute("SELECT dir_name FROM chronicle_archives WHERE id = %s", (archive_id,))
    row = cursor.fetchone()
    cursor.execute("DELETE FROM chronicle_archives WHERE id = %s", (archive_id,))
    if row:
        base = os.path.realpath(root or archive_root())
        path = os.path.realpath(os.path.join(base, str(row["dir_name"])))
        if path.startswith(base + os.sep):
            shutil.rmtree(path, ignore_errors=True)


def archive_file(row: Dict[str, Any], which: str, root: Optional[str] = None) -> Optional[str]:
    """The file's path from the index row (never from the request), or None."""
    if which not in FILES:
        return None
    base = os.path.realpath(root or archive_root())
    path = os.path.realpath(os.path.join(base, str(row["dir_name"]), FILES[which]))
    if not path.startswith(base + os.sep) or not os.path.isfile(path):
        return None
    return path


def archive_size(row: Dict[str, Any], root: Optional[str] = None) -> int:
    """Bytes on disk of the archive's files (0 when they are gone)."""
    total = 0
    for which in FILES:
        path = archive_file(row, which, root)
        if path:
            try:
                total += os.path.getsize(path)
            except OSError:
                pass
    return total
