"""
Message routes for ShadowRealms AI
Handles saving and retrieving messages for campaigns and locations
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

messages_bp = Blueprint('messages', __name__)

@messages_bp.route('/campaigns/<int:campaign_id>/locations/<int:location_id>', methods=['GET'])
@jwt_required()
def get_messages(campaign_id, location_id):
    """Get all messages for a specific location"""
    try:
        user_id = get_jwt_identity()
        
        # Optional pagination parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify user has access to campaign
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = %s AND (created_by = %s OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = %s
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            return jsonify({'error': 'Unauthorized or campaign not found'}), 403
        
        # Fetch messages for the location
        cursor.execute("""
            SELECT 
                m.id,
                m.campaign_id,
                m.location_id,
                m.user_id,
                m.character_id,
                m.message_type,
                m.content,
                m.role,
                m.created_at,
                u.username,
                c.name as character_name
            FROM messages m
            JOIN users u ON m.user_id = u.id
            LEFT JOIN characters c ON m.character_id = c.id
            WHERE m.campaign_id = %s AND m.location_id = %s
            ORDER BY m.created_at ASC
            LIMIT %s OFFSET %s
        """, (campaign_id, location_id, limit, offset))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'id': row['id'],
                'campaign_id': row['campaign_id'],
                'location_id': row['location_id'],
                'user_id': row['user_id'],
                'character_id': row['character_id'],
                'message_type': row['message_type'],
                'content': row['content'],
                'role': row['role'],
                'created_at': row['created_at'],
                'username': row['username'],
                'character_name': row['character_name']
            })
        
        return jsonify(messages), 200
        
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return jsonify({'error': 'Failed to fetch messages'}), 500

@messages_bp.route('/campaigns/<int:campaign_id>/locations/<int:location_id>', methods=['POST'])
@jwt_required()
def save_message(campaign_id, location_id):
    """Save a new message"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'content' not in data:
            return jsonify({'error': 'Message content is required'}), 400
        
        content = data.get('content')
        message_type = data.get('message_type', 'ic')  # ic, ooc, system, action
        role = data.get('role', 'user')  # user or assistant (for AI messages)
        character_id = data.get('character_id')
        
        if not content.strip():
            return jsonify({'error': 'Message content cannot be empty'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user is currently banned
        try:
            from services.ooc_monitor import create_ooc_monitor
            from services.llm_service import create_llm_service
            
            llm_service = create_llm_service()
            ooc_monitor = create_ooc_monitor(llm_service)
            is_banned, ban_message = ooc_monitor.check_user_ban(user_id)
            
            if is_banned:
                return jsonify({
                    'error': 'You are temporarily banned',
                    'ban_message': ban_message
                }), 403
        except Exception as e:
            logger.error(f"Error checking ban status: {e}")
            # Continue if ban check fails
        
        # Verify user has access to campaign
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = %s AND (created_by = %s OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = %s
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            return jsonify({'error': 'Unauthorized or campaign not found'}), 403
        
        # Verify location exists in this campaign AND get location type
        cursor.execute("""
            SELECT id, type FROM locations
            WHERE id = %s AND campaign_id = %s
        """, (location_id, campaign_id))
        
        location_row = cursor.fetchone()
        if not location_row:
            return jsonify({'error': 'Location not found'}), 404
        
        location_type = location_row['type']
        
        # CHECK FOR OOC VIOLATIONS (only for user messages, not AI)
        ooc_warning = None
        if role == 'user':
            try:
                from services.ooc_monitor import create_ooc_monitor
                from services.llm_service import create_llm_service
                
                llm_service = create_llm_service()
                ooc_monitor = create_ooc_monitor(llm_service)
                
                is_violation, warning_msg, should_ban = ooc_monitor.check_message(
                    message=content,
                    user_id=user_id,
                    campaign_id=campaign_id,
                    location_type=location_type
                )
                
                if is_violation:
                    logger.warning(f"OOC violation detected for user {user_id}: {content[:50]}...")
                    
                    if should_ban:
                        # User has been banned
                        return jsonify({
                            'error': 'OOC violation - temporarily banned',
                            'warning': warning_msg,
                            'violation': True
                        }), 403
                    else:
                        # Store warning to include in response
                        ooc_warning = warning_msg
                        logger.info(f"Issuing OOC warning to user {user_id}")
            except Exception as e:
                logger.error(f"Error checking OOC violation: {e}")
                # Continue if OOC check fails - don't block legitimate messages
        
        # Insert message
        cursor.execute("""
            INSERT INTO messages (
                campaign_id, location_id, user_id, character_id,
                message_type, content, role, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            campaign_id, location_id, user_id, character_id,
            message_type, content, role, datetime.now().isoformat()
        ))
        
        result = cursor.fetchone()
        message_id = result['id']
        conn.commit()
        
        # Store message embedding in ChromaDB for semantic search
        try:
            from services.rag_service import get_rag_service
            rag_service = get_rag_service()
            
            # Get character name if applicable
            character_name = None
            if character_id:
                cursor.execute("SELECT name FROM characters WHERE id = %s", (character_id,))
                char = cursor.fetchone()
                if char:
                    character_name = char[0]
            
            # Embed the message
            rag_service.store_message_embedding(
                message_id=message_id,
                campaign_id=campaign_id,
                location_id=location_id,
                user_id=user_id,
                content=content,
                role=role,
                character_name=character_name
            )
            logger.info(f"Message {message_id} embedded for semantic search")
        except Exception as e:
            # Don't fail the request if embedding fails
            logger.warning(f"Failed to embed message: {e}")
        
        # Fetch the saved message with joined data
        cursor.execute("""
            SELECT 
                m.id,
                m.campaign_id,
                m.location_id,
                m.user_id,
                m.character_id,
                m.message_type,
                m.content,
                m.role,
                m.created_at,
                u.username,
                c.name as character_name
            FROM messages m
            JOIN users u ON m.user_id = u.id
            LEFT JOIN characters c ON m.character_id = c.id
            WHERE m.id = %s
        """, (message_id,))
        
        row = cursor.fetchone()
        saved_message = {
            'id': row['id'],
            'campaign_id': row['campaign_id'],
            'location_id': row['location_id'],
            'user_id': row['user_id'],
            'character_id': row['character_id'],
            'message_type': row['message_type'],
            'content': row['content'],
            'role': row['role'],
            'created_at': row['created_at'],
            'username': row['username'],
            'character_name': row['character_name']
        }
        
        logger.info(f"Message saved: ID={message_id}, Campaign={campaign_id}, Location={location_id}")
        
        # Build response
        response_data = {
            'message': 'Message saved successfully',
            'data': saved_message
        }
        
        # Include OOC warning if there was a violation
        if ooc_warning:
            response_data['ooc_warning'] = ooc_warning
        
        return jsonify(response_data), 201
        
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        return jsonify({'error': 'Failed to save message'}), 500

@messages_bp.route('/messages/<int:message_id>', methods=['DELETE'])
@jwt_required()
def delete_message(message_id):
    """Delete a message (admin or message author only)"""
    try:
        user_id = get_jwt_identity()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user is admin or message owner
        cursor.execute("""
            SELECT m.user_id, c.created_by, u.role
            FROM messages m
            JOIN campaigns c ON m.campaign_id = c.id
            JOIN users u ON u.id = %s
            WHERE m.id = %s
        """, (user_id, message_id))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Message not found'}), 404
        
        message_owner_id, campaign_creator_id, user_role = row
        
        # Only message owner, campaign creator, or admin can delete
        if user_id != message_owner_id and user_id != campaign_creator_id and user_role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete the message
        cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
        conn.commit()
        
        logger.info(f"Message deleted: ID={message_id} by User={user_id}")
        
        return jsonify({'message': 'Message deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return jsonify({'error': 'Failed to delete message'}), 500

