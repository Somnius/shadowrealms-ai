#!/usr/bin/env python3
"""
ShadowRealms AI - Admin User Management Routes
Administrative controls for user moderation, bans, and character management
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import bcrypt
import json
import logging
import os
import re
import secrets
from datetime import datetime, timedelta

from database import (
    get_db,
    ensure_character_downtime_requests_table,
    ensure_characters_is_active_column,
    ensure_characters_is_npc_column,
    ensure_characters_play_suspension_columns,
    ensure_characters_wod_sheet_columns,
    ensure_character_portrait_url_column,
    ensure_users_allow_multi_campaign_play_column,
    ensure_users_self_switch_playing_character_column,
    ensure_users_restrict_self_join_new_chronicles_column,
    ensure_campaigns_listing_columns,
    ensure_campaigns_staff_pause_columns,
)
from services.moderation_audit import log_moderation_action, moderation_entry_kind
from routes.auth import load_invites, save_invites
from services.play_suspension import ALLOWED_REASON_CODES

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def _sql_ph() -> str:
    return "%s" if os.getenv("DATABASE_TYPE", "sqlite").lower() == "postgresql" else "?"

def require_admin():
    """Decorator to ensure user is admin"""
    def decorator(f):
        @jwt_required()
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.close()
            db.close()
            
            if not user or user['role'] != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
            
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

@bp.route('/users', methods=['GET'])
@require_admin()
def get_all_users():
    """Get all users with their status"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        ensure_users_allow_multi_campaign_play_column(cursor)
        ensure_users_self_switch_playing_character_column(cursor)
        db.commit()
        cursor.execute("""
            SELECT id, username, email, role, is_active, created_at, last_login,
                   ban_type, ban_until, ban_reason, banned_by, banned_at,
                   allow_multi_campaign_play, self_switch_playing_character
            FROM users
            ORDER BY created_at DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            user_data = {
                'id': row['id'],
                'username': row['username'],
                'email': row['email'],
                'role': row['role'],
                'is_active': bool(row['is_active']),
                'created_at': row['created_at'],
                'last_login': row['last_login'],
                'ban_type': row['ban_type'],
                'ban_until': row['ban_until'],
                'ban_reason': row['ban_reason'],
                'banned_by': row['banned_by'],
                'banned_at': row['banned_at'],
                'allow_multi_campaign_play': bool(
                    row.get('allow_multi_campaign_play') or False
                ),
                'self_switch_playing_character': bool(
                    row.get('self_switch_playing_character') or False
                ),
            }
            
            # Check if temp ban has expired
            if user_data['ban_type'] == 'temporary' and user_data['ban_until']:
                # PostgreSQL returns datetime objects, SQLite returns strings
                ban_until = user_data['ban_until']
                if isinstance(ban_until, str):
                    ban_until = datetime.fromisoformat(ban_until)
                
                if datetime.now() > ban_until:
                    user_data['ban_type'] = None
                    user_data['is_banned'] = False
                else:
                    user_data['is_banned'] = True
                    user_data['ban_time_remaining'] = str(ban_until - datetime.now())
            elif user_data['ban_type'] == 'permanent':
                user_data['is_banned'] = True
            else:
                user_data['is_banned'] = False
            
            users.append(user_data)
        
        cursor.close()
        db.close()
        
        return jsonify(users), 200
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'error': 'Failed to get users'}), 500

@bp.route('/users/<int:user_id>', methods=['PUT'])
@require_admin()
def update_user(user_id):
    """Update user profile (username, email)"""
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        updates = []
        params = []
        
        if 'username' in data:
            updates.append("username = %s")
            params.append(data['username'])
        
        if 'email' in data:
            updates.append("email = %s")
            params.append(data['email'])
        
        if 'role' in data and data['role'] in ['admin', 'player']:
            updates.append("role = %s")
            params.append(data['role'])

        if 'allow_multi_campaign_play' in data:
            ensure_users_allow_multi_campaign_play_column(cursor)
            db.commit()
            updates.append("allow_multi_campaign_play = %s")
            params.append(bool(data['allow_multi_campaign_play']))

        if 'self_switch_playing_character' in data:
            ensure_users_self_switch_playing_character_column(cursor)
            db.commit()
            updates.append("self_switch_playing_character = %s")
            params.append(bool(data['self_switch_playing_character']))

        if 'restrict_self_join_new_chronicles' in data:
            ensure_users_restrict_self_join_new_chronicles_column(cursor)
            db.commit()
            updates.append("restrict_self_join_new_chronicles = %s")
            params.append(bool(data['restrict_self_join_new_chronicles']))
        
        if not updates:
            return jsonify({'error': 'No valid fields to update'}), 400
        
        params.append(user_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        
        cursor.execute(query, params)
        db.commit()
        
        # Log the action
        log_moderation_action(user_id, admin_id, 'edit_profile', {
            'updated_fields': list(data.keys())
        })
        
        cursor.close()
        db.close()
        
        return jsonify({'message': 'User updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return jsonify({'error': 'Failed to update user'}), 500

@bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@require_admin()
def reset_user_password(user_id):
    """Reset user password to admin-chosen password"""
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()
        
        new_password = data.get('new_password')
        if not new_password or len(new_password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", 
                      (password_hash.decode('utf-8'), user_id))
        db.commit()
        
        # Log the action
        log_moderation_action(user_id, admin_id, 'reset_password', {
            'reset_by_admin': True
        })
        
        cursor.close()
        db.close()
        
        return jsonify({'message': 'Password reset successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        return jsonify({'error': 'Failed to reset password'}), 500

@bp.route('/users/<int:user_id>/ban', methods=['POST'])
@require_admin()
def ban_user(user_id):
    """Ban a user (temporary or permanent)"""
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()
        
        ban_type = data.get('ban_type')  # 'temporary' or 'permanent'
        ban_reason = data.get('ban_reason', 'No reason provided')
        
        if ban_type not in ['temporary', 'permanent']:
            return jsonify({'error': 'Invalid ban type'}), 400
        
        ban_until = None
        if ban_type == 'temporary':
            duration_hours = data.get('duration_hours')
            duration_days = data.get('duration_days')
            
            if not duration_hours and not duration_days:
                return jsonify({'error': 'Duration required for temporary ban'}), 400
            
            hours = duration_hours or 0
            days = duration_days or 0
            ban_until = datetime.now() + timedelta(days=days, hours=hours)
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET ban_type = %s, ban_until = %s, ban_reason = %s, banned_by = %s, banned_at = %s, is_active = 0
            WHERE id = %s
        """, (ban_type, ban_until.isoformat() if ban_until else None, ban_reason, admin_id, datetime.now(), user_id))
        
        db.commit()
        
        # Log the action
        log_moderation_action(user_id, admin_id, 'ban', {
            'ban_type': ban_type,
            'ban_until': ban_until.isoformat() if ban_until else None,
            'ban_reason': ban_reason
        })
        
        cursor.close()
        db.close()
        
        return jsonify({'message': f'User banned ({ban_type})'}), 200
        
    except Exception as e:
        logger.error(f"Error banning user: {e}")
        return jsonify({'error': 'Failed to ban user'}), 500

