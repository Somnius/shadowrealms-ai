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
  GET     /api/voice/health                       site admin: speech status, queues, VRAM, disk, minutes today, cloud errors
  GET/PUT /api/voice/cloud-settings               site admin: cloud voices (Gemini) off / free / paid, model
  GET     /api/voice/translations?campaign_id&location_id&ids=1,2&lang=el
                                                  translations / originals of a room's messages
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
    ensure_message_translations_table,
    ensure_messages_voice_columns,
    ensure_users_voice_settings_column,
    get_db,
)
from routes.messages import room_visible, visible_message
from services.location_access import user_can_bypass_closed_location
from services import cloud_voices, speech_client, transcript_check, translation, voice_audio, voice_clips
from services.request_validation import RequestValidationError
from services.voice_tts import PREVIEW_TEXT, guess_lang, readout_kind, tts_bodies
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
        translation.forget_members()  # hear-in language changes count from the next message
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
            "cloud_available": _cloud_config()["tier"] != "off",
        }), 200
    except Exception as e:  # noqa: BLE001
        logger.error("chronicle voice settings error: %s", type(e).__name__)
        return jsonify({"error": "Failed to load voice settings"}), 500
    finally:
        conn.close()


@voice_bp.route("/campaigns/<int:campaign_id>/voice-clips", methods=["DELETE"])
@jwt_required()
def delete_campaign_clips(campaign_id):
    """The Storyteller (creator) or an admin deletes every voice recording of the chronicle; the
    messages keep their text and the mic mark, only the replay goes (0.22)."""
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    conn, cursor = _open()
    try:
        row, can_edit = _campaign_access(cursor, campaign_id, user_id)
        if row is None:
            return jsonify({"error": "Chronicle not found"}), 404
        if not can_edit:
            return jsonify({"error": "Only the Storyteller can change this"}), 403
        ensure_messages_voice_columns(cursor)
        gone = voice_clips.forget_sent_clips(cursor, campaign_id)  # unsent drafts: the 24 h sweep
        conn.commit()
        voice_clips.drop_files(gone)  # files only once the rows are gone for good
        return jsonify({"deleted": len(gone)}), 200
    except Exception as e:  # noqa: BLE001
        logger.error("delete chronicle clips error: %s", type(e).__name__)
        return jsonify({"error": "Failed to delete the recordings"}), 500
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
        if status == 400 and job.get("error") == "unknown_voice" and body.get("voice"):
            # the character's chosen voice left the catalog: speak with the gender voice instead
            body = {k: v for k, v in body.items() if k != "voice"}
            status, job = speech_client.call_json("POST", "/tts", body)
    except speech_client.SpeechUnavailable:
        return _SPEECH_DOWN
    if status >= 400:
        code = job.get("error") if isinstance(job.get("error"), str) else "speech_failed"
        return {"error": code}, (503 if status >= 500 else 400)
    if job.get("key"):
        voice_audio.remember(cursor, message_id, job["key"], job.get("voice"))
    if job.get("fallback_key"):  # a cloud line that may end up in the local voice
        voice_audio.remember(cursor, message_id, job["fallback_key"], None)
    return _job_out(job), 200


# Cloud voices (0.23): the site setting; the speech service holds the keys and makes the call.

def _get_setting(key):
    try:
        from services.ai_runtime_settings import get_app_setting
        return get_app_setting(key)
    except Exception:  # noqa: BLE001  no settings table yet: cloud voices stay off
        return None


def _set_setting(key, value):
    from services.ai_runtime_settings import set_app_setting
    set_app_setting(key, value)


def _cloud_config():
    return cloud_voices.read_config(_get_setting)


