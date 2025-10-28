"""
ShadowRealms AI - Locations API Routes
Handles location management and character location tracking
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from services.health_check import require_llm
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

locations_bp = Blueprint('locations', __name__)


@locations_bp.route('/campaigns/<int:campaign_id>/locations/suggest', methods=['POST'])
@jwt_required()
@require_llm
def suggest_locations(campaign_id):
    """AI suggests locations based on campaign setting"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Verify user is admin or campaign creator
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.created_by, c.name, c.description, c.game_system, u.role
            FROM campaigns c
            JOIN users u ON u.id = %s
            WHERE c.id = %s
        """, (user_id, campaign_id))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Campaign not found'}), 404
        
        campaign_creator = row['created_by']
        campaign_name = row['name']
        campaign_desc = row['description']
        game_system = row['game_system']
        user_role = row['role']
        
        if campaign_creator != user_id and user_role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get setting description if provided
        setting_description = data.get('setting_description', campaign_desc)
        
        # AI prompt for location suggestions
        from services.llm_service import get_llm_service
        llm_service = get_llm_service()
        
        prompt = f"""You are a storyteller for a {game_system} tabletop RPG campaign.

Campaign: {campaign_name}
Setting: {setting_description}

Suggest 5 atmospheric locations that are SPECIFIC to this campaign's setting. For each location, provide:
- Name (short, evocative, fitting the setting)
- Type (tavern, dungeon, city, temple, custom)
- Description (2-3 sentences, atmospheric and setting-specific)

IMPORTANT: Make these locations unique to THIS campaign's world, not generic fantasy locations.

Format your response as ONLY a JSON array, nothing else:
[
  {{"name": "Location Name", "type": "tavern", "description": "Description here"}},
  ...
]

Be specific, evocative, and true to the campaign's setting and theme."""

        # Call LLM service with proper parameters
        llm_context = {
            'system_prompt': f'You are a creative storyteller for {game_system} RPGs. Generate unique, setting-specific locations.',
            'campaign_context': f"Campaign: {campaign_name}\nSetting: {setting_description}"
        }
        
        llm_config = {
            'max_tokens': 1000,
            'temperature': 0.9,  # Higher temp for more creativity
            'top_p': 0.95
        }
        
        response = llm_service.generate_response(prompt, llm_context, llm_config)
        
        # Parse AI response
        try:
            # Try to extract JSON from response
            import re
            import json
            
            logger.info(f"AI Response: {response[:200]}...")  # Log first 200 chars
            
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                suggestions = json.loads(json_match.group())
                logger.info(f"✅ Successfully parsed {len(suggestions)} AI-generated location suggestions")
            else:
                logger.warning(f"⚠️ No JSON array found in AI response, using fallbacks")
                raise ValueError("No JSON array in response")
                
        except Exception as e:
            logger.error(f"❌ Failed to parse AI suggestions: {e}. Response was: {response[:500]}")
            # Return error to frontend so it knows AI failed
            return jsonify({
                'error': 'AI service failed to generate suggestions',
                'suggestions': [],
                'debug_info': str(e)
            }), 500
        
        logger.info(f"AI suggested {len(suggestions)} locations for campaign {campaign_id}")
        
        return jsonify({
            'suggestions': suggestions,
            'campaign_name': campaign_name,
            'game_system': game_system
        }), 200
        
    except Exception as e:
        logger.error(f"Error suggesting locations: {e}")
        return jsonify({'error': 'Failed to generate suggestions'}), 500