@bp.route('/users/<int:user_id>/unban', methods=['POST'])
@require_admin()
def unban_user(user_id):
    """Unban a user"""
    try:
        admin_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET ban_type = NULL, ban_until = NULL, ban_reason = NULL, banned_by = NULL, banned_at = NULL, is_active = 1
            WHERE id = %s
        """, (user_id,))
        
        db.commit()
        
        # Log the action
        log_moderation_action(user_id, admin_id, 'unban', {})
        
        cursor.close()
        db.close()
        
        return jsonify({'message': 'User unbanned successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error unbanning user: {e}")
        return jsonify({'error': 'Failed to unban user'}), 500

@bp.route('/users/<int:user_id>/characters', methods=['GET'])
@require_admin()
def get_user_characters(user_id):
    """Get all characters for a user"""
    try:
        ph = _sql_ph()
        db = get_db()
        cursor = db.cursor()
        ensure_character_portrait_url_column(cursor)
        ensure_characters_is_active_column(cursor)
        ensure_characters_wod_sheet_columns(cursor)
        ensure_characters_is_npc_column(cursor)
        ensure_characters_play_suspension_columns(cursor)
        db.commit()

        cursor.execute(f"""
            SELECT id, name, system_type, campaign_id, is_npc, is_active, created_at,
                   sheet_locked,
                   play_suspended,
                   play_suspension_reason_code, play_suspension_message,
                   play_suspended_at, play_suspended_by
            FROM characters
            WHERE user_id = {ph}
            ORDER BY created_at DESC
        """, (user_id,))
        
        characters = []
        for row in cursor.fetchall():
            characters.append({
                'id': row['id'],
                'name': row['name'],
                'character_type': row.get('system_type'),
                'system_type': row.get('system_type'),
                'campaign_id': row['campaign_id'],
                'is_npc': bool(row.get('is_npc')),
                'is_active': bool(row['is_active']),
                'created_at': row['created_at'],
                'sheet_locked': bool(row.get('sheet_locked')),
                'play_suspended': bool(row.get('play_suspended') or False),
                'play_suspension_reason_code': row.get('play_suspension_reason_code'),
                'play_suspension_message': row.get('play_suspension_message'),
                'play_suspended_at': row.get('play_suspended_at'),
                'play_suspended_by': row.get('play_suspended_by'),
            })
        
        cursor.close()
        db.close()
        
        return jsonify(characters), 200
        
    except Exception as e:
        logger.error(f"Error getting characters: {e}")
        return jsonify({'error': 'Failed to get characters'}), 500

@bp.route('/characters/<int:character_id>/convert-to-npc', methods=['POST'])
@require_admin()
def convert_character_to_npc(character_id):
    """Convert a player character to NPC"""
    try:
        admin_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Update character to be NPC
        cursor.execute("""
            INSERT INTO character_moderation (character_id, action, moderated_by, moderated_at)
            VALUES (%s, 'convert_to_npc', %s, %s)
        """, (character_id, admin_id, datetime.now()))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({'message': 'Character converted to NPC'}), 200
        
    except Exception as e:
        logger.error(f"Error converting character: {e}")
        return jsonify({'error': 'Failed to convert character'}), 500

@bp.route('/characters/<int:character_id>/kill', methods=['POST'])
@require_admin()
def kill_character(character_id):
    """Kill a character with AI-generated death description"""
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()
        
        death_type = data.get('death_type', 'mid')  # 'soft', 'mid', 'horrible'
        
        if death_type not in ['soft', 'mid', 'horrible']:
            return jsonify({'error': 'Invalid death type'}), 400
        
        # TODO: Generate AI death description based on campaign events
        death_descriptions = {
            'soft': "Your character fades peacefully into the shadows, their story complete.",
            'mid': "In a moment of sacrifice, your character falls to save others.",
            'horrible': "The darkness claims your character in a brutal and terrifying end."
        }
        death_description = death_descriptions[death_type]
        
        db = get_db()
        cursor = db.cursor()
        
        # Deactivate character
        cursor.execute("""
            INSERT INTO character_moderation 
            (character_id, action, death_type, death_description, moderated_by, moderated_at)
            VALUES (%s, 'kill', %s, %s, %s, %s)
        """, (character_id, death_type, death_description, admin_id, datetime.now()))
        
        db.commit()
        cursor.close()
        db.close()
        
        return jsonify({
            'message': 'Character killed',
            'death_description': death_description
        }), 200
        
    except Exception as e:
        logger.error(f"Error killing character: {e}")
        return jsonify({'error': 'Failed to kill character'}), 500

@bp.route('/moderation-log', methods=['GET'])
@require_admin()
def get_moderation_log():
    """Get moderation action log"""
    try:
        limit = request.args.get('limit', 100, type=int)
        limit = max(1, min(limit, 500))
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT ml.id, ml.user_id, u.username AS target_username, ml.admin_id,
                   a.username AS actor_username,
                   ml.action, ml.details, ml.created_at
            FROM user_moderation_log ml
            LEFT JOIN users u ON ml.user_id = u.id
            LEFT JOIN users a ON ml.admin_id = a.id
            ORDER BY ml.created_at DESC
            LIMIT %s
        """, (limit,))
        
        logs = []
        for row in cursor.fetchall():
            details = json.loads(row['details']) if row['details'] else {}
            uid = row['user_id']
            aid = row['admin_id']
            action = row['action']
            logs.append({
                'id': row['id'],
                'user_id': uid,
                'username': row['target_username'],
                'admin_id': aid,
                'admin_username': row['actor_username'],
                'action': action,
                'details': details,
                'created_at': row['created_at'],
                'entry_kind': moderation_entry_kind(action, uid, aid, details),
            })
        
        cursor.close()
        db.close()
        
        return jsonify(logs), 200
        
    except Exception as e:
        logger.error(f"Error getting moderation log: {e}")
        return jsonify({'error': 'Failed to get moderation log'}), 500


