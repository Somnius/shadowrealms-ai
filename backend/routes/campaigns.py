#!/usr/bin/env python3
"""
ShadowRealms AI - Campaigns Routes
Campaign management and world building
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import json
from datetime import datetime

from database import get_db
from services.gpu_monitor import gpu_monitor_service

logger = logging.getLogger(__name__)

bp = Blueprint('campaigns', __name__)

@bp.route('/', methods=['GET'])
@jwt_required()
def get_campaigns():
    """Get campaigns (filtered by user role and permissions)"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Build query based on user role
        if current_user['role'] == 'admin':
            # Admins can see all campaigns
            cursor.execute("""
                SELECT c.*, u.username as creator_name
                FROM campaigns c
                JOIN users u ON c.created_by = u.id
                ORDER BY c.created_at DESC
            """)
        elif current_user['role'] == 'helper':
            # Helpers can see all campaigns
            cursor.execute("""
                SELECT c.*, u.username as creator_name
                FROM campaigns c
                JOIN users u ON c.created_by = u.id
                ORDER BY c.created_at DESC
            """)
        else:
            # Players can only see campaigns they're part of
            cursor.execute("""
                SELECT DISTINCT c.*, u.username as creator_name
                FROM campaigns c
                JOIN users u ON c.created_by = u.id
                JOIN characters ch ON c.id = ch.campaign_id
                WHERE ch.user_id = ?
                ORDER BY c.created_at DESC
            """, (current_user_id,))
        
        campaigns = []
        for row in cursor.fetchall():
            campaigns.append({
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'system_type': row['system_type'],
                'setting': row['setting'],
                'created_by': row['created_by'],
                'creator_name': row['creator_name'],
                'is_active': bool(row['is_active']),
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            })
        
        return jsonify({
            'campaigns': campaigns,
            'total': len(campaigns)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}")
        return jsonify({'error': 'Failed to retrieve campaigns'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/', methods=['POST'])
@jwt_required()
def create_campaign():
    """Create new campaign (admin/helper only)"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Required fields
        name = data.get('name')
        system_type = data.get('system_type')
        
        if not all([name, system_type]):
            return jsonify({'error': 'Name and system type are required'}), 400
        
        if system_type not in ['d20', 'd10', 'besm']:
            return jsonify({'error': 'Invalid system type'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if current user can create campaigns
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] not in ['admin', 'helper']:
            return jsonify({'error': 'Admin or helper access required'}), 403
        
        # Check if campaign name already exists
        cursor.execute("SELECT id FROM campaigns WHERE name = ?", (name,))
        if cursor.fetchone():
            return jsonify({'error': 'Campaign name already exists'}), 409
        
        # Create campaign
        cursor.execute("""
            INSERT INTO campaigns (name, description, system_type, setting, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            data.get('description', ''),
            system_type,
            data.get('setting', ''),
            current_user_id,
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        campaign_id = cursor.lastrowid
        db.commit()
        
        logger.info(f"Campaign '{name}' created by user {current_user_id}")
        
        return jsonify({
            'message': 'Campaign created successfully',
            'campaign_id': campaign_id,
            'name': name
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        return jsonify({'error': 'Failed to create campaign'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:campaign_id>', methods=['GET'])
@jwt_required()
def get_campaign(campaign_id):
    """Get specific campaign details"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get campaign
        cursor.execute("""
            SELECT c.*, u.username as creator_name
            FROM campaigns c
            JOIN users u ON c.created_by = u.id
            WHERE c.id = ?
        """, (campaign_id,))
        
        campaign = cursor.fetchone()
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Check access permissions
        if current_user['role'] not in ['admin', 'helper']:
            # Players can only see campaigns they're part of
            cursor.execute("""
                SELECT COUNT(*) as character_count
                FROM characters
                WHERE user_id = ? AND campaign_id = ?
            """, (current_user_id, campaign_id))
            
            if cursor.fetchone()['character_count'] == 0:
                return jsonify({'error': 'Access denied'}), 403
        
        # Get campaign statistics
        cursor.execute("""
            SELECT COUNT(*) as character_count
            FROM characters WHERE campaign_id = ?
        """, (campaign_id,))
        
        character_count = cursor.fetchone()['character_count']
        
        cursor.execute("""
            SELECT COUNT(*) as location_count
            FROM locations WHERE campaign_id = ?
        """, (campaign_id,))
        
        location_count = cursor.fetchone()['location_count']
        
        return jsonify({
            'campaign': {
                'id': campaign['id'],
                'name': campaign['name'],
                'description': campaign['description'],
                'system_type': campaign['system_type'],
                'setting': campaign['setting'],
                'created_by': campaign['created_by'],
                'creator_name': campaign['creator_name'],
                'is_active': bool(campaign['is_active']),
                'created_at': campaign['created_at'],
                'updated_at': campaign['updated_at']
            },
            'statistics': {
                'characters': character_count,
                'locations': location_count
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign {campaign_id}: {e}")
        return jsonify({'error': 'Failed to retrieve campaign'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:campaign_id>', methods=['PUT'])
@jwt_required()
def update_campaign(campaign_id):
    """Update campaign (admin/helper or creator only)"""
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
        
        # Get campaign
        cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        campaign = cursor.fetchone()
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Check permissions
        if current_user['role'] not in ['admin', 'helper'] and campaign['created_by'] != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update fields
        updates = []
        params = []
        
        if 'name' in data and data['name'] != campaign['name']:
            # Check if name is already taken
            cursor.execute("SELECT id FROM campaigns WHERE name = ? AND id != ?", (data['name'], campaign_id))
            if cursor.fetchone():
                return jsonify({'error': 'Campaign name already exists'}), 409
            
            updates.append("name = ?")
            params.append(data['name'])
        
        if 'description' in data:
            updates.append("description = ?")
            params.append(data['description'])
        
        if 'system_type' in data and data['system_type'] != campaign['system_type']:
            if data['system_type'] not in ['d20', 'd10', 'besm']:
                return jsonify({'error': 'Invalid system type'}), 400
            
            updates.append("system_type = ?")
            params.append(data['system_type'])
        
        if 'setting' in data:
            updates.append("setting = ?")
            params.append(data['setting'])
        
        if 'is_active' in data and data['is_active'] != campaign['is_active']:
            if current_user['role'] != 'admin':
                return jsonify({'error': 'Only admins can change campaign status'}), 403
            
            updates.append("is_active = ?")
            params.append(data['is_active'])
        
        # Apply updates if any
        if updates:
            params.append(datetime.utcnow())  # updated_at
            params.append(campaign_id)
            
            query = f"UPDATE campaigns SET {', '.join(updates)}, updated_at = ? WHERE id = ?"
            cursor.execute(query, params)
            
            db.commit()
            
            logger.info(f"Campaign {campaign_id} updated by user {current_user_id}")
        
        # Return updated campaign
        return get_campaign(campaign_id)
        
    except Exception as e:
        logger.error(f"Error updating campaign {campaign_id}: {e}")
        return jsonify({'error': 'Failed to update campaign'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/<int:campaign_id>', methods=['DELETE'])
@jwt_required()
def delete_campaign(campaign_id):
    """Delete campaign (admin only)"""
    try:
        current_user_id = get_jwt_identity()
        
        db = get_db()
        cursor = db.cursor()
        
        # Check if current user is admin
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        # Check if campaign exists
        cursor.execute("SELECT name FROM campaigns WHERE id = ?", (campaign_id,))
        campaign = cursor.fetchone()
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Soft delete - mark as inactive instead of removing
        cursor.execute("UPDATE campaigns SET is_active = 0, updated_at = ? WHERE id = ?", 
                      (datetime.utcnow(), campaign_id))
        
        db.commit()
        
        logger.info(f"Campaign {campaign_id} ({campaign['name']}) deactivated by admin {current_user_id}")
        
        return jsonify({'message': 'Campaign deactivated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting campaign {campaign_id}: {e}")
        return jsonify({'error': 'Failed to delete campaign'}), 500
    finally:
        if 'db' in locals():
            db.close()