def _in_hear_lang(cursor, msg, user_settings):
    """(message to speak, waiting). The listener's hear-in language: its translation (or the
    speaker's own original) when there is one; else a translation is queued and the client waits
    (never translated inside this audio request)."""
    hear = normalize_user_voice_settings(user_settings).get("hear_lang")
    src = msg.get("lang") or guess_lang(msg.get("content"))
    if hear not in translation.LANGS or hear == src or translation.readout_skip(msg):
        return msg, False
    ensure_message_translations_table(cursor)
    row = translation.get_rows(cursor, [msg["id"]]).get(int(msg["id"]), {}).get(hear)
    if row:
        return {**msg, "content": row["text"], "lang": hear}, False
    translation.schedule(msg["id"], [hear])
    return msg, True


def _dice_marker(cursor, msg):
    """The JSON marker row of a roll line (same room, same animation id), or None."""
    kind = str(msg.get("ai_message_kind") or "").strip().lower()
    prefix, _, anim = kind.partition(":")
    if not anim:
        return None
    marker_kind = ("dice_animation_hidden:" if prefix == "dice_roll_hidden" else "dice_animation:") + anim
    cursor.execute(
        "SELECT content FROM messages WHERE campaign_id = %s AND location_id = %s "
        "AND LOWER(ai_message_kind) = %s ORDER BY id ASC LIMIT 1",
        (msg["campaign_id"], msg["location_id"], marker_kind),
    )
    row = cursor.fetchone()
    try:
        out = json.loads((row or {}).get("content") or "")
    except (TypeError, ValueError):
        return None
    return out if isinstance(out, dict) else None


@voice_bp.route("/voice/voices", methods=["GET"])
@jwt_required()
def voices():
    # 200 with available false when the service is off: a GET 503 would raise the app-wide notice
    try:
        status, data = speech_client.call_json("GET", "/voices")
    except speech_client.SpeechUnavailable:
        status, data = 503, {}
    if status != 200:
        return jsonify({"available": False, "voices": [], "defaults": {}, "cloud_voices": []}), 200
    on = _cloud_config()["tier"] != "off"
    return jsonify({"available": True, "voices": data.get("voices") or [],
                    "defaults": data.get("defaults") or {},
                    "cloud_voices": (data.get("cloud_voices") or []) if on else []}), 200


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
    chunk = data.get("chunk", 0)  # read along (0.22): one job per sentence-sized chunk
    if isinstance(chunk, bool) or not isinstance(chunk, int) or not 0 <= chunk < 200:
        return jsonify({"error": "chunk must be a chunk number"}), 400
    ui_lang = data.get("lang") if data.get("lang") in ("en", "el") else None
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
        gender = override = None
        if msg.get("character_id"):
            cursor.execute("SELECT gender, voice_override FROM characters WHERE id = %s",
                           (msg["character_id"],))
            ch = cursor.fetchone() or {}
            gender, override = ch.get("gender"), ch.get("voice_override")
        cursor.execute("SELECT voice_settings FROM campaigns WHERE id = %s", (msg["campaign_id"],))
        camp = (cursor.fetchone() or {}).get("voice_settings")
        user_settings = _user_settings(cursor, user_id)
        original = msg.get("content")
        if data.get("original") is not True:
            msg, waiting = _in_hear_lang(cursor, msg, user_settings)
            if waiting:
                return jsonify({"state": "waiting_translation"}), 200
        hear = normalize_user_voice_settings(user_settings).get("hear_lang")
        listen_lang = hear if hear in ("en", "el") else (ui_lang or "en")
        marker = _dice_marker(cursor, msg) if readout_kind(msg) == "dice" else None
        bodies = tts_bodies(msg, gender, user_settings, camp, override, listen_lang=listen_lang,
                            marker=marker, roll_source=original)
        if not bodies:
            return jsonify({"error": "not_spoken"}), 400
        if chunk >= len(bodies):
            return jsonify({"error": "no_such_chunk"}), 400
        out, status = _speech_tts(cursor, cloud_voices.apply(bodies[chunk], _cloud_config(), camp), mid)
        conn.commit()
        if status == 200:
            out.update({"chunk": chunk, "chunks": len(bodies), "text": bodies[chunk]["text"]})
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
    except speech_client.SpeechUnavailable:  # a failed job, not a GET 503 (app-wide notice)
        return jsonify({"job_id": job_id, "state": "failed", "error": "speech_unavailable"}), 200
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
        body = {"text": PREVIEW_TEXT[lang], "lang": lang, "voice": vid}
        cfg = _cloud_config()
        if cloud_voices.is_cloud_voice(vid):
            if cfg["tier"] == "off":
                return jsonify({"error": "cloud_voices_off"}), 400
            body["cloud"] = {"tier": cfg["tier"], "model": cfg["model"]}
        out, status = _speech_tts(cursor, body, None)
        conn.commit()
        return jsonify(out), status
    finally:
        conn.close()


