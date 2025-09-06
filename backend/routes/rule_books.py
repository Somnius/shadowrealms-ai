#!/usr/bin/env python3
"""
Rule Books API Routes
Handles rule book processing, storage, and retrieval for enhanced AI knowledge.
"""

import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Create blueprint
bp = Blueprint('rule_books', __name__)

@bp.route('/scan', methods=['GET'])
@jwt_required()
def scan_rule_books():
    """Scan for available rule books in the books directory"""
    try:
        from services.rule_book_service import RuleBookProcessor
        
        config = current_app.config
        processor = RuleBookProcessor(config)
        
        # Find all available rule books
        found_books = processor.find_rule_books()
        
        # Format response
        books_info = []
        for book in found_books:
            books_info.append({
                'book_id': book['book_id'],
                'name': book['book_info']['name'],
                'system': book['book_info']['system'],
                'file_path': str(book['file_path']),
                'file_size': book['file_size'],
                'file_size_mb': round(book['file_size'] / (1024 * 1024), 2),
                'priority': book['book_info']['priority']
            })
        
        return jsonify({
            'success': True,
            'books_found': len(books_info),
            'books': books_info
        }), 200
        
    except Exception as e:
        logger.error(f"Error scanning rule books: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/process', methods=['POST'])
@jwt_required()
def process_rule_book():
    """Process a specific rule book for RAG integration"""
    try:
        data = request.get_json()
        book_id = data.get('book_id')
        
        if not book_id:
            return jsonify({
                'success': False,
                'error': 'book_id is required'
            }), 400
        
        from services.rule_book_service import RuleBookRAGService
        from services.rag_service import create_rag_service
        from services.embedding_service import create_embedding_service
        
        # Initialize services
        config = current_app.config
        rag_service = create_rag_service(config)
        embedding_service = create_embedding_service(config)
        rule_book_service = RuleBookRAGService(config, rag_service, embedding_service)
        
        # Find the book file
        processor = rule_book_service.processor
        found_books = processor.find_rule_books()
        
        book_file = None
        for book in found_books:
            if book['book_id'] == book_id:
                book_file = book['file_path']
                break
        
        if not book_file:
            return jsonify({
                'success': False,
                'error': f'Book {book_id} not found'
            }), 404
        
        # Process and store the book
        success = rule_book_service.process_and_store_rule_book(book_id, book_file)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Successfully processed and stored {book_id}',
                'book_id': book_id
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to process {book_id}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error processing rule book: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/search', methods=['POST'])
@jwt_required()
def search_rule_books():
    """Search through processed rule books"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        system = data.get('system')  # Optional filter by system
        limit = data.get('limit', 10)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'query is required'
            }), 400
        
        from services.rule_book_service import RuleBookRAGService
        from services.rag_service import create_rag_service
        from services.embedding_service import create_embedding_service
        
        # Initialize services
        config = current_app.config
        rag_service = create_rag_service(config)
        embedding_service = create_embedding_service(config)
        rule_book_service = RuleBookRAGService(config, rag_service, embedding_service)
        
        # Search rule books
        results = rule_book_service.search_rule_books(query, system, limit)
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                'text': result.get('content', ''),  # RAG service returns 'content', not 'text'
                'book_name': result.get('metadata', {}).get('book_name', 'Unknown'),
                'book_id': result.get('metadata', {}).get('book_id', ''),
                'system': result.get('metadata', {}).get('system', ''),
                'page_number': result.get('metadata', {}).get('page_number', '?'),
                'relevance_score': result.get('distance', 0)  # ChromaDB uses distance
            })
        
        return jsonify({
            'success': True,
            'query': query,
            'system_filter': system,
            'results_count': len(formatted_results),
            'results': formatted_results
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching rule books: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/context', methods=['POST'])
@jwt_required()
def get_rule_context():
    """Get relevant rule context for AI generation"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        system = data.get('system')  # Optional filter by system
        limit = data.get('limit', 5)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'query is required'
            }), 400
        
        from services.rule_book_service import RuleBookRAGService
        from services.rag_service import create_rag_service
        from services.embedding_service import create_embedding_service
        
        # Initialize services
        config = current_app.config
        rag_service = create_rag_service(config)
        embedding_service = create_embedding_service(config)
        rule_book_service = RuleBookRAGService(config, rag_service, embedding_service)
        
        # Get rule context
        context = rule_book_service.get_rule_context(query, system, limit)
        
        return jsonify({
            'success': True,
            'query': query,
            'system_filter': system,
            'context': context,
            'context_length': len(context)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting rule context: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/status', methods=['GET'])
@jwt_required()
def get_rule_books_status():
    """Get status of processed rule books"""
    try:
        from services.rule_book_service import RuleBookProcessor
        
        config = current_app.config
        processor = RuleBookProcessor(config)
        
        # Check processed books
        processed_books = []
        for book_id in processor.rule_books.keys():
            processed_file = processor.processed_dir / f"{book_id}_processed.json"
            if processed_file.exists():
                with open(processed_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    processed_books.append({
                        'book_id': book_id,
                        'book_name': data.get('book_name', 'Unknown'),
                        'system': data.get('system', ''),
                        'processed_at': data.get('processed_at', ''),
                        'total_chunks': data.get('total_chunks', 0),
                        'total_pages': data.get('total_pages', 0),
                        'total_words': data.get('total_words', 0)
                    })
        
        return jsonify({
            'success': True,
            'processed_books': len(processed_books),
            'books': processed_books
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting rule books status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/systems', methods=['GET'])
@jwt_required()
def get_available_systems():
    """Get list of available game systems"""
    try:
        from services.rule_book_service import RuleBookProcessor
        
        config = current_app.config
        processor = RuleBookProcessor(config)
        
        # Get unique systems
        systems = list(set(book_info['system'] for book_info in processor.rule_books.values()))
        
        return jsonify({
            'success': True,
            'systems': systems,
            'systems_count': len(systems)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting available systems: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
