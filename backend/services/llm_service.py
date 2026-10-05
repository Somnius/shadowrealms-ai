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
from .lm_studio_model import get_effective_lm_studio_model_id, resolve_lm_studio_model_id
from .smart_model_router import SmartModelRouter, create_smart_model_router
from .rag_service import RAGService, create_rag_service

logger = logging.getLogger(__name__)


def _campaign_context_to_send(context):
    """
    The campaign context to add as its own message, or '' when the system prompt
    already contains it (routes/ai.py builds it into system_prompt), so it's sent once.
    """
    cc = str(context.get('campaign_context') or '').strip()
    if not cc or cc in str(context.get('system_prompt') or ''):
        return ''
    return cc


def _merge_master_system_prompt(context: Dict[str, Any]) -> Dict[str, Any]:
    """Prepend admin-configured master system prompt to route-specific system_prompt."""
    from services.ai_runtime_settings import get_app_setting

    if not isinstance(context, dict):
        return context
    master = (get_app_setting("ai_master_system_prompt") or "").strip()
    if not master:
        return context
    ctx = dict(context)
    base = (ctx.get("system_prompt") or "").strip()
    if base:
        ctx["system_prompt"] = f"{master}\n\n---\n\n{base}"
    else:
        ctx["system_prompt"] = master
    return ctx


def _remember_generation(result: Dict[str, Any]) -> None:
    """Keep provider/model/role/language of the last generation in flask.g (for API responses)."""
    try:
        from flask import g, has_request_context

        if has_request_context():
            g.ai_generation = {
                k: result.get(k)
                for k in ('provider', 'model_used', 'role', 'language', 'task_type', 'ms', 'attempts', 'error',
                          'trimmed', 'script_fix')
                if result.get(k) is not None
            }
    except Exception:  # noqa: BLE001
        pass


def last_generation_meta() -> Optional[Dict[str, Any]]:
    try:
        from flask import g, has_request_context

        return g.get('ai_generation') if has_request_context() else None
    except Exception:  # noqa: BLE001
        return None


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
        self.config = config
        self.base_url = config.get('LM_STUDIO_URL', 'http://localhost:1234')
        self.api_key = config.get('LM_STUDIO_API_KEY', '')
        # Previously: self.model = config.get('LM_STUDIO_MODEL', 'gemma-4-e2b-it')
        self.model = resolve_lm_studio_model_id(
            self.base_url, config.get('LM_STUDIO_MODEL'), config.get('LM_STUDIO_API_KEY')
        )
        self.timeout = int(config.get('LM_STUDIO_TIMEOUT', 120) or 120)
    
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
                "model": get_effective_lm_studio_model_id(self.config),
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
            reasoning_effort = (self.config.get('LM_STUDIO_REASONING_EFFORT') or '').strip()
            if reasoning_effort:
                payload['reasoning_effort'] = reasoning_effort

            # Add context if available
            if _campaign_context_to_send(context):
                payload['messages'].insert(1, {
                    "role": "system",
                    "content": f"Campaign Context: {_campaign_context_to_send(context)}"
                })
            
            # Make request to LM Studio
            hdrs = {'Content-Type': 'application/json'}
            if (self.api_key or '').strip():
                hdrs['Authorization'] = f'Bearer {self.api_key.strip()}'
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
                headers=hdrs,
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
        self.model = config.get('OLLAMA_MODEL', 'llama3.2:3b')
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
            
            # Add context if available (this provider doesn't send system_prompt, so this is the only copy)
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

class AIUnavailableError(RuntimeError):
    """Every configured model failed (LLMService.generate_response with raise_on_error=True)."""


class LLMService:
    """Main LLM service that manages multiple providers with smart routing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Use smart model router for efficient resource management
        self.model_router = create_smart_model_router(config)
        
        # Initialize RAG service for memory and context
        self.rag_service = create_rag_service(config)
        
        # Keep legacy providers for backward compatibility
        self.provider_priority = ['lm_studio', 'ollama']
        self.providers = {
            'lm_studio': LMStudioProvider(config),
            'ollama': OllamaProvider(config)
        }
        
        logger.info("LLM Service initialized with SmartModelRouter and RAG")
    
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
    
    def generate_response(self, prompt: str, context: Dict[str, Any], config: Dict[str, Any],
                          raise_on_error: bool = False) -> str:
        """
        Generate response using smart model routing with RAG augmentation.

        When every model fails the router's error text is returned, or AIUnavailableError is
        raised with raise_on_error=True (the Storyteller chat must not hand that text out as
        an AI reply).
        """
        context = _merge_master_system_prompt(context)
        context = dict(context or {})
        # Routing and language look at what the player wrote, not the RAG-augmented prompt.
        context.setdefault('player_message', prompt)
        if not context.get('reply_language'):
            # Every caller (Storyteller, /ai slash helpers, location suggestions) answers in the
            # language of what the player wrote, else their UI language, else English.
            from services.language import resolve_reply_language

            context['reply_language'] = resolve_reply_language(
                context['player_message'], context.get('player_user_id') or context.get('user_id')
            )
        # Laya's intent, once per message: it gates the rule-book search and picks the model
        # (SmartModelRouter.detect_task_type reuses context['laya_intent']). None = unknown.
        if 'laya_intent' not in context and not context.get('skip_classifier'):
            from services.classifier import classify_intent_cached

            context['laya_intent'] = classify_intent_cached(context['player_message'])

        # Get campaign context for RAG augmentation
        campaign_id = context.get('campaign_id')
        user_id = context.get('user_id')
        
        # Augment prompt with relevant context
        if campaign_id:
            augmented_prompt = self.rag_service.augment_prompt(
                prompt, campaign_id, user_id, rules_edition=context.get('rules_edition'),
                max_tokens=context.get('rag_budget_tokens'),
                game_system=context.get('game_system'),
                intent=context.get('laya_intent'),
                query_embedding=context.get('query_embedding'),
            )
            logger.info(f"Augmented prompt with RAG context for campaign {campaign_id}")
        else:
            augmented_prompt = prompt
            logger.info("No campaign context available, using original prompt")
        
        # Use smart model router for intelligent model selection
        result = self.model_router.generate_response(augmented_prompt, context, config)
        _remember_generation(result)
        
        if 'error' in result or not str(result.get('response') or '').strip():
            logger.error(f"SmartModelRouter error: {result.get('error') or 'empty response'}")
            if raise_on_error:
                raise AIUnavailableError(str(result.get('error') or 'empty response'))
            return result['response']
        
        # Store interaction in memory
        if campaign_id and user_id:
            self.rag_service.store_interaction(
                prompt, 
                result['response'], 
                campaign_id, 
                user_id,
                result.get('task_type', 'general')
            )
            logger.info(f"Stored interaction in RAG memory")
        
        # Log the interaction
        logger.info(f"Generated response using {result['model_used']} for {result['task_type']} task")
        
        return result['response']
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status for all providers and RAG"""
        status = {
            'available_providers': self.get_available_providers(),
            'primary_provider': None,
            'providers': {},
            'rag_status': self.rag_service.get_system_status(),
            'model_router_status': self.model_router.get_system_status()
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
