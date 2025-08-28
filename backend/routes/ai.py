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

logger = logging.getLogger(__name__)

bp = Blueprint('ai', __name__)

@bp.route('/status', methods=['GET'])
@jwt_required()
def get_ai_status():
    """Get AI service status and GPU monitoring information"""
    try:
        current_user_id = get_jwt_identity()
        
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
def ai_chat():
    """AI chat endpoint with performance-based response generation"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        message = data.get('message')
        campaign_id = data.get('campaign_id')
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
            response = generate_efficient_response(message, context, campaign_id)
            response_type = 'efficient'
        elif performance_mode.value == 'medium':
            # Balanced mode - normal response
            response = generate_balanced_response(message, context, campaign_id)
            response_type = 'balanced'
        else:
            # Fast mode - full response
            response = generate_full_response(message, context, campaign_id)
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
def ai_world_building():
    """AI-assisted world building endpoint"""
    try:
        current_user_id = get_jwt_identity()
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
        current_user_id = get_jwt_identity()
        
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
def generate_efficient_response(message: str, context: dict, campaign_id: int) -> str:
    """Generate efficient (basic) AI response"""
    return f"AI Response (Efficient Mode): {message[:100]}... [Response optimized for resource conservation]"

def generate_balanced_response(message: str, context: dict, campaign_id: int) -> str:
    """Generate balanced AI response"""
    return f"AI Response (Balanced Mode): {message[:200]}... [Response with balanced quality and performance]"

def generate_full_response(message: str, context: dict, campaign_id: int) -> str:
    """Generate full AI response"""
    return f"AI Response (Full Mode): {message} [Full quality response with maximum detail]"

def generate_basic_world_content(world_type: str, description: str) -> str:
    """Generate basic world content"""
    return f"Basic {world_type.title()}: {description[:100]}... [Basic content for resource conservation]"

def generate_balanced_world_content(world_type: str, description: str) -> str:
    """Generate balanced world content"""
    return f"Balanced {world_type.title()}: {description[:200]}... [Balanced content with good detail]"

def generate_detailed_world_content(world_type: str, description: str) -> str:
    """Generate detailed world content"""
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
