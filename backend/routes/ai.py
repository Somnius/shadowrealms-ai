#!/usr/bin/env python3
"""
ShadowRealms AI - AI Routes
AI integration, GPU monitoring, and LLM services
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import logging
import json
from datetime import datetime
from typing import Optional, Tuple

from database import get_db
from services.gpu_monitor import gpu_monitor_service
from services.llm_service import get_llm_service, last_generation_meta
from services.health_check import get_health_check_service, require_llm, require_ai_services
from services.ai_slash_commands import (
    EXPLAIN_VERBS,
    parse_ai_slash_line,
    execute_ai_slash_command,
    FUTURE_COMMAND_SUGGESTIONS,
    SUPPORTED_AI_SLASH_VERBS,
)
from services.message_time_format import format_message_time
from services.rules_edition import (
    DEFAULT_RULES_EDITION,
    edition_of,
    rules_edition_label,
    storyteller_rules_brief,
)
from services.character_prompt import format_character_for_prompt
from services import dice_pools
from services.assistant_grants import grant_assistant_reply
from services.request_validation import RequestValidationError, chat_text, strict_int

# Longest player message /api/ai/chat accepts (characters).
MAX_CHAT_MESSAGE_CHARS = 8000
# Shown instead of a reply when every model failed. Never contains the player's text, and no
# assistant grant is issued for it, so it can't be saved as a Storyteller message.
AI_UNAVAILABLE_TEXT = 'The AI Storyteller is unavailable right now. Please try again in a moment.'


def _public_ai_meta():
    """Which provider/model/role/language produced the last reply (no prompts, no keys)."""
    meta = last_generation_meta() or {}
    out = {k: meta[k] for k in ('provider', 'model_used', 'role', 'language', 'task_type', 'ms',
                                'trimmed', 'script_fix') if k in meta}
    if meta.get('attempts'):
        out['fallback_from'] = [
            {'provider': a.get('provider'), 'model': a.get('model')} for a in meta['attempts']
        ]
    return out


from services.log_safety import safe_log_value
logger = logging.getLogger(__name__)

bp = Blueprint('ai', __name__)

@bp.route('/health', methods=['GET'])
def check_ai_health():
    """
    Check health of all AI services (LM Studio, Ollama, ChromaDB)
    Quality over Speed - Verify services before operations
    """
    try:
        health_check = get_health_check_service()
        results = health_check.check_all_services()
        
        status_code = 200 if results['all_services_ok'] else 503
        
        return jsonify({
            'status': 'healthy' if results['all_services_ok'] else 'degraded',
            'services': {
                'lm_studio': results['lm_studio'],
                'ollama': results['ollama'],
                'chromadb': results['chromadb']
            },
            'llm_provider': health_check.get_primary_llm_provider(),
            'timestamp': datetime.utcnow().isoformat()
        }), status_code
        
    except Exception as e:
        logger.error(f"Error checking AI health: {e}")
        return jsonify({
            'status': 'error',
            'error': 'AI health check failed',
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@bp.route('/llm/status', methods=['GET'])
@jwt_required()
def get_llm_status():
    """Get LLM service status and available providers"""
    try:
        current_user_id = int(get_jwt_identity())
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get LLM service status
        llm_service = get_llm_service()
        llm_status = llm_service.get_system_status()
        
        return jsonify({
            'llm_status': llm_status,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting LLM status: {e}")
        return jsonify({'error': 'Failed to retrieve LLM status'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/llm/test', methods=['POST'])
@jwt_required()
def test_llm_provider():
    """Test a specific LLM provider"""
    try:
        current_user_id = int(get_jwt_identity())
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        data = request.get_json()
        provider_name = data.get('provider', 'lm_studio')
        
        # Test the provider
        llm_service = get_llm_service()
        test_result = llm_service.test_provider(provider_name)
        
        return jsonify({
            'test_result': test_result,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error testing LLM provider: {e}")
        return jsonify({'error': 'Failed to test LLM provider'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/status', methods=['GET'])
@jwt_required()
def get_ai_status():
    """Get AI service status and GPU monitoring information"""
    try:
        current_user_id = int(get_jwt_identity())
        
        db = get_db()
        cursor = db.cursor()
        
        # Get current user role
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get GPU status summary
        gpu_status = gpu_monitor_service.get_gpu_status_summary()
        
        # Get resource recommendations
        recommendations = gpu_monitor_service.get_resource_recommendations()
        
        # Get AI response configuration
        ai_config = gpu_monitor_service.get_ai_response_config()
        
        return jsonify({
            'ai_status': {
                'monitoring_active': gpu_status['monitoring_active'],
                'performance_mode': gpu_status['performance_mode'],
                'overall_health': gpu_status['overall_health'],
                'gpu_count': gpu_status['gpu_count']
            },
            'system_resources': {
                'cpu_usage': gpu_status.get('cpu_usage', 0),
                'memory_usage': gpu_status.get('memory_usage', 0),
                'gpu_details': gpu_status.get('gpu_details', [])
            },
            'ai_configuration': ai_config,
            'recommendations': recommendations,
            'timestamp': gpu_status.get('timestamp', 0)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting AI status: {e}")
        return jsonify({'error': 'Failed to retrieve AI status'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/chat', methods=['POST'])
@jwt_required()
@require_ai_services
def ai_chat():
    """AI chat endpoint with performance-based response generation"""
    db = None
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json()
        
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'No data provided'}), 400
        
        message = data.get('message')
        campaign_id = data.get('campaign_id')
        location_id = data.get('location')  # Get location from request
        context = data.get('context') or {}
        try:
            message = chat_text(message, 'Message', MAX_CHAT_MESSAGE_CHARS)
            location_id = strict_int(location_id, 'location', None, 1)
            # The message this one replies to (the chat's reply quote); see build_reply_context.
            reply_to_id = strict_int(data.get('reply_to_id'), 'reply_to_id', None, 1)
            if not isinstance(context, dict):
                raise RequestValidationError('context must be an object')
        except RequestValidationError as e:
            return jsonify({'error': e.public_message}), 400
        # From `/chat …` in UI: use full storyteller pipeline even in OOC rooms (not moderation-only path)
        assistant_direct = bool(data.get('assistant_direct') or data.get('direct_chat'))
        
        db = get_db()
        cursor = db.cursor()
        
        # Verify campaign access: member, creator, or site admin
        if campaign_id:
            try:
                campaign_id = int(campaign_id)
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid campaign_id'}), 400
            cursor.execute("""
                SELECT c.id
                FROM campaigns c
                WHERE c.id = %s AND c.is_active = TRUE
                  AND (
                    c.created_by = %s
                    OR EXISTS (
                        SELECT 1 FROM campaign_players cp
                        WHERE cp.campaign_id = c.id AND cp.user_id = %s
                    )
                    OR EXISTS (
                        SELECT 1 FROM users u
                        WHERE u.id = %s AND LOWER(TRIM(COALESCE(u.role, ''))) = 'admin'
                    )
                  )
            """, (campaign_id, current_user_id, current_user_id, current_user_id))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Resolve location type from DB (authoritative; do not trust client-only hints)
        location_type = None
        if campaign_id and location_id:
            cursor.execute("""
                SELECT type FROM locations
                WHERE id = %s AND campaign_id = %s AND is_active = TRUE
            """, (location_id, campaign_id))
            loc_row = cursor.fetchone()
            if loc_row and loc_row['type']:
                location_type = str(loc_row['type']).strip().lower()

        performance_mode = gpu_monitor_service.get_performance_mode()
        ai_config = gpu_monitor_service.get_ai_response_config()
        is_limited = gpu_monitor_service.is_resource_limited()

        # OOC rooms: do not run in-character storyteller; only moderate when content is IC-relevant
        if campaign_id and location_id and location_type == 'ooc' and not assistant_direct:
            ooc_text = generate_ooc_room_response(
                message, campaign_id, location_id, current_user_id
            )
            if ooc_text is None:
                return jsonify({
                    'response': None,
                    'ooc_no_reply': True,
                    'response_type': 'ooc_silent',
                    'performance_mode': performance_mode.value,
                    'ai_config': ai_config,
                    'resource_limited': is_limited,
                    'timestamp': datetime.utcnow().isoformat()
                }), 200
            store_ai_memory(
                campaign_id, 'conversation', message, ooc_text,
                {**context, 'ooc_moderation': True}
            )
            grant_assistant_reply(current_user_id, campaign_id, location_id, ooc_text)
            return jsonify({
                'response': ooc_text,
                'ooc_no_reply': False,
                'response_type': 'ooc_moderation',
                'performance_mode': performance_mode.value,
                'ai_config': ai_config,
                'resource_limited': is_limited,
                'timestamp': datetime.utcnow().isoformat()
            }), 200

        # In-character and other locations: full storyteller pipeline
        from services.reply_context import build_reply_context

        reply_context = build_reply_context(campaign_id, location_id, current_user_id, reply_to_id)
        # Generate AI response based on performance mode
        if performance_mode.value == 'slow':
            # Efficient mode - basic response
            response = generate_efficient_response(message, context, campaign_id, location_id, current_user_id,
                                                   reply_context=reply_context)
            response_type = 'efficient'
        elif performance_mode.value == 'medium':
            # Balanced mode - normal response
            response = generate_balanced_response(message, context, campaign_id, location_id, current_user_id,
                                                  reply_context=reply_context)
            response_type = 'balanced'
        else:
            # Fast mode - full response
            response = generate_full_response(message, context, campaign_id, location_id, current_user_id,
                                              reply_context=reply_context)
            response_type = 'full'

        roll_requests = []
        if response is not None and campaign_id:
            response, roll_requests = resolve_roll_tags(response, current_user_id, campaign_id)

        if response is None:
            # Every model failed: fixed text, no AI memory, no grant (not saveable as Storyteller).
            return jsonify({
                'error': AI_UNAVAILABLE_TEXT,
                'ai_unavailable': True,
                'ai_meta': _public_ai_meta(),
                'timestamp': datetime.utcnow().isoformat()
            }), 503
        
        # Store conversation in AI memory
        if campaign_id:
            store_ai_memory(campaign_id, 'conversation', message, response, context)
            # The browser saves this reply as an assistant message; allow exactly this text once.
            grant_assistant_reply(current_user_id, campaign_id, location_id, response)
        
        return jsonify({
            'response': response,
            'roll_requests': roll_requests,
            'response_type': response_type,
            'ai_meta': _public_ai_meta(),
            'performance_mode': performance_mode.value,
            'ai_config': ai_config,
            'resource_limited': is_limited,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error in AI chat: {e}")
        return jsonify({'error': 'AI chat failed'}), 500
    finally:
        if db is not None:
            db.close()


@bp.route('/slash', methods=['POST'])
@jwt_required()
def ai_slash_command():
    """
    Run a /ai command; any text it returns may then be saved once as an assistant message.
    private_markdown (/ai explain of a hidden roll) is never granted: it is for the requester only.
    """
    resp = _ai_slash_command_impl()
    response, status = resp if isinstance(resp, tuple) else (resp, 200)
    try:
        body = response.get_json(silent=True) or {}
        req = request.get_json(silent=True) or {}
        campaign_id = req.get('campaign_id')
        if campaign_id:
            user_id = int(get_jwt_identity())
            for key in ('display_markdown', 'llm_acknowledgment'):
                if body.get(key):
                    grant_assistant_reply(user_id, campaign_id, req.get('location_id'), body[key])
    except Exception as e:  # noqa: BLE001
        logger.error(f"Could not grant /ai slash reply: {e}")
    return response, status


def _ai_slash_command_impl():
    """
    Chat /ai … commands (diagnostics & tools). Examples: /ai health, /ai roll 4+3@7
    Does not require Chroma/LLM globally — each subcommand enforces what it needs.
    """
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json() or {}
        line = (data.get('line') or data.get('message') or '').strip()
        campaign_id = data.get('campaign_id')
        location_id = data.get('location_id')
        if not line:
            return jsonify({'error': 'line or message is required'}), 400
        try:
            # The message the /ai line replies to (the chat sends it with the line); /ai explain
            # explains that roll.
            reply_to_id = strict_int(data.get('reply_to_id'), 'reply_to_id', None, 1)
            campaign_id = strict_int(campaign_id, 'campaign_id', None, 1)
            location_id = strict_int(location_id, 'location_id', None, 1)
        except RequestValidationError as e:
            return jsonify({'error': e.public_message}), 400

        db_role = get_db()
        cur_role = db_role.cursor()
        cur_role.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        urow = cur_role.fetchone()
        cur_role.close()
        db_role.close()
        site_role = ((urow or {}).get("role") or "").strip().lower()

        parsed = parse_ai_slash_line(line)
        if not parsed:
            return jsonify({
                'error': 'Not a recognized /ai command (expected e.g. /ai health …)',
                'future_commands_suggestion': FUTURE_COMMAND_SUGGESTIONS,
                'supported_commands': SUPPORTED_AI_SLASH_VERBS,
            }), 400

        verb, payload = parsed
        RELAXED_AI_VERBS = frozenset({'clean', 'dice-diff'})
        needs_relaxed_auth = verb in RELAXED_AI_VERBS
        # /ai explain: every member of the chronicle (membership is checked below).
        for_members = verb in EXPLAIN_VERBS

        owner_ok = False
        if site_role != "admin" and campaign_id:
            db_o = get_db()
            co = db_o.cursor()
            try:
                co.execute(
                    """
                    SELECT created_by FROM campaigns
                    WHERE id = %s AND is_active = TRUE
                    """,
                    (campaign_id,),
                )
                orow = co.fetchone()
                if orow and int(orow['created_by']) == int(current_user_id):
                    owner_ok = True
            finally:
                co.close()
                db_o.close()

        if site_role != "admin":
            if needs_relaxed_auth and not owner_ok:
                return jsonify({
                    "error": "Only site administrators or the campaign owner may use this command.",
                    "display_markdown": (
                        "**Permission denied**\n\n"
                        "Only the **campaign owner** or a **site administrator** can use **`/ai clean`** or **`/ai dice-diff`**."
                    ),
                    "supported_commands": SUPPORTED_AI_SLASH_VERBS,
                    "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
                }), 403
            if not needs_relaxed_auth and not for_members and not (verb == 'help' and owner_ok):
                return jsonify({
                    "error": "Only site administrators may use /ai commands.",
                    "display_markdown": (
                        "**`/ai` is restricted**\n\n"
                        "Only **administrator** accounts can use most `/ai` commands. "
                        "**Campaign owners** may use **`/ai help`**, **`/ai clean …`**, and **`/ai dice-diff …`**. "
                        "For d10 rolls (classic or V5, per campaign), everyone can use **Roll dice** in the right sidebar.\n"
                    ),
                    "supported_commands": SUPPORTED_AI_SLASH_VERBS,
                    "future_commands_suggestion": FUTURE_COMMAND_SUGGESTIONS,
                }), 403

        if needs_relaxed_auth:
            if not campaign_id or location_id is None:
                return jsonify({
                    'error': 'campaign_id and location_id are required',
                    'display_markdown': (
                        f'**`/{verb}`**\n\n'
                        'Open a **campaign location** first so the server knows which room to affect.'
                    ),
                    'supported_commands': SUPPORTED_AI_SLASH_VERBS,
                    'future_commands_suggestion': FUTURE_COMMAND_SUGGESTIONS,
                }), 400
            db_r = get_db()
            cur_r = db_r.cursor()
            try:
                cur_r.execute(
                    """
                    SELECT created_by FROM campaigns
                    WHERE id = %s AND is_active = TRUE
                    """,
                    (campaign_id,),
                )
                crow = cur_r.fetchone()
                if not crow:
                    return jsonify({'error': 'Campaign not found'}), 404
                if site_role != "admin" and int(crow['created_by']) != int(current_user_id):
                    return jsonify({
                        'error': 'Only the campaign owner or a site admin can use this command.',
                        'display_markdown': (
                            '**Permission denied**\n\n'
                            'Only the **campaign owner** or a **site administrator** can use '
                            '**`/ai clean`** or **`/ai dice-diff`**.'
                        ),
                        'supported_commands': SUPPORTED_AI_SLASH_VERBS,
                        'future_commands_suggestion': FUTURE_COMMAND_SUGGESTIONS,
                    }), 403
                cur_r.execute(
                    """
                    SELECT id FROM locations
                    WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                    """,
                    (location_id, campaign_id),
                )
                if not cur_r.fetchone():
                    return jsonify({'error': 'Location not found in this campaign'}), 404
            finally:
                cur_r.close()
                db_r.close()
        elif for_members and (not campaign_id or location_id is None):
            return jsonify({
                'error': 'campaign_id and location_id are required for /ai explain',
                'display_markdown': (
                    '**`/ai explain`**\n\n'
                    'Use this inside a campaign room: reply to a dice card with `/ai explain`.'
                ),
                'supported_commands': SUPPORTED_AI_SLASH_VERBS,
                'future_commands_suggestion': FUTURE_COMMAND_SUGGESTIONS,
            }), 400
        elif verb == 'context' and (not campaign_id or location_id is None):
            return jsonify({
                'error': 'campaign_id and location_id are required for /ai context',
                'display_markdown': (
                    '**`/ai context`**\n\n'
                    'Use this from inside a campaign chat room so the server knows which location to inspect.'
                ),
                'supported_commands': SUPPORTED_AI_SLASH_VERBS,
                'future_commands_suggestion': FUTURE_COMMAND_SUGGESTIONS,
            }), 400

        if campaign_id and not needs_relaxed_auth:
            db = get_db()
            cursor = db.cursor()
            try:
                cursor.execute(
                    """
                    SELECT c.id FROM campaigns c
                    WHERE c.id = %s AND c.is_active = TRUE
                      AND (
                        c.created_by = %s
                        OR EXISTS (
                            SELECT 1 FROM campaign_players cp
                            WHERE cp.campaign_id = c.id AND cp.user_id = %s
                        )
                        OR EXISTS (
                            SELECT 1 FROM users u
                            WHERE u.id = %s AND LOWER(TRIM(COALESCE(u.role, ''))) = 'admin'
                        )
                      )
                    """,
                    (campaign_id, current_user_id, current_user_id, current_user_id),
                )
                if not cursor.fetchone():
                    return jsonify({'error': 'Campaign not found or access denied'}), 404
                if verb == 'context' or for_members:
                    cursor.execute("""
                        SELECT id FROM locations
                        WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                    """, (location_id, campaign_id))
                    if not cursor.fetchone():
                        return jsonify({'error': 'Location not found in this campaign'}), 404
            finally:
                cursor.close()
                db.close()

        try:
            result = execute_ai_slash_command(
                verb,
                payload,
                current_user_id,
                campaign_id=campaign_id,
                location_id=location_id,
                reply_to_id=reply_to_id,
            )
        except RequestValidationError as e:
            return jsonify({
                'error': e.public_message,
                'supported_commands': SUPPORTED_AI_SLASH_VERBS,
                'future_commands_suggestion': FUTURE_COMMAND_SUGGESTIONS,
            }), 400

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in /api/ai/slash: {e}")
        return jsonify({'error': 'Slash command failed'}), 500


@bp.route('/world-building', methods=['POST'])
@jwt_required()
@require_ai_services
def ai_world_building():
    """AI-assisted world building endpoint"""
    db = None
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Check if user can create world content
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT role FROM users WHERE id = %s", (current_user_id,))
        current_user = cursor.fetchone()
        
        if not current_user or current_user['role'] not in ['admin', 'helper']:
            return jsonify({'error': 'Admin or helper access required'}), 403
        
        world_type = data.get('type')  # 'location', 'npc', 'story', 'lore'
        description = data.get('description')
        campaign_id = data.get('campaign_id')
        
        if not all([world_type, description, campaign_id]):
            return jsonify({'error': 'Type, description, and campaign ID are required'}), 400
        
        # Get current performance mode
        performance_mode = gpu_monitor_service.get_performance_mode()
        
        # Generate world content based on performance mode
        if performance_mode.value == 'slow':
            world_content = generate_basic_world_content(world_type, description)
        elif performance_mode.value == 'medium':
            world_content = generate_balanced_world_content(world_type, description)
        else:
            world_content = generate_detailed_world_content(world_type, description)
        
        # Store in AI memory
        store_ai_memory(campaign_id, 'world_fact', description, world_content, {
            'type': world_type,
            'generated_by': current_user_id
        })
        
        return jsonify({
            'world_content': world_content,
            'type': world_type,
            'performance_mode': performance_mode.value,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error in AI world building: {e}")
        return jsonify({'error': 'AI world building failed'}), 500
    finally:
        if db is not None:
            db.close()

@bp.route('/memory/<int:campaign_id>', methods=['GET'])
@jwt_required()
def get_ai_memory(campaign_id):
    """Get AI memory for a specific campaign"""
    try:
        current_user_id = int(get_jwt_identity())
        
        db = get_db()
        cursor = db.cursor()
        
        # Verify campaign access
        cursor.execute("""
            SELECT c.*, u.role as user_role
            FROM campaigns c
            JOIN users u ON u.id = %s
            WHERE c.id = %s AND c.is_active = TRUE
        """, (current_user_id, campaign_id))
        
        campaign = cursor.fetchone()
        
        if not campaign:
            return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Get AI memory for campaign
        cursor.execute("""
            SELECT id, memory_type, content, context, created_at, accessed_at
            FROM ai_memory
            WHERE campaign_id = %s
            ORDER BY created_at DESC
            LIMIT 100
        """, (campaign_id,))
        
        memories = []
        for row in cursor.fetchall():
            memories.append({
                'id': row['id'],
                'type': row['memory_type'],
                'content': row['content'],
                'context': json.loads(row['context']) if row['context'] else {},
                'created_at': row['created_at'],
                'accessed_at': row['accessed_at']
            })
        
        return jsonify({
            'memories': memories,
            'total': len(memories),
            'campaign_id': campaign_id
        }), 200
        
    except Exception as e:
        logger.error("Error getting AI memory for campaign %s: %s", safe_log_value(campaign_id), safe_log_value(e))
        return jsonify({'error': 'Failed to retrieve AI memory'}), 500
    finally:
        if 'db' in locals():
            db.close()

# Helper functions for AI response generation

# Per performance mode: reply size/sampling, how much room history and long-term memory to
# fetch (the token budget may use less), and the opening instruction.
STORYTELLER_MODES = {
    'efficient': {
        'llm': {'max_tokens': 256, 'temperature': 0.6, 'top_p': 0.8},
        'history_rows': 10, 'semantic': 0, 'npc_history': False,
        'intro': 'You are the AI Storyteller of a tabletop RPG chronicle. Keep replies concise.',
        'outro': ('Respond as the Storyteller, addressing the player character by name and taking into '
                  'account their background, any NPCs present, the conversation history and the location. '
                  'Roleplay NPCs naturally.'),
    },
    'balanced': {
        'llm': {'max_tokens': 512, 'temperature': 0.7, 'top_p': 0.9},
        'history_rows': 16, 'semantic': 3, 'npc_history': False,
        'intro': ('You are the AI Storyteller of a tabletop RPG chronicle. Give detailed, immersive replies '
                  'of good quality.'),
        'outro': ('Respond as the Storyteller, addressing the player character by name and taking into '
                  'account their clan/class, background, any NPCs present, the conversation history, the '
                  "location and relevant past events. Be descriptive and true to the game system's lore. "
                  'Roleplay NPCs with distinct personalities and motivations.'),
    },
    'full': {
        'llm': {'max_tokens': 1024, 'temperature': 0.8, 'top_p': 0.95},
        'history_rows': 24, 'semantic': 5, 'npc_history': True,
        'intro': ('You are the AI Storyteller of a tabletop RPG chronicle. Give comprehensive, detailed, '
                  'immersive replies.'),
        'outro': ('Respond as the Storyteller, addressing the player character by name, considering their '
                  'clan/class, nature, demeanor and background. Take into account the NPCs present (their '
                  'personalities, motivations and recent actions), the conversation history, the location, '
                  'relevant past events and the campaign setting. Be descriptive, immersive and true to the '
                  "game system's lore and atmosphere. Give each NPC a distinct voice and agenda. React to the "
                  "player's actions and reference past events when relevant."),
    },
}
# Share of the prompt budget the RAG rule-book/memory sections (user turn) may take, and
# the long-term message memory (system prompt).
RAG_BUDGET_SHARE = 0.25
SEMANTIC_BUDGET_SHARE = 0.10


def _storyteller_reply(mode: str, message: str, campaign_id: int, location_id: int = None,
                       user_id: int = None, reply_context: str = '') -> Optional[str]:
    """
    One Storyteller reply; None when no model could answer.

    reply_context: the message the player replied to (services.reply_context), a fixed part
    of the prompt right before the closing instructions.

    The prompt is built to fit the model's context (services.storyteller_prompt): fixed parts
    first (instructions, campaign, character, location, NPCs), then the newest room history
    that fits, then long-term memory; the RAG sections in the user turn get their own share.
    The player's message is sent once, as the user turn.
    """
    from services import storyteller_prompt as sp
    from services.ai_roles import storyteller_context_tokens
    from services.rag_service import embed_query

    cfg = STORYTELLER_MODES[mode]
    try:
        llm_service = get_llm_service()
        budget = sp.prompt_budget(storyteller_context_tokens(), cfg['llm']['max_tokens'])
        rag_budget = int(budget * RAG_BUDGET_SHARE)

        campaign_context = get_campaign_context(campaign_id)
        fixed = [cfg['intro'], campaign_context]
        roll_rule = ''
        if user_id and campaign_id:
            char_data = get_character_context(user_id, campaign_id)
            if char_data['has_character']:
                fixed.append(char_data['formatted'])
                # Pools from the sheet, and roll tags instead of invented pools (services/dice_pools.py).
                fixed.append(dice_pools.prompt_block(char_data['row'], char_data['rules_edition']))
                roll_rule = dice_pools.roll_instruction(char_data['rules_edition'])
        history_rows = []
        if location_id:
            fixed.append(get_location_context(location_id, campaign_id)['formatted'])
            npc_data = get_location_npcs(location_id, campaign_id)
            if npc_data['count'] > 0:
                npc_lines = [npc_data['formatted']]
                if cfg['npc_history']:
                    for npc in npc_data['npcs'][:3]:
                        npc_hist = get_npc_history(npc['id'], limit=3)
                        if npc_hist['count'] > 0:
                            npc_lines.append(f"{npc['name']}'s {npc_hist['formatted']}")
                fixed.append("\n".join(npc_lines))
            history_rows = get_recent_messages(location_id, campaign_id, limit=cfg['history_rows'])['messages']
        if reply_context:
            fixed.append(reply_context)
        fixed.append(cfg['outro'])
        fixed.append(sp.IN_WORLD_RULE)
        if roll_rule:  # last, with the in-world rule: the roll tag is its one exception
            fixed[-1] += "\n" + roll_rule

        used = sum(sp.estimate_tokens(x) for x in fixed) + sp.estimate_tokens(message) + rag_budget
        # The message is embedded once; every vector search of this reply reuses it.
        query_embedding = embed_query(message)
        semantic_text = ''
        if location_id and cfg['semantic'] and query_embedding is not None:
            seen = {" ".join(str(r.get('content') or '').split()) for r in history_rows}
            seen.add(" ".join(message.split()))
            semantic_data = get_semantic_message_history(message, campaign_id, location_id,
                                                         limit=cfg['semantic'], exclude=seen,
                                                         query_embedding=query_embedding)
            if semantic_data['count'] > 0:
                semantic_text = sp.truncate_to_tokens(semantic_data['formatted'],
                                                      int(budget * SEMANTIC_BUDGET_SHARE))
                used += sp.estimate_tokens(semantic_text)
        history_text, n_hist = sp.format_history(
            history_rows, message, max(0, budget - used),
            time_label=lambda r: r.get('time_display') or '',
        )
        logger.info(
            "Storyteller prompt (%s): budget %s tokens, fixed+RAG %s, history %s rows",
            mode, budget, used, n_hist,
        )
        parts = fixed[:-1] + [x for x in (semantic_text, history_text) if x] + fixed[-1:]
        rules_edition, game_system = get_campaign_rules(campaign_id)
        llm_context = {
            'system_prompt': "\n\n".join(p for p in parts if p),
            'campaign_id': campaign_id,
            'rules_edition': rules_edition,
            'game_system': game_system,
            'query_embedding': query_embedding,
            # Only for the reply-language fallback (users.ui_language). Not 'user_id': that
            # would switch on LLMService.store_interaction, which was never on for chat.
            'player_user_id': user_id,
            'ai_role': 'storyteller',
            'rag_budget_tokens': rag_budget,
        }
        return llm_service.generate_response(message, llm_context, dict(cfg['llm']), raise_on_error=True)
    except Exception as e:
        logger.error(f"Error generating {mode} response: {e}")
        return None


def resolve_roll_tags(response: str, user_id: int, campaign_id: int):
    """
    The Storyteller's [[roll: …]] tags resolved against the requester's sheet: (text, requests).

    Runs before the assistant grant and AI memory, so the saved message is exactly the text
    returned. Without a character the tags become plain text (no chip). Never raises.
    """
    if not response or '[' not in response:
        return response, []
    try:
        char = get_character_context(user_id, campaign_id)
        if char.get('has_character'):
            return dice_pools.apply_roll_tags(response, char['row'], char['rules_edition'], char['id'])
        return dice_pools.apply_roll_tags(response, None, get_campaign_rules_edition(campaign_id))
    except Exception as e:  # noqa: BLE001 - a reply without chips beats no reply
        logger.error("Could not resolve roll tags: %s", e)
        return response, []


def generate_efficient_response(message: str, context: dict, campaign_id: int, location_id: int = None, user_id: int = None,
                             reply_context: str = '') -> Optional[str]:
    """Generate efficient (basic) AI response; None when no model could answer."""
    return _storyteller_reply('efficient', message, campaign_id, location_id, user_id, reply_context)


def generate_balanced_response(message: str, context: dict, campaign_id: int, location_id: int = None, user_id: int = None,
                             reply_context: str = '') -> Optional[str]:
    """Generate balanced AI response; None when no model could answer."""
    return _storyteller_reply('balanced', message, campaign_id, location_id, user_id, reply_context)


def generate_full_response(message: str, context: dict, campaign_id: int, location_id: int = None, user_id: int = None,
                             reply_context: str = '') -> Optional[str]:
    """Generate full AI response; None when no model could answer."""
    return _storyteller_reply('full', message, campaign_id, location_id, user_id, reply_context)


OOC_ROOM_NOTES = {
    'en': (
        "This looks like in-character play. The OOC room is for talking as players "
        "(rules, dice, scheduling, chat), so please take the scene to an in-character location."
    ),
    'el': (
        "Αυτό μοιάζει με παιχνίδι μέσα στον ρόλο. Το δωμάτιο OOC είναι για κουβέντα ως παίκτες "
        "(κανόνες, ζάρια, προγραμματισμός, συζήτηση), οπότε συνέχισε τη σκηνή σε μια τοποθεσία του παιχνιδιού."
    ),
}


def generate_ooc_room_response(
    message: str, campaign_id: int, location_id: int, user_id: int
):
    """
    OOC channel: return None when no AI reply is needed; otherwise a short moderator note.
    Uses services.classifier (Laya / Jev / LLM prompt) to decide whether the message is
    in-character; never narrates or continues the story. Fails silent.

    Staff (admin, helper, campaign owner) get no note, like the OOC monitor. The verdict is
    shared with the monitor's check of the same text in save_message (classify_cached).
    """
    from services.classifier import ClassifierUnavailable, classify_cached
    from services.language import resolve_reply_language
    from services.ooc_monitor import is_exempt_from_ooc_moderation, ooc_campaign_context

    try:
        db = get_db()
        try:
            cursor = db.cursor()
            cursor.execute(
                "SELECT u.role, c.created_by FROM users u, campaigns c WHERE u.id = %s AND c.id = %s",
                (user_id, campaign_id),
            )
            who = cursor.fetchone() or {}
        finally:
            db.close()
        owner = who.get('created_by') is not None and int(who['created_by']) == int(user_id)
        if is_exempt_from_ooc_moderation(who.get('role'), owner):
            return None
        campaign_ctx = ooc_campaign_context(campaign_id)
        if campaign_ctx is None:
            return None
        result = classify_cached(message, campaign_ctx)
    except ClassifierUnavailable as e:
        logger.error(f"OOC room moderation: no classifier available: {e}")
        return None
    except Exception as e:
        logger.error(f"Error in OOC room AI moderation: {e}")
        return None
    logger.info(
        "OOC room classify by %s: P(in character)=%s intent=%s%s",
        result['provider'], result['ooc_violation']['score'], result['intent']['label'],
        ' (cached)' if result.get('cached') else '',
    )
    if not result['ooc_violation']['label']:
        return None
    return OOC_ROOM_NOTES[resolve_reply_language(message, user_id)]


class AIContextManager:
    """Smart context manager that prioritizes and assembles context based on token limits"""
    
    def __init__(self, max_context_tokens: int = 4000):
        self.max_context_tokens = max_context_tokens
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def build_context(self, message: str, campaign_id: int, location_id: int = None, 
                      user_id: int = None, mode: str = 'balanced') -> dict:
        """
        Build optimized AI context based on mode and token limits
        
        Priority order:
        1. Campaign basics (ALWAYS include)
        2. Character info (ALWAYS include if available)
        3. Location info (HIGH priority)
        4. Active combat (CRITICAL if active)
        5. Recent messages (HIGH priority)
        6. NPCs present (MEDIUM priority)
        7. Semantic history (MEDIUM priority for balanced/full)
        8. Relationships (LOW priority)
        9. Connected locations (LOW priority)
        """
        context_parts = []
        token_budget = self.max_context_tokens
        
        # 1. Campaign context (CRITICAL - always include)
        campaign_ctx = get_campaign_context(campaign_id)
        campaign_tokens = self.estimate_tokens(campaign_ctx)
        if campaign_tokens < token_budget:
            context_parts.append(("campaign", campaign_ctx, campaign_tokens))
            token_budget -= campaign_tokens
        
        # 2. Character context (CRITICAL)
        character_ctx = ""
        if user_id:
            char_data = get_character_context(user_id, campaign_id)
            if char_data.get('has_character'):
                character_ctx = char_data['formatted']
                char_tokens = self.estimate_tokens(character_ctx)
                if char_tokens < token_budget:
                    context_parts.append(("character", character_ctx, char_tokens))
                    token_budget -= char_tokens
        
        # Early return if no location (shouldn't happen in normal gameplay)
        if not location_id:
            return self._format_context(context_parts)
        
        # 3. Location context (HIGH priority)
        loc_data = get_location_context(location_id, campaign_id)
        loc_ctx = loc_data['formatted']
        loc_tokens = self.estimate_tokens(loc_ctx)
        if loc_tokens < token_budget:
            context_parts.append(("location", loc_ctx, loc_tokens))
            token_budget -= loc_tokens
        
        # 4. Active combat (CRITICAL if present)
        combat_data = get_active_combat(location_id, campaign_id)
        if combat_data.get('has_combat'):
            combat_ctx = combat_data['formatted']
            combat_tokens = self.estimate_tokens(combat_ctx)
            if combat_tokens < token_budget:
                context_parts.append(("combat", combat_ctx, combat_tokens))
                token_budget -= combat_tokens
        
        # 5. Recent message history (HIGH priority)
        msg_limit = {'efficient': 5, 'balanced': 10, 'full': 15}.get(mode, 10)
        msg_data = get_recent_messages(location_id, campaign_id, limit=msg_limit)
        if msg_data['count'] > 0:
            msg_ctx = msg_data['formatted']
            msg_tokens = self.estimate_tokens(msg_ctx)
            if msg_tokens < token_budget:
                context_parts.append(("messages", msg_ctx, msg_tokens))
                token_budget -= msg_tokens
        
        # 6. NPCs at location (MEDIUM priority)
        npc_data = get_location_npcs(location_id, campaign_id)
        if npc_data['count'] > 0:
            npc_ctx = npc_data['formatted']
            npc_tokens = self.estimate_tokens(npc_ctx)
            if npc_tokens < token_budget:
                context_parts.append(("npcs", npc_ctx, npc_tokens))
                token_budget -= npc_tokens
        
        # 7. Semantic history (MEDIUM priority, skip for efficient mode)
        if mode in ['balanced', 'full'] and token_budget > 500:
            semantic_limit = 3 if mode == 'balanced' else 5
            semantic_data = get_semantic_message_history(message, campaign_id, location_id, limit=semantic_limit)
            if semantic_data['count'] > 0:
                semantic_ctx = semantic_data['formatted']
                semantic_tokens = self.estimate_tokens(semantic_ctx)
                if semantic_tokens < token_budget:
                    context_parts.append(("semantic", semantic_ctx, semantic_tokens))
                    token_budget -= semantic_tokens
        
        # 8. Relationships (LOW priority, only for full mode with budget)
        if mode == 'full' and token_budget > 300 and user_id:
            if character_ctx:  # Only if we have character info
                char_id = get_character_context(user_id, campaign_id).get('id')
                if char_id:
                    rel_data = get_entity_relationships('character', char_id, campaign_id, limit=3)
                    if rel_data['count'] > 0:
                        rel_ctx = rel_data['formatted']
                        rel_tokens = self.estimate_tokens(rel_ctx)
                        if rel_tokens < token_budget:
                            context_parts.append(("relationships", rel_ctx, rel_tokens))
                            token_budget -= rel_tokens
        
        # 9. Connected locations (LOW priority, only if budget allows)
        if token_budget > 200:
            conn_data = get_connected_locations(location_id)
            if conn_data['count'] > 0:
                conn_ctx = conn_data['formatted']
                conn_tokens = self.estimate_tokens(conn_ctx)
                if conn_tokens < token_budget:
                    context_parts.append(("connections", conn_ctx, conn_tokens))
                    token_budget -= conn_tokens
        
        return self._format_context(context_parts)
    
    def _format_context(self, context_parts: list) -> dict:
        """Format context parts into final context dictionary"""
        full_context = "\n\n".join([part[1] for part in context_parts])
        total_tokens = sum([part[2] for part in context_parts])
        
        return {
            'formatted': full_context,
            'token_estimate': total_tokens,
            'parts_included': [part[0] for part in context_parts]
        }

# Create a global context manager instance
_context_manager = None

def get_context_manager():
    """Get or create the global context manager"""
    global _context_manager
    if _context_manager is None:
        _context_manager = AIContextManager(max_context_tokens=4000)
    return _context_manager

def get_campaign_rules(campaign_id) -> Tuple[str, Optional[str]]:
    """(rules_edition, game_system) of a campaign; ('classic', None) when missing/unknown."""
    if not campaign_id:
        return DEFAULT_RULES_EDITION, None
    db = None
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT rules_edition, game_system FROM campaigns WHERE id = %s", (campaign_id,))
        row = cursor.fetchone()
        return edition_of(row), (row or {}).get('game_system')
    except Exception as e:
        logger.error("Error reading rules_edition for campaign %s: %s", safe_log_value(campaign_id), safe_log_value(e))
        return DEFAULT_RULES_EDITION, None
    finally:
        if db is not None:
            db.close()


def get_campaign_rules_edition(campaign_id) -> str:
    """rules_edition of a campaign ('classic' when missing/unknown)."""
    return get_campaign_rules(campaign_id)[0]


def get_campaign_context(campaign_id: int) -> str:
    """Get campaign context for AI responses"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get campaign details
        cursor.execute("""
            SELECT name, description, game_system, status, rules_edition
            FROM campaigns
            WHERE id = %s AND is_active = TRUE
        """, (campaign_id,))
        
        campaign = cursor.fetchone()
        if not campaign:
            return "No campaign context available"
        
        # No ai_memory here: it is campaign-wide (other rooms' scenes would leak into this
        # one) and repeats the room history the Storyteller prompt already has.
        edition = edition_of(campaign)
        context = f"Campaign: {campaign['name']} ({campaign['game_system']})\n"
        context += f"Rules edition: {rules_edition_label(edition)} [rules_edition={edition}]\n"
        context += f"Description: {campaign['description'] or 'No description'}\n"
        context += f"Status: {campaign['status'] or 'active'}\n"
        context += "\n" + storyteller_rules_brief(edition, campaign['game_system']) + "\n"

        return context
        
    except Exception as e:
        logger.error(f"Error getting campaign context: {e}")
        return "Error retrieving campaign context"
    finally:
        if 'db' in locals():
            db.close()

