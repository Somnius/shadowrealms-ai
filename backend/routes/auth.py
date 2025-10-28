#!/usr/bin/env python3
"""
ShadowRealms AI - Authentication Routes
User authentication, registration, and JWT management
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import bcrypt
import logging
import json
import os
from datetime import datetime, timedelta

from database import get_db
from services.gpu_monitor import gpu_monitor_service

logger = logging.getLogger(__name__)

def load_invites():
    """Load invite codes from invites.json"""
    invites_file = os.path.join(os.path.dirname(__file__), '..', 'invites.json')
    try:
        with open(invites_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("invites.json not found")
        return {"invites": {}}
    except json.JSONDecodeError:
        logger.error("invites.json is not valid JSON")
        return {"invites": {}}

def save_invites(data):
    """Save invite codes to invites.json"""
    invites_file = os.path.join(os.path.dirname(__file__), '..', 'invites.json')
    with open(invites_file, 'w') as f:
        json.dump(data, f, indent=2)

def validate_invite_code(code):
    """Validate an invite code and return its type (admin/player) or None"""
    invites_data = load_invites()
    invites = invites_data.get('invites', {})
    
    if code not in invites:
        return None
    
    invite = invites[code]
    
    # Check if invite has uses remaining
    if invite['uses'] >= invite['max_uses']:
        return None
    
    return invite['type']

def use_invite_code(code):
    """Mark an invite code as used"""
    invites_data = load_invites()
    if code in invites_data['invites']:
        invites_data['invites'][code]['uses'] += 1
        save_invites(invites_data)
        return True
    return False

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
        invite_code = data.get('invite_code')
        
        # Validation
        if not all([username, email, password, invite_code]):
            return jsonify({'error': 'Username, email, password, and invite code are required'}), 400
        
        if len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters'}), 400
        
        # Validate invite code
        role = validate_invite_code(invite_code)
        if role is None:
            return jsonify({'error': 'Invalid or expired invite code'}), 403
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Check if user already exists
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (username, email, password_hash.decode('utf-8'), role, datetime.utcnow()))
        
        user_id = cursor.fetchone()['id']
        db.commit()
        
        # Mark invite code as used
        use_invite_code(invite_code)
        
        # Create access token
        access_token = create_access_token(identity=user_id)
        
        logger.info(f"New user registered: {username} ({email}) with role: {role} using invite: {invite_code}")
        
        return jsonify({
            'message': 'User registered successfully',
            'access_token': access_token,
            'user': {
                'id': user_id,
                'username': username,
                'email': email,
                'role': role
            }
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
            FROM users WHERE username = %s
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
            UPDATE users SET last_login = %s WHERE id = %s
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
            FROM users WHERE id = %s
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
            FROM users WHERE id = %s
        """, (current_user_id,))
        
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get user statistics
        cursor.execute("""
            SELECT COUNT(*) as campaign_count
            FROM campaigns WHERE created_by = %s
        """, (current_user_id,))
        
        campaign_count = cursor.fetchone()['campaign_count']
        
        cursor.execute("""
            SELECT COUNT(*) as character_count
            FROM characters WHERE user_id = %s
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
