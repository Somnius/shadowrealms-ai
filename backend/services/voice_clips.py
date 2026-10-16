"""
Voice clips (docs/VOICE.md, Phase 3): what a player recorded, kept as Ogg/Opus in the speech
service for the chronicle's lifetime. The voice_clips row says whose it is, which room, and which
message it was sent with (NULL until sent). Deleted with the message and with the chronicle.
"""

import json
import logging
import os
import re

from database import ensure_voice_clips_table
from services import speech_client

logger = logging.getLogger(__name__)

CLIP_ID = re.compile(r"^[0-9a-f]{32}$")
SOURCES = ("voice", "phone-voice")


def max_clip_bytes():
    return int(os.getenv("VOICE_CLIP_MAX_BYTES", str(8 * 1024 * 1024)))


def clips_max_bytes():
    """Disk cap for all clips (VOICE_CLIPS_MAX_GB, default 20)."""
    try:
        gb = float(os.getenv("VOICE_CLIPS_MAX_GB", "20"))
    except ValueError:
        gb = 20.0
    return int(gb * 1024 ** 3)


UNMETERED_MS = 180_000  # a clip with no known length counts as the longest one


def used_bytes(cursor):
    """Rough disk use: 16 kbps Opus is 2 KB a second, plus room for an AAC copy (another ~2 KB/s)
    for some phones. A clip whose length is not known yet counts as the longest allowed."""
    ensure_voice_clips_table(cursor)
    cursor.execute(
        "SELECT COALESCE(SUM(COALESCE(duration_ms, %s)), 0) AS ms FROM voice_clips", (UNMETERED_MS,)
    )
    ms = (cursor.fetchone() or {}).get("ms") or 0
    return int(ms) * 4


def record(cursor, clip_id, campaign_id, location_id, user_id, lang, duration_ms=None):
    ensure_voice_clips_table(cursor)
    cursor.execute(
        "INSERT INTO voice_clips (clip_id, campaign_id, location_id, user_id, lang, duration_ms) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (clip_id, campaign_id, location_id, user_id, lang, duration_ms),
    )


def get(cursor, clip_id):
    if not CLIP_ID.match(clip_id or ""):
        return None
    ensure_voice_clips_table(cursor)
    cursor.execute("SELECT * FROM voice_clips WHERE clip_id = %s", (clip_id,))
    return cursor.fetchone()


def note_transcript(cursor, clip_id, text, duration_s):
    ensure_voice_clips_table(cursor)
    ms = int(round(float(duration_s or 0) * 1000)) or None
    cursor.execute(
        "UPDATE voice_clips SET transcript_raw = %s, duration_ms = COALESCE(%s, duration_ms) "
        "WHERE clip_id = %s",
        (text, ms, clip_id),
    )


def note_checked(cursor, clip_id, segments):
    """Phase 6: the checked transcript (JSON segments), or "[]" when the check changed nothing."""
    ensure_voice_clips_table(cursor)
    cursor.execute(
        "UPDATE voice_clips SET transcript_checked = %s WHERE clip_id = %s",
        (json.dumps(segments or [], ensure_ascii=False), clip_id),
    )


def checked_segments(clip):
    """None when not checked yet, [] when checked and unchanged, else the segments."""
    raw = (clip or {}).get("transcript_checked")
    if raw is None:
        return None
    try:
        segs = json.loads(raw)
    except ValueError:
        return []
    return segs if isinstance(segs, list) else []


def note_translation(cursor, clip_id, lang, text):
    ensure_voice_clips_table(cursor)
    cursor.execute(
        "UPDATE voice_clips SET translated_lang = %s, translated_text = %s WHERE clip_id = %s",
        (lang, text, clip_id),
    )


def attach_error(clip, user_id, campaign_id, location_id):
    """Why this clip cannot be sent with a new message here, or None."""
    if clip is None:
        return "clip_not_found"
    if int(clip["user_id"]) != int(user_id):
        return "clip_not_found"
    if int(clip["campaign_id"]) != int(campaign_id) or int(clip.get("location_id") or 0) != int(location_id):
        return "clip_wrong_room"
    if clip.get("message_id"):
        return "clip_already_sent"
    return None


def attach(cursor, clip_id, message_id):
    """Link the clip to its message. False when another send got it first (the caller rolls back)."""
    cursor.execute(
        "UPDATE voice_clips SET message_id = %s WHERE clip_id = %s AND message_id IS NULL",
        (message_id, clip_id),
    )
    return cursor.rowcount == 1


def _drop_files(clip_ids):
    for cid in clip_ids:
        try:
            speech_client.call_json("DELETE", f"/clips/{cid}")
        except speech_client.SpeechUnavailable:
            logger.warning("speech service down: clip %s left on disk", cid[:8])


def forget_message_clips(cursor, message_ids):
    """Delete the clips sent with these messages (rows and files). Returns the clip ids."""
    ids = [int(i) for i in (message_ids or [])]
    if not ids:
        return []
    ensure_voice_clips_table(cursor)
    ph = ", ".join(["%s"] * len(ids))
    cursor.execute(f"SELECT clip_id FROM voice_clips WHERE message_id IN ({ph})", tuple(ids))
    gone = [r["clip_id"] for r in cursor.fetchall()]
    cursor.execute(f"DELETE FROM voice_clips WHERE message_id IN ({ph})", tuple(ids))
    _drop_files(gone)
    return gone


def forget_campaign_clips(cursor, campaign_id):
    """Delete every clip of a chronicle (sent or not)."""
    ensure_voice_clips_table(cursor)
    cursor.execute("SELECT clip_id FROM voice_clips WHERE campaign_id = %s", (campaign_id,))
    gone = [r["clip_id"] for r in cursor.fetchall()]
    cursor.execute("DELETE FROM voice_clips WHERE campaign_id = %s", (campaign_id,))
    _drop_files(gone)
    return gone