def _generate_unique_invite_code(invites_dict):
    for _ in range(64):
        code = f"SR-{secrets.token_hex(3).upper()}-{secrets.token_hex(2).upper()}"
        if code not in invites_dict:
            return code
    return None


@bp.route('/invites', methods=['GET'])
@require_admin()
def list_invites():
    """List all invite codes (admin only)."""
    try:
        data = load_invites()
        invites = data.get('invites', {})
        out = []
        for code, meta in invites.items():
            out.append({
                'code': code,
                'type': meta.get('type'),
                'description': meta.get('description', ''),
                'max_uses': meta.get('max_uses', 1),
                'uses': meta.get('uses', 0),
                'created_at': meta.get('created_at'),
                'created_by': meta.get('created_by'),
            })
        out.sort(key=lambda x: (x.get('created_at') or ''), reverse=True)
        return jsonify(out), 200
    except Exception as e:
        logger.error(f"Error listing invites: {e}")
        return jsonify({'error': 'Failed to list invites'}), 500


@bp.route('/invites', methods=['POST'])
@require_admin()
def create_invite():
    """Create a new invite code for players (or admin) to use at signup."""
    try:
        admin_id = get_jwt_identity()
        payload = request.get_json() or {}

        inv_type = (payload.get('type') or 'player').strip().lower()
        if inv_type not in ('admin', 'player'):
            return jsonify({'error': 'type must be admin or player'}), 400

        max_uses = int(payload.get('max_uses', 1))
        if max_uses < 1 or max_uses > 500:
            return jsonify({'error': 'max_uses must be between 1 and 500'}), 400

        description = (payload.get('description') or '').strip()
        custom_code = (payload.get('code') or '').strip() or None

        invites_data = load_invites()
        if 'invites' not in invites_data:
            invites_data['invites'] = {}
        invites = invites_data['invites']

        if custom_code:
            if len(custom_code) < 6 or len(custom_code) > 64:
                return jsonify({'error': 'Custom code must be 6–64 characters'}), 400
            if not re.match(r'^[A-Za-z0-9_-]+$', custom_code):
                return jsonify({
                    'error': 'Custom code may only contain letters, numbers, underscore, and hyphen'
                }), 400
            if custom_code in invites:
                return jsonify({'error': 'That invite code already exists'}), 400
            code = custom_code
        else:
            code = _generate_unique_invite_code(invites)
            if not code:
                return jsonify({'error': 'Could not generate a unique invite code'}), 500

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT username FROM users WHERE id = %s", (admin_id,))
        row = cursor.fetchone()
        cursor.close()
        db.close()
        admin_name = row['username'] if row else str(admin_id)

        invites[code] = {
            'type': inv_type,
            'description': description,
            'max_uses': max_uses,
            'uses': 0,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'created_by': admin_name,
        }
        save_invites(invites_data)

        logger.info("Admin %s created invite %s type=%s max_uses=%s", admin_name, code, inv_type, max_uses)

        invite_out = dict(invites[code])
        invite_out['code'] = code
        return jsonify({
            'message': 'Invite code created',
            'invite': invite_out,
        }), 201

    except Exception as e:
        logger.error(f"Error creating invite: {e}")
        return jsonify({'error': 'Failed to create invite'}), 500


