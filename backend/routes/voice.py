"""
Voice (docs/VOICE.md).

  GET/PUT /api/voice/settings                     the player's own choices (users.voice_settings)
  GET     /api/campaigns/<cid>/voice-settings     chronicle defaults + this player's effective rules
  PUT     /api/campaigns/<cid>/voice-settings     creator or site admin
  GET     /api/voice/voices                       the speech service's catalog
  POST    /api/voice/tts/jobs {message_id}        speak a line: a job, or done at once from the cache
  GET     /api/voice/tts/jobs/<job_id>            job state
  GET     /api/voice/audio/<key>?fmt=ogg|m4a      the audio, for whoever may read one of its messages
  POST    /api/voice/tts/preview {voice_id}       a fixed sample sentence in that voice
"""

import json
import logging

import re

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database import (
    ensure_character_portrait_url_column,
    ensure_characters_gender_column,
    ensure_messages_ai_message_kind_column,
    ensure_messages_reply_to_column,
    ensure_messages_speaker_mode_column,
    ensure_users_player_profile_columns,
    ensure_voice_audio_table,
    ensure_campaigns_voice_settings_column,
    ensure_users_voice_settings_column,
    get_db,
)
from routes.messages import visible_message
from services import speech_client, voice_audio
from services.request_validation import RequestValidationError
from services.voice_tts import PREVIEW_TEXT, tts_request
from services.voice_settings import (
    effective_readout,
    normalize_campaign_voice_settings,
    normalize_user_voice_settings,
    validate_campaign_voice_settings,
    validate_user_voice_settings,
)

logger = logging.getLogger(__name__)
voice_bp = Blueprint("voice", __name__)


def _uid():
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError):
        return None


def _open():
    conn = get_db()
    cursor = conn.cursor()
    ensure_users_voice_settings_column(cursor)
    ensure_campaigns_voice_settings_column(cursor)
    conn.commit()
    return conn, cursor