# ---------------------------------------------------------------------------------------------
# Speaking (Phase 3): a recorded clip goes up only when the player taps Transcribe; the speech
# service keeps it as Ogg/Opus and transcribes it (Whisper on the GPU, or gpu_busy). The text
# comes back to the player to edit; nothing is posted until they send it (save_message, clip_id).

_MIMES = ("audio/webm", "audio/mp4", "audio/ogg", "audio/mpeg", "audio/wav", "audio/x-m4a", "audio/aac")


def _room_ok(cursor, campaign_id, location_id, user_id):
    """The chronicle row when this player may post in this room (same closed-room rule as
    save_message), else None."""
    row, _ = _campaign_access(cursor, campaign_id, user_id)
    if row is None:
        return None
    cursor.execute("SELECT campaign_id, is_open FROM locations WHERE id = %s", (location_id,))
    loc = cursor.fetchone()
    if not loc or int(loc["campaign_id"]) != int(campaign_id):
        return None
    raw_open = loc.get("is_open")
    is_open = True if raw_open is None else bool(raw_open) if not isinstance(raw_open, (int, float)) else raw_open != 0
    if not is_open and not user_can_bypass_closed_location(cursor, user_id, campaign_id):
        return None
    return row


@voice_bp.route("/voice/clips", methods=["POST"])
@jwt_required()
def create_clip():
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    f = request.files.get("audio")
    lang = request.form.get("lang", "")
    try:
        campaign_id = int(request.form.get("campaign_id", ""))
        location_id = int(request.form.get("location_id", ""))
    except ValueError:
        return jsonify({"error": "campaign_id and location_id are needed"}), 400
    if f is None:
        return jsonify({"error": "audio is needed"}), 400
    if lang not in ("el", "en"):
        return jsonify({"error": "lang must be el or en"}), 400
    mime = (f.mimetype or "").split(";")[0].strip().lower()
    if mime not in _MIMES:
        return jsonify({"error": "bad_format"}), 400
    data = f.read(voice_clips.max_clip_bytes() + 1)
    if not data:
        return jsonify({"error": "empty_upload"}), 400
    if len(data) > voice_clips.max_clip_bytes():
        return jsonify({"error": "too_large"}), 413
    conn, cursor = _open()
    try:
        camp = _room_ok(cursor, campaign_id, location_id, user_id)
        if camp is None:
            return jsonify({"error": "Chronicle not found"}), 404
        max_s = normalize_campaign_voice_settings(camp.get("voice_settings"))["max_clip_seconds"]
        if voice_clips.used_bytes(cursor) >= voice_clips.clips_max_bytes():
            return jsonify({"error": "clips_disk_full"}), 507
        fields = {"lang": lang, "max_seconds": str(max_s)}
        if transcript_check.enabled():  # phase 6: names as a Whisper hint, Laya flags misheard words
            fields["prompt"] = transcript_check.whisper_prompt(
                transcript_check.chronicle_names(cursor, campaign_id), lang)
            fields["check"] = "1"
        try:
            status, job = speech_client.call_upload("/stt", fields, "clip", data, mime)
        except speech_client.SpeechUnavailable:
            return jsonify(_SPEECH_DOWN[0]), 503
        if status >= 400 or not job.get("clip"):
            code = job.get("error") if isinstance(job.get("error"), str) else "speech_failed"
            return jsonify({"error": code}), (503 if status >= 500 else 400)
        try:
            dur_ms = int(round(float(job["duration"]) * 1000)) if job.get("duration") else None
        except (TypeError, ValueError):
            dur_ms = None
        voice_clips.record(cursor, job["clip"], campaign_id, location_id, user_id, lang, dur_ms)
        conn.commit()
        out = _job_out(job)
        out["clip_id"] = job["clip"]
        return jsonify(out), 200
    except Exception as e:  # noqa: BLE001
        logger.error("clip upload error: %s", type(e).__name__)
        return jsonify({"error": "Failed to keep the recording"}), 500
    finally:
        conn.close()