@bp.route('/downtime-requests', methods=['GET'])
@require_admin()
def admin_list_downtime_requests():
    """List character downtime / sheet-change requests (newest first)."""
    try:
        status_filter = (request.args.get('status') or '').strip().lower()
        db = get_db()
        cursor = db.cursor()
        ensure_character_downtime_requests_table(cursor)
        db.commit()

        q = """
            SELECT d.id, d.character_id, d.user_id, d.campaign_id, d.request_text,
                   d.status, d.admin_reason, d.resolved_at, d.resolved_by, d.created_at,
                   ch.name AS character_name, c.name AS campaign_name, u.username AS player_username
            FROM character_downtime_requests d
            JOIN characters ch ON ch.id = d.character_id
            JOIN campaigns c ON c.id = d.campaign_id
            JOIN users u ON u.id = d.user_id
        """
        params = []
        if status_filter in ('pending', 'approved', 'rejected'):
            q += " WHERE LOWER(TRIM(d.status)) = %s"
            params.append(status_filter)
        q += " ORDER BY d.created_at DESC LIMIT 500"
        cursor.execute(q, params)
        rows = cursor.fetchall()
        out = []
        for r in rows:
            out.append({
                'id': r['id'],
                'character_id': r['character_id'],
                'character_name': r['character_name'],
                'user_id': r['user_id'],
                'player_username': r['player_username'],
                'campaign_id': r['campaign_id'],
                'campaign_name': r['campaign_name'],
                'request_text': r['request_text'],
                'status': r['status'],
                'admin_reason': r.get('admin_reason'),
                'resolved_at': r.get('resolved_at'),
                'resolved_by': r.get('resolved_by'),
                'created_at': r['created_at'],
            })
        cursor.close()
        db.close()
        return jsonify({'requests': out, 'total': len(out)}), 200
    except Exception as e:
        logger.error(f"admin_list_downtime_requests: {e}")
        return jsonify({'error': 'Failed to list downtime requests'}), 500


