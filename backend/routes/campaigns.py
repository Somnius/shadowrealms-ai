#!/usr/bin/env python3
"""
ShadowRealms AI - Campaign Management API
RESTful API for campaign creation, management, and RAG integration
"""

import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.rag_service import create_rag_service
from services.embedding_service import create_embedding_service
from database import get_db

logger = logging.getLogger(__name__)

# Create blueprint
campaigns_bp = Blueprint('campaigns', __name__, url_prefix='/api/campaigns')

def get_rag_service():
    """Get RAG service instance"""
    config = current_app.config
    return create_rag_service(config)

def get_embedding_service():
    """Get embedding service instance"""
    config = current_app.config
    return create_embedding_service(config)

@campaigns_bp.route('/', methods=['POST'])
@jwt_required()
def create_campaign():
    """Create a new campaign"""
    try:
        user_id = get_jwt_identity()
        
        # Handle malformed JSON
        try:
            data = request.get_json()
        except Exception as e:
            return jsonify({'error': 'Invalid JSON format'}), 400
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'description', 'game_system']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Get database connection
        conn = get_db()
        cursor = conn.cursor()
        
        # Create campaign in database
        cursor.execute("""
            INSERT INTO campaigns (name, description, game_system, created_by, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data['name'],
            data['description'],
            data['game_system'],
            user_id,
            datetime.now().isoformat(),
            'active'
        ))
        
        campaign_id = cursor.lastrowid
        conn.commit()
        
        # Store campaign data in RAG system
        rag_service = get_rag_service()
        campaign_data = {
            'name': data['name'],
            'description': data['description'],
            'game_system': data['game_system'],
            'settings': data.get('settings', {}),
            'world_info': data.get('world_info', {}),
            'created_at': datetime.now().isoformat()
        }
        
        memory_id = rag_service.store_campaign_data(campaign_id, campaign_data)
        
        # Store initial world data if provided
        if 'world_info' in data:
            world_memory_id = rag_service.store_world_data(campaign_id, data['world_info'])
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'Campaign created successfully',
            'campaign_id': campaign_id,
            'memory_id': memory_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        return jsonify({'error': 'Failed to create campaign'}), 500

@campaigns_bp.route('/', methods=['GET'])
@jwt_required()
def get_campaigns():
    """Get all campaigns for the user"""
    try:
        user_id = get_jwt_identity()
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, game_system, created_at, status
            FROM campaigns
            WHERE created_by = ? OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = ?
            )
            ORDER BY created_at DESC
        """, (user_id, user_id))
        
        campaigns = []
        for row in cursor.fetchall():
            campaigns.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'game_system': row[3],
                'created_at': row[4],
                'status': row[5]
            })
        
        cursor.close()
        conn.close()
        
        return jsonify(campaigns), 200
        
    except Exception as e:
        logger.error(f"Error getting campaigns: {e}")
        return jsonify({'error': 'Failed to get campaigns'}), 500

@campaigns_bp.route('/<int:campaign_id>', methods=['GET', 'PUT'])
@jwt_required()
def get_or_update_campaign(campaign_id):
    """Get or update specific campaign details"""
    if request.method == 'PUT':
        return update_campaign(campaign_id)
    
    try:
        user_id = get_jwt_identity()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user has access to campaign
        cursor.execute("""
            SELECT id, name, description, game_system, created_by, created_at, status
            FROM campaigns
            WHERE id = ? AND (created_by = ? OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = ?
            ))
        """, (campaign_id, user_id, user_id))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Campaign not found'}), 404
        
        campaign = {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'game_system': row[3],
            'created_by': row[4],
            'created_at': row[5],
            'status': row[6]
        }
        
        # Get campaign context from RAG
        rag_service = get_rag_service()
        context = rag_service.get_campaign_context(campaign_id)
        
        campaign['context'] = context
        
        cursor.close()
        conn.close()
        
        return jsonify(campaign), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign: {e}")
        return jsonify({'error': 'Failed to get campaign'}), 500

