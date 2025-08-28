#!/usr/bin/env python3
"""
ShadowRealms AI - LLM Service Layer
Abstract interface for multiple LLM providers (LM Studio, Ollama)
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate_response(self, prompt: str, context: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Generate response from LLM"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available"""
        pass
    
    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        pass

class LMStudioProvider(LLMProvider):
    """LM Studio LLM provider implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get('LM_STUDIO_URL', 'http://localhost:1234')
        self.api_key = config.get('LM_STUDIO_API_KEY', '')
        self.model = config.get('LM_STUDIO_MODEL', 'mythomakise-merged-13b')
        self.timeout = config.get('LM_STUDIO_TIMEOUT', 30)
    
    def is_available(self) -> bool:
        """Check if LM Studio is available"""
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"LM Studio not available: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get LM Studio model information"""
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=self.timeout)
            if response.status_code == 200:
                models = response.json()
                return {
                    'provider': 'LM Studio',
                    'models': models.get('data', []),
                    'base_url': self.base_url,
                    'status': 'available'
                }
        except Exception as e:
            logger.error(f"Error getting LM Studio model info: {e}")
        
        return {
            'provider': 'LM Studio',
            'models': [],
            'base_url': self.base_url,
            'status': 'unavailable'
        }
    
    def generate_response(self, prompt: str, context: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Generate response using LM Studio"""
        try:
            # Prepare the request payload
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": context.get('system_prompt', 'You are a helpful AI assistant for tabletop RPGs.')
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": config.get('max_tokens', 1024),
                "temperature": config.get('temperature', 0.7),
                "stream": False
            }
            
            # Add context if available
            if context.get('campaign_context'):
                payload['messages'].insert(1, {
                    "role": "system",
                    "content": f"Campaign Context: {context['campaign_context']}"
                })
            
            # Make request to LM Studio
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}' if self.api_key else ''
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"LM Studio API error: {response.status_code} - {response.text}")
                return f"Error: LM Studio API returned {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error generating response with LM Studio: {e}")
            return f"Error: Failed to generate response - {str(e)}"

class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get('OLLAMA_URL', 'http://localhost:11434')
        self.model = config.get('OLLAMA_MODEL', 'command-r:35b')
        self.timeout = config.get('OLLAMA_TIMEOUT', 30)
    
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get Ollama model information"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=self.timeout)
            if response.status_code == 200:
                models = response.json()
                return {
                    'provider': 'Ollama',
                    'models': models.get('models', []),
                    'base_url': self.base_url,
                    'status': 'available'
                }
        except Exception as e:
            logger.error(f"Error getting Ollama model info: {e}")
        
        return {
            'provider': 'Ollama',
            'models': [],
            'base_url': self.base_url,
            'status': 'unavailable'
        }
    
    def generate_response(self, prompt: str, context: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Generate response using Ollama"""
        try:
            # Prepare the request payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": config.get('max_tokens', 1024),
                    "temperature": config.get('temperature', 0.7),
                    "top_p": config.get('top_p', 0.9)
                }
            }
            
            # Add context if available
            if context.get('campaign_context'):
                payload['prompt'] = f"Campaign Context: {context['campaign_context']}\n\nUser: {prompt}"
            
            # Make request to Ollama
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', 'No response generated')
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return f"Error: Ollama API returned {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error generating response with Ollama: {e}")
            return f"Error: Failed to generate response - {str(e)}"

class LLMService:
    """Main LLM service that manages multiple providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers = {
            'lm_studio': LMStudioProvider(config),
            'ollama': OllamaProvider(config)
        }
        
        # Priority order for providers
        self.provider_priority = ['lm_studio', 'ollama']
        
        logger.info("LLM Service initialized")
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        available = []
        for provider_name, provider in self.providers.items():
            if provider.is_available():
                available.append(provider_name)
        return available
    
    def get_primary_provider(self) -> Optional[LLMProvider]:
        """Get the primary (first available) provider"""
        for provider_name in self.provider_priority:
            provider = self.providers.get(provider_name)
            if provider and provider.is_available():
                return provider
        return None
    
    def generate_response(self, prompt: str, context: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Generate response using the best available provider"""
        # Get primary provider
        provider = self.get_primary_provider()
        
        if not provider:
            return "Error: No LLM providers available"
        
        # Generate response
        response = provider.generate_response(prompt, context, config)
        
        # Log the interaction
        logger.info(f"Generated response using {provider.__class__.__name__}")
        
        return response
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status for all providers"""
        status = {
            'available_providers': self.get_available_providers(),
            'primary_provider': None,
            'providers': {}
        }
        
        for provider_name, provider in self.providers.items():
            provider_info = provider.get_model_info()
            status['providers'][provider_name] = provider_info
            
            # Set primary provider
            if not status['primary_provider'] and provider.is_available():
                status['primary_provider'] = provider_name
        
        return status
    
    def test_provider(self, provider_name: str) -> Dict[str, Any]:
        """Test a specific provider"""
        provider = self.providers.get(provider_name)
        
        if not provider:
            return {'error': f'Provider {provider_name} not found'}
        
        # Test availability
        is_available = provider.is_available()
        
        # Test response generation if available
        test_response = None
        if is_available:
            try:
                test_response = provider.generate_response(
                    "Hello, this is a test message.",
                    {'system_prompt': 'You are a helpful AI assistant.'},
                    {'max_tokens': 50, 'temperature': 0.7}
                )
            except Exception as e:
                test_response = f"Error: {str(e)}"
        
        return {
            'provider': provider_name,
            'available': is_available,
            'test_response': test_response,
            'model_info': provider.get_model_info()
        }

# Global LLM service instance
llm_service = None

def initialize_llm_service(config: Dict[str, Any]) -> LLMService:
    """Initialize the global LLM service"""
    global llm_service
    llm_service = LLMService(config)
    return llm_service

def get_llm_service() -> LLMService:
    """Get the global LLM service instance"""
    if llm_service is None:
        raise RuntimeError("LLM Service not initialized. Call initialize_llm_service() first.")
    return llm_service
