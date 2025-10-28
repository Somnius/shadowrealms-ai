"""
ShadowRealms AI - Dice Rolling API Routes
Handles dice rolls for manual player rolls and AI-triggered rolls
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from database import get_db
from services.dice_service import dice_service
import logging
import json

logger = logging.getLogger(__name__)

dice_bp = Blueprint('dice', __name__)


@dice_bp.route('/campaigns/<int:campaign_id>/roll', methods=['POST'])
@jwt_required()
def manual_roll(campaign_id):
    """
    Manual dice roll by player
    
    Body:
        pool_size: int - Number of d10s to roll
        difficulty: int - Target number (default 6)
        specialty: bool - Whether this is a specialty roll (10s count as 2)
        character_id: int (optional) - Character making the roll
        action_description: str (optional) - What the roll is for
        location_id: int (optional) - Where the roll is happening
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate input
        pool_size = data.get('pool_size')
        if not pool_size or pool_size < 1:
            return jsonify({'error': 'pool_size must be at least 1'}), 400
        
        difficulty = data.get('difficulty', 6)
        specialty = data.get('specialty', False)
        character_id = data.get('character_id')
        action_description = data.get('action_description', 'Manual roll')
        location_id = data.get('location_id')
        
        # Roll the dice
        roll_result = dice_service.roll_d10_pool(pool_size, difficulty, specialty)
        
        # Save to database
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO dice_rolls (
                campaign_id, location_id, user_id, character_id, 
                roll_type, action_description, dice_pool, difficulty,
                results, successes, is_botch, is_critical, modifiers
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            campaign_id, location_id, user_id, character_id,
            'manual', action_description, pool_size, difficulty,
            json.dumps(roll_result['results']), roll_result['successes'],
            roll_result['is_botch'], roll_result['is_critical'],
            json.dumps({'specialty': specialty})
        ))
        
        result = cursor.fetchone()
        roll_id = result['id']
        conn.commit()
        
        # Get character name if provided
        character_name = None
        if character_id:
            cursor.execute("SELECT name FROM characters WHERE id = %s", (character_id,))
            row = cursor.fetchone()
            if row:
                character_name = row['name']
        
        # Format for chat
        chat_message = dice_service.format_roll_for_chat(
            roll_result, character_name, action_description
        )
        
        logger.info(f"Manual roll by user {user_id}: {roll_result['successes']} successes")
        
        return jsonify({
            'roll_id': roll_id,
            'roll_result': roll_result,
            'chat_message': chat_message
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing manual roll: {e}")
        return jsonify({'error': 'Failed to process roll'}), 500


@dice_bp.route('/campaigns/<int:campaign_id>/roll/contested', methods=['POST'])
@jwt_required()
def contested_roll(campaign_id):
    """
    Contested roll between two parties
    
    Body:
        attacker_pool: int
        defender_pool: int
        difficulty: int (optional, default 6)
        attacker_character_id: int (optional)
        defender_character_id: int (optional)
        action_description: str (optional)
        location_id: int (optional)
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        attacker_pool = data.get('attacker_pool')
        defender_pool = data.get('defender_pool')
        
        if not attacker_pool or not defender_pool:
            return jsonify({'error': 'Both attacker_pool and defender_pool required'}), 400
        
        difficulty = data.get('difficulty', 6)
        action_description = data.get('action_description', 'Contested roll')
        location_id = data.get('location_id')
        
        # Roll
        result = dice_service.roll_contested(attacker_pool, defender_pool, difficulty)
        
        # Save both rolls to database
        conn = get_db()
        cursor = conn.cursor()
        
        # Attacker roll
        cursor.execute("""
            INSERT INTO dice_rolls (
                campaign_id, location_id, user_id, character_id,
                roll_type, action_description, dice_pool, difficulty,
                results, successes, is_botch, is_critical
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            campaign_id, location_id, user_id, data.get('attacker_character_id'),
            'contested_attacker', action_description, attacker_pool, difficulty,
            json.dumps(result['attacker_roll']['results']),
            result['attacker_roll']['successes'],
            result['attacker_roll']['is_botch'],
            result['attacker_roll']['is_critical']
        ))
        
        # Defender roll
        cursor.execute("""
            INSERT INTO dice_rolls (
                campaign_id, location_id, user_id, character_id,
                roll_type, action_description, dice_pool, difficulty,
                results, successes, is_botch, is_critical
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            campaign_id, location_id, user_id, data.get('defender_character_id'),
            'contested_defender', action_description, defender_pool, difficulty,
            json.dumps(result['defender_roll']['results']),
            result['defender_roll']['successes'],
            result['defender_roll']['is_botch'],
            result['defender_roll']['is_critical']
        ))
        
        conn.commit()
        
        logger.info(f"Contested roll in campaign {campaign_id}: {result['winner']} wins")
        
        return jsonify({
            'result': result,
            'message': result['message']
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing contested roll: {e}")
        return jsonify({'error': 'Failed to process contested roll'}), 500


@dice_bp.route('/campaigns/<int:campaign_id>/roll/ai', methods=['POST'])
@jwt_required()
def ai_roll(campaign_id):
    """
    AI-triggered roll for NPC actions, events, weather, etc.
    Can be called by AI service or by admin
    
    Body:
        action_type: str - 'npc_attack', 'npc_social', 'weather', 'event', 'mystery'
        context: dict - Context for determining dice pool
        location_id: int (optional)
        description: str (optional)
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Verify user is admin (AI service should have admin token)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row or row['role'] != 'admin':
            return jsonify({'error': 'Unauthorized - admin only'}), 403
        
        action_type = data.get('action_type', 'event')
        context = data.get('context', {})
        location_id = data.get('location_id')
        description = data.get('description', f'AI {action_type} roll')
        
        # AI determines appropriate dice pool
        pool_size, difficulty = dice_service.ai_determine_pool(action_type, context)
        
        # Roll
        roll_result = dice_service.roll_d10_pool(pool_size, difficulty)
        
        # Save to database
        cursor.execute("""
            INSERT INTO dice_rolls (
                campaign_id, location_id, user_id,
                roll_type, action_description, dice_pool, difficulty,
                results, successes, is_botch, is_critical, modifiers
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            campaign_id, location_id, user_id,
            f'ai_{action_type}', description, pool_size, difficulty,
            json.dumps(roll_result['results']), roll_result['successes'],
            roll_result['is_botch'], roll_result['is_critical'],
            json.dumps(context)
        ))
        
        result = cursor.fetchone()
        roll_id = result['id']
        conn.commit()
        
        logger.info(f"AI roll ({action_type}) in campaign {campaign_id}: {roll_result['successes']} successes")
        
        return jsonify({
            'roll_id': roll_id,
            'roll_result': roll_result,
            'pool_size': pool_size,
            'difficulty': difficulty,
            'action_type': action_type
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing AI roll: {e}")
        return jsonify({'error': 'Failed to process AI roll'}), 500


@dice_bp.route('/campaigns/<int:campaign_id>/rolls', methods=['GET'])
@jwt_required()
def get_roll_history(campaign_id):
    """
    Get roll history for a campaign
    
    Query params:
        limit: int (default 50)
        location_id: int (optional)
        character_id: int (optional)
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        location_id = request.args.get('location_id', type=int)
        character_id = request.args.get('character_id', type=int)
        
        conn = get_db()
        cursor = conn.cursor()
        
        query = """
            SELECT dr.*, u.username, c.name as character_name
            FROM dice_rolls dr
            LEFT JOIN users u ON dr.user_id = u.id
            LEFT JOIN characters c ON dr.character_id = c.id
            WHERE dr.campaign_id = %s
        """
        params = [campaign_id]
        
        if location_id:
            query += " AND dr.location_id = %s"
            params.append(location_id)
        
        if character_id:
            query += " AND dr.character_id = %s"
            params.append(character_id)
        
        query += " ORDER BY dr.rolled_at DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, params)
        
        rolls = []
        for row in cursor.fetchall():
            rolls.append({
                'id': row['id'],
                'campaign_id': row['campaign_id'],
                'location_id': row['location_id'],
                'user_id': row['user_id'],
                'character_id': row['character_id'],
                'roll_type': row['roll_type'],
                'action_description': row['action_description'],
                'dice_pool': row['dice_pool'],
                'difficulty': row['difficulty'],
                'results': json.loads(row['results']),
                'successes': row['successes'],
                'is_botch': row['is_botch'],
                'is_critical': row['is_critical'],
                'modifiers': json.loads(row['modifiers']) if row['modifiers'] else {},
                'rolled_at': row['rolled_at'],
                'username': row['username'],
                'character_name': row['character_name']
            })
        
        return jsonify(rolls), 200
        
    except Exception as e:
        logger.error(f"Error fetching roll history: {e}")
        return jsonify({'error': 'Failed to fetch roll history'}), 500


@dice_bp.route('/campaigns/<int:campaign_id>/roll/templates', methods=['GET'])
@jwt_required()
def get_roll_templates(campaign_id):
    """Get roll templates (system-wide and campaign-specific)"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM dice_roll_templates
            WHERE campaign_id = %s OR is_system = 1
            ORDER BY is_system DESC, name ASC
        """, (campaign_id,))
        
        templates = []
        for row in cursor.fetchall():
            templates.append({
                'id': row['id'],
                'campaign_id': row['campaign_id'],
                'name': row['name'],
                'description': row['description'],
                'dice_pool_formula': row['dice_pool_formula'],
                'default_difficulty': row['default_difficulty'],
                'created_by': row['created_by'],
                'is_system': row['is_system'],
                'created_at': row['created_at']
            })
        
        return jsonify(templates), 200
        
    except Exception as e:
        logger.error(f"Error fetching roll templates: {e}")
        return jsonify({'error': 'Failed to fetch templates'}), 500

