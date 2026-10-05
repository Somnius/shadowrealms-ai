#!/usr/bin/env python3
"""
ShadowRealms AI - Smart Model Router
Resource-efficient model routing for 16GB VRAM system
"""

import os
import json
import logging
import requests

from services.lm_studio_model import (
    LM_STUDIO_ROUTE_KEY,
    get_effective_lm_studio_model_id,
    resolve_lm_studio_model_id,
)
import time
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime, timedelta

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

class TaskType(Enum):
    """Types of AI tasks for model routing"""
    ROLEPLAY = "roleplay"
    WORLD_BUILDING = "world_building"
    STORYTELLING = "storytelling"
    CREATIVE = "creative"
    DICE_ROLLING = "dice_rolling"
    COMBAT = "combat"
    CHARACTER_CREATION = "character_creation"
    RULES = "rules"
    GENERAL = "general"


# Classifier intent label -> TaskType (services/classifier.INTENTS)
INTENT_TASK_TYPES = {
    "dice": TaskType.DICE_ROLLING,
    "combat": TaskType.COMBAT,
    "rules_question": TaskType.RULES,
    "roleplay": TaskType.ROLEPLAY,
    "general": TaskType.GENERAL,
}
INTENT_MIN_SCORE = 0.6

class ModelProvider(Enum):
    """Available model providers"""
    LM_STUDIO = "lm_studio"
    OLLAMA = "ollama"

