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
import re
import secrets
from datetime import datetime, timedelta

from database import get_db, ensure_character_downtime_requests_table
from routes.auth import load_invites, save_invites

logger = logging.getLogger(__name__)

bp = Blueprint('admin', __name__, url_prefix='/api/admin')

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

def log_moderation_action(user_id, admin_id, action, details):
    """Log a moderation action"""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO user_moderation_log (user_id, admin_id, action, details, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, admin_id, action, json.dumps(details), datetime.now()))
    db.commit()
    cursor.close()
    db.close()

@bp.route('/users', methods=['GET'])
@require_admin()
def get_all_users():
    """Get all users with their status"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, username, email, role, is_active, created_at, last_login,
                   ban_type, ban_until, ban_reason, banned_by, banned_at
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
                'banned_at': row['banned_at']
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
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, name, character_type, campaign_id, is_npc, is_active, created_at
            FROM characters
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        
        characters = []
        for row in cursor.fetchall():
            characters.append({
                'id': row['id'],
                'name': row['name'],
                'character_type': row['character_type'],
                'campaign_id': row['campaign_id'],
                'is_npc': bool(row['is_npc']),
                'is_active': bool(row['is_active']),
                'created_at': row['created_at']
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
        limit = request.args.get('limit', 50, type=int)
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT ml.id, ml.user_id, u.username as username, ml.admin_id, a.username as admin_username, 
                   ml.action, ml.details, ml.created_at
            FROM user_moderation_log ml
            JOIN users u ON ml.user_id = u.id
            JOIN users a ON ml.admin_id = a.id
            ORDER BY ml.created_at DESC
            LIMIT %s
        """, (limit,))
        
        logs = []
        for row in cursor.fetchall():
            logs.append({
                'id': row['id'],
                'user_id': row['user_id'],
                'username': row['username'],
                'admin_id': row['admin_id'],
                'admin_username': row['admin_username'],
                'action': row['action'],
                'details': json.loads(row['details']) if row['details'] else {},
                'created_at': row['created_at']
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

