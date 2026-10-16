"""
Voice (docs/VOICE.md), Phase 1: settings only; the phone reads messages out by itself.

  GET/PUT /api/voice/settings                     the player's own choices (users.voice_settings)
  GET     /api/campaigns/<cid>/voice-settings     chronicle defaults + this player's effective rules
  PUT     /api/campaigns/<cid>/voice-settings     creator or site admin
"""

import json
import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from database import (
    ensure_campaigns_voice_settings_column,
    ensure_users_voice_settings_column,
    get_db,
)
from services.request_validation import RequestValidationError
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