@voice_bp.route("/voice/stt/jobs/<job_id>", methods=["GET"])
@jwt_required()
def stt_job_status(job_id):
    user_id = _uid()
    if user_id is None or not _HEX.match(job_id or ""):
        return jsonify({"error": "Job not found"}), 404
    try:
        status, job = speech_client.call_json("GET", f"/stt/{job_id}")
    except speech_client.SpeechUnavailable:
        return jsonify({"job_id": job_id, "state": "failed", "error": "speech_unavailable"}), 200
    if status != 200:
        return jsonify({"error": "Job not found"}), 404
    conn, cursor = _open()
    try:
        clip = voice_clips.get(cursor, job.get("clip"))
        if clip is None or int(clip["user_id"]) != user_id:
            return jsonify({"error": "Job not found"}), 404
        out = _job_out(job)
        out["clip_id"] = clip["clip_id"]
        if job.get("status") == "done":
            text = (job.get("text") or "").strip()
            if clip.get("transcript_raw") is None:
                voice_clips.note_transcript(cursor, clip["clip_id"], text, job.get("duration"))
                conn.commit()
            out["text"] = text
            segs = voice_clips.checked_segments(clip)
            if segs is None and job.get("words"):
                # Phase 6: Krikri fixes only Laya's flagged words, within 4.5 s, else Whisper's text
                segs = transcript_check.check(
                    job["words"], job.get("suspects") or [], clip.get("lang") or "en",
                    transcript_check.chronicle_names(cursor, int(clip["campaign_id"])),
                    probs=job.get("probs"))
                voice_clips.note_checked(cursor, clip["clip_id"], segs)
                conn.commit()
            if segs:
                out["checked"] = segs
                out["text"] = transcript_check.text_of(segs)
                out["text_raw"] = text
            out["duration_ms"] = int(round(float(job.get("duration") or 0) * 1000))
            write = normalize_user_voice_settings(_user_settings(cursor, user_id)).get("write_lang")
            spoke = clip.get("lang") or guess_lang(text)
            text = out["text"]  # the checked text when the check fixed something
            if text and write in translation.LANGS and write != spoke:
                # the text step shows both at once (one short line through the translator role)
                try:
                    if clip.get("translated_lang") == write and clip.get("translated_text"):
                        tr = clip["translated_text"]
                    else:
                        tr, _ = translation.translate(
                            text, spoke, write, names=translation.chronicle_names(cursor, clip.get("campaign_id")))
                        voice_clips.note_translation(cursor, clip["clip_id"], write, tr)
                        conn.commit()
                    out["translated"] = {"lang": write, "text": tr}
                except Exception as e:  # noqa: BLE001
                    logger.warning("dictation translation failed: %s", type(e).__name__)
                    out["translate_failed"] = write
        return jsonify(out), 200
    finally:
        conn.close()