class SmartModelRouter:
    """Resource-efficient model routing system for 16GB VRAM"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # LM Studio uses a stable route key; OpenAI "model" id is resolved per request
        # (admin override + loaded model — see get_effective_lm_studio_model_id).
        resolve_lm_studio_model_id(
            config.get('LM_STUDIO_URL', 'http://localhost:1234'),
            config.get('LM_STUDIO_MODEL'),
            config.get('LM_STUDIO_API_KEY'),
        )

        self.model_configs = {
            LM_STUDIO_ROUTE_KEY: {
                'provider': ModelProvider.LM_STUDIO,
                'base_url': config.get('LM_STUDIO_URL', 'http://localhost:1234'),
                'specialties': [TaskType.ROLEPLAY, TaskType.CHARACTER_CREATION, TaskType.STORYTELLING, TaskType.WORLD_BUILDING, TaskType.GENERAL],
                'vram_usage': 8,  # GB
                'max_tokens': 1024,
                'temperature': 0.8,
                'description': 'Primary model for all RPG tasks',
                'priority': 1  # Always loaded
            },
            # Fallback model (always available)
            'llama3.2:3b': {
                'provider': ModelProvider.OLLAMA,
                'base_url': config.get('OLLAMA_URL', 'http://localhost:11434'),
                'specialties': [TaskType.DICE_ROLLING, TaskType.COMBAT, TaskType.GENERAL],
                'vram_usage': 2,  # GB
                'max_tokens': 512,
                'temperature': 0.6,
                'description': 'Fast fallback for all tasks',
                'priority': 1  # Always loaded
            }
        }
        
        # Task routing priorities (simplified to 2 models)
        self.task_routing = {
            TaskType.ROLEPLAY: [LM_STUDIO_ROUTE_KEY, 'llama3.2:3b'],
            TaskType.WORLD_BUILDING: [LM_STUDIO_ROUTE_KEY, 'llama3.2:3b'],
            TaskType.STORYTELLING: [LM_STUDIO_ROUTE_KEY, 'llama3.2:3b'],
            TaskType.CREATIVE: [LM_STUDIO_ROUTE_KEY, 'llama3.2:3b'],
            TaskType.DICE_ROLLING: ['llama3.2:3b', LM_STUDIO_ROUTE_KEY],
            TaskType.COMBAT: ['llama3.2:3b', LM_STUDIO_ROUTE_KEY],
            TaskType.CHARACTER_CREATION: [LM_STUDIO_ROUTE_KEY, 'llama3.2:3b'],
            TaskType.RULES: [LM_STUDIO_ROUTE_KEY, 'llama3.2:3b'],
            TaskType.GENERAL: [LM_STUDIO_ROUTE_KEY, 'llama3.2:3b']
        }
        
        # Model state tracking
        self.loaded_models = set()
        self.model_last_used = {}
        self.model_timeout = 300  # 5 minutes
        self.max_vram_usage = 14  # Leave 2GB buffer
        
        # Load priority 1 models on startup
        self._load_priority_models()
        
        logger.info("SmartModelRouter initialized for 16GB VRAM system")
    
    def _load_priority_models(self):
        """Load priority 1 models on startup"""
        for model_name, config in self.model_configs.items():
            if config['priority'] == 1:
                if self.load_model(model_name):
                    logger.info(f"✅ Loaded priority model: {model_name}")
                else:
                    logger.warning(f"⚠️  Failed to load priority model: {model_name}")
    
    def detect_task_type(self, prompt: str, context: Dict[str, Any]) -> TaskType:
        """
        Task type of the player's message. The classifier's intent (Laya / Jev) when one is
        configured and confident; otherwise the keyword rules below. Uses the raw player
        message (context['player_message']) rather than the RAG-augmented prompt.
        """
        text = str(context.get('player_message') or prompt or '')
        if 'laya_intent' in context:
            # Already classified for this message (LLMService.generate_response): reuse it.
            intent = context['laya_intent']
            if intent and intent.get('score', 0) >= INTENT_MIN_SCORE and intent.get('label') in INTENT_TASK_TYPES:
                return INTENT_TASK_TYPES[intent['label']]
        elif not context.get('skip_classifier'):
            try:
                from services.classifier import classify_intent_fast

                intent = classify_intent_fast(text)
            except Exception as e:  # noqa: BLE001 - routing must never fail on the classifier
                logger.warning(f"Intent classifier failed, using keywords: {e}")
                intent = None
            if intent and intent.get('score', 0) >= INTENT_MIN_SCORE and intent.get('label') in INTENT_TASK_TYPES:
                return INTENT_TASK_TYPES[intent['label']]
        return self.detect_task_type_keywords(text)

    def detect_task_type_keywords(self, prompt: str) -> TaskType:
        """Keyword fallback (the original router rules)."""
        prompt_lower = prompt.lower()

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
    
    @staticmethod
    def resolve_role(task_type: TaskType, context: Dict[str, Any]) -> str:
        """
        AI role (services/ai_roles.ROLES) for this call:
        - context['ai_role'] == 'storyteller' -> storyteller_el / storyteller_en by context['reply_language']
        - an explicit role name is used as is
        - no role: dice/combat -> utility (as the old router did), anything else -> storyteller_en
        """
        from services.ai_roles import ROLES

        hint = str(context.get('ai_role') or '').strip()
        if hint == 'storyteller':
            return 'storyteller_el' if context.get('reply_language') == 'el' else 'storyteller_en'
        if hint in ROLES:
            return hint
        if task_type in (TaskType.DICE_ROLLING, TaskType.COMBAT):
            return 'utility'
        return 'storyteller_en'

    @staticmethod
    def build_messages(prompt: str, context: Dict[str, Any]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        system = str(context.get('system_prompt') or '').strip()
        if context.get('reply_language'):
            from services.language import reply_language_instruction

            instruction = reply_language_instruction(
                context['reply_language'], storyteller=context.get('ai_role') == 'storyteller'
            )
            system = f"{system}\n\n{instruction}".strip()
        if system:
            messages.append({'role': 'system', 'content': system})
        cc = _campaign_context_to_send(context)
        if cc:
            messages.append({'role': 'system', 'content': f"Campaign Context: {cc}"})
        messages.append({'role': 'user', 'content': prompt})
        return messages

    def generate_response(self, prompt: str, context: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Pick the AI role for this message and generate through its provider chain (services/ai_roles)."""
        from services.ai_providers import ProviderError
        from services.ai_roles import generate_for_role

        task_type = self.detect_task_type(prompt, context)
        role = self.resolve_role(task_type, context)
        params = {
            'max_tokens': config.get('max_tokens', 1024),
            'temperature': config.get('temperature', 0.7),
        }
        budget = None
        if context.get('ai_role') == 'storyteller':  # player chat behind nginx's 60 s
            from services.ai_roles import storyteller_timeouts

            attempt_timeout, budget = storyteller_timeouts()
            params['timeout'] = attempt_timeout
        if config.get('timeout'):
            params['timeout'] = config['timeout']
        try:
            messages = self.build_messages(prompt, context)
            res = generate_for_role(role, messages, params, budget_s=budget)
        except ProviderError as e:
            logger.error(f"All providers failed for role {role}: {e}")
            return {
                'response': 'Error: the AI is unavailable right now (all configured models failed).',
                'model_used': None,
                'task_type': task_type.value,
                'role': role,
                'error': str(e),
            }
        text, script_fix = res['text'], None
        if context.get('reply_language') == 'el':
            text, script_fix = self._fix_greek_script(text, role, res, messages, params, budget)
        out = {
            'response': text,
            'model_used': res['model'],
            'provider': res['provider'],
            'role': role,
            'language': context.get('reply_language'),
            'attempts': res['attempts'],
            'ms': res['ms'],
            'task_type': task_type.value,
            'timestamp': datetime.now().isoformat()
        }
        if res.get('trimmed'):
            out['trimmed'] = res['trimmed']
        if script_fix:
            out['script_fix'] = script_fix
        return out

    @staticmethod
    def _fix_greek_script(text, role, res, messages, params, budget):
        """
        Small models writing Greek sometimes drop CJK/Thai/Arabic/Tamil characters into words.
        Retry once on the same model at a lower temperature; if that is still mixed (or fails),
        strip the foreign characters. Returns (text, None | 'retried' | 'stripped').
        """
        from services.ai_providers import ProviderError
        from services.ai_roles import generate_for_role
        from services.storyteller_prompt import foreign_script_chars, strip_foreign_script

        bad = foreign_script_chars(text)
        if not bad:
            return text, None
        logger.warning("Greek reply from %s/%s has %d foreign-script characters (%r); retrying once",
                       res['provider'], res['model'], len(bad), ''.join(bad[:12]))
        retry_params = {**params, 'temperature': max(0.1, float(params.get('temperature') or 0.7) - 0.4)}
        left = (budget or 120) - res['ms'] / 1000.0 - 2
        if left < 5:
            logger.warning("No time left to retry the Greek reply; stripping foreign-script characters")
            return strip_foreign_script(text), 'stripped'
        try:
            again = generate_for_role(role, messages, retry_params, chain=[(res['provider'], res['model'])],
                                      budget_s=left)['text']
            if not foreign_script_chars(again):
                return again, 'retried'
            text = again
        except ProviderError as e:
            logger.warning("Greek script retry failed: %s", e)
        logger.warning("Greek reply still mixed after retry; stripping foreign-script characters")
        return strip_foreign_script(text), 'stripped'

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
            entry = {
                'available': is_available,
                'loaded': is_loaded,
                'provider': model_config['provider'].value,
                'specialties': [t.value for t in model_config['specialties']],
                'vram_usage': model_config['vram_usage'],
                'priority': model_config['priority'],
                'description': model_config['description'],
            }
            if model_name == LM_STUDIO_ROUTE_KEY:
                entry['effective_openai_model_id'] = get_effective_lm_studio_model_id(self.config)
            status['models'][model_name] = entry
        
        return status
    
    def get_available_models(self) -> List[str]:
        """Get list of currently available models"""
        available = []
        
        # Check LM Studio models
        try:
            response = requests.get(f"{self.config.get('LM_STUDIO_URL', 'http://localhost:1234')}/v1/models", timeout=5)
            if response.status_code == 200:
                models = response.json().get('data', [])
                if models:
                    available.append(LM_STUDIO_ROUTE_KEY)
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