def get_location_context(location_id: int, campaign_id: int) -> dict:
    """Get location context for AI responses (only active locations)"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get location details - ONLY ACTIVE LOCATIONS
        cursor.execute("""
            SELECT id, name, type, description
            FROM locations
            WHERE id = %s AND campaign_id = %s AND is_active = TRUE
        """, (location_id, campaign_id))
        
        location = cursor.fetchone()
        if not location:
            return {
                'name': 'Unknown Location',
                'type': 'unknown',
                'description': 'No description available',
                'formatted': 'Location: Unknown'
            }
        
        formatted = f"Location: {location['name']} ({location['type']})"
        if location['description']:
            formatted += f"\nDescription: {location['description']}"
        
        logger.info(f"Retrieved location context for location {location_id}: {location['name']}")
        
        return {
            'id': location['id'],
            'name': location['name'],
            'type': location['type'],
            'description': location['description'] or '',
            'formatted': formatted
        }
        
    except Exception as e:
        logger.error(f"Error getting location context: {e}")
        return {
            'name': 'Error',
            'type': 'error',
            'description': 'Failed to load location',
            'formatted': 'Location: Error loading location data'
        }
    finally:
        if 'db' in locals():
            db.close()

def get_recent_messages(location_id: int, campaign_id: int, limit: int = 15) -> dict:
    """Get recent message history for AI context"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get recent messages from this location
        cursor.execute("""
            SELECT 
                m.content,
                m.role,
                m.created_at,
                u.username
            FROM messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.campaign_id = %s AND m.location_id = %s
              AND COALESCE(m.ai_message_kind, '') NOT LIKE 'dice_animation%%'
            ORDER BY m.created_at DESC
            LIMIT %s
        """, (campaign_id, location_id, limit))
        
        messages = cursor.fetchall()
        
        if not messages:
            return {
                'count': 0,
                'messages': [],
                'formatted': 'No previous conversation in this location.'
            }
        
        # Format conversation history (reverse to chronological order)
        history_lines = []
        out_messages = []
        for msg in reversed(messages):
            time_label = format_message_time(msg['created_at'])
            who = "Storyteller" if msg['role'] == 'assistant' else f"Player {msg['username']}"
            history_lines.append(f"[{time_label}] {who}: {msg['content']}")
            m = dict(msg)
            m['time_display'] = time_label
            out_messages.append(m)

        formatted = "Recent Conversation History:\n" + "\n".join(history_lines)

        logger.info(f"Retrieved {len(messages)} messages for location {location_id}")

        return {
            'count': len(messages),
            'messages': out_messages,
            'formatted': formatted
        }
        
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}")
        return {
            'count': 0,
            'messages': [],
            'formatted': 'Error loading conversation history.'
        }
    finally:
        if 'db' in locals():
            db.close()