def _user_settings(cursor, user_id):
    cursor.execute("SELECT voice_settings FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    return row.get("voice_settings") if row else None


@voice_bp.route("/voice/settings", methods=["GET", "PUT"])
@jwt_required()
def my_voice_settings():
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    conn, cursor = _open()
    try:
        current = _user_settings(cursor, user_id)
        if request.method == "GET":
            return jsonify(normalize_user_voice_settings(current)), 200
        try:
            settings = validate_user_voice_settings(request.get_json(silent=True), current)
        except RequestValidationError as e:
            return jsonify({"error": e.public_message}), 400
        cursor.execute(
            "UPDATE users SET voice_settings = %s WHERE id = %s", (json.dumps(settings), user_id)
        )
        conn.commit()
        return jsonify(settings), 200
    except Exception as e:  # noqa: BLE001
        logger.error("voice settings error: %s", type(e).__name__)
        return jsonify({"error": "Failed to save voice settings"}), 500
    finally:
        conn.close()


def _campaign_access(cursor, campaign_id, user_id):
    """(row, can_edit) when the viewer may open the chronicle, else (None, False)."""
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone()
    is_admin = bool(u and u.get("role") == "admin")
    cursor.execute(
        "SELECT id, created_by, voice_settings FROM campaigns WHERE id = %s", (campaign_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None, False
    is_creator = str(row.get("created_by")) == str(user_id)
    if not (is_admin or is_creator):
        cursor.execute(
            "SELECT 1 FROM campaign_players WHERE campaign_id = %s AND user_id = %s",
            (campaign_id, user_id),
        )
        if not cursor.fetchone():
            return None, False
    return row, is_admin or is_creator


@voice_bp.route("/campaigns/<int:campaign_id>/voice-settings", methods=["GET", "PUT"])
@jwt_required()
def campaign_voice_settings(campaign_id):
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    conn, cursor = _open()
    try:
        row, can_edit = _campaign_access(cursor, campaign_id, user_id)
        if row is None:
            return jsonify({"error": "Chronicle not found"}), 404
        current = row.get("voice_settings")
        if request.method == "PUT":
            if not can_edit:
                return jsonify({"error": "Only the Storyteller can change this"}), 403
            try:
                current = validate_campaign_voice_settings(request.get_json(silent=True), current)
            except RequestValidationError as e:
                return jsonify({"error": e.public_message}), 400
            cursor.execute(
                "UPDATE campaigns SET voice_settings = %s WHERE id = %s",
                (json.dumps(current), campaign_id),
            )
            conn.commit()
        return jsonify({
            "settings": normalize_campaign_voice_settings(current),
            "can_edit": can_edit,
            "effective": effective_readout(_user_settings(cursor, user_id), current),
        }), 200
    except Exception as e:  # noqa: BLE001
        logger.error("chronicle voice settings error: %s", type(e).__name__)
        return jsonify({"error": "Failed to load voice settings"}), 500
    finally:
        conn.close()


# ---------------------------------------------------------------------------------------------
# Server voices (Phase 2): the speech service does the work and keeps the cache.

_HEX = re.compile(r"^[A-Za-z0-9]{8,80}$")
_SPEECH_DOWN = ({"error": "speech_unavailable"}, 503)


def _job_out(job):
    out = {"job_id": job.get("id"), "state": job.get("status")}
    for k in ("position", "key", "error"):
        if job.get(k) is not None:
            out[k] = job[k]
    return out


def _speech_tts(cursor, body, message_id):
    """POST /tts on the speech service; remembers the key. (json, status)."""
    try:
        status, job = speech_client.call_json("POST", "/tts", body)
    except speech_client.SpeechUnavailable:
        return _SPEECH_DOWN
    if status >= 400:
        code = job.get("error") if isinstance(job.get("error"), str) else "speech_failed"
        return {"error": code}, (503 if status >= 500 else 400)
    if job.get("key"):
        voice_audio.remember(cursor, message_id, job["key"], job.get("voice"))
    return _job_out(job), 200


@voice_bp.route("/voice/voices", methods=["GET"])
@jwt_required()
def voices():
    try:
        status, data = speech_client.call_json("GET", "/voices")
    except speech_client.SpeechUnavailable:
        return jsonify(_SPEECH_DOWN[0]), 503
    if status != 200:
        return jsonify({"error": "speech_failed"}), 503
    return jsonify({"voices": data.get("voices") or [], "defaults": data.get("defaults") or {}}), 200


@voice_bp.route("/voice/tts/jobs", methods=["POST"])
@jwt_required()
def create_tts_job():
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    data = request.get_json(silent=True) or {}
    mid = data.get("message_id")
    if isinstance(mid, bool) or not isinstance(mid, int) or mid <= 0:
        return jsonify({"error": "message_id must be a message id"}), 400
    conn, cursor = _open()
    try:
        for ensure in (ensure_character_portrait_url_column, ensure_messages_ai_message_kind_column, ensure_messages_speaker_mode_column,
                       ensure_messages_reply_to_column, ensure_users_player_profile_columns,
                       ensure_characters_gender_column, ensure_voice_audio_table):
            ensure(cursor)
        conn.commit()
        msg = visible_message(cursor, mid, user_id)
        if msg is None:
            return jsonify({"error": "Message not found"}), 404
        gender = None
        if msg.get("character_id"):
            cursor.execute("SELECT gender FROM characters WHERE id = %s", (msg["character_id"],))
            gender = (cursor.fetchone() or {}).get("gender")
        cursor.execute("SELECT voice_settings FROM campaigns WHERE id = %s", (msg["campaign_id"],))
        camp = (cursor.fetchone() or {}).get("voice_settings")
        body = tts_request(msg, gender, _user_settings(cursor, user_id), camp)
        if body is None:
            return jsonify({"error": "not_spoken"}), 400
        out, status = _speech_tts(cursor, body, mid)
        conn.commit()
        return jsonify(out), status
    except Exception as e:  # noqa: BLE001
        logger.error("tts job error: %s", type(e).__name__)
        return jsonify({"error": "Failed to start speech"}), 500
    finally:
        conn.close()


@voice_bp.route("/voice/tts/jobs/<job_id>", methods=["GET"])
@jwt_required()
def tts_job_status(job_id):
    if not _HEX.match(job_id or ""):
        return jsonify({"error": "Job not found"}), 404
    try:
        status, job = speech_client.call_json("GET", f"/tts/{job_id}")
    except speech_client.SpeechUnavailable:
        return jsonify(_SPEECH_DOWN[0]), 503
    if status != 200:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(_job_out(job)), 200


@voice_bp.route("/voice/audio/<key>", methods=["GET"])
@jwt_required()
def tts_audio(key):
    user_id = _uid()
    fmt = request.args.get("fmt", "ogg")
    if user_id is None or not _HEX.match(key or "") or fmt not in ("ogg", "m4a"):
        return jsonify({"error": "Not found"}), 404
    conn, cursor = _open()
    try:
        for ensure in (ensure_character_portrait_url_column, ensure_messages_ai_message_kind_column, ensure_messages_speaker_mode_column,
                       ensure_messages_reply_to_column, ensure_users_player_profile_columns):
            ensure(cursor)
        ids = voice_audio.message_ids_for_key(cursor, key)
        ok = any(i is None or visible_message(cursor, i, user_id) is not None for i in ids)
    finally:
        conn.close()
    if not ok:
        return jsonify({"error": "Not found"}), 404
    try:
        status, raw, ctype = speech_client.call_bytes(f"/audio/{key}?fmt={fmt}")
    except speech_client.SpeechUnavailable:
        return jsonify(_SPEECH_DOWN[0]), 503
    if status != 200:
        return jsonify({"error": "Not found"}), 404
    resp = Response(raw, mimetype="audio/ogg" if fmt == "ogg" else "audio/mp4")
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@voice_bp.route("/voice/tts/preview", methods=["POST"])
@jwt_required()
def tts_preview():
    data = request.get_json(silent=True) or {}
    vid = data.get("voice_id")
    lang = data.get("lang")
    if not isinstance(vid, str) or not 0 < len(vid) <= 80 or lang not in PREVIEW_TEXT:
        return jsonify({"error": "voice_id and lang (en or el) are needed"}), 400
    conn, cursor = _open()
    try:
        ensure_voice_audio_table(cursor)
        out, status = _speech_tts(cursor, {"text": PREVIEW_TEXT[lang], "lang": lang, "voice": vid}, None)
        conn.commit()
        return jsonify(out), status
    finally:
        conn.close()
