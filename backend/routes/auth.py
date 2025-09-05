#!/usr/bin/env python3
"""
ShadowRealms AI - Authentication Routes
User authentication, registration, and JWT management
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import bcrypt
import logging
from datetime import datetime, timedelta

from database import get_db
from services.gpu_monitor import gpu_monitor_service

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__)

@bp.route('/register', methods=['POST'])
def register():
    """User registration endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'player')  # Default to player role
        
        # Validation
        if not all([username, email, password]):
            return jsonify({'error': 'Username, email, and password are required'}), 400
        
        if role not in ['admin', 'helper', 'player']:
            return jsonify({'error': 'Invalid role'}), 400
        
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Check if user already exists
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            return jsonify({'error': 'Username or email already exists'}), 409
        
        # Insert new user
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (username, email, password_hash.decode('utf-8'), role, datetime.utcnow()))
        
        user_id = cursor.lastrowid
        db.commit()
        
        logger.info(f"New user registered: {username} ({email}) with role: {role}")
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': user_id,
            'username': username,
            'role': role
        }), 201
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        username = data.get('username')
        password = data.get('password')
        
        if not all([username, password]):
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Get user from database
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, username, email, password_hash, role, is_active
            FROM users WHERE username = ?
        """, (username,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user['is_active']:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Update last login
        cursor.execute("""
            UPDATE users SET last_login = ? WHERE id = ?
        """, (datetime.utcnow(), user['id']))
        
        db.commit()
        
        # Create JWT tokens
        access_token = create_access_token(
            identity=str(user['id']),
            additional_claims={
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
        )
        
        refresh_token = create_refresh_token(
            identity=str(user['id']),
            additional_claims={
                'username': user['username'],
                'role': user['role']
            }
        )
        
        logger.info(f"User logged in: {username} (ID: {user['id']})")
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh JWT token endpoint"""
    try:
        current_user_id = get_jwt_identity()
        
        # Get user info from database
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, username, email, role, is_active
            FROM users WHERE id = ?
        """, (current_user_id,))
        
        user = cursor.fetchone()
        
        if not user or not user['is_active']:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        # Create new access token
        access_token = create_access_token(
            identity=str(user['id']),
            additional_claims={
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
        )
        
        return jsonify({
            'access_token': access_token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return jsonify({'error': 'Token refresh failed'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get current user profile"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT id, username, email, role, created_at, last_login
            FROM users WHERE id = ?
        """, (current_user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user statistics
        cursor.execute("""
            SELECT COUNT(*) as campaign_count
            FROM campaigns WHERE created_by = ?
        """, (current_user_id,))
        
        campaign_count = cursor.fetchone()['campaign_count']
        
        cursor.execute("""
            SELECT COUNT(*) as character_count
            FROM characters WHERE user_id = ?
        """, (current_user_id,))
        
        character_count = cursor.fetchone()['character_count']
        
        return jsonify({
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'role': user['role'],
                'created_at': user['created_at'],
                'last_login': user['last_login']
            },
            'statistics': {
                'campaigns_created': campaign_count,
                'characters_owned': character_count
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Profile retrieval error: {e}")
        return jsonify({'error': 'Profile retrieval failed'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """User logout endpoint (client-side token removal)"""
    # Note: JWT tokens are stateless, so we can't invalidate them server-side
    # The client should remove the tokens from storage
    return jsonify({'message': 'Logout successful'}), 200