# bge-m3 cosine relevance: same-language matches score ~0.73, Greek<->English ~0.57-0.67
# (measured 2026-10-04), so 0.7 dropped every cross-language memory.
SEMANTIC_MIN_RELEVANCE = 0.5


def get_semantic_message_history(query: str, campaign_id: int, location_id: int = None, limit: int = 5,
                                 exclude=None, query_embedding=None) -> dict:
    """Get semantically relevant messages from long-term memory (skipping texts in `exclude`;
    query_embedding: `query` already embedded)"""
    try:
        from services.rag_service import get_rag_service
        rag_service = get_rag_service()
        
        # Retrieve semantically relevant messages
        relevant_messages = rag_service.retrieve_relevant_messages(
            query=query,
            campaign_id=campaign_id,
            location_id=location_id,
            limit=limit + len(exclude or ()),
            min_relevance=SEMANTIC_MIN_RELEVANCE,
            query_embedding=query_embedding,
        )
        if exclude:
            relevant_messages = [m for m in relevant_messages
                                 if " ".join(str(m.get('content') or '').split()) not in exclude]
        relevant_messages = relevant_messages[:limit]
        
        if not relevant_messages:
            return {
                'count': 0,
                'messages': [],
                'formatted': ''
            }
        
        # Format relevant messages
        formatted_lines = ["Relevant earlier moments in this location:"]
        for msg in relevant_messages:
            content = " ".join(str(msg['content'] or '').split())
            if len(content) > 400:
                content = content[:400].rstrip() + " […]"
            metadata = msg['metadata'] or {}
            ts = metadata.get('timestamp')
            time_label = format_message_time(ts) if ts else 'earlier'
            if metadata.get('role') == 'assistant':
                who = 'Storyteller'
            else:
                who = metadata.get('character_name') or 'Player'
            formatted_lines.append(f"[{time_label}] {who}: {content}")
        
        formatted = "\n".join(formatted_lines)
        
        logger.info(f"Retrieved {len(relevant_messages)} semantically relevant messages")
        
        return {
            'count': len(relevant_messages),
            'messages': relevant_messages,
            'formatted': formatted
        }
        
    except Exception as e:
        logger.error(f"Error retrieving semantic message history: {e}")
        return {
            'count': 0,
            'messages': [],
            'formatted': ''
        }

