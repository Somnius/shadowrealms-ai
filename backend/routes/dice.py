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


def _json_field(value, default):
    if value is None or value == '':
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _user_can_access_campaign(cursor, user_id: int, campaign_id: int) -> bool:
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone()
    if u and u.get("role") == "admin":
        cursor.execute(
            """
            SELECT 1 FROM campaigns c
            WHERE c.id = %s AND c.is_active = TRUE
            """,
            (campaign_id,),
        )
        return cursor.fetchone() is not None
    cursor.execute(
        """
        SELECT 1 FROM campaigns c
        WHERE c.id = %s AND c.is_active = TRUE
          AND (
            c.created_by = %s
            OR EXISTS (
                SELECT 1 FROM campaign_players cp
                WHERE cp.campaign_id = c.id AND cp.user_id = %s
            )
          )
        """,
        (campaign_id, user_id, user_id),
    )
    return cursor.fetchone() is not None


def _character_ok_for_user_campaign(cursor, character_id: int, user_id: int, campaign_id: int) -> bool:
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    u = cursor.fetchone()
    if u and u.get("role") == "admin":
        cursor.execute(
            """
            SELECT 1 FROM characters
            WHERE id = %s AND campaign_id = %s
            """,
            (character_id, campaign_id),
        )
        return cursor.fetchone() is not None
    cursor.execute(
        """
        SELECT 1 FROM characters
        WHERE id = %s AND user_id = %s AND campaign_id = %s
        """,
        (character_id, user_id, campaign_id),
    )
    return cursor.fetchone() is not None


@dice_bp.route('/campaigns/<int:campaign_id>/roll', methods=['POST'])
@jwt_required()
def manual_roll(campaign_id):
    """
    Manual dice roll by player
    
    Body:
        pool_size: int - Number of d10s to roll (or use pool_expression)
        pool_expression: str (optional) - e.g. "4+3", "7-1" (Storyteller pool)
        difficulty: int - Target number (default 6)
        specialty: bool - Whether this is a specialty roll (10s count as 2)
        character_id: int (optional) - Character making the roll
        action_description: str (optional) - What the roll is for
        location_id: int (optional) - Where the roll is happening
    """
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json() or {}

        conn = get_db()
        cursor = conn.cursor()

        if not _user_can_access_campaign(cursor, user_id, campaign_id):
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found or access denied'}), 403

        pool_expression = (data.get('pool_expression') or '').strip()
        if pool_expression:
            from services.wod_dice import parse_pool_expression

            try:
                pool_size = parse_pool_expression(pool_expression)
            except ValueError as e:
                cursor.close()
                conn.close()
                return jsonify({'error': str(e)}), 400
        else:
            pool_size = data.get('pool_size')
            if not pool_size or int(pool_size) < 1:
                cursor.close()
                conn.close()
                return jsonify({'error': 'pool_size must be at least 1 (or send pool_expression)'}), 400
            pool_size = int(pool_size)
            if pool_size > 50:
                cursor.close()
                conn.close()
                return jsonify({'error': 'pool_size must be at most 50'}), 400

        difficulty = int(data.get('difficulty', 6))
        if difficulty < 2 or difficulty > 10:
            cursor.close()
            conn.close()
            return jsonify({'error': 'difficulty must be between 2 and 10'}), 400

        specialty = bool(data.get('specialty', False))
        character_id = data.get('character_id')
        if character_id is not None:
            character_id = int(character_id)
            if not _character_ok_for_user_campaign(cursor, character_id, user_id, campaign_id):
                cursor.close()
                conn.close()
                return jsonify({'error': 'Character not found or not yours in this campaign'}), 400

        action_description = (data.get('action_description') or 'Dice roll').strip() or 'Dice roll'
        location_id = data.get('location_id')
        leniency_floor = None
        if location_id is not None:
            location_id = int(location_id)
            cursor.execute(
                """
                SELECT dice_leniency_floor FROM locations
                WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                """,
                (location_id, campaign_id),
            )
            loc_row = cursor.fetchone()
            if not loc_row:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Location not found in this campaign'}), 400
            lf = loc_row.get("dice_leniency_floor")
            if lf is not None:
                try:
                    leniency_floor = int(lf)
                except (TypeError, ValueError):
                    leniency_floor = None

        # Roll the dice
        roll_result = dice_service.roll_d10_pool(
            pool_size, difficulty, specialty, leniency_floor=leniency_floor
        )
        
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
            json.dumps({
                'specialty': specialty,
                'pool_expression': pool_expression or None,
                'leniency_floor': roll_result.get('leniency_floor'),
            })
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

        cursor.close()
        conn.close()

        return jsonify({
            'roll_id': roll_id,
            'roll_result': roll_result,
            'chat_message': chat_message
        }), 200
        
    except Exception as e:
        logger.exception("Error processing manual roll: %s", e)
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
    Admin-only: list dice rolls for one campaign location (everyone’s rolls in that room).

    Query params:
        location_id: int (required) — current chat room / channel
        limit: int (optional, default 100, max 200)
    """
    try:
        user_id = int(get_jwt_identity())
        limit = request.args.get('limit', 100, type=int) or 100
        limit = max(1, min(int(limit), 200))
        location_id = request.args.get('location_id', type=int)
        if not location_id:
            return jsonify({'error': 'location_id query parameter is required'}), 400

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            urow = cursor.fetchone()
            if not urow or urow.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403

            cursor.execute(
                """
                SELECT 1 FROM locations
                WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                """,
                (location_id, campaign_id),
            )
            if not cursor.fetchone():
                return jsonify({'error': 'Location not found in this campaign'}), 404

            cursor.execute(
                """
                SELECT dr.*, u.username, c.name AS character_name
                FROM dice_rolls dr
                LEFT JOIN users u ON dr.user_id = u.id
                LEFT JOIN characters c ON dr.character_id = c.id
                WHERE dr.campaign_id = %s AND dr.location_id = %s
                ORDER BY dr.rolled_at DESC
                LIMIT %s
                """,
                (campaign_id, location_id, limit),
            )

            rolls = []
            for row in cursor.fetchall():
                ra = row['rolled_at']
                rolled_at_out = ra.isoformat() if hasattr(ra, 'isoformat') else str(ra)
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
                    'results': _json_field(row['results'], []),
                    'successes': row['successes'],
                    'is_botch': bool(row['is_botch']),
                    'is_critical': bool(row['is_critical']),
                    'modifiers': _json_field(row.get('modifiers'), {}),
                    'rolled_at': rolled_at_out,
                    'username': row['username'],
                    'character_name': row['character_name'],
                })

            return jsonify(rolls), 200
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        logger.exception("Error fetching roll history: %s", e)
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

