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

from database import get_db
from services.gpu_monitor import gpu_monitor_service
from services.llm_service import get_llm_service
from services.health_check import get_health_check_service, require_llm, require_ai_services

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
            'error': str(e),
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
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
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
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
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
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
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
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        message = data.get('message')
        campaign_id = data.get('campaign_id')
        location_id = data.get('location')  # Get location from request
        context = data.get('context', {})
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        db = get_db()
        cursor = db.cursor()
        
        # Verify campaign access
        if campaign_id:
            cursor.execute("""
                SELECT c.*, u.role as user_role
                FROM campaigns c
                JOIN users u ON u.id = ?
                WHERE c.id = ? AND c.is_active = 1
            """, (current_user_id, campaign_id))
            
            campaign = cursor.fetchone()
            
            if not campaign:
                return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Get current performance mode
        performance_mode = gpu_monitor_service.get_performance_mode()
        ai_config = gpu_monitor_service.get_ai_response_config()
        
        # Check if resources are limited
        is_limited = gpu_monitor_service.is_resource_limited()
        
        # Generate AI response based on performance mode
        if performance_mode.value == 'slow':
            # Efficient mode - basic response
            response = generate_efficient_response(message, context, campaign_id, location_id, current_user_id)
            response_type = 'efficient'
        elif performance_mode.value == 'medium':
            # Balanced mode - normal response
            response = generate_balanced_response(message, context, campaign_id, location_id, current_user_id)
            response_type = 'balanced'
        else:
            # Fast mode - full response
            response = generate_full_response(message, context, campaign_id, location_id, current_user_id)
            response_type = 'full'
        
        # Store conversation in AI memory
        if campaign_id:
            store_ai_memory(campaign_id, 'conversation', message, response, context)
        
        return jsonify({
            'response': response,
            'response_type': response_type,
            'performance_mode': performance_mode.value,
            'ai_config': ai_config,
            'resource_limited': is_limited,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error in AI chat: {e}")
        return jsonify({'error': 'AI chat failed'}), 500
    finally:
        if 'db' in locals():
            db.close()

@bp.route('/world-building', methods=['POST'])
@jwt_required()
@require_ai_services
def ai_world_building():
    """AI-assisted world building endpoint"""
    try:
        current_user_id = int(get_jwt_identity())
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Check if user can create world content
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("SELECT role FROM users WHERE id = ?", (current_user_id,))
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
        if 'db' in locals():
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
            JOIN users u ON u.id = ?
            WHERE c.id = ? AND c.is_active = 1
        """, (current_user_id, campaign_id))
        
        campaign = cursor.fetchone()
        
        if not campaign:
            return jsonify({'error': 'Campaign not found or access denied'}), 404
        
        # Get AI memory for campaign
        cursor.execute("""
            SELECT id, memory_type, content, context, created_at, accessed_at
            FROM ai_memory
            WHERE campaign_id = ?
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
        logger.error(f"Error getting AI memory for campaign {campaign_id}: {e}")
        return jsonify({'error': 'Failed to retrieve AI memory'}), 500
    finally:
        if 'db' in locals():
            db.close()

# Helper functions for AI response generation
def generate_efficient_response(message: str, context: dict, campaign_id: int, location_id: int = None, user_id: int = None) -> str:
    """Generate efficient (basic) AI response"""
    try:
        llm_service = get_llm_service()
        
        # Get campaign context for better responses
        campaign_context = get_campaign_context(campaign_id)
        
        # Get character context if provided
        character_context = ""
        if user_id and campaign_id:
            char_data = get_character_context(user_id, campaign_id)
            if char_data['has_character']:
                character_context = f"\n\n{char_data['formatted']}"
        
        # Get location context if provided
        location_context = ""
        npc_context = ""
        message_history = ""
        if location_id:
            loc_data = get_location_context(location_id, campaign_id)
            location_context = f"\n\n{loc_data['formatted']}"
            
            # Get NPCs at location
            npc_data = get_location_npcs(location_id, campaign_id)
            if npc_data['count'] > 0:
                npc_context = f"\n\n{npc_data['formatted']}"
            
            # Get recent messages (limited for efficient mode)
            msg_data = get_recent_messages(location_id, campaign_id, limit=5)
            if msg_data['count'] > 0:
                message_history = f"\n\n{msg_data['formatted']}"
        
        # Prepare context for LLM
        llm_context = {
            'system_prompt': f'''You are a helpful AI assistant for tabletop RPGs. Provide concise, helpful responses optimized for resource conservation.

{campaign_context}{character_context}{location_context}{npc_context}{message_history}

Current player message: {message}

Respond naturally as the AI storyteller, addressing the player character by name and taking into account their background, any NPCs present, the conversation history, and location context. If NPCs are present, roleplay them naturally in your responses.''',
            'campaign_context': campaign_context
        }
        
        # Configure for efficient mode
        llm_config = {
            'max_tokens': 256,
            'temperature': 0.6,
            'top_p': 0.8
        }
        
        return llm_service.generate_response(message, llm_context, llm_config)
        
    except Exception as e:
        logger.error(f"Error generating efficient response: {e}")
        return f"AI Response (Efficient Mode): {message[:100]}... [Response optimized for resource conservation]"

def generate_balanced_response(message: str, context: dict, campaign_id: int, location_id: int = None, user_id: int = None) -> str:
    """Generate balanced AI response"""
    try:
        llm_service = get_llm_service()
        
        # Get campaign context for better responses
        campaign_context = get_campaign_context(campaign_id)
        
        # Get character context if provided
        character_context = ""
        if user_id and campaign_id:
            char_data = get_character_context(user_id, campaign_id)
            if char_data['has_character']:
                character_context = f"\n\n{char_data['formatted']}"
        
        # Get location context if provided
        location_context = ""
        npc_context = ""
        message_history = ""
        semantic_context = ""
        if location_id:
            loc_data = get_location_context(location_id, campaign_id)
            location_context = f"\n\n{loc_data['formatted']}"
            
            # Get NPCs at location
            npc_data = get_location_npcs(location_id, campaign_id)
            if npc_data['count'] > 0:
                npc_context = f"\n\n{npc_data['formatted']}"
            
            # Get recent messages (moderate limit for balanced mode)
            msg_data = get_recent_messages(location_id, campaign_id, limit=10)
            if msg_data['count'] > 0:
                message_history = f"\n\n{msg_data['formatted']}"
            
            # Get semantically relevant past messages
            semantic_data = get_semantic_message_history(message, campaign_id, location_id, limit=3)
            if semantic_data['count'] > 0:
                semantic_context = f"\n\n{semantic_data['formatted']}"
        
        # Prepare context for LLM
        llm_context = {
            'system_prompt': f'''You are an AI storyteller for tabletop RPGs. Provide balanced, detailed, immersive responses with good quality and reasonable performance.

{campaign_context}{character_context}{location_context}{npc_context}{message_history}{semantic_context}

Current player message: {message}

Respond as the AI storyteller, addressing the player character by name and taking into account their clan/class, background, any NPCs present, the conversation history, location context, and relevant past events. Be descriptive and true to the game system's lore. Roleplay NPCs with distinct personalities and motivations.''',
            'campaign_context': campaign_context
        }
        
        # Configure for balanced mode
        llm_config = {
            'max_tokens': 512,
            'temperature': 0.7,
            'top_p': 0.9
        }
        
        return llm_service.generate_response(message, llm_context, llm_config)
        
    except Exception as e:
        logger.error(f"Error generating balanced response: {e}")
        return f"AI Response (Balanced Mode): {message[:200]}... [Response with balanced quality and performance]"

def generate_full_response(message: str, context: dict, campaign_id: int, location_id: int = None, user_id: int = None) -> str:
    """Generate full AI response"""
    try:
        llm_service = get_llm_service()
        
        # Get campaign context for better responses
        campaign_context = get_campaign_context(campaign_id)
        
        # Get character context if provided
        character_context = ""
        if user_id and campaign_id:
            char_data = get_character_context(user_id, campaign_id)
            if char_data['has_character']:
                character_context = f"\n\n{char_data['formatted']}"
        
        # Get location context if provided
        location_context = ""
        npc_context = ""
        message_history = ""
        semantic_context = ""
        if location_id:
            loc_data = get_location_context(location_id, campaign_id)
            location_context = f"\n\n{loc_data['formatted']}"
            
            # Get NPCs at location with their histories
            npc_data = get_location_npcs(location_id, campaign_id)
            if npc_data['count'] > 0:
                npc_context_lines = [npc_data['formatted']]
                # For full mode, also include recent NPC activity
                for npc in npc_data['npcs'][:3]:  # Top 3 most relevant NPCs
                    npc_hist = get_npc_history(npc['id'], limit=3)
                    if npc_hist['count'] > 0:
                        npc_context_lines.append(f"\n{npc['name']}'s {npc_hist['formatted']}")
                npc_context = "\n\n" + "\n".join(npc_context_lines)
            
            # Get recent messages (full limit for maximum context)
            msg_data = get_recent_messages(location_id, campaign_id, limit=15)
            if msg_data['count'] > 0:
                message_history = f"\n\n{msg_data['formatted']}"
            
            # Get semantically relevant past messages (full mode gets more)
            semantic_data = get_semantic_message_history(message, campaign_id, location_id, limit=5)
            if semantic_data['count'] > 0:
                semantic_context = f"\n\n{semantic_data['formatted']}"
        
        # Prepare context for LLM
        llm_context = {
            'system_prompt': f'''You are an AI storyteller for tabletop RPGs. Provide comprehensive, detailed, immersive responses with maximum quality and depth.

{campaign_context}{character_context}{location_context}{npc_context}{message_history}{semantic_context}

Current player message: {message}

Respond as the AI storyteller, addressing the player character by name, considering their clan/class, nature, demeanor, and background. Take into account NPCs present (their personalities, motivations, and recent actions), the entire conversation history, location context, relevant past events from days/weeks ago, and campaign setting. Be descriptive, immersive, and true to the game system's lore and atmosphere. Roleplay each NPC with a distinct voice, personality, and agenda. React dynamically to the player's actions. Reference past events naturally when relevant.''',
            'campaign_context': campaign_context
        }
        
        # Configure for full mode
        llm_config = {
            'max_tokens': 1024,
            'temperature': 0.8,
            'top_p': 0.95
        }
        
        return llm_service.generate_response(message, llm_context, llm_config)
        
    except Exception as e:
        logger.error(f"Error generating full response: {e}")
        return f"AI Response (Full Mode): {message} [Full quality response with maximum detail]"

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

def get_campaign_context(campaign_id: int) -> str:
    """Get campaign context for AI responses"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get campaign details
        cursor.execute("""
            SELECT name, description, game_system, status
            FROM campaigns
            WHERE id = ? AND is_active = 1
        """, (campaign_id,))
        
        campaign = cursor.fetchone()
        if not campaign:
            return "No campaign context available"
        
        # Get recent AI memory for context
        cursor.execute("""
            SELECT content, memory_type, created_at
            FROM ai_memory
            WHERE campaign_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        """, (campaign_id,))
        
        memories = cursor.fetchall()
        
        context = f"Campaign: {campaign['name']} ({campaign['game_system']})\n"
        context += f"Description: {campaign['description'] or 'No description'}\n"
        context += f"Status: {campaign['status'] or 'active'}\n"
        
        if memories:
            context += "\nRecent Context:\n"
            for memory in memories:
                context += f"- {memory['memory_type']}: {memory['content'][:100]}...\n"
        
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
            WHERE id = ? AND campaign_id = ? AND is_active = 1
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
            WHERE m.campaign_id = ? AND m.location_id = ?
            ORDER BY m.created_at DESC
            LIMIT ?
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
        for msg in reversed(messages):
            # Format timestamp
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(msg['created_at'])
                time_ago = format_time_ago(timestamp)
            except:
                time_ago = 'recently'
            
            role_label = "User" if msg['role'] == 'user' else "AI"
            history_lines.append(f"[{time_ago}] {role_label} ({msg['username']}): {msg['content']}")
        
        formatted = "Recent Conversation History:\n" + "\n".join(history_lines)
        
        logger.info(f"Retrieved {len(messages)} messages for location {location_id}")
        
        return {
            'count': len(messages),
            'messages': [dict(msg) for msg in messages],
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

def format_time_ago(timestamp) -> str:
    """Format timestamp as relative time"""
    try:
        from datetime import datetime
        now = datetime.now()
        diff = now - timestamp
        
        if diff.seconds < 60:
            return "just now"
        elif diff.seconds < 3600:
            mins = diff.seconds // 60
            return f"{mins} min ago"
        elif diff.seconds < 86400:
            hours = diff.seconds // 3600
            return f"{hours} hr ago"
        elif diff.days == 1:
            return "yesterday"
        elif diff.days < 7:
            return f"{diff.days} days ago"
        else:
            return timestamp.strftime("%b %d")
    except:
        return "recently"

def get_semantic_message_history(query: str, campaign_id: int, location_id: int = None, limit: int = 5) -> dict:
    """Get semantically relevant messages from long-term memory"""
    try:
        from services.rag_service import get_rag_service
        rag_service = get_rag_service()
        
        # Retrieve semantically relevant messages
        relevant_messages = rag_service.retrieve_relevant_messages(
            query=query,
            campaign_id=campaign_id,
            location_id=location_id,
            limit=limit,
            min_relevance=0.7
        )
        
        if not relevant_messages:
            return {
                'count': 0,
                'messages': [],
                'formatted': ''
            }
        
        # Format relevant messages
        formatted_lines = ["Relevant Past Context:"]
        for msg in relevant_messages:
            content = msg['content']
            metadata = msg['metadata']
            relevance = msg['relevance']
            
            # Get timestamp
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(metadata.get('timestamp', ''))
                time_ago = format_time_ago(timestamp)
            except:
                time_ago = 'some time ago'
            
            # Format the message
            character = metadata.get('character_name', 'Unknown')
            role = metadata.get('role', 'user')
            formatted_lines.append(f"[{time_ago}] {character} ({role}): {content}")
        
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
            WHERE campaign_id = ? AND location_id = ? AND is_active = 1
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
            WHERE npc_id = ?
            ORDER BY created_at DESC
            LIMIT ?
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
        for msg in reversed(messages):
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(msg['created_at'])
                time_ago = format_time_ago(timestamp)
            except:
                time_ago = 'recently'
            
            line = f"[{time_ago}] {msg['content']}"
            if msg['context']:
                line += f" ({msg['context']})"
            history_lines.append(line)
        
        formatted = "NPC Recent Activity:\n" + "\n".join(history_lines)
        
        return {
            'count': len(messages),
            'messages': [dict(msg) for msg in messages],
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
            VALUES (?, ?, ?, ?, ?, ?)
        """, (npc_id, location_id, campaign_id, message, context, datetime.now()))
        
        # Update NPC's last_seen timestamp
        cursor.execute("""
            UPDATE npcs
            SET last_seen = ?
            WHERE id = ?
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
            WHERE campaign_id = ? AND location_id = ? AND status = 'active'
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
            WHERE cp.encounter_id = ?
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
            WHERE campaign_id = ? AND entity1_type = ? AND entity1_id = ?
            ORDER BY ABS(strength) DESC
            LIMIT ?
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
                (lc.location1_id = ? AND lc.location2_id = l.id) OR
                (lc.location2_id = ? AND lc.location1_id = l.id AND lc.is_bidirectional = 1)
            )
            WHERE (lc.location1_id = ? OR (lc.location2_id = ? AND lc.is_bidirectional = 1))
            AND l.is_active = 1
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
        db = get_db()
        cursor = db.cursor()
        
        # Get character for this user in this campaign
        cursor.execute("""
            SELECT 
                c.id,
                c.name,
                c.character_class,
                c.level,
                c.character_data,
                cam.game_system
            FROM characters c
            JOIN campaigns cam ON c.campaign_id = cam.id
            WHERE c.user_id = ? AND c.campaign_id = ?
            LIMIT 1
        """, (user_id, campaign_id))
        
        character = cursor.fetchone()
        if not character:
            return {
                'has_character': False,
                'formatted': 'No character found for this campaign.'
            }
        
        # Parse character_data JSON if available
        character_data = {}
        if character['character_data']:
            try:
                character_data = json.loads(character['character_data'])
            except:
                pass
        
        # Build formatted character info
        formatted_lines = [f"Character: {character['name']}"]
        
        if character['character_class']:
            formatted_lines.append(f"Class/Clan: {character['character_class']}")
        
        if character['level']:
            formatted_lines.append(f"Level/Generation: {character['level']}")
        
        # Add game system specific info
        game_system = character['game_system'] or 'Unknown'
        formatted_lines.append(f"Game System: {game_system}")
        
        # Extract key character data fields
        if character_data:
            # Common fields across systems
            if 'clan' in character_data:
                formatted_lines.append(f"Clan: {character_data['clan']}")
            if 'generation' in character_data:
                formatted_lines.append(f"Generation: {character_data['generation']}")
            if 'background' in character_data:
                background = character_data['background']
                if len(background) > 200:
                    background = background[:200] + "..."
                formatted_lines.append(f"Background: {background}")
            if 'nature' in character_data:
                formatted_lines.append(f"Nature: {character_data['nature']}")
            if 'demeanor' in character_data:
                formatted_lines.append(f"Demeanor: {character_data['demeanor']}")
            
            # Attributes
            if 'attributes' in character_data:
                attrs = character_data['attributes']
                if isinstance(attrs, dict):
                    attr_summary = ", ".join([f"{k}: {v}" for k, v in list(attrs.items())[:5]])
                    formatted_lines.append(f"Key Attributes: {attr_summary}")
            
            # Current status
            if 'blood_pool' in character_data:
                formatted_lines.append(f"Blood Pool: {character_data.get('blood_pool', 0)}")
            if 'willpower' in character_data:
                formatted_lines.append(f"Willpower: {character_data.get('willpower', 0)}")
            if 'health' in character_data:
                formatted_lines.append(f"Health: {character_data.get('health', 'Normal')}")
        
        formatted = "\n".join(formatted_lines)
        
        logger.info(f"Retrieved character context for user {user_id}: {character['name']}")
        
        return {
            'has_character': True,
            'id': character['id'],
            'name': character['name'],
            'class': character['character_class'],
            'level': character['level'],
            'game_system': game_system,
            'data': character_data,
            'formatted': formatted
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
            VALUES (?, ?, ?, ?, ?, ?)
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