def get_location_npcs(location_id: int, campaign_id: int) -> dict:
    """Get NPCs present at a location"""
    try:
        import json
        db = get_db()
        cursor = db.cursor()
        
        # Get active NPCs at this location
        cursor.execute("""
            SELECT 
                id,
                name,
                type,
                description,
                personality,
                faction,
                npc_data
            FROM npcs
            WHERE campaign_id = %s AND location_id = %s AND is_active = TRUE
            ORDER BY name
        """, (campaign_id, location_id))
        
        npcs = cursor.fetchall()
        
        if not npcs:
            return {
                'count': 0,
                'npcs': [],
                'formatted': 'No NPCs present at this location.'
            }
        
        # Format NPC info
        formatted_lines = [f"NPCs Present ({len(npcs)}):"]
        npc_list = []
        
        for npc in npcs:
            npc_dict = dict(npc)
            npc_list.append(npc_dict)
            
            npc_info = f"- {npc['name']}"
            if npc['type']:
                npc_info += f" ({npc['type']})"
            if npc['description']:
                desc = npc['description']
                if len(desc) > 100:
                    desc = desc[:100] + "..."
                npc_info += f": {desc}"
            formatted_lines.append(npc_info)
            
            # Add personality if available
            if npc['personality']:
                formatted_lines.append(f"  Personality: {npc['personality']}")
        
        formatted = "\n".join(formatted_lines)
        
        logger.info(f"Retrieved {len(npcs)} NPCs for location {location_id}")
        
        return {
            'count': len(npcs),
            'npcs': npc_list,
            'formatted': formatted
        }
        
    except Exception as e:
        logger.error(f"Error getting location NPCs: {e}")
        return {
            'count': 0,
            'npcs': [],
            'formatted': 'Error loading NPCs.'
        }
    finally:
        if 'db' in locals():
            db.close()

