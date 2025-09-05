#!/usr/bin/env python3
"""
ShadowRealms AI - Model Router System
Intelligent routing of tasks to specialized models based on context and requirements
"""

import os
import json
import logging
import requests
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskType(Enum):
    """Types of AI tasks for model routing"""
    ROLEPLAY = "roleplay"
    WORLD_BUILDING = "world_building"
    STORYTELLING = "storytelling"
    CREATIVE = "creative"
    GREEK_CONTENT = "greek_content"
    TRANSLATION = "translation"
    DICE_ROLLING = "dice_rolling"
    COMBAT = "combat"
    CHARACTER_CREATION = "character_creation"
    GENERAL = "general"

class ModelProvider(Enum):
    """Available model providers"""
    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"

class ModelRouter:
    """Smart model routing system with resource management"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Primary models (always available)
        self.primary_model = 'mythomakisemerged-13b'
        self.fallback_model = 'command-r:35b'
        
        # Model configurations with resource requirements
        self.model_configs = {
            # Primary Models (Keep loaded)
            'mythomakisemerged-13b': {
                'provider': ModelProvider.LM_STUDIO,
                'base_url': config.get('LM_STUDIO_URL', 'http://localhost:1234'),
                'specialties': [TaskType.ROLEPLAY, TaskType.CHARACTER_CREATION, TaskType.GENERAL, TaskType.STORYTELLING],
                'max_tokens': 1024,
                'temperature': 0.8,
                'description': 'Primary roleplay and character consistency',
                'vram_usage': '8GB',
                'priority': 'high',
                'always_loaded': True
            },
            'command-r:35b': {
                'provider': ModelProvider.OLLAMA,
                'base_url': config.get('OLLAMA_URL', 'http://localhost:11434'),
                'specialties': [TaskType.GENERAL, TaskType.STORYTELLING, TaskType.WORLD_BUILDING],
                'max_tokens': 2048,
                'temperature': 0.8,
                'description': 'Fallback for complex tasks',
                'vram_usage': '20GB',
                'priority': 'high',
                'always_loaded': False
            },
            
            # Specialized Models (Load on demand)
            'meltemi-7b-v1-i1': {
                'provider': ModelProvider.LM_STUDIO,
                'base_url': config.get('LM_STUDIO_URL', 'http://localhost:1234'),
                'specialties': [TaskType.GREEK_CONTENT, TaskType.TRANSLATION],
                'max_tokens': 512,
                'temperature': 0.7,
                'description': 'Greek language model',
                'vram_usage': '5GB',
                'priority': 'low',
                'always_loaded': False
            },
            'llama3.2:3b': {
                'provider': ModelProvider.OLLAMA,
                'base_url': config.get('OLLAMA_URL', 'http://localhost:11434'),
                'specialties': [TaskType.DICE_ROLLING, TaskType.COMBAT],
                'max_tokens': 512,
                'temperature': 0.6,
                'description': 'Fast game mechanics',
                'vram_usage': '2GB',
                'priority': 'medium',
                'always_loaded': False
            },
            'qwen2.5:7b': {
                'provider': ModelProvider.OLLAMA,
                'base_url': config.get('OLLAMA_URL', 'http://localhost:11434'),
                'specialties': [TaskType.CREATIVE],
                'max_tokens': 1024,
                'temperature': 0.9,
                'description': 'Creative tasks',
                'vram_usage': '4GB',
                'priority': 'low',
                'always_loaded': False
            }
        }
        
        # Task routing priorities
        self.task_routing = {
            TaskType.ROLEPLAY: ['mythomakisemerged-13b', 'qwen2.5:7b', 'command-r:35b'],
            TaskType.WORLD_BUILDING: ['llama3.1:70b', 'mistral:7b-instruct', 'command-r:35b'],
            TaskType.STORYTELLING: ['llama3.1:70b', 'command-r:35b', 'mythomakisemerged-13b'],
            TaskType.CREATIVE: ['qwen2.5:7b', 'mythomakisemerged-13b', 'llama3.1:70b'],
            TaskType.GREEK_CONTENT: ['meltemi-7b-v1-i1', 'llama3.1:70b'],
            TaskType.TRANSLATION: ['meltemi-7b-v1-i1', 'llama3.1:70b'],
            TaskType.DICE_ROLLING: ['llama3.2:3b', 'mistral:7b-instruct'],
            TaskType.COMBAT: ['llama3.2:3b', 'mythomakisemerged-13b'],
            TaskType.CHARACTER_CREATION: ['mythomakisemerged-13b', 'qwen2.5:7b'],
            TaskType.GENERAL: ['command-r:35b', 'llama3.1:70b', 'mythomakisemerged-13b']
        }
        
        logger.info("ModelRouter initialized with {} models".format(len(self.model_configs)))
    
    def detect_task_type(self, prompt: str, context: Dict[str, Any]) -> TaskType:
        """Detect the type of task based on prompt and context"""
        prompt_lower = prompt.lower()
        
        # Greek content detection
        if any(word in prompt for word in ['γεια', 'καλησπέρα', 'καλημέρα', 'ελληνικά', 'greek']):
            return TaskType.GREEK_CONTENT
        
        # Character creation
        if any(word in prompt_lower for word in ['character', 'create', 'background', 'stats', 'sheet', 'class', 'race']):
            return TaskType.CHARACTER_CREATION
        
        # World building
        if any(word in prompt_lower for word in ['world', 'setting', 'location', 'city', 'kingdom', 'realm', 'universe']):
            return TaskType.WORLD_BUILDING
        
        # Storytelling
        if any(word in prompt_lower for word in ['story', 'plot', 'narrative', 'adventure', 'quest', 'campaign']):
            return TaskType.STORYTELLING
        
        # Creative tasks
        if any(word in prompt_lower for word in ['creative', 'imagine', 'describe', 'artistic', 'poetry', 'song']):
            return TaskType.CREATIVE
        
        # Game mechanics
        if any(word in prompt_lower for word in ['roll', 'dice', 'combat', 'fight', 'attack', 'damage', 'hp']):
            return TaskType.DICE_ROLLING
        
        # Roleplay (default for RPG context)
        if any(word in prompt_lower for word in ['roleplay', 'rp', 'character', 'player', 'npc', 'dialogue']):
            return TaskType.ROLEPLAY
        
        return TaskType.GENERAL
    
    def get_best_model(self, task_type: TaskType, context: Dict[str, Any]) -> Optional[str]:
        """Get the best model for a specific task type"""
        available_models = self.get_available_models()
        
        # Get priority list for this task type
        priority_models = self.task_routing.get(task_type, [])
        
        # Find the first available model in priority order
        for model_name in priority_models:
            if model_name in available_models:
                return model_name
        
        # Fallback to any available model
        if available_models:
            return available_models[0]
        
        return None
    
    def get_available_models(self) -> List[str]:
        """Get list of currently available models"""
        available = []
        
        # Check LM Studio models
        try:
            response = requests.get(f"{self.config.get('LM_STUDIO_URL', 'http://localhost:1234')}/v1/models", timeout=5)
            if response.status_code == 200:
                models = response.json().get('data', [])
                for model in models:
                    model_id = model.get('id')
                    if model_id in self.model_configs:
                        available.append(model_id)
        except Exception as e:
            logger.warning(f"Error checking LM Studio models: {e}")
        
        # Check Ollama models
        try:
            response = requests.get(f"{self.config.get('OLLAMA_URL', 'http://localhost:11434')}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                for model in models:
                    model_name = model.get('name')
                    if model_name in self.model_configs:
                        available.append(model_name)
        except Exception as e:
            logger.warning(f"Error checking Ollama models: {e}")
        
        return available
    
    def generate_response(self, prompt: str, context: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate response using the best available model for the task"""
        # Detect task type
        task_type = self.detect_task_type(prompt, context)
        
        # Get best model for this task
        model_name = self.get_best_model(task_type, context)
        
        if not model_name:
            return {
                'response': 'Error: No suitable models available',
                'model_used': None,
                'task_type': task_type.value,
                'error': 'No models available'
            }
        
        # Get model configuration
        model_config = self.model_configs.get(model_name, {})
        
        # Generate response
        try:
            if model_config['provider'] == ModelProvider.LM_STUDIO:
                response = self._generate_lm_studio_response(model_name, prompt, context, config, model_config)
            elif model_config['provider'] == ModelProvider.OLLAMA:
                response = self._generate_ollama_response(model_name, prompt, context, config, model_config)
            else:
                raise ValueError(f"Unknown provider: {model_config['provider']}")
            
            return {
                'response': response,
                'model_used': model_name,
                'task_type': task_type.value,
                'provider': model_config['provider'].value,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating response with {model_name}: {e}")
            return {
                'response': f'Error generating response: {str(e)}',
                'model_used': model_name,
                'task_type': task_type.value,
                'error': str(e)
            }
    
    def _generate_lm_studio_response(self, model_name: str, prompt: str, context: Dict[str, Any], config: Dict[str, Any], model_config: Dict[str, Any]) -> str:
        """Generate response using LM Studio"""
        base_url = model_config['base_url']
        
        # Prepare messages
        messages = []
        
        # Add system prompt if provided
        if context.get('system_prompt'):
            messages.append({
                'role': 'system',
                'content': context['system_prompt']
            })
        
        # Add campaign context if available
        if context.get('campaign_context'):
            messages.append({
                'role': 'system',
                'content': f"Campaign Context: {context['campaign_context']}"
            })
        
        # Add user prompt
        messages.append({
            'role': 'user',
            'content': prompt
        })
        
        # Prepare payload
        payload = {
            'model': model_name,
            'messages': messages,
            'max_tokens': config.get('max_tokens', model_config.get('max_tokens', 1024)),
            'temperature': config.get('temperature', model_config.get('temperature', 0.7)),
            'stream': False
        }
        
        # Make request
        response = requests.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            timeout=config.get('timeout', 30),
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            raise Exception(f"LM Studio API error: {response.status_code} - {response.text}")
    
    def _generate_ollama_response(self, model_name: str, prompt: str, context: Dict[str, Any], config: Dict[str, Any], model_config: Dict[str, Any]) -> str:
        """Generate response using Ollama"""
        base_url = model_config['base_url']
        
        # Prepare full prompt with context
        full_prompt = prompt
        
        if context.get('system_prompt'):
            full_prompt = f"System: {context['system_prompt']}\n\nUser: {prompt}"
        
        if context.get('campaign_context'):
            full_prompt = f"Campaign Context: {context['campaign_context']}\n\n{full_prompt}"
        
        # Prepare payload
        payload = {
            'model': model_name,
            'prompt': full_prompt,
            'stream': False,
            'options': {
                'temperature': config.get('temperature', model_config.get('temperature', 0.7)),
                'num_predict': config.get('max_tokens', model_config.get('max_tokens', 1024))
            }
        }
        
        # Make request
        response = requests.post(
            f"{base_url}/api/generate",
            json=payload,
            timeout=config.get('timeout', 30),
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            return response.json()['response']
        else:
            raise Exception(f"Ollama API error: {response.status_code} - {response.text}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status for all models"""
        available_models = self.get_available_models()
        
        status = {
            'total_models': len(self.model_configs),
            'available_models': len(available_models),
            'models': {}
        }
        
        for model_name, model_config in self.model_configs.items():
            is_available = model_name in available_models
            status['models'][model_name] = {
                'available': is_available,
                'provider': model_config['provider'].value,
                'specialties': [t.value for t in model_config['specialties']],
                'description': model_config['description']
            }
        
        return status

def create_model_router(config: Dict[str, Any]) -> ModelRouter:
    """Create and initialize ModelRouter instance"""
    return ModelRouter(config)
