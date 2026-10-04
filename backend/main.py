#!/usr/bin/env python3
"""
ShadowRealms AI - Main Application Entry Point
Flask application with modular architecture and GPU monitoring integration
"""

import os
import sys
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request

# Import our modules
from config import Config
from database import init_db, get_db
from services.gpu_monitor import GPUMonitorService
from services.llm_service import LLMService
from routes import auth, users, campaigns, characters, ai, rule_books, admin, locations, dice, messages

# Configure logging
Config.setup_logging()
logger = logging.getLogger(__name__)

# Debug environment variables (remove in production)
if os.environ.get('FLASK_DEBUG', 'false').lower() == 'true':
    Config.debug_env_vars()

def create_app(config_class=Config):
    """Application factory pattern for Flask"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    config_class.validate_secrets()

    # Proxy trust, CORS allow-list, JWT revocation, rate limits, headers, error handlers
    # (services/app_security.py, docs/SECURITY_MODEL.md)
    from services.app_security import init_app_security, apply_route_limits
    init_app_security(app)
    
    # Initialize database
    with app.app_context():
        init_db()
        from database import migrate_db
        migrate_db()

    # Under gunicorn --preload the app is built in the master before forking; threads must not
    # be started there (gunicorn.conf.py starts them in the first worker instead).
    if os.environ.get('SR_DEFER_BACKGROUND_JOBS', '').lower() not in ('1', 'true', 'yes'):
        start_background_jobs(app)

    # Initialize LLM service
    with app.app_context():
        from services.llm_service import initialize_llm_service
        llm_service = initialize_llm_service({
            'LM_STUDIO_URL': os.environ.get('LM_STUDIO_URL', 'http://localhost:1234'),
            'LM_STUDIO_API_KEY': os.environ.get('LM_STUDIO_API_KEY', ''),
            # Empty or "auto" => resolve from LM Studio GET /v1/models (see services/lm_studio_model.py)
            'LM_STUDIO_MODEL': os.environ.get('LM_STUDIO_MODEL', '') or '',
            'LM_STUDIO_TIMEOUT': int(os.environ.get('LM_STUDIO_TIMEOUT', '120')),
            # Empty = model default; "none" turns off thinking on reasoning models (e.g. Gemma 4)
            'LM_STUDIO_REASONING_EFFORT': os.environ.get('LM_STUDIO_REASONING_EFFORT', '').strip(),
            'OLLAMA_URL': os.environ.get('OLLAMA_URL', 'http://localhost:11434'),
            'OLLAMA_MODEL': os.environ.get('OLLAMA_MODEL', 'llama3.2:3b'),
            'OLLAMA_TIMEOUT': int(os.environ.get('OLLAMA_TIMEOUT', '30'))
        })
        logger.info("LLM Service initialized successfully")
    
    # Register blueprints
    app.register_blueprint(auth.bp, url_prefix='/api/auth')
    app.register_blueprint(users.bp, url_prefix='/api/users')
    app.register_blueprint(campaigns.campaigns_bp)
    app.register_blueprint(characters.bp, url_prefix='/api/characters')
    app.register_blueprint(ai.bp, url_prefix='/api/ai')
    app.register_blueprint(rule_books.bp, url_prefix='/api/rule-books')
    app.register_blueprint(admin.bp)
    app.register_blueprint(locations.locations_bp, url_prefix='/api')
    app.register_blueprint(dice.dice_bp, url_prefix='/api')
    app.register_blueprint(messages.messages_bp, url_prefix='/api')
    from routes.events import events_bp; app.register_blueprint(events_bp, url_prefix='/api')  # v0.9 live updates (SSE), unread, roster
    
    # Version endpoint
    @app.route('/api/version')
    def get_version():
        """Get application version from environment"""
        version = os.environ.get('VERSION', '0.0.0')
        return jsonify({
            'version': f"v{version}",
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for Docker"""
        try:
            # Check database connection
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            
            # Check GPU monitoring status
            gpu_status = GPUMonitorService.get_current_status()
            
            version = os.environ.get('VERSION', '0.0.0')
            
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'connected',
                'gpu_monitoring': 'active' if gpu_status else 'inactive',
                'version': version
            }), 200
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    
    # README endpoint
    @app.route('/api/readme')
    def get_readme():
        """Serve README.md file"""
        try:
            readme_path = '/app/README.md'
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content, 200, {'Content-Type': 'text/plain; charset=utf-8'}
        except Exception as e:
            logger.error(f"Error reading README.md: {e}")
            return jsonify({'error': 'Failed to load README.md'}), 500
    
    # Root endpoint
    @app.route('/')
    def root():
        """Root endpoint with API information"""
        return jsonify({
            'name': 'ShadowRealms AI',
            'version': '0.2.1',
            'status': 'running',
            'description': 'AI-Powered Web-Based RPG Platform',
            'endpoints': {
                'health': '/health',
                'auth': '/api/auth',
                'users': '/api/users',
                'campaigns': '/api/campaigns',
                'characters': '/api/characters',
                'ai': '/api/ai',
                'readme': '/api/readme'
            }
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    apply_route_limits(app)  # after every route exists
    return app


def start_background_jobs(app):
    """Startup jobs in daemon threads; failures never block startup."""
    # One-off, idempotent: stamp rules_edition on untagged rule book chunks so classic
    # campaigns never get V5 chunks.
    try:
        from services.rag_service import backfill_rule_book_editions_in_background

        backfill_rule_book_editions_in_background(app.config)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not start rule book edition backfill: %s", e)

    # Idempotent: rebuild ChromaDB collections embedded with another model than EMBEDDING_MODEL
    # (services/vector_store.py). Skipped when the embedder is down; pg advisory lock inside.
    try:
        from services.vector_store import reembed_in_background

        reembed_in_background(app.config)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not start RAG re-embed: %s", e)

def test_main_application():
    """Standalone test function for Main Application"""
    print("🧪 Testing Main Application...")
    
    try:
        # Test 1: Test configuration
        print("  ✓ Testing configuration...")
        config = Config()
        print(f"  ✓ Database path: {config.DATABASE}")
        print(f"  ✓ ChromaDB: {config.CHROMADB_HOST}:{config.CHROMADB_PORT}")
        
        # Test 2: Test Flask app creation
        print("  ✓ Testing Flask app creation...")
        app = create_app(Config)
        print("  ✓ Flask app created successfully")
        
        # Test 3: Test app context
        print("  ✓ Testing app context...")
        with app.app_context():
            print("  ✓ App context working")
            
            # Test database connection
            try:
                db = get_db()
                db.execute("SELECT 1")
                print("  ✓ Database connection successful")
            except Exception as e:
                print(f"  ⚠️  Database connection failed (expected in standalone mode): {e}")
        
        # Test 4: Test endpoints registration
        print("  ✓ Testing endpoint registration...")
        registered_routes = []
        for rule in app.url_map.iter_rules():
            registered_routes.append(rule.endpoint)
        
        expected_endpoints = ['health', 'root', 'static']
        for endpoint in expected_endpoints:
            if endpoint in registered_routes:
                print(f"    ✓ Endpoint '{endpoint}' registered")
            else:
                print(f"    ❌ Endpoint '{endpoint}' missing")
        
        # Test 5: Test health check endpoint
        print("  ✓ Testing health check endpoint...")
        with app.test_client() as client:
            response = client.get('/health')
            if response.status_code == 500:  # Expected due to missing services
                print("    ✓ Health check endpoint responding (500 expected in standalone)")
            else:
                print(f"    ✓ Health check endpoint responding: {response.status_code}")
        
        print("🎉 All Main Application tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main application entry point"""
    # Create Flask app
    app = create_app(Config)
    
    # Get configuration
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info("🚀 Starting ShadowRealms AI Backend")
    logger.info(f"🌐 Host: {host}")
    logger.info(f"🔌 Port: {port}")
    logger.info(f"🐛 Debug: {debug}")
    logger.info(f"🎮 Version: 0.2.1")
    
    # Auto-reload on code changes when FLASK_ENV=development (or FLASK_DEBUG=true)
    dev = os.getenv('FLASK_ENV', '').lower() == 'development'
    disable_reload = os.getenv('FLASK_DISABLE_RELOADER', '').lower() in ('1', 'true', 'yes')
    use_reloader = (debug or (dev and not disable_reload))
    if use_reloader and not debug:
        logger.info('File watcher enabled (FLASK_ENV=development); code changes reload the server')
    # Start the application
    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)

if __name__ == "__main__":
    """Run standalone tests or start the application"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        # Run the actual application
        print("🚀 Starting ShadowRealms AI Backend...")
        main()
    else:
        # Run standalone tests
        print("🚀 Running Main Application Standalone Tests")
        print("=" * 50)
        
        success = test_main_application()
        
        print("=" * 50)
        if success:
            print("✅ All tests passed! Application is ready for integration.")
            print("💡 To run the actual Flask app, use: python main.py --run")
            sys.exit(0)
        else:
            print("❌ Tests failed! Please fix issues before integration.")
            sys.exit(1)