def get_npc_history(npc_id: int, limit: int = 5) -> dict:
    """Get recent NPC statements and actions"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get recent NPC messages
        cursor.execute("""
            SELECT 
                content,
                context,
                created_at
            FROM npc_messages
            WHERE npc_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (npc_id, limit))
        
        messages = cursor.fetchall()
        
        if not messages:
            return {
                'count': 0,
                'messages': [],
                'formatted': 'No recent NPC activity.'
            }
        
        # Format NPC history (reverse to chronological order)
        history_lines = []
        out_messages = []
        for msg in reversed(messages):
            time_label = format_message_time(msg['created_at'])
            line = f"[{time_label}] {msg['content']}"
            if msg['context']:
                line += f" ({msg['context']})"
            history_lines.append(line)
            m = dict(msg)
            m['time_display'] = time_label
            out_messages.append(m)

        formatted = "NPC Recent Activity:\n" + "\n".join(history_lines)

        return {
            'count': len(messages),
            'messages': out_messages,
            'formatted': formatted
        }
        
    except Exception as e:
        logger.error(f"Error getting NPC history: {e}")
        return {
            'count': 0,
            'messages': [],
            'formatted': 'Error loading NPC history.'
        }
    finally:
        if 'db' in locals():
            db.close()

def store_npc_interaction(npc_id: int, location_id: int, campaign_id: int, message: str, context: str = None) -> bool:
    """Store an NPC interaction/statement"""
    try:
        from datetime import datetime
        db = get_db()
        cursor = db.cursor()
        
        # Store NPC message
        cursor.execute("""
            INSERT INTO npc_messages (npc_id, location_id, campaign_id, content, context, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (npc_id, location_id, campaign_id, message, context, datetime.now()))
        
        # Update NPC's last_seen timestamp
        cursor.execute("""
            UPDATE npcs
            SET last_seen = %s
            WHERE id = %s
        """, (datetime.now(), npc_id))
        
        db.commit()
        logger.info(f"Stored NPC interaction for NPC {npc_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing NPC interaction: {e}")
        return False
    finally:
        if 'db' in locals():
            db.close()

def get_active_combat(location_id: int, campaign_id: int) -> dict:
    """Get active combat encounter at a location"""
    try:
        import json
        db = get_db()
        cursor = db.cursor()
        
        # Check for active combat
        cursor.execute("""
            SELECT id, round_number, initiative_order
            FROM combat_encounters
            WHERE campaign_id = %s AND location_id = %s AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        """, (campaign_id, location_id))
        
        encounter = cursor.fetchone()
        if not encounter:
            return {'has_combat': False, 'formatted': ''}
        
        # Get participants
        cursor.execute("""
            SELECT 
                cp.id, cp.initiative, cp.current_hp, cp.max_hp, cp.conditions,
                c.name as character_name, n.name as npc_name
            FROM combat_participants cp
            LEFT JOIN characters c ON cp.character_id = c.id
            LEFT JOIN npcs n ON cp.npc_id = n.id
            WHERE cp.encounter_id = %s
            ORDER BY cp.initiative DESC
        """, (encounter['id'],))
        
        participants = cursor.fetchall()
        
        # Format combat info
        formatted_lines = [f"⚔️ ACTIVE COMBAT - Round {encounter['round_number']}"]
        formatted_lines.append("Initiative Order:")
        for p in participants:
            name = p['character_name'] or p['npc_name'] or 'Unknown'
            hp_status = f"HP: {p['current_hp']}/{p['max_hp']}" if p['current_hp'] and p['max_hp'] else ""
            conditions = p['conditions'] or ""
            formatted_lines.append(f"  {p['initiative']}: {name} {hp_status} {conditions}")
        
        formatted = "\n".join(formatted_lines)
        
        return {
            'has_combat': True,
            'encounter_id': encounter['id'],
            'round': encounter['round_number'],
            'formatted': formatted
        }
        
    except Exception as e:
        logger.error(f"Error getting active combat: {e}")
        return {'has_combat': False, 'formatted': ''}
    finally:
        if 'db' in locals():
            db.close()

def get_entity_relationships(entity_type: str, entity_id: int, campaign_id: int, limit: int = 5) -> dict:
    """Get relationships for a character or NPC"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT 
                entity2_type, entity2_id, relationship_type, strength, notes
            FROM relationships
            WHERE campaign_id = %s AND entity1_type = %s AND entity1_id = %s
            ORDER BY ABS(strength) DESC
            LIMIT %s
        """, (campaign_id, entity_type, entity_id, limit))
        
        relationships = cursor.fetchall()
        
        if not relationships:
            return {'count': 0, 'formatted': ''}
        
        # Format relationships
        formatted_lines = []
        for rel in relationships:
            strength_emoji = "❤️" if rel['strength'] > 5 else "⚔️" if rel['strength'] < -5 else "🤝"
            formatted_lines.append(
                f"{strength_emoji} {rel['relationship_type']} (strength: {rel['strength']}): {rel['notes'] or 'No details'}"
            )
        
        formatted = "Relationships:\n" + "\n".join(formatted_lines)
        
        return {
            'count': len(relationships),
            'relationships': [dict(r) for r in relationships],
            'formatted': formatted
        }
        
    except Exception as e:
        logger.error(f"Error getting relationships: {e}")
        return {'count': 0, 'formatted': ''}
    finally:
        if 'db' in locals():
            db.close()

def get_connected_locations(location_id: int) -> dict:
    """Get locations connected to the current location (only active locations)"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT 
                l.id, l.name, l.type, lc.connection_type, lc.description
            FROM location_connections lc
            JOIN locations l ON (
                (lc.location1_id = %s AND lc.location2_id = l.id) OR
                (lc.location2_id = %s AND lc.location1_id = l.id AND lc.is_bidirectional = TRUE)
            )
            WHERE (lc.location1_id = %s OR (lc.location2_id = %s AND lc.is_bidirectional = TRUE))
            AND l.is_active = TRUE
        """, (location_id, location_id, location_id, location_id))
        
        connections = cursor.fetchall()
        
        if not connections:
            return {'count': 0, 'formatted': ''}
        
        # Format connections
        formatted_lines = ["Connected Areas:"]
        for conn in connections:
            conn_desc = f" ({conn['description']})" if conn['description'] else ""
            formatted_lines.append(f"  → {conn['name']} ({conn['type']}) via {conn['connection_type']}{conn_desc}")
        
        formatted = "\n".join(formatted_lines)
        
        return {
            'count': len(connections),
            'connections': [dict(c) for c in connections],
            'formatted': formatted
        }
        
    except Exception as e:
        logger.error(f"Error getting connected locations: {e}")
        return {'count': 0, 'formatted': ''}
    finally:
        if 'db' in locals():
            db.close()

def get_character_context(user_id: int, campaign_id: int) -> dict:
    """Get character context for AI responses"""
    try:
        import json
        from services.playing_character import effective_playing_character_id

        db = get_db()
        cursor = db.cursor()

        eid = effective_playing_character_id(cursor, user_id, campaign_id)
        if eid is None:
            return {
                'has_character': False,
                'formatted': 'No character found for this campaign.'
            }

        cursor.execute("""
            SELECT 
                c.id,
                c.name,
                c.system_type,
                c.attributes,
                c.skills,
                c.background,
                c.merits_flaws,
                c.wod_meta,
                c.rules_edition AS character_rules_edition,
                c.character_class,
                c.level,
                c.character_data,
                cam.game_system,
                cam.rules_edition
            FROM characters c
            JOIN campaigns cam ON c.campaign_id = cam.id
            WHERE c.id = %s AND c.user_id = %s AND c.campaign_id = %s
        """, (eid, user_id, campaign_id))
        
        character = cursor.fetchone()
        if not character:
            return {
                'has_character': False,
                'formatted': 'No character found for this campaign.'
            }

        # The campaign's edition is authoritative (characters copy it at creation).
        edition = edition_of(character)
        game_system = character['game_system'] or 'Unknown'
        formatted = format_character_for_prompt(dict(character), edition)

        character_data = {}
        if character.get('character_data'):
            try:
                character_data = json.loads(character['character_data'])
            except (TypeError, ValueError):
                character_data = {}

        logger.info(f"Retrieved character context for user {user_id}: {character['name']}")
        
        return {
            'has_character': True,
            'id': character['id'],
            'name': character['name'],
            'class': character.get('character_class'),
            'level': character.get('level'),
            'game_system': game_system,
            'rules_edition': edition,
            'data': character_data,
            'formatted': formatted,
            'row': dict(character),
        }
        
    except Exception as e:
        logger.error(f"Error getting character context: {e}")
        return {
            'has_character': False,
            'formatted': 'Error loading character data.'
        }
    finally:
        if 'db' in locals():
            db.close()

def generate_basic_world_content(world_type: str, description: str) -> str:
    """Generate basic world content"""
    try:
        llm_service = get_llm_service()
        
        prompt = f"Create a basic {world_type} for a tabletop RPG based on: {description}"
        
        llm_context = {
            'system_prompt': f'You are a creative assistant for tabletop RPGs. Create concise, basic {world_type} content optimized for resource conservation.',
        }
        
        llm_config = {
            'max_tokens': 256,
            'temperature': 0.6,
            'top_p': 0.8
        }
        
        return llm_service.generate_response(prompt, llm_context, llm_config)
        
    except Exception as e:
        logger.error(f"Error generating basic world content: {e}")
        return f"Basic {world_type.title()}: {description[:100]}... [Basic content for resource conservation]"

def generate_balanced_world_content(world_type: str, description: str) -> str:
    """Generate balanced world content"""
    try:
        llm_service = get_llm_service()
        
        prompt = f"Create a detailed {world_type} for a tabletop RPG based on: {description}"
        
        llm_context = {
            'system_prompt': f'You are a creative assistant for tabletop RPGs. Create balanced, detailed {world_type} content with good quality and reasonable performance.',
        }
        
        llm_config = {
            'max_tokens': 512,
            'temperature': 0.7,
            'top_p': 0.9
        }
        
        return llm_service.generate_response(prompt, llm_context, llm_config)
        
    except Exception as e:
        logger.error(f"Error generating balanced world content: {e}")
        return f"Balanced {world_type.title()}: {description[:200]}... [Balanced content with good detail]"

def generate_detailed_world_content(world_type: str, description: str) -> str:
    """Generate detailed world content"""
    try:
        llm_service = get_llm_service()
        
        prompt = f"Create a comprehensive, detailed {world_type} for a tabletop RPG based on: {description}"
        
        llm_context = {
            'system_prompt': f'You are a creative assistant for tabletop RPGs. Create comprehensive, detailed {world_type} content with maximum quality and depth.',
        }
        
        llm_config = {
            'max_tokens': 1024,
            'temperature': 0.8,
            'top_p': 0.95
        }
        
        return llm_service.generate_response(prompt, llm_context, llm_config)
        
    except Exception as e:
        logger.error(f"Error generating detailed world content: {e}")
        return f"Detailed {world_type.title()}: {description} [Full detail content with maximum quality]"

def store_ai_memory(campaign_id: int, memory_type: str, content: str, response: str, context: dict):
    """Store AI memory in database"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            INSERT INTO ai_memory (campaign_id, memory_type, content, context, created_at, accessed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            campaign_id,
            memory_type,
            f"{content}\n\nAI Response: {response}",
            json.dumps(context),
            datetime.utcnow(),
            datetime.utcnow()
        ))
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error storing AI memory: {e}")
    finally:
        if 'db' in locals():
            db.close()