@bp.route('/downtime-requests/<int:req_id>', methods=['PATCH'])
@require_admin()
def admin_resolve_downtime_request(req_id):
    """Approve or reject a downtime request (reason recommended for reject)."""
    try:
        admin_id = get_jwt_identity()
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON body required'}), 400
        status = (data.get('status') or '').strip().lower()
        if status not in ('approved', 'rejected'):
            return jsonify({'error': 'status must be approved or rejected'}), 400
        reason = (data.get('admin_reason') or '').strip()
        if status == 'rejected' and not reason:
            return jsonify({'error': 'admin_reason is required when rejecting'}), 400

        db = get_db()
        cursor = db.cursor()
        ensure_character_downtime_requests_table(cursor)
        db.commit()

        cursor.execute(
            "SELECT id, status FROM character_downtime_requests WHERE id = %s",
            (req_id,),
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            db.close()
            return jsonify({'error': 'Request not found'}), 404
        if (row.get('status') or '').lower() != 'pending':
            cursor.close()
            db.close()
            return jsonify({'error': 'Request is already resolved'}), 409

        now = datetime.utcnow()
        cursor.execute(
            """
            UPDATE character_downtime_requests
            SET status = %s, admin_reason = %s, resolved_at = %s, resolved_by = %s
            WHERE id = %s
            """,
            (status, reason or None, now, admin_id, req_id),
        )
        db.commit()
        cursor.close()
        db.close()
        return jsonify({'message': 'Request updated', 'id': req_id, 'status': status}), 200
    except Exception as e:
        logger.error(f"admin_resolve_downtime_request: {e}")
        return jsonify({'error': 'Failed to update request'}), 500


@bp.route('/characters/<int:character_id>/play-status', methods=['PATCH'])
@require_admin()
def admin_patch_character_play_status(character_id):
    """Suspend or clear suspension for a player character (storytelling / admin hold)."""
    admin_id = int(get_jwt_identity())
    data = request.get_json()
    if not data or 'suspended' not in data:
        return jsonify({'error': 'JSON body with suspended (boolean) is required'}), 400
    suspended = bool(data['suspended'])

    try:
        db = get_db()
        cursor = db.cursor()
        ensure_characters_play_suspension_columns(cursor)
        ensure_characters_is_npc_column(cursor)
        db.commit()

        ph = _sql_ph()
        cursor.execute(
            f"""
            SELECT id, user_id, name, campaign_id, is_npc
            FROM characters WHERE id = {ph}
            """,
            (character_id,),
        )
        ch = cursor.fetchone()
        if not ch:
            cursor.close()
            db.close()
            return jsonify({'error': 'Character not found'}), 404
        if ch.get('is_npc'):
            cursor.close()
            db.close()
            return jsonify({'error': 'Cannot suspend NPC rows this way'}), 400

        owner_id = ch['user_id']
        now = datetime.utcnow()

        if not suspended:
            cursor.execute(
                """
                UPDATE characters SET
                    play_suspended = FALSE,
                    play_suspension_reason_code = NULL,
                    play_suspension_message = NULL,
                    play_suspended_at = NULL,
                    play_suspended_by = NULL,
                    play_suspension_updated_at = %s
                WHERE id = %s
                """,
                (now, character_id),
            )
            log_moderation_action(owner_id, admin_id, 'character_play_clear', {
                'character_id': character_id,
            })
        else:
            reason = (data.get('reason_code') or '').strip()
            if reason not in ALLOWED_REASON_CODES:
                cursor.close()
                db.close()
                return jsonify({
                    'error': 'reason_code must be one of: '
                    + ', '.join(sorted(ALLOWED_REASON_CODES)),
                }), 400
            message = (data.get('message') or '').strip()
            cursor.execute(
                """
                UPDATE characters SET
                    play_suspended = TRUE,
                    play_suspension_reason_code = %s,
                    play_suspension_message = %s,
                    play_suspended_at = %s,
                    play_suspended_by = %s,
                    play_suspension_updated_at = %s
                WHERE id = %s
                """,
                (reason, message or None, now, admin_id, now, character_id),
            )
            log_moderation_action(owner_id, admin_id, 'character_play_suspend', {
                'character_id': character_id,
                'reason_code': reason,
                'message': message,
            })

        db.commit()
        cursor.close()
        db.close()
        return jsonify({'message': 'Play status updated', 'character_id': character_id}), 200
    except Exception as e:
        logger.error(f"admin_patch_character_play_status: {e}")
        return jsonify({'error': 'Failed to update play status'}), 500


def _wod_meta_summary(raw):
    if not raw:
        return {}
    try:
        meta = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    out = {}
    for k in ('clan', 'auspice', 'tradition', 'template', 'sect'):
        if meta.get(k):
            out[k] = meta[k]
    return out


@bp.route('/users/<int:user_id>/debug', methods=['GET'])
@require_admin()
def admin_get_user_debug(user_id):
    """Aggregate user / membership / characters / downtime / moderation (admin tooling)."""
    try:
        db = get_db()
        cursor = db.cursor()
        ensure_users_allow_multi_campaign_play_column(cursor)
        ensure_characters_play_suspension_columns(cursor)
        ensure_character_downtime_requests_table(cursor)
        db.commit()

        cursor.execute(
            """
            SELECT id, username, email, role, is_active, created_at, last_login,
                   display_timezone, player_avatar_url, active_character_id,
                   ban_type, ban_until, ban_reason, banned_by, banned_at,
                   allow_multi_campaign_play
            FROM users WHERE id = %s
            """,
            (user_id,),
        )
        u = cursor.fetchone()
        if not u:
            cursor.close()
            db.close()
            return jsonify({'error': 'User not found'}), 404

        user_out = {k: u[k] for k in u.keys()}
        user_out['is_active'] = bool(user_out.get('is_active'))
        user_out['allow_multi_campaign_play'] = bool(
            user_out.get('allow_multi_campaign_play') or False
        )

        cursor.execute(
            """
            SELECT cp.campaign_id, cp.joined_at, cp.role AS member_role, c.name AS campaign_name,
                   c.game_system, c.created_by
            FROM campaign_players cp
            JOIN campaigns c ON c.id = cp.campaign_id
            WHERE cp.user_id = %s
            ORDER BY cp.joined_at DESC
            """,
            (user_id,),
        )
        memberships = []
        for row in cursor.fetchall():
            memberships.append({
                'campaign_id': row['campaign_id'],
                'campaign_name': row['campaign_name'],
                'game_system': row['game_system'],
                'joined_at': row['joined_at'],
                'member_role': row.get('member_role'),
                'is_owner': str(row.get('created_by')) == str(user_id),
            })

        cursor.execute(
            """
            SELECT id, name, game_system, created_at, created_by
            FROM campaigns
            WHERE created_by = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        owned = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT id, name, system_type, campaign_id, is_active, sheet_locked, created_at,
                   wod_meta,
                   play_suspended,
                   play_suspension_reason_code, play_suspension_message,
                   play_suspended_at, play_suspended_by
            FROM characters
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        characters_out = []
        for row in cursor.fetchall():
            characters_out.append({
                'id': row['id'],
                'name': row['name'],
                'system_type': row['system_type'],
                'campaign_id': row['campaign_id'],
                'is_active': bool(row['is_active']),
                'sheet_locked': bool(row.get('sheet_locked')),
                'created_at': row['created_at'],
                'play_suspended': bool(row.get('play_suspended') or False),
                'play_suspension_reason_code': row.get('play_suspension_reason_code'),
                'play_suspension_message': row.get('play_suspension_message'),
                'play_suspended_at': row.get('play_suspended_at'),
                'play_suspended_by': row.get('play_suspended_by'),
                'wod_meta_summary': _wod_meta_summary(row.get('wod_meta')),
            })

        cursor.execute(
            """
            SELECT d.id, d.character_id, d.campaign_id, d.request_text, d.status,
                   d.admin_reason, d.resolved_at, d.created_at
            FROM character_downtime_requests d
            WHERE d.user_id = %s
            ORDER BY d.created_at DESC
            LIMIT 100
            """,
            (user_id,),
        )
        downtime = [dict(r) for r in cursor.fetchall()]

        cursor.execute(
            """
            SELECT id, admin_id, action, details, created_at
            FROM user_moderation_log
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (user_id,),
        )
        mod_log = [dict(r) for r in cursor.fetchall()]

        char_mod = []
        try:
            ids = [c['id'] for c in characters_out]
            if ids:
                ph = ','.join(['%s'] * len(ids))
                cursor.execute(
                    f"""
                    SELECT * FROM character_moderation
                    WHERE character_id IN ({ph})
                    ORDER BY moderated_at DESC
                    LIMIT 100
                    """,
                    tuple(ids),
                )
                char_mod = [dict(r) for r in cursor.fetchall()]
        except Exception:
            char_mod = []

        cursor.close()
        db.close()

        return jsonify({
            'user': user_out,
            'campaign_memberships': memberships,
            'campaigns_owned': owned,
            'characters': characters_out,
            'downtime_requests': downtime,
            'user_moderation_log': mod_log,
            'character_moderation': char_mod,
        }), 200
    except Exception as e:
        logger.error(f"admin_get_user_debug: {e}")
        return jsonify({'error': 'Failed to load debug profile'}), 500


def _row_get(row, key, default=None):
    """sqlite3.Row has no .get; RealDictCursor rows do."""
    try:
        val = row[key]
        return val if val is not None else default
    except (KeyError, TypeError, IndexError):
        return default


def _truthy_db_bool(val, default=False):
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    s = str(val).strip().lower()
    if s in ("", "none"):
        return default
    return s in ("1", "true", "yes", "t")


def _campaign_is_active(raw):
    """Campaigns.is_active: default True when column missing or null."""
    if raw is None:
        return True
    return _truthy_db_bool(raw, default=True)


@bp.route('/campaigns', methods=['GET'])
@require_admin()
def list_all_campaigns():
    """List every campaign for admin UI pickers (e.g. membership override)."""
    try:
        db = get_db()
        cursor = db.cursor()
        ensure_campaigns_listing_columns(cursor)
        ensure_campaigns_staff_pause_columns(cursor)
        db.commit()
        cursor.execute(
            """
            SELECT c.id, c.name, c.description, c.game_system, c.status, c.created_at, c.created_by,
                   c.is_active, c.listing_visibility, c.accepting_players, c.max_players,
                   c.admin_inactive_reason, c.admin_inactive_at,
                   u.username AS creator_username
            FROM campaigns c
            LEFT JOIN users u ON u.id = c.created_by
            ORDER BY LOWER(COALESCE(c.name, ''))
            """
        )
        rows = cursor.fetchall() or []
        out = []
        for row in rows:
            acc_players = _truthy_db_bool(_row_get(row, "accepting_players"), default=False)
            is_act = _campaign_is_active(_row_get(row, "is_active", True))
            out.append({
                'id': row['id'],
                'name': _row_get(row, 'name', ''),
                'description': _row_get(row, 'description', '') or '',
                'game_system': _row_get(row, 'game_system', '') or '',
                'status': _row_get(row, 'status', 'active') or 'active',
                'created_at': _row_get(row, 'created_at'),
                'created_by': _row_get(row, 'created_by'),
                'creator_username': _row_get(row, 'creator_username', '') or '',
                'is_active': is_act,
                'listing_visibility': _row_get(row, 'listing_visibility', 'private') or 'private',
                'accepting_players': acc_players,
                'max_players': _row_get(row, 'max_players'),
                'admin_inactive_reason': _row_get(row, 'admin_inactive_reason', '') or '',
                'admin_inactive_at': _row_get(row, 'admin_inactive_at'),
            })
        cursor.close()
        db.close()
        return jsonify(out), 200
    except Exception as e:
        logger.error(f"list_all_campaigns: {e}")
        return jsonify({'error': 'Failed to list campaigns'}), 500


@bp.route('/users/<int:user_id>/campaign-memberships', methods=['GET'])
@require_admin()
def admin_user_campaign_memberships_list(user_id):
    """Chronicles this user is tied to: roster + created-but-missing-from-roster (legacy)."""
    try:
        db = get_db()
        cursor = db.cursor()
        ensure_campaigns_listing_columns(cursor)
        db.commit()
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': 'User not found'}), 404

        cursor.execute(
            """
            SELECT c.id, c.name, c.game_system, cp.role AS member_role
            FROM campaign_players cp
            INNER JOIN campaigns c ON c.id = cp.campaign_id
            WHERE cp.user_id = %s
            ORDER BY LOWER(COALESCE(c.name, ''))
            """,
            (user_id,),
        )
        seen = set()
        out = []
        for row in cursor.fetchall() or []:
            cid = row['id']
            seen.add(cid)
            out.append({
                'id': cid,
                'name': _row_get(row, 'name', ''),
                'game_system': _row_get(row, 'game_system', '') or '',
                'member_role': _row_get(row, 'member_role', 'player') or 'player',
                'via': 'campaign_players',
            })

        cursor.execute(
            """
            SELECT c.id, c.name, c.game_system
            FROM campaigns c
            WHERE c.created_by = %s
              AND c.id NOT IN (
                  SELECT campaign_id FROM campaign_players WHERE user_id = %s
              )
            ORDER BY LOWER(COALESCE(c.name, ''))
            """,
            (user_id, user_id),
        )
        for row in cursor.fetchall() or []:
            cid = row['id']
            if cid in seen:
                continue
            out.append({
                'id': cid,
                'name': _row_get(row, 'name', ''),
                'game_system': _row_get(row, 'game_system', '') or '',
                'member_role': 'owner',
                'via': 'created_by_only',
            })

        cursor.close()
        db.close()
        return jsonify(out), 200
    except Exception as e:
        logger.error(f"admin_user_campaign_memberships_list: {e}")
        return jsonify({'error': 'Failed to load memberships'}), 500


@bp.route('/users/<int:user_id>/campaigns/<int:campaign_id>/membership', methods=['POST'])
@require_admin()
def admin_user_campaign_membership(user_id, campaign_id):
    """Add or remove campaign_players row (admin-only campaign access override)."""
    admin_id = int(get_jwt_identity())
    data = request.get_json() or {}
    action = (data.get('action') or '').strip().lower()
    if action not in ('add', 'remove'):
        return jsonify({'error': 'action must be "add" or "remove"'}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': 'User not found'}), 404
        cursor.execute("SELECT id FROM campaigns WHERE id = %s", (campaign_id,))
        if not cursor.fetchone():
            cursor.close()
            db.close()
            return jsonify({'error': 'Campaign not found'}), 404

        now = datetime.utcnow()
        db_type = os.getenv('DATABASE_TYPE', 'sqlite').lower()
        if action == 'add':
            if db_type == 'postgresql':
                cursor.execute(
                    """
                    INSERT INTO campaign_players (campaign_id, user_id, joined_at, role)
                    VALUES (%s, %s, %s, 'player')
                    ON CONFLICT (campaign_id, user_id) DO NOTHING
                    """,
                    (campaign_id, user_id, now),
                )
            else:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO campaign_players (campaign_id, user_id, joined_at, role)
                    VALUES (%s, %s, %s, 'player')
                    """,
                    (campaign_id, user_id, now),
                )
        else:
            cursor.execute(
                """
                DELETE FROM campaign_players
                WHERE campaign_id = %s AND user_id = %s
                """,
                (campaign_id, user_id),
            )

        log_moderation_action(user_id, admin_id, f'campaign_membership_{action}', {
            'campaign_id': campaign_id,
        })
        db.commit()
        cursor.close()
        db.close()
        return jsonify({
            'message': f'Membership {action}ed',
            'user_id': user_id,
            'campaign_id': campaign_id,
        }), 200
    except Exception as e:
        logger.error(f"admin_user_campaign_membership: {e}")
        return jsonify({'error': 'Failed to update membership'}), 500


def _runtime_llm_config():
    return {
        'LM_STUDIO_URL': os.environ.get('LM_STUDIO_URL', 'http://localhost:1234'),
        'LM_STUDIO_API_KEY': os.environ.get('LM_STUDIO_API_KEY', ''),
        'LM_STUDIO_MODEL': os.environ.get('LM_STUDIO_MODEL', '') or '',
        'LM_STUDIO_TIMEOUT': int(os.environ.get('LM_STUDIO_TIMEOUT', '120') or 120),
    }


@bp.route('/ai-settings', methods=['GET', 'PUT'])
@require_admin()
def ai_settings():
    """Admin: LM Studio model override + global master system prompt."""
    from services.ai_runtime_settings import get_app_setting, set_app_setting
    from services.lm_studio_model import get_effective_lm_studio_model_id, invalidate_lm_studio_model_cache

    cfg = _runtime_llm_config()
    if request.method == 'GET':
        return jsonify({
            'lm_studio_model': get_app_setting('lm_studio_model') or '',
            'ai_master_system_prompt': get_app_setting('ai_master_system_prompt') or '',
            'effective_lm_studio_model': get_effective_lm_studio_model_id(cfg),
            'env_lm_studio_model': cfg['LM_STUDIO_MODEL'],
            'lm_studio_url': cfg['LM_STUDIO_URL'],
        }), 200

    data = request.get_json(silent=True) or {}
    out = {}
    if 'lm_studio_model' in data:
        v = data['lm_studio_model']
        if v is None or str(v).strip() == '':
            set_app_setting('lm_studio_model', None)
            out['lm_studio_model'] = ''
        else:
            s = str(v).strip()
            set_app_setting('lm_studio_model', s)
            out['lm_studio_model'] = s
        invalidate_lm_studio_model_cache()
    if 'ai_master_system_prompt' in data:
        v = data['ai_master_system_prompt']
        if v is None:
            set_app_setting('ai_master_system_prompt', None)
        else:
            set_app_setting('ai_master_system_prompt', str(v))
        out['ai_master_system_prompt'] = get_app_setting('ai_master_system_prompt') or ''

    out['effective_lm_studio_model'] = get_effective_lm_studio_model_id(_runtime_llm_config())
    out['ok'] = True
    return jsonify(out), 200


@bp.route('/lm-studio/models', methods=['GET'])
@require_admin()
def list_lm_studio_models_admin():
    """List models from LM Studio OpenAI + native APIs (admin only)."""
    import requests as req

    base = (os.environ.get('LM_STUDIO_URL') or 'http://localhost:1234').rstrip('/')
    ak = (os.environ.get('LM_STUDIO_API_KEY') or '').strip()
    hdrs = {'Content-Type': 'application/json'}
    if ak:
        hdrs['Authorization'] = f'Bearer {ak}'
    openai_data = []
    native_data = []
    err = None
    try:
        r = req.get(f'{base}/v1/models', timeout=15, headers=hdrs)
        if r.status_code == 200:
            openai_data = r.json().get('data') or []
        else:
            err = f'GET /v1/models: {r.status_code}'
    except Exception as e:
        err = str(e)
    try:
        r2 = req.get(f'{base}/api/v1/models', timeout=15, headers=hdrs)
        if r2.status_code == 200:
            native_data = r2.json().get('models') or []
    except Exception:
        pass
    return jsonify({
        'lm_studio_url': base,
        'openai_models': openai_data,
        'native_models': native_data,
        'error': err,
    }), 200


@bp.route('/users/<int:user_id>/delete-account', methods=['POST'])
@require_admin()
def delete_user_account_preserve_chats(user_id):
    """Remove a player account and all their characters; keep location chat rows (reassign to archive user)."""
    from services.user_account_delete import delete_player_account_preserving_chats

    try:
        admin_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid admin session'}), 401

    db = get_db()
    try:
        ok, err, stats = delete_player_account_preserving_chats(db, user_id, admin_id)
        if not ok:
            return jsonify({'error': err or 'Delete failed'}), 400
        return jsonify({
            'message': 'User and characters removed. Location chat history is preserved under the archive account.',
            'stats': stats,
        }), 200
    except Exception as e:
        logger.error(f"delete_user_account_preserve_chats: {e}")
        return jsonify({'error': 'Server error during account deletion'}), 500
    finally:
        db.close()