@voice_bp.route("/voice/clips/<clip_id>/audio", methods=["GET"])
@jwt_required()
def clip_audio(clip_id):
    """Everyone who can read the message may replay it; an unsent clip only its owner."""
    user_id = _uid()
    fmt = request.args.get("fmt", "ogg")
    if user_id is None or fmt not in ("ogg", "m4a"):
        return jsonify({"error": "Not found"}), 404
    conn, cursor = _open()
    try:
        for ensure in (ensure_character_portrait_url_column, ensure_messages_ai_message_kind_column,
                       ensure_messages_speaker_mode_column, ensure_messages_reply_to_column,
                       ensure_users_player_profile_columns):
            ensure(cursor)
        clip = voice_clips.get(cursor, clip_id)
        if clip is None:
            ok = False
        elif clip.get("message_id"):
            ok = visible_message(cursor, int(clip["message_id"]), user_id) is not None
        else:
            ok = int(clip["user_id"]) == user_id
    finally:
        conn.close()
    if not ok:
        return jsonify({"error": "Not found"}), 404
    try:
        status, raw, _ = speech_client.call_bytes(f"/clips/{clip_id}?fmt={fmt}")
    except speech_client.SpeechUnavailable:
        return jsonify(_SPEECH_DOWN[0]), 503
    if status != 200:
        return jsonify({"error": "Not found"}), 404
    resp = Response(raw, mimetype="audio/ogg" if fmt == "ogg" else "audio/mp4")
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


# ---------------------------------------------------------------------------------------------
# Health (Phase 5): site admins only.

@voice_bp.route("/voice/health", methods=["GET"])
@jwt_required()
def voice_health():
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    conn, cursor = _open()
    try:
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        u = cursor.fetchone()
        if not u or u.get("role") != "admin":
            return jsonify({"error": "Admin only"}), 403
        minutes = voice_clips.minutes_today(cursor)
        est = voice_clips.used_bytes(cursor)
    finally:
        conn.close()
    try:
        status, speech = speech_client.call_json("GET", "/health")
    except speech_client.SpeechUnavailable:
        status, speech = 503, {}
    up = status == 200
    stt, tts, clips = (speech.get(k) or {} for k in ("stt", "tts", "clips")) if up else ({}, {}, {})
    return jsonify({
        "speech": {"up": up, "stt_loaded": stt.get("loaded"), "pocket_loaded": tts.get("pocket_loaded"),
                   "pocket_error": tts.get("pocket_error")},
        "queues": {"stt": stt.get("queue"), "tts": tts.get("queue")},
        "vram": {"free_mb": stt.get("vram_free_mb"), "needed_mb": stt.get("vram_needed_mb")},
        "disk": {"clips_bytes": clips.get("bytes"), "clips_estimate_bytes": est,
                 "clips_cap_bytes": voice_clips.clips_max_bytes(),
                 "tts_cache_bytes": tts.get("cache_bytes"), "tts_cache_cap_bytes": tts.get("cache_cap_bytes")},
        "minutes_today": minutes,
        "cloud": dict(speech.get("cloud") or {}, **_cloud_config()) if up else _cloud_config(),
    }), 200


def _is_admin(cursor, user_id):
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone()
    return bool(u and u.get("role") == "admin")


@voice_bp.route("/voice/cloud-settings", methods=["GET", "PUT"])
@jwt_required()
def cloud_settings():
    """Admin → AI system → Cloud voices (Gemini): off / free / paid, and the model. Keys are
    reported present or not (asked of the speech service, which holds them), never shown."""
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    conn, cursor = _open()
    try:
        if not _is_admin(cursor, user_id):
            return jsonify({"error": "Admin only"}), 403
    finally:
        conn.close()
    if request.method == "PUT":
        try:
            cfg = cloud_voices.validate_config(request.get_json(silent=True))
        except RequestValidationError as e:
            return jsonify({"error": e.public_message}), 400
        _set_setting(cloud_voices.SETTING_TIER, None if cfg["tier"] == "off" else cfg["tier"])
        _set_setting(cloud_voices.SETTING_MODEL,
                     None if cfg["model"] == cloud_voices.DEFAULT_MODEL else cfg["model"])
    try:
        status, speech = speech_client.call_json("GET", "/health")
    except speech_client.SpeechUnavailable:
        status, speech = 503, {}
    keys = (speech.get("cloud") or {}).get("keys") if status == 200 else None
    return jsonify(dict(_cloud_config(), models=list(cloud_voices.MODELS),
                        keys=keys if isinstance(keys, dict) else None)), 200


