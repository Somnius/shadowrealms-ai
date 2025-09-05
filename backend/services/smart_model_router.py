#!/usr/bin/env python3
"""
ShadowRealms AI - Smart Model Router
Resource-efficient model routing for 16GB VRAM system
"""

import os
import json
import logging
import requests
import time
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TaskType(Enum):
    """Types of AI tasks for model routing"""
    ROLEPLAY = "roleplay"
    WORLD_BUILDING = "world_building"
    STORYTELLING = "storytelling"
    CREATIVE = "creative"
    GREEK_CONTENT = "greek_content"
    DICE_ROLLING = "dice_rolling"
    COMBAT = "combat"
    CHARACTER_CREATION = "character_creation"
    GENERAL = "general"

class ModelProvider(Enum):
    """Available model providers"""
    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"

class SmartModelRouter:
    """Resource-efficient model routing system for 16GB VRAM"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Model configurations with VRAM requirements
        self.model_configs = {
            # Primary models (always available)
            'mythomakisemerged-13b': {
                'provider': ModelProvider.LM_STUDIO,
                'base_url': config.get('LM_STUDIO_URL', 'http://localhost:1234'),
                'specialties': [TaskType.ROLEPLAY, TaskType.CHARACTER_CREATION, TaskType.GENERAL],
                'vram_usage': 8,  # GB
                'max_tokens': 1024,
                'temperature': 0.8,
                'description': 'Primary roleplay and character consistency',
                'priority': 1  # Always loaded
            },
            'llama3.2:3b': {
                'provider': ModelProvider.OLLAMA,
                'base_url': config.get('OLLAMA_URL', 'http://localhost:11434'),
                'specialties': [TaskType.DICE_ROLLING, TaskType.COMBAT, TaskType.GENERAL],
                'vram_usage': 2,  # GB
                'max_tokens': 512,
                'temperature': 0.6,
                'description': 'Fast responses for game mechanics',
                'priority': 1  # Always loaded
            },
            
            # Specialized models (load on demand)
            'meltemi-7b-v1-i1': {
                'provider': ModelProvider.LM_STUDIO,
                'base_url': config.get('LM_STUDIO_URL', 'http://localhost:1234'),
                'specialties': [TaskType.GREEK_CONTENT],
                'vram_usage': 5,  # GB
                'max_tokens': 512,
                'temperature': 0.7,
                'description': 'Greek language model',
                'priority': 2  # Load on demand
            },
            'command-r:35b': {
                'provider': ModelProvider.OLLAMA,
                'base_url': config.get('OLLAMA_URL', 'http://localhost:11434'),
                'specialties': [TaskType.STORYTELLING, TaskType.WORLD_BUILDING],
                'vram_usage': 20,  # GB - too large for always-on
                'max_tokens': 2048,
                'temperature': 0.8,
                'description': 'Complex storytelling and world-building',
                'priority': 3  # Load only when needed
            }
        }
        
        # Task routing priorities (fallback order)
        self.task_routing = {
            TaskType.ROLEPLAY: ['mythomakisemerged-13b', 'llama3.2:3b'],
            TaskType.WORLD_BUILDING: ['command-r:35b', 'mythomakisemerged-13b'],
            TaskType.STORYTELLING: ['command-r:35b', 'mythomakisemerged-13b'],
            TaskType.CREATIVE: ['mythomakisemerged-13b', 'llama3.2:3b'],
            TaskType.GREEK_CONTENT: ['meltemi-7b-v1-i1', 'mythomakisemerged-13b'],
            TaskType.DICE_ROLLING: ['llama3.2:3b', 'mythomakisemerged-13b'],
            TaskType.COMBAT: ['llama3.2:3b', 'mythomakisemerged-13b'],
            TaskType.CHARACTER_CREATION: ['mythomakisemerged-13b', 'llama3.2:3b'],
            TaskType.GENERAL: ['mythomakisemerged-13b', 'llama3.2:3b']
        }
        
        # Model state tracking
        self.loaded_models = set()
        self.model_last_used = {}
        self.model_timeout = 300  # 5 minutes
        self.max_vram_usage = 14  # Leave 2GB buffer
        
        logger.info("SmartModelRouter initialized for 16GB VRAM system")
    
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
    
    def get_current_vram_usage(self) -> int:
        """Calculate current VRAM usage"""
        total_vram = 0
        for model_name in self.loaded_models:
            if model_name in self.model_configs:
                total_vram += self.model_configs[model_name]['vram_usage']
        return total_vram
    
    def can_load_model(self, model_name: str) -> bool:
        """Check if we can load a model without exceeding VRAM limits"""
        if model_name not in self.model_configs:
            return False
        
        required_vram = self.model_configs[model_name]['vram_usage']
        current_vram = self.get_current_vram_usage()
        
        return (current_vram + required_vram) <= self.max_vram_usage
    
    def unload_old_models(self):
        """Unload models that haven't been used recently"""
        current_time = time.time()
        models_to_unload = []
        
        for model_name, last_used in self.model_last_used.items():
            if current_time - last_used > self.model_timeout:
                models_to_unload.append(model_name)
        
        for model_name in models_to_unload:
            if model_name in self.loaded_models and self.model_configs[model_name]['priority'] > 1:
                self.unload_model(model_name)
                logger.info(f"Unloaded unused model: {model_name}")
    
    def load_model(self, model_name: str) -> bool:
        """Load a model if possible"""
        if model_name in self.loaded_models:
            self.model_last_used[model_name] = time.time()
            return True
        
        if not self.can_load_model(model_name):
            # Try to unload old models first
            self.unload_old_models()
            if not self.can_load_model(model_name):
                logger.warning(f"Cannot load {model_name}: insufficient VRAM")
                return False
        
        # Load the model
        self.loaded_models.add(model_name)
        self.model_last_used[model_name] = time.time()
        logger.info(f"Loaded model: {model_name}")
        return True
    
    def unload_model(self, model_name: str):
        """Unload a model to free VRAM"""
        if model_name in self.loaded_models:
            self.loaded_models.remove(model_name)
            if model_name in self.model_last_used:
                del self.model_last_used[model_name]
            logger.info(f"Unloaded model: {model_name}")
    
    def get_best_model(self, task_type: TaskType, context: Dict[str, Any]) -> Optional[str]:
        """Get the best available model for a specific task type"""
        # Get priority list for this task type
        priority_models = self.task_routing.get(task_type, [])
        
        # Try to load models in priority order
        for model_name in priority_models:
            if model_name in self.model_configs:
                # Check if it's a priority 1 model (always loaded)
                if self.model_configs[model_name]['priority'] == 1:
                    if model_name in self.loaded_models:
                        return model_name
                else:
                    # Try to load specialized model
                    if self.load_model(model_name):
                        return model_name
        
        # Fallback to any loaded model
        if self.loaded_models:
            return list(self.loaded_models)[0]
        
        return None
    
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
            
            # Update last used time
            self.model_last_used[model_name] = time.time()
            
            return {
                'response': response,
                'model_used': model_name,
                'task_type': task_type.value,
                'provider': model_config['provider'].value,
                'vram_usage': self.get_current_vram_usage(),
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
            'loaded_models': list(self.loaded_models),
            'current_vram_usage': self.get_current_vram_usage(),
            'max_vram_usage': self.max_vram_usage,
            'models': {}
        }
        
        for model_name, model_config in self.model_configs.items():
            is_available = model_name in available_models
            is_loaded = model_name in self.loaded_models
            
            status['models'][model_name] = {
                'available': is_available,
                'loaded': is_loaded,
                'provider': model_config['provider'].value,
                'specialties': [t.value for t in model_config['specialties']],
                'vram_usage': model_config['vram_usage'],
                'priority': model_config['priority'],
                'description': model_config['description']
            }
        
        return status
    
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

def create_smart_model_router(config: Dict[str, Any]) -> SmartModelRouter:
    """Create and initialize SmartModelRouter instance"""
    return SmartModelRouter(config)
