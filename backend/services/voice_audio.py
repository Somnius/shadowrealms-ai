"""
The voice_audio index (docs/VOICE.md): which message (NULL for a voice preview) was spoken with
which key in the speech service's cache. Two listeners of the same line share one key and one file.
"""

import logging

from database import ensure_voice_audio_table
from services import speech_client

logger = logging.getLogger(__name__)


def remember(cursor, message_id, key, voice_id):
    ensure_voice_audio_table(cursor)
    if message_id is None:
        cursor.execute("SELECT 1 FROM voice_audio WHERE message_id IS NULL AND audio_key = %s", (key,))
    else:
        cursor.execute(
            "SELECT 1 FROM voice_audio WHERE message_id = %s AND audio_key = %s", (message_id, key)
        )
    if cursor.fetchone():
        return
    cursor.execute(
        "INSERT INTO voice_audio (message_id, audio_key, voice_id) VALUES (%s, %s, %s)",
        (message_id, key, voice_id),
    )


def message_ids_for_key(cursor, key):
    """[ids] of the messages that use this key; None in the list means a preview (anyone may hear)."""
    ensure_voice_audio_table(cursor)
    cursor.execute("SELECT DISTINCT message_id FROM voice_audio WHERE audio_key = %s", (key,))
    return [r.get("message_id") for r in cursor.fetchall()]


def forget_message_audio(cursor, message_ids):
    """Drop the index rows of deleted messages, and the files no other line still uses."""
    ids = [int(i) for i in (message_ids or [])]
    if not ids:
        return []
    ensure_voice_audio_table(cursor)
    ph = ", ".join(["%s"] * len(ids))
    cursor.execute(f"SELECT DISTINCT audio_key FROM voice_audio WHERE message_id IN ({ph})", tuple(ids))
    keys = [r["audio_key"] for r in cursor.fetchall()]
    cursor.execute(f"DELETE FROM voice_audio WHERE message_id IN ({ph})", tuple(ids))
    gone = []
    for key in keys:
        cursor.execute("SELECT 1 FROM voice_audio WHERE audio_key = %s", (key,))
        if cursor.fetchone():
            continue  # another message (or a preview) still says the same words
        try:
            speech_client.call_json("DELETE", f"/audio/{key}")
        except speech_client.SpeechUnavailable:
            logger.warning("speech service down: audio %s left in the cache", key[:8])
        gone.append(key)
    return gone
