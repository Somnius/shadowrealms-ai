"""
The voice_audio index (docs/VOICE.md): which message (NULL for a voice preview) was spoken with
which key in the speech service's cache. Two listeners of the same line share one key and one file.
"""

import logging

from database import ensure_voice_audio_table
from services import speech_client

logger = logging.getLogger(__name__)


def remember(cursor, message_id, key, voice_id, campaign_id=None, location_id=None):
    """campaign_id/location_id: audio of no message that belongs to a chronicle's room (a recap)."""
    ensure_voice_audio_table(cursor)
    if message_id is None and campaign_id is not None:
        cursor.execute(
            "SELECT 1 FROM voice_audio WHERE message_id IS NULL AND campaign_id = %s AND location_id = %s "
            "AND audio_key = %s", (campaign_id, location_id, key))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO voice_audio (message_id, audio_key, voice_id, campaign_id, location_id) "
                "VALUES (NULL, %s, %s, %s, %s)", (key, voice_id, campaign_id, location_id))
        return
    if message_id is None:
        cursor.execute("SELECT 1 FROM voice_audio WHERE message_id IS NULL AND campaign_id IS NULL AND audio_key = %s", (key,))
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


def rows_for_key(cursor, key):
    """[{message_id, campaign_id, location_id}] using this key. No message and no campaign: a preview."""
    ensure_voice_audio_table(cursor)
    cursor.execute("SELECT DISTINCT message_id, campaign_id, location_id FROM voice_audio WHERE audio_key = %s", (key,))
    return cursor.fetchall()


def message_ids_for_key(cursor, key):
    """[ids] of the messages that use this key; None in the list means a preview (anyone may hear)."""
    ensure_voice_audio_table(cursor)
    cursor.execute("SELECT DISTINCT message_id FROM voice_audio WHERE audio_key = %s", (key,))
    return [r.get("message_id") for r in cursor.fetchall()]


def forget_campaign_audio(cursor, campaign_id):
    """Drop a deleted chronicle's audio of no message (recaps), and the files nothing else uses."""
    ensure_voice_audio_table(cursor)
    cursor.execute("SELECT DISTINCT audio_key FROM voice_audio WHERE message_id IS NULL AND campaign_id = %s",
                   (campaign_id,))
    keys = [r["audio_key"] for r in cursor.fetchall()]
    cursor.execute("DELETE FROM voice_audio WHERE message_id IS NULL AND campaign_id = %s", (campaign_id,))
    return _drop_unused(cursor, keys)


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
    return _drop_unused(cursor, keys)


def _drop_unused(cursor, keys):
    gone = []
    for key in keys:
        # Claim the file with a tombstone row only if no row uses the key (one statement, so a
        # line cached meanwhile keeps its file); the file goes, then the tombstone.
        cursor.execute(
            "INSERT INTO voice_audio (message_id, audio_key, voice_id) "
            "SELECT -1, %s, NULL WHERE NOT EXISTS (SELECT 1 FROM voice_audio WHERE audio_key = %s)",
            (key, key),
        )
        if cursor.rowcount != 1:
            continue  # another message (or a preview) still says the same words
        try:
            speech_client.call_json("DELETE", f"/audio/{key}")
        except speech_client.SpeechUnavailable:
            logger.warning("speech service down: audio %s left in the cache", key[:8])
        cursor.execute("DELETE FROM voice_audio WHERE message_id = -1 AND audio_key = %s", (key,))
        gone.append(key)
    return gone
