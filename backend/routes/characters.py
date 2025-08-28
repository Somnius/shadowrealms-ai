#!/usr/bin/env python3
"""
ShadowRealms AI - Characters Routes
Character management and character sheets
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import json
from datetime import datetime

from database import get_db
from services.gpu_monitor import gpu_monitor_service

logger = logging.getLogger(__name__)

bp = Blueprint('characters', __name__)

@bp.route('/', methods=['GET'])
@jwt_required()
def get_characters():
    """Get characters (filtered by user and campaign)"""
    try:
        current_user_id = get_jwt_identity()
        campaign_id = request.args.get('campaign_id', type=int)
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Build query based on user role and filters
        if current_user['role'] in ['admin', 'helper']:
            # Admins and helpers can see all characters
            if campaign_id:
                cursor.execute("""
                    SELECT ch.*, u.username as owner_name, c.name as campaign_name
                    FROM characters ch
                    JOIN users u ON ch.user_id = u.id
                    JOIN campaigns c ON ch.campaign_id = c.id
                    WHERE ch.campaign_id = ?
                    ORDER BY ch.created_at DESC
                """, (campaign_id,))
            else:
                cursor.execute("""
                    SELECT ch.*, u.username as owner_name, c.name as campaign_name
                    FROM characters ch
                    JOIN users u ON ch.user_id = u.id
                    JOIN campaigns c ON ch.campaign_id = c.id
                    ORDER BY ch.created_at DESC
                """)
        else:
            # Players can only see their own characters
            if campaign_id:
                cursor.execute("""
                    SELECT ch.*, u.username as owner_name, c.name as campaign_name
                    FROM characters ch
                    JOIN users u ON ch.user_id = u.id
                    JOIN campaigns c ON ch.campaign_id = c.id
                    WHERE ch.user_id = ? AND ch.campaign_id = ?
                    ORDER BY ch.created_at DESC
                """, (current_user_id, campaign_id))
            else:
                cursor.execute("""
                    SELECT ch.*, u.username as owner_name, c.name as campaign_name
                    FROM characters ch
                    JOIN users u ON ch.user_id = u.id
                    JOIN campaigns c ON ch.campaign_id = c.id
                    WHERE ch.user_id = ?
                    ORDER BY ch.created_at DESC
                """, (current_user_id,))
        
        characters = []
        for row in cursor.fetchall():
            characters.append({
                'id': row['id'],
                'name': row['name'],
                'system_type': row['system_type'],
                'attributes': json.loads(row['attributes']) if row['attributes'] else {},
                'skills': json.loads(row['skills']) if row['skills'] else {},
                'background': row['background'],
                'merits_flaws': json.loads(row['merits_flaws']) if row['merits_flaws'] else {},
                'user_id': row['user_id'],
                'owner_name': row['owner_name'],
                'campaign_id': row['campaign_id'],
                'campaign_name': row['campaign_name'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        
        return jsonify({
            'characters': characters,
            'total': len(characters)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting characters: {e}")
        return jsonify({'error': 'Failed to retrieve characters'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/', methods=['POST'])
@jwt_required()
def create_character():
    """Create new character"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Required fields
        name = data.get('name')
        campaign_id = data.get('campaign_id')
        system_type = data.get('system_type')
        
        if not all([name, campaign_id, system_type]):
            return jsonify({'error': 'Name, campaign ID, and system type are required'}), 400
        
        if system_type not in ['d20', 'd10', 'besm']:
            return jsonify({'error': 'Invalid system type'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Verify campaign exists and user has access
        cursor.execute("""
            SELECT c.*, u.role as user_role
            FROM campaigns c
            JOIN users u ON u.id = ?
            WHERE c.id = ? AND c.is_active = 1
        """, (current_user_id, campaign_id))
        
        campaign = cursor.fetchone()
        
        if not campaign:
            return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Check if character name already exists in this campaign
        cursor.execute("""
            SELECT id FROM characters 
            WHERE name = ? AND campaign_id = ?
        """, (name, campaign_id))
        
        if cursor.fetchone():
            return jsonify({'error': 'Character name already exists in this campaign'}), 409
        
        # Create character
        cursor.execute("""
            INSERT INTO characters (name, system_type, attributes, skills, background, merits_flaws, user_id, campaign_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            system_type,
            json.dumps(data.get('attributes', {})),
            json.dumps(data.get('skills', {})),
            data.get('background', ''),
            json.dumps(data.get('merits_flaws', {})),
            current_user_id,
            campaign_id,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        character_id = cursor.lastrowid
        db.commit()
        
        logger.info(f"Character '{name}' created by user {current_user_id} in campaign {campaign_id}")
        
        return jsonify({
            'message': 'Character created successfully',
            'character_id': character_id,
            'name': name
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating character: {e}")
        return jsonify({'error': 'Failed to create character'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:character_id>', methods=['GET'])
@jwt_required()
def get_character(character_id):
    """Get specific character details"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get character
        cursor.execute("""
            SELECT ch.*, u.username as owner_name, c.name as campaign_name
            FROM characters ch
            JOIN users u ON ch.user_id = u.id
            JOIN campaigns c ON ch.campaign_id = c.id
            WHERE ch.id = ?
        """, (character_id,))
        
        character = cursor.fetchone()
        
        if not character:
            return jsonify({'error': 'Character not found'}), 404
        
        # Check access permissions
        if current_user['role'] not in ['admin', 'helper'] and character['user_id'] != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'character': {
                'id': character['id'],
                'name': character['name'],
                'system_type': character['system_type'],
                'attributes': json.loads(character['attributes']) if character['attributes'] else {},
                'skills': json.loads(character['skills']) if character['skills'] else {},
                'background': character['background'],
                'merits_flaws': json.loads(character['merits_flaws']) if character['merits_flaws'] else {},
                'user_id': character['user_id'],
                'owner_name': character['owner_name'],
                'campaign_id': character['campaign_id'],
                'campaign_name': character['campaign_name'],
                'created_at': character['created_at'],
                'updated_at': character['updated_at']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting character {character_id}: {e}")
        return jsonify({'error': 'Failed to retrieve character'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:character_id>', methods=['PUT'])
@jwt_required()
def update_character(character_id):
    """Update character (owner, admin, or helper only)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get character
        cursor.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        character = cursor.fetchone()
        
        if not character:
            return jsonify({'error': 'Character not found'}), 404
        
        # Check permissions
        if current_user['role'] not in ['admin', 'helper'] and character['user_id'] != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update fields
        updates = []
        params = []
        
        if 'name' in data and data['name'] != character['name']:
            # Check if name is already taken in this campaign
            cursor.execute("""
                SELECT id FROM characters 
                WHERE name = ? AND campaign_id = ? AND id != ?
            """, (data['name'], character['campaign_id'], character_id))
            
            if cursor.fetchone():
                return jsonify({'error': 'Character name already exists in this campaign'}), 409
            
            updates.append("name = ?")
            params.append(data['name'])
        
        if 'attributes' in data:
            updates.append("attributes = ?")
            params.append(json.dumps(data['attributes']))
        
        if 'skills' in data:
            updates.append("skills = ?")
            params.append(json.dumps(data['skills']))
        
        if 'background' in data:
            updates.append("background = ?")
            params.append(data['background'])
        
        if 'merits_flaws' in data:
            updates.append("merits_flaws = ?")
            params.append(json.dumps(data['merits_flaws']))
        
        # Apply updates if any
        if updates:
            params.append(datetime.utcnow())  # updated_at
            params.append(character_id)
            
            query = f"UPDATE characters SET {', '.join(updates)}, updated_at = ? WHERE id = ?"
            cursor.execute(query, params)
            
            db.commit()
            
            logger.info(f"Character {character_id} updated by user {current_user_id}")
        
        # Return updated character
        return get_character(character_id)
        
    except Exception as e:
        logger.error(f"Error updating character {character_id}: {e}")
        return jsonify({'error': 'Failed to update character'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:character_id>', methods=['DELETE'])
@jwt_required()
def delete_character(character_id):
    """Delete character (owner, admin, or helper only)"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get character
        cursor.execute("SELECT * FROM characters WHERE id = ?", (character_id,))
        character = cursor.fetchone()
        
        if not character:
            return jsonify({'error': 'Character not found'}), 404
        
        # Check permissions
        if current_user['role'] not in ['admin', 'helper'] and character['user_id'] != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Delete character
        cursor.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        db.commit()
        
        logger.info(f"Character {character_id} ({character['name']}) deleted by user {current_user_id}")
        
        return jsonify({'message': 'Character deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting character {character_id}: {e}")
        return jsonify({'error': 'Failed to delete character'}), 500
    finally:
        if 'db' in locals():
            db.close()