def update_campaign(campaign_id):
    """Update campaign details (admin only)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if user is admin or campaign creator
        cursor.execute("""
            SELECT created_by FROM campaigns WHERE id = ?
        """, (campaign_id,))
        
        row = cursor.fetchone()
        if not row:
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Check if user is creator
        cursor.execute("""
            SELECT role FROM users WHERE id = ?
        """, (user_id,))
        user_row = cursor.fetchone()
        
        if row[0] != user_id and (not user_row or user_row[0] != 'admin'):
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Update campaign fields if provided
        updates = []
        params = []
        
        if 'name' in data:
            updates.append('name = ?')
            params.append(data['name'])
        
        if 'description' in data:
            updates.append('description = ?')
            params.append(data['description'])
        
        if updates:
            params.append(campaign_id)
            query = f"UPDATE campaigns SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
        
        return jsonify({'message': 'Campaign updated successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error updating campaign: {e}")
        return jsonify({'error': 'Failed to update campaign'}), 500

@campaigns_bp.route('/<int:campaign_id>/world', methods=['POST'])
@jwt_required()
def update_world_data(campaign_id):
    """Update world-building data for campaign"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Verify user has access to campaign
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = ? AND (created_by = ? OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = ?
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Store world data in RAG
        rag_service = get_rag_service()
        memory_id = rag_service.store_world_data(campaign_id, data)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'World data updated successfully',
            'memory_id': memory_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating world data: {e}")
        return jsonify({'error': 'Failed to update world data'}), 500

@campaigns_bp.route('/<int:campaign_id>/search', methods=['POST'])
@jwt_required()
def search_campaign_memory(campaign_id):
    """Search campaign memory using RAG"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        query = data.get('query', '')
        memory_type = data.get('memory_type', 'all')
        limit = data.get('limit', 5)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Verify user has access to campaign
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = ? AND (created_by = ? OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = ?
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Search using RAG
        rag_service = get_rag_service()
        
        if memory_type == 'all':
            # Search all memory types
            results = {}
            for mem_type in ['campaigns', 'characters', 'world', 'sessions', 'rules']:
                memories = rag_service.retrieve_memories(query, mem_type, campaign_id, limit)
                if memories:
                    results[mem_type] = memories
        else:
            # Search specific memory type
            memories = rag_service.retrieve_memories(query, memory_type, campaign_id, limit)
            results = {memory_type: memories}
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'query': query,
            'results': results,
            'total_results': sum(len(memories) for memories in results.values())
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching campaign memory: {e}")
        return jsonify({'error': 'Failed to search campaign memory'}), 500

@campaigns_bp.route('/<int:campaign_id>/context', methods=['POST'])
@jwt_required()
def get_campaign_context(campaign_id):
    """Get campaign context for AI generation"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        query = data.get('query', '')
        
        # Verify user has access to campaign
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = ? AND (created_by = ? OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = ?
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Get context from RAG
        rag_service = get_rag_service()
        context = rag_service.get_campaign_context(campaign_id, query)
        
        # Augment prompt if provided
        if query:
            augmented_prompt = rag_service.augment_prompt(query, campaign_id, user_id)
            context['augmented_prompt'] = augmented_prompt
        
        cursor.close()
        conn.close()
        
        return jsonify({'context': context}), 200
        
    except Exception as e:
        logger.error(f"Error getting campaign context: {e}")
        return jsonify({'error': 'Failed to get campaign context'}), 500

@campaigns_bp.route('/<int:campaign_id>/interaction', methods=['POST'])
@jwt_required()
def store_interaction(campaign_id):
    """Store AI interaction for campaign"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        prompt = data.get('prompt', '')
        response = data.get('response', '')
        interaction_type = data.get('interaction_type', 'general')
        
        if not prompt or not response:
            return jsonify({'error': 'Prompt and response are required'}), 400
        
        # Verify user has access to campaign
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM campaigns
            WHERE id = ? AND (created_by = ? OR id IN (
                SELECT campaign_id FROM campaign_players WHERE user_id = ?
            ))
        """, (campaign_id, user_id, user_id))
        
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'error': 'Campaign not found'}), 404
        
        # Store interaction in RAG
        rag_service = get_rag_service()
        memory_id = rag_service.store_interaction(prompt, response, campaign_id, user_id, interaction_type)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'message': 'Interaction stored successfully',
            'memory_id': memory_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error storing interaction: {e}")
        return jsonify({'error': 'Failed to store interaction'}), 500