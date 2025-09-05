#!/usr/bin/env python3
"""
ShadowRealms AI - Configuration Management
Environment-based configuration for development and production
"""

import os
import logging
from datetime import timedelta

# Load environment variables from .env file (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not available, continue without it
    pass

# Debug: Print environment variables for troubleshooting
import os

class Config:
    """Configuration class for ShadowRealms AI"""
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'dev-secret-key-change-in-production'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Flask Application Settings
    FLASK_HOST = os.environ.get('FLASK_HOST') or '0.0.0.0'
    FLASK_PORT = int(os.environ.get('FLASK_PORT') or 5000)
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    # Database Configuration
    DATABASE = os.environ.get('DATABASE') or '/app/data/shadowrealms.db'
    
    # AI/LLM Configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_BASE_URL = os.environ.get('OPENAI_BASE_URL') or 'http://localhost:1234/v1'
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL') or 'gpt-3.5-turbo'
    
    # ChromaDB Configuration
    CHROMADB_HOST = os.environ.get('CHROMADB_HOST') or 'localhost'
    CHROMADB_PORT = int(os.environ.get('CHROMADB_PORT') or 8000)
    
    # GPU Monitoring Configuration
    GPU_THRESHOLD_HIGH = int(os.environ.get('GPU_THRESHOLD_HIGH') or 80)
    GPU_THRESHOLD_MEDIUM = int(os.environ.get('GPU_THRESHOLD_MEDIUM') or 60)
    MONITORING_INTERVAL = int(os.environ.get('MONITORING_INTERVAL') or 5)
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_FILE = os.environ.get('LOG_FILE') or '/app/logs/backend.log'
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    @classmethod
    def setup_logging(cls):
        """Setup comprehensive logging configuration"""
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(cls.LOG_FILE), exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, cls.LOG_LEVEL),
            format=cls.LOG_FORMAT,
            handlers=[
                # Console handler
                logging.StreamHandler(),
                # File handler
                logging.FileHandler(cls.LOG_FILE)
            ]
        )
        
        # Set specific logger levels
        logging.getLogger('werkzeug').setLevel(logging.INFO)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        
        # Log configuration
        logger = logging.getLogger(__name__)
        logger.info(f"Logging configured - Level: {cls.LOG_LEVEL}, File: {cls.LOG_FILE}")
        logger.info(f"Database: {cls.DATABASE}")
        logger.info(f"ChromaDB: {cls.CHROMADB_HOST}:{cls.CHROMADB_PORT}")
        logger.info(f"GPU Thresholds - High: {cls.GPU_THRESHOLD_HIGH}%, Medium: {cls.GPU_THRESHOLD_MEDIUM}%")
        
        # Log Flask configuration
        logger.info(f"Flask Host: {cls.FLASK_HOST}")
        logger.info(f"Flask Port: {cls.FLASK_PORT}")
        logger.info(f"Flask Debug: {cls.FLASK_DEBUG}")
        logger.info(f"Flask Secret Key: {'*' * 10 if cls.SECRET_KEY != 'dev-secret-key-change-in-production' else 'DEFAULT (CHANGE THIS)'}")
        logger.info(f"JWT Secret Key: {'*' * 10 if cls.JWT_SECRET_KEY != 'jwt-secret-key-change-in-production' else 'DEFAULT (CHANGE THIS)'}")
    
    @classmethod
    def debug_env_vars(cls):
        """Debug method to show environment variable loading"""
        print("🔧 Flask Configuration Debug:")
        print("=" * 40)
        print(f"FLASK_SECRET_KEY: {os.environ.get('FLASK_SECRET_KEY', 'NOT SET')}")
        print(f"JWT_SECRET_KEY: {os.environ.get('JWT_SECRET_KEY', 'NOT SET')}")
        print(f"FLASK_HOST: {os.environ.get('FLASK_HOST', 'NOT SET')}")
        print(f"FLASK_PORT: {os.environ.get('FLASK_PORT', 'NOT SET')}")
        print(f"FLASK_DEBUG: {os.environ.get('FLASK_DEBUG', 'NOT SET')}")
        print(f"DATABASE: {os.environ.get('DATABASE', 'NOT SET')}")
        print(f"CHROMADB_HOST: {os.environ.get('CHROMADB_HOST', 'NOT SET')}")
        print(f"REDIS_HOST: {os.environ.get('REDIS_HOST', 'NOT SET')}")
        print("=" * 40)

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    DATABASE_ECHO = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    DATABASE_ECHO = False

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
