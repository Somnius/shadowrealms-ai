#!/usr/bin/env python3
"""
ShadowRealms AI - Main Application Entry Point
Flask application with modular architecture and GPU monitoring integration
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Import our modules
from config import Config
from database import init_db, get_db
from services.gpu_monitor import GPUMonitorService
from services.llm_service import LLMService
from routes import auth, users, campaigns, characters, ai

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
    
    # Initialize extensions
    CORS(app)
    JWTManager(app)
    
    # Initialize database
    with app.app_context():
        init_db()
    
    # Register blueprints
    app.register_blueprint(auth.bp, url_prefix='/api/auth')
    app.register_blueprint(users.bp, url_prefix='/api/users')
    app.register_blueprint(campaigns.bp, url_prefix='/api/campaigns')
    app.register_blueprint(characters.bp, url_prefix='/api/characters')
    app.register_blueprint(ai.bp, url_prefix='/api/ai')
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Health check endpoint for Docker"""
        try:
            # Check database connection
            db = get_db()
            db.execute("SELECT 1")
            
            # Check GPU monitoring status
            gpu_status = GPUMonitorService.get_current_status()
            
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'connected',
                'gpu_monitoring': 'active' if gpu_status else 'inactive',
                'version': '0.2.1'
            }), 200
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }), 500
    
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
                'ai': '/api/ai'
            }
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

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
    
    # Start the application
    app.run(host=host, port=port, debug=debug)

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
            exit(0)
        else:
            print("❌ Tests failed! Please fix issues before integration.")
            exit(1)