# Language override (Phase 4): captions. Translations are made ahead of time (after the message
# is saved); this only reads them, and queues one that a listener needs but nobody made yet.

MAX_TRANSLATION_IDS = 60
RECENT_TRANSLATION_WINDOW = 200  # GET only queues jobs for the newest lines of a room


@voice_bp.route("/voice/translations", methods=["GET"])
@jwt_required()
def room_translations():
    user_id = _uid()
    if user_id is None:
        return jsonify({"error": "Invalid session"}), 401
    lang = request.args.get("lang") or ""
    try:
        campaign_id = int(request.args.get("campaign_id", ""))
        location_id = int(request.args.get("location_id", ""))
        ids = sorted({int(x) for x in (request.args.get("ids") or "").split(",") if x.strip()})
    except ValueError:
        return jsonify({"error": "campaign_id, location_id and ids are needed"}), 400
    if lang and lang not in translation.LANGS:
        return jsonify({"error": "lang must be en or el"}), 400
    ids = ids[:MAX_TRANSLATION_IDS]
    conn, cursor = _open()
    try:
        ensure_messages_voice_columns(cursor)
        ensure_messages_ai_message_kind_column(cursor)
        ensure_message_translations_table(cursor)
        conn.commit()
        if not room_visible(cursor, campaign_id, location_id, user_id):
            return jsonify({"error": "Not found"}), 404
        if not ids:
            return jsonify({"translations": {}, "pending": []}), 200
        marks = ",".join(["%s"] * len(ids))
        cursor.execute(
            f"SELECT id, content, lang, role, message_type, ai_message_kind FROM messages"
            f" WHERE campaign_id = %s AND location_id = %s AND id IN ({marks})",
            [campaign_id, location_id, *ids],
        )
        msgs = {int(r["id"]): r for r in cursor.fetchall() if not translation.readout_skip(r)}
        # only the room's recent lines are queued from here (old ids are answered, never queued)
        cursor.execute("SELECT MAX(id) AS top FROM messages WHERE campaign_id = %s AND location_id = %s",
                       (campaign_id, location_id))
        top = cursor.fetchone() or {}
        floor = int(top.get("top") or 0) - RECENT_TRANSLATION_WINDOW
        rows = translation.get_rows(cursor, msgs.keys())
        out, pending = {}, []
        for mid, m in msgs.items():
            have = rows.get(mid, {})
            mine = {lg: r for lg, r in have.items() if r["kind"] == "original" or lg == lang}
            if mine:
                out[str(mid)] = mine
            src = m.get("lang") or guess_lang(m.get("content"))
            if lang and lang != src and lang not in have:
                if translation.is_pending(mid, lang) or (
                        mid > floor and translation.schedule(mid, [lang], cap=translation.MAX_PENDING)):
                    pending.append(mid)
        return jsonify({"translations": out, "pending": pending}), 200
    finally:
        conn.close()


@voice_bp.route("/voice/translate", methods=["POST"])
@jwt_required()
def translate_text():
    """The recorder's text step: the player's own line into the write-in language (phone
    dictation, or after editing the transcript). Short lines only."""
    if _uid() is None:
        return jsonify({"error": "Invalid session"}), 401
    data = request.get_json(silent=True) or {}
    text, src, dst = data.get("text"), data.get("from"), data.get("to")
    if (not isinstance(text, str) or not text.strip() or len(text) > translation.MAX_CHARS
            or src not in translation.LANGS or dst not in translation.LANGS or src == dst):
        return jsonify({"error": "text, from and to (en or el, different) are needed"}), 400
    try:
        out, _ = translation.translate(text, src, dst)
    except Exception as e:  # noqa: BLE001
        logger.warning("translate failed: %s", type(e).__name__)
        return jsonify({"error": "translation_failed"}), 503
    return jsonify({"lang": dst, "text": out}), 200
