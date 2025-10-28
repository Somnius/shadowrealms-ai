#!/usr/bin/env python3
"""
ShadowRealms AI - Users Routes
User management and role-based operations
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
from datetime import datetime

from database import get_db
from services.gpu_monitor import gpu_monitor_service

logger = logging.getLogger(__name__)

bp = Blueprint('users', __name__)

@bp.route('/', methods=['GET'])
@jwt_required()
def get_users():
    """Get all users (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if current user is admin
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get all users
        cursor.execute("""
            SELECT id, username, email, role, created_at, last_login, is_active
            FROM users
            ORDER BY created_at DESC
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row['id'],
                'username': row['username'],
                'email': row['email'],
                'role': row['role'],
                'created_at': row['created_at'],
                'last_login': row['last_login'],
                'is_active': bool(row['is_active'])
            })
        
        return jsonify({
            'users': users,
            'total': len(users)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return jsonify({'error': 'Failed to retrieve users'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """Get specific user by ID"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Users can only view their own profile unless they're admin/helper
        if current_user['role'] not in ['admin', 'helper'] and current_user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get target user
        cursor.execute("""
            SELECT id, username, email, role, created_at, last_login, is_active
            FROM users WHERE id = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user statistics
        cursor.execute("""
            SELECT COUNT(*) as campaign_count
            FROM campaigns WHERE created_by = %s
        """, (user_id,))
        
        campaign_count = cursor.fetchone()['campaign_count']
        
        cursor.execute("""
            SELECT COUNT(*) as character_count
            FROM characters WHERE user_id = %s
        """, (user_id,))
        
        character_count = cursor.fetchone()['character_count']
        
        return jsonify({
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'created_at': user['created_at'],
                'last_login': user['last_login'],
                'is_active': bool(user['is_active'])
            },
            'statistics': {
                'campaigns_created': campaign_count,
                'characters_owned': character_count
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return jsonify({'error': 'Failed to retrieve user'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """Update user information (admin or self)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Check permissions
        if current_user['role'] not in ['admin', 'helper'] and current_user_id != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Get target user
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        target_user = cursor.fetchone()
        
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update fields
        updates = []
        params = []
        
        # Username update
        if 'username' in data and data['username'] != target_user['username']:
            # Check if username is already taken
            cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (data['username'], user_id))
            if cursor.fetchone():
                return jsonify({'error': 'Username already taken'}), 409
            
            updates.append("username = %s")
            params.append(data['username'])
        
        # Email update
        if 'email' in data and data['email'] != target_user['email']:
            # Check if email is already taken
            cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (data['email'], user_id))
            if cursor.fetchone():
                return jsonify({'error': 'Email already taken'}), 409
            
            updates.append("email = %s")
            params.append(data['email'])
        
        # Role update (admin only)
        if 'role' in data and data['role'] != target_user['role']:
            if current_user['role'] != 'admin':
                return jsonify({'error': 'Only admins can change user roles'}), 403
            
            if data['role'] not in ['admin', 'helper', 'player']:
                return jsonify({'error': 'Invalid role'}), 400
            
            updates.append("role = %s")
            params.append(data['role'])
        
        # Active status update (admin only)
        if 'is_active' in data and data['is_active'] != target_user['is_active']:
            if current_user['role'] != 'admin':
                return jsonify({'error': 'Only admins can change user status'}), 403
            
            updates.append("is_active = %s")
            params.append(data['is_active'])
        
        # Apply updates if any
        if updates:
            params.append(datetime.utcnow())  # updated_at
            params.append(user_id)
            
            query = f"UPDATE users SET {', '.join(updates)}, updated_at = %s WHERE id = %s"
            cursor.execute(query, params)
            
            db.commit()
            
            logger.info(f"User {user_id} updated by user {current_user_id}")
        
        # Return updated user
        return get_user(user_id)
        
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        return jsonify({'error': 'Failed to update user'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """Delete user (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if current user is admin
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Prevent self-deletion
        if current_user_id == user_id:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        # Check if user exists
        cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
        target_user = cursor.fetchone()
        
        if not target_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Soft delete - mark as inactive instead of removing
        cursor.execute("UPDATE users SET is_active = 0, updated_at = %s WHERE id = %s", 
                      (datetime.utcnow(), user_id))
        
        db.commit()
        
        logger.info(f"User {user_id} ({target_user['username']}) deactivated by admin {current_user_id}")
        
        return jsonify({'message': 'User deactivated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        return jsonify({'error': 'Failed to delete user'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/stats', methods=['GET'])
@jwt_required()
def get_user_stats():
    """Get user statistics (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if current user is admin
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get user statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_users,
                COUNT(CASE WHEN role = 'admin' THEN 1 END) as admin_count,
                COUNT(CASE WHEN role = 'helper' THEN 1 END) as helper_count,
                COUNT(CASE WHEN role = 'player' THEN 1 END) as player_count,
                COUNT(CASE WHEN last_login > datetime('now', '-7 days') THEN 1 END) as active_this_week
            FROM users
        """)
        
        stats = cursor.fetchone()
        
        return jsonify({
            'user_statistics': {
                'total_users': stats['total_users'],
                'active_users': stats['active_users'],
                'inactive_users': stats['total_users'] - stats['active_users'],
                'role_distribution': {
                    'admins': stats['admin_count'],
                    'helpers': stats['helper_count'],
                    'players': stats['player_count']
                },
                'activity': {
                    'active_this_week': stats['active_this_week'],
                    'active_this_month': 0  # Could add more detailed tracking
                }
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return jsonify({'error': 'Failed to retrieve user statistics'}), 500
    finally:
        if 'db' in locals():
            db.close()