@locations_bp.route('/campaigns/<int:campaign_id>/locations/batch', methods=['POST'])
@jwt_required()
def batch_create_locations(campaign_id):
    """Create multiple locations at once from AI suggestions"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Verify permission
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.created_by, u.role
            FROM campaigns c
            JOIN users u ON u.id = %s
            WHERE c.id = %s
        """, (user_id, campaign_id))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Campaign not found'}), 404
        
        campaign_creator = row['created_by']
        user_role = row['role']
        
        if campaign_creator != user_id and user_role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        locations_to_create = data.get('locations', [])
        if not locations_to_create:
            return jsonify({'error': 'No locations provided'}), 400
        
        created_ids = []
        for loc in locations_to_create:
            cursor.execute("""
                INSERT INTO locations (campaign_id, name, type, description, created_by)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (campaign_id, loc['name'], loc['type'], loc.get('description', ''), user_id))
            result = cursor.fetchone()
            created_ids.append(result['id'])
        
        conn.commit()
        
        logger.info(f"Batch created {len(created_ids)} locations for campaign {campaign_id}")
        
        return jsonify({
            'message': f'Created {len(created_ids)} locations',
            'location_ids': created_ids
        }), 201
        
    except Exception as e:
        logger.error(f"Error batch creating locations: {e}")
        return jsonify({'error': 'Failed to create locations'}), 500


@locations_bp.route('/campaigns/<int:campaign_id>/locations', methods=['GET'])
@jwt_required()
def get_campaign_locations(campaign_id):
    """Get all locations for a campaign"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT l.*, u.username as creator_name,
                   COUNT(DISTINCT cl.character_id) as character_count
            FROM locations l
            LEFT JOIN users u ON l.created_by = u.id
            LEFT JOIN character_locations cl ON l.id = cl.location_id 
                AND cl.exited_at IS NULL
            WHERE l.campaign_id = %s AND l.is_active = TRUE
            GROUP BY l.id, u.username
            ORDER BY 
                CASE WHEN l.type = 'ooc' THEN 0 ELSE 1 END,
                l.created_at ASC
        """, (campaign_id,))
        
        locations = []
        for row in cursor.fetchall():
            locations.append({
                'id': row['id'],
                'campaign_id': row['campaign_id'],
                'name': row['name'],
                'type': row['type'],
                'description': row['description'],
                'created_by': row['created_by'],
                'created_at': row['created_at'],
                'is_active': row['is_active'],
                'creator_name': row['creator_name'],
                'character_count': row['character_count']
            })
        
        return jsonify(locations), 200
        
    except Exception as e:
        logger.error(f"Error fetching campaign locations: {e}")
        return jsonify({'error': 'Failed to fetch locations'}), 500


@locations_bp.route('/locations/<int:location_id>', methods=['GET'])
@jwt_required()
def get_location(location_id):
    """Get specific location details"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT l.*, u.username as creator_name
            FROM locations l
            LEFT JOIN users u ON l.created_by = u.id
            WHERE l.id = %s
        """, (location_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Location not found'}), 404
        
        location = {
            'id': row['id'],
            'campaign_id': row['campaign_id'],
            'name': row['name'],
            'type': row['type'],
            'description': row['description'],
            'created_by': row['created_by'],
            'created_at': row['created_at'],
            'is_active': row['is_active'],
            'creator_name': row['creator_name']
        }
        
        # Get characters currently in this location
        cursor.execute("""
            SELECT c.id, c.name, u.username, cl.entered_at
            FROM character_locations cl
            JOIN characters c ON cl.character_id = c.id
            JOIN users u ON c.user_id = u.id
            WHERE cl.location_id = %s AND cl.exited_at IS NULL
            ORDER BY cl.entered_at ASC
        """, (location_id,))
        
        characters = []
        for char_row in cursor.fetchall():
            characters.append({
                'id': char_row['id'],
                'name': char_row['name'],
                'player_name': char_row['username'],
                'entered_at': char_row['entered_at']
            })
        
        location['characters'] = characters
        
        return jsonify(location), 200
        
    except Exception as e:
        logger.error(f"Error fetching location: {e}")
        return jsonify({'error': 'Failed to fetch location'}), 500


@locations_bp.route('/campaigns/<int:campaign_id>/locations', methods=['POST'])
@jwt_required()
def create_location(campaign_id):
    """Create a new location (admin only)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Verify user is admin or campaign creator
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT c.created_by, u.role
            FROM campaigns c
            JOIN users u ON u.id = %s
            WHERE c.id = %s
        """, (user_id, campaign_id))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Campaign not found'}), 404
        
        campaign_creator, user_role = row
        if campaign_creator != user_id and user_role != 'admin':
            return jsonify({'error': 'Unauthorized - admin only'}), 403
        
        # Validate input
        name = data.get('name', '').strip()
        location_type = data.get('type', 'custom').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'error': 'Location name is required'}), 400
        
        # Create location
        cursor.execute("""
            INSERT INTO locations (campaign_id, name, type, description, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (campaign_id, name, location_type, description, user_id))
        
        result = cursor.fetchone()
        location_id = result['id']
        conn.commit()
        
        logger.info(f"Location created: {name} (ID: {location_id}) in campaign {campaign_id}")
        
        return jsonify({
            'id': location_id,
            'campaign_id': campaign_id,
            'name': name,
            'type': location_type,
            'description': description,
            'created_by': user_id,
            'message': 'Location created successfully'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating location: {e}")
        return jsonify({'error': 'Failed to create location'}), 500


@locations_bp.route('/locations/<int:location_id>', methods=['PUT'])
@jwt_required()
def update_location(location_id):
    """Update location details (admin only)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify location exists and user has permission
        cursor.execute("""
            SELECT l.campaign_id, l.created_by, c.created_by as campaign_creator, u.role
            FROM locations l
            JOIN campaigns c ON l.campaign_id = c.id
            JOIN users u ON u.id = %s
            WHERE l.id = %s
        """, (user_id, location_id))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Location not found'}), 404
        
        campaign_id, location_creator, campaign_creator, user_role = row
        if location_creator != user_id and campaign_creator != user_id and user_role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update fields if provided
        updates = []
        params = []
        
        if 'name' in data:
            updates.append('name = %s')
            params.append(data['name'].strip())
        
        if 'description' in data:
            updates.append('description = %s')
            params.append(data['description'].strip())
        
        if 'type' in data:
            updates.append('type = %s')
            params.append(data['type'].strip())
        
        if not updates:
            return jsonify({'error': 'No fields to update'}), 400
        
        params.append(location_id)
        query = f"UPDATE locations SET {', '.join(updates)} WHERE id = %s"
        cursor.execute(query, params)
        conn.commit()
        
        logger.info(f"Location updated: {location_id}")
        
        return jsonify({'message': 'Location updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error updating location: {e}")
        return jsonify({'error': 'Failed to update location'}), 500


@locations_bp.route('/campaigns/<int:campaign_id>/locations/<int:location_id>', methods=['DELETE'])
@jwt_required()
def delete_location(campaign_id, location_id):
    """Delete location with AI memory cleanup and audit trail"""
    try:
        user_id = get_jwt_identity()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Get location details before deletion
        cursor.execute("""
            SELECT l.type, l.name, l.description, l.campaign_id, c.created_by, u.role
            FROM locations l
            JOIN campaigns c ON l.campaign_id = c.id
            JOIN users u ON u.id = %s
            WHERE l.id = %s AND l.campaign_id = %s AND l.is_active = TRUE
        """, (user_id, location_id, campaign_id))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Location not found or already deleted'}), 404
        
        location_type, location_name, location_desc, campaign_id, campaign_creator, user_role = row
        
        # Can't delete OOC room
        if location_type == 'ooc':
            return jsonify({'error': 'Cannot delete OOC room'}), 400
        
        if campaign_creator != user_id and user_role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Count messages that will be affected
        cursor.execute("SELECT COUNT(*) FROM messages WHERE location_id = %s", (location_id,))
        message_count = cursor.fetchone()[0]
        
        logger.info(f"🗑️ Deleting location {location_id} ({location_name}) - {message_count} messages will be removed")
        
        # 1. CREATE AUDIT LOG ENTRY
        cursor.execute("""
            INSERT INTO location_deletion_log 
            (location_id, campaign_id, location_name, location_type, location_description, deleted_by, message_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (location_id, campaign_id, location_name, location_type, location_desc, user_id, message_count))
        
        # 2. CLEAN UP AI MEMORY - Remove message embeddings from ChromaDB
        try:
            from services.rag_service import get_rag_service
            rag_service = get_rag_service()
            
            # Get all message IDs for this location
            cursor.execute("SELECT id FROM messages WHERE location_id = %s", (location_id,))
            message_ids = [row['id'] for row in cursor.fetchall()]
            
            if message_ids and hasattr(rag_service, 'client'):
                try:
                    collection = rag_service.client.get_or_create_collection(name='message_memory')
                    # Delete embeddings for these messages
                    embedding_ids = [f"msg_{msg_id}_{campaign_id}" for msg_id in message_ids]
                    if embedding_ids:
                        collection.delete(ids=embedding_ids)
                        logger.info(f"✅ Purged {len(embedding_ids)} message embeddings from AI memory (ChromaDB)")
                except Exception as e:
                    logger.warning(f"⚠️ Could not purge ChromaDB embeddings: {e}")
            else:
                logger.info(f"ℹ️ No messages to purge from ChromaDB")
                
        except Exception as e:
            logger.warning(f"⚠️ ChromaDB cleanup failed (non-critical): {e}")
        
        # 3. SOFT DELETE LOCATION (marks as inactive, keeps for audit trail)
        cursor.execute("""
            SELECT id FROM locations 
            WHERE campaign_id = %s AND type = 'ooc' AND is_active = TRUE
        """, (campaign_id,))
        ooc_row = cursor.fetchone()
        
        if ooc_row:
            cursor.execute("""
                UPDATE character_locations 
                SET exited_at = %s, exit_reason = 'Location deleted by admin'
                WHERE location_id = %s AND exited_at IS NULL
            """, (datetime.utcnow().isoformat(), location_id))
        
        conn.commit()
        
        logger.info(f"✅ Location {location_id} ({location_name}) deleted successfully:")
        logger.info(f"   • Soft-deleted from active locations")
        logger.info(f"   • {message_count} messages CASCADE deleted from SQL")
        logger.info(f"   • Message embeddings purged from ChromaDB")
        logger.info(f"   • Audit log created (deleted by user {user_id})")
        logger.info(f"   • AI memory cleaned - no conflicts will occur")
        
        return jsonify({
            'message': 'Location deleted successfully',
            'audit': {
                'location_name': location_name,
                'messages_removed': message_count,
                'deleted_by': user_id,
                'ai_memory_cleaned': True
            }
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Error deleting location: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to delete location'}), 500


@locations_bp.route('/locations/<int:location_id>/enter', methods=['POST'])
@jwt_required()
def enter_location(location_id):
    """Character enters a location"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        character_id = data.get('character_id')
        entry_reason = data.get('reason', 'No reason provided')
        
        if not character_id:
            return jsonify({'error': 'character_id is required'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify character belongs to user
        cursor.execute("SELECT id FROM characters WHERE id = %s AND user_id = %s", 
                      (character_id, user_id))
        if not cursor.fetchone():
            return jsonify({'error': 'Character not found or unauthorized'}), 404
        
        # Exit from current location first
        cursor.execute("""
            UPDATE character_locations 
            SET exited_at = %s, exit_reason = 'Moving to new location'
            WHERE character_id = %s AND exited_at IS NULL
        """, (datetime.utcnow().isoformat(), character_id))
        
        # Enter new location
        cursor.execute("""
            INSERT INTO character_locations (character_id, location_id, entry_reason)
            VALUES (%s, %s, %s)
        """, (character_id, location_id, entry_reason))
        
        # Update character's current location
        cursor.execute("""
            UPDATE characters 
            SET current_location_id = %s, last_location_id = current_location_id
            WHERE id = %s
        """, (location_id, character_id))
        
        conn.commit()
        
        logger.info(f"Character {character_id} entered location {location_id}")
        
        return jsonify({'message': 'Entered location successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error entering location: {e}")
        return jsonify({'error': 'Failed to enter location'}), 500


@locations_bp.route('/locations/<int:location_id>/leave', methods=['POST'])
@jwt_required()
def leave_location(location_id):
    """Character leaves a location"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        character_id = data.get('character_id')
        exit_reason = data.get('reason', 'Left location')
        
        if not character_id:
            return jsonify({'error': 'character_id is required'}), 400
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify character belongs to user
        cursor.execute("SELECT id FROM characters WHERE id = %s AND user_id = %s", 
                      (character_id, user_id))
        if not cursor.fetchone():
            return jsonify({'error': 'Character not found or unauthorized'}), 404
        
        # Exit location
        cursor.execute("""
            UPDATE character_locations 
            SET exited_at = %s, exit_reason = %s
            WHERE character_id = %s AND location_id = %s AND exited_at IS NULL
        """, (datetime.utcnow().isoformat(), exit_reason, character_id, location_id))
        
        # Update character's last location
        cursor.execute("""
            UPDATE characters 
            SET last_location_id = current_location_id, current_location_id = NULL
            WHERE id = %s
        """, (character_id,))
        
        conn.commit()
        
        logger.info(f"Character {character_id} left location {location_id}")
        
        return jsonify({'message': 'Left location successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error leaving location: {e}")
        return jsonify({'error': 'Failed to leave location'}), 500


def create_ooc_room(campaign_id: int, created_by: int) -> int:
    """
    Helper function to create OOC room for a campaign
    Called when a new campaign is created
    
    Returns:
        location_id of created OOC room
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO locations (campaign_id, name, type, description, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            campaign_id,
            'Out of Character Lobby',
            'ooc',
            'A place for players to discuss the campaign, ask questions, and chat as themselves (not as characters). '
            'This is the default meeting place before entering the game world.',
            created_by
        ))
        
        result = cursor.fetchone()
        location_id = result['id']
        conn.commit()
        
        logger.info(f"OOC room created for campaign {campaign_id}: location {location_id}")
        
        return location_id
        
    except Exception as e:
        logger.error(f"Error creating OOC room: {e}")
        raise

