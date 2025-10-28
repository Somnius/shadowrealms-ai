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
from datetime import datetime, timedelta

from database import get_db

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

