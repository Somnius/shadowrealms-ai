#!/usr/bin/env python3
"""
ShadowRealms AI - Health Check Service
Validates critical services (LM Studio, Ollama, ChromaDB) before operations
Quality over Speed - Prevent operations with missing dependencies
"""

import logging
import requests
from typing import Dict, Any, Tuple
from functools import wraps
from flask import jsonify

logger = logging.getLogger(__name__)

class HealthCheckService:
    """Service to check health of critical AI/LLM dependencies"""
    
    def __init__(self):
        self.last_check_results = {}
        self.check_timeout = 5  # seconds
    
    def check_lm_studio(self, base_url: str = 'http://localhost:1234') -> Tuple[bool, str]:
        """
        Check if LM Studio is running and responding
        
        Returns:
            Tuple[bool, str]: (is_available, message)
        """
        try:
            response = requests.get(
                f"{base_url}/v1/models",
                timeout=self.check_timeout
            )
            
            if response.status_code == 200:
                models = response.json().get('data', [])
                if not models:
                    return (False, "LM Studio is running but no models are loaded. Please load a model in LM Studio.")
                
                model_names = [m.get('id', 'Unknown') for m in models]
                return (True, f"LM Studio is running. Available models: {', '.join(model_names)}")
            else:
                return (False, f"LM Studio responded with status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            return (False, "Cannot connect to LM Studio. Please start LM Studio and load a model.")
        except requests.exceptions.Timeout:
            return (False, "LM Studio connection timed out. Is it running?")
        except Exception as e:
            logger.error(f"Unexpected error checking LM Studio: {e}")
            return (False, f"Error checking LM Studio: {str(e)}")
    
    def check_ollama(self, base_url: str = 'http://localhost:11434') -> Tuple[bool, str]:
        """
        Check if Ollama is running and responding
        
        Returns:
            Tuple[bool, str]: (is_available, message)
        """
        try:
            response = requests.get(
                f"{base_url}/api/tags",
                timeout=self.check_timeout
            )
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                if not models:
                    return (False, "Ollama is running but no models are installed.")
                
                model_names = [m.get('name', 'Unknown') for m in models]
                return (True, f"Ollama is running. Available models: {', '.join(model_names[:3])}")
            else:
                return (False, f"Ollama responded with status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            return (False, "Cannot connect to Ollama. Is it running?")
        except requests.exceptions.Timeout:
            return (False, "Ollama connection timed out.")
        except Exception as e:
            logger.error(f"Unexpected error checking Ollama: {e}")
            return (False, f"Error checking Ollama: {str(e)}")
    
    def check_chromadb(self, host: str = 'chromadb', port: int = 8000) -> Tuple[bool, str]:
        """
        Check if ChromaDB is running and responding
        
        Returns:
            Tuple[bool, str]: (is_available, message)
        """
        try:
            response = requests.get(
                f"http://{host}:{port}/api/v1/heartbeat",
                timeout=self.check_timeout
            )
            
            if response.status_code == 200:
                return (True, "ChromaDB is running")
            else:
                return (False, f"ChromaDB responded with status {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            return (False, "Cannot connect to ChromaDB. Check if the container is running.")
        except requests.exceptions.Timeout:
            return (False, "ChromaDB connection timed out.")
        except Exception as e:
            logger.error(f"Unexpected error checking ChromaDB: {e}")
            return (False, f"Error checking ChromaDB: {str(e)}")
    
    def check_all_services(self) -> Dict[str, Any]:
        """
        Check all critical services
        
        Returns:
            Dict with status of all services
        """
        import os
        
        lm_studio_url = os.getenv('LM_STUDIO_URL', 'http://localhost:1234')
        ollama_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        chromadb_host = os.getenv('CHROMADB_HOST', 'chromadb')
        chromadb_port = int(os.getenv('CHROMADB_PORT', 8000))
        
        lm_studio_ok, lm_studio_msg = self.check_lm_studio(lm_studio_url)
        ollama_ok, ollama_msg = self.check_ollama(ollama_url)
        chromadb_ok, chromadb_msg = self.check_chromadb(chromadb_host, chromadb_port)
        
        # At least one LLM provider must be available
        llm_available = lm_studio_ok or ollama_ok
        
        results = {
            'lm_studio': {
                'available': lm_studio_ok,
                'message': lm_studio_msg,
                'url': lm_studio_url
            },
            'ollama': {
                'available': ollama_ok,
                'message': ollama_msg,
                'url': ollama_url
            },
            'chromadb': {
                'available': chromadb_ok,
                'message': chromadb_msg,
                'host': chromadb_host,
                'port': chromadb_port
            },
            'llm_available': llm_available,
            'all_services_ok': llm_available and chromadb_ok
        }
        
        self.last_check_results = results
        return results
    
    def get_primary_llm_provider(self) -> str:
        """
        Determine which LLM provider is currently available
        
        Returns:
            'lm_studio', 'ollama', or 'none'
        """
        if not self.last_check_results:
            self.check_all_services()
        
        if self.last_check_results.get('lm_studio', {}).get('available'):
            return 'lm_studio'
        elif self.last_check_results.get('ollama', {}).get('available'):
            return 'ollama'
        else:
            return 'none'


# Global health check service instance
_health_check_service = None

def get_health_check_service() -> HealthCheckService:
    """Get or create the global health check service instance"""
    global _health_check_service
    if _health_check_service is None:
        _health_check_service = HealthCheckService()
    return _health_check_service


def require_llm(f):
    """
    Decorator to check if LLM service is available before executing route
    Quality over Speed - Fail fast with clear error message
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        health_check = get_health_check_service()
        results = health_check.check_all_services()
        
        if not results['llm_available']:
            error_messages = []
            
            if not results['lm_studio']['available']:
                error_messages.append(f"❌ LM Studio: {results['lm_studio']['message']}")
            
            if not results['ollama']['available']:
                error_messages.append(f"❌ Ollama: {results['ollama']['message']}")
            
            logger.error("AI operation failed: No LLM provider available")
            logger.error(f"LM Studio: {results['lm_studio']['message']}")
            logger.error(f"Ollama: {results['ollama']['message']}")
            
            return jsonify({
                'error': 'AI Service Unavailable',
                'message': 'No LLM provider is currently available. Please start LM Studio or Ollama.',
                'details': error_messages,
                'instructions': [
                    '1. Start LM Studio and load a model, OR',
                    '2. Start Ollama and ensure models are available',
                    '3. Check that the service is running on the configured port'
                ]
            }), 503  # 503 Service Unavailable
        
        # LLM is available, proceed with the request
        return f(*args, **kwargs)
    
    return decorated_function


def require_chromadb(f):
    """
    Decorator to check if ChromaDB is available before executing route
    Quality over Speed - Fail fast with clear error message
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        health_check = get_health_check_service()
        results = health_check.check_all_services()
        
        if not results['chromadb']['available']:
            logger.error(f"ChromaDB operation failed: {results['chromadb']['message']}")
            
            return jsonify({
                'error': 'Vector Database Unavailable',
                'message': 'ChromaDB is not currently available.',
                'details': results['chromadb']['message'],
                'instructions': [
                    '1. Check if ChromaDB container is running: docker compose ps',
                    '2. Restart ChromaDB: docker compose restart chromadb',
                    '3. Check logs: docker compose logs chromadb'
                ]
            }), 503  # 503 Service Unavailable
        
        # ChromaDB is available, proceed with the request
        return f(*args, **kwargs)
    
    return decorated_function


def require_ai_services(f):
    """
    Decorator to check if ALL AI services (LLM + ChromaDB) are available
    Use this for operations that need both LLM and vector database
    Quality over Speed - Comprehensive check before operation
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        health_check = get_health_check_service()
        results = health_check.check_all_services()
        
        if not results['all_services_ok']:
            error_details = []
            instructions = []
            
            if not results['llm_available']:
                error_details.append("❌ No LLM provider available (LM Studio or Ollama)")
                instructions.extend([
                    '• Start LM Studio and load a model, OR',
                    '• Start Ollama with available models'
                ])
            
            if not results['chromadb']['available']:
                error_details.append(f"❌ ChromaDB: {results['chromadb']['message']}")
                instructions.extend([
                    '• Check ChromaDB container: docker compose ps chromadb',
                    '• Restart ChromaDB: docker compose restart chromadb'
                ])
            
            logger.error("AI operation failed: Required services unavailable")
            for detail in error_details:
                logger.error(detail)
            
            return jsonify({
                'error': 'AI Services Unavailable',
                'message': 'One or more required AI services are not available.',
                'details': error_details,
                'instructions': instructions,
                'service_status': {
                    'lm_studio': results['lm_studio'],
                    'ollama': results['ollama'],
                    'chromadb': results['chromadb']
                }
            }), 503  # 503 Service Unavailable
        
        # All AI services available, proceed with the request
        return f(*args, **kwargs)
    
    return decorated_function

