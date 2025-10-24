#!/usr/bin/env python3
"""
ShadowRealms AI - RAG Service
Comprehensive memory system for campaign continuity and context awareness
"""

import os
import json
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings
import requests

logger = logging.getLogger(__name__)

class RAGService:
    """Retrieval-Augmented Generation service for campaign memory"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.chroma_host = config.get('CHROMADB_HOST', 'localhost')
        self.chroma_port = config.get('CHROMADB_PORT', 8000)
        
        # Initialize ChromaDB client
        self.client = chromadb.HttpClient(
            host=self.chroma_host,
            port=self.chroma_port,
            settings=Settings(allow_reset=True)
        )
        
        # Collection names for different types of memory
        self.collections = {
            'campaigns': 'campaign_memory',
            'characters': 'character_memory', 
            'world': 'world_memory',
            'sessions': 'session_memory',
            'rules': 'rules_memory',
            'rule_books': 'rule_books'
        }
        
        # Initialize collections
        self._initialize_collections()
        
        logger.info("RAG Service initialized with ChromaDB")
    
    def _initialize_collections(self):
        """Initialize all required collections"""
        for collection_name in self.collections.values():
            try:
                # Try to get existing collection
                self.client.get_collection(collection_name)
                logger.info(f"Collection {collection_name} already exists")
            except:
                # Create new collection
                self.client.create_collection(
                    name=collection_name,
                    metadata={"description": f"Memory collection for {collection_name}"}
                )
                logger.info(f"Created collection {collection_name}")
    
    def _get_collection(self, memory_type: str):
        """Get collection by memory type"""
        collection_name = self.collections.get(memory_type, 'campaign_memory')
        return self.client.get_collection(collection_name)
    
    def _generate_id(self, content: str, context: Dict[str, Any]) -> str:
        """Generate unique ID for memory entry"""
        # Create hash from content and context
        hash_input = f"{content}_{context.get('campaign_id', '')}_{context.get('user_id', '')}_{datetime.now().isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def store_memory(self, content: str, memory_type: str, context: Dict[str, Any], metadata: Dict[str, Any] = None) -> str:
        """Store memory in appropriate collection"""
        try:
            collection = self._get_collection(memory_type)
            
            # Generate unique ID
            memory_id = self._generate_id(content, context)
            
            # Prepare metadata
            full_metadata = {
                'campaign_id': context.get('campaign_id', 0),  # Use 0 for global/system-wide
                'user_id': context.get('user_id', 0),         # Use 0 for system content
                'memory_type': memory_type,
                'timestamp': datetime.now().isoformat(),
                'content_length': len(content)
            }
            
            if metadata:
                full_metadata.update(metadata)
            
            # Filter out None values to prevent ChromaDB validation errors
            full_metadata = {k: v for k, v in full_metadata.items() if v is not None}
            
            # Store in ChromaDB
            collection.add(
                documents=[content],
                metadatas=[full_metadata],
                ids=[memory_id]
            )
            
            logger.info(f"Stored memory: {memory_type} - {memory_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            return None
    
    def retrieve_memories(self, query: str, memory_type: str, campaign_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant memories for a query"""
        try:
            collection = self._get_collection(memory_type)
            
            # Query with campaign filter
            results = collection.query(
                query_texts=[query],
                n_results=limit,
                where={"campaign_id": campaign_id}
            )
            
            memories = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    memory = {
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0.0
                    }
                    memories.append(memory)
            
            logger.info(f"Retrieved {len(memories)} memories for query: {query[:50]}...")
            return memories
            
        except Exception as e:
            logger.error(f"Error retrieving memories: {e}")
            return []
    
    def store_campaign_data(self, campaign_id: int, data: Dict[str, Any]) -> str:
        """Store campaign-specific data"""
        content = json.dumps(data, indent=2)
        context = {'campaign_id': campaign_id, 'user_id': 'system'}
        metadata = {'data_type': 'campaign_config'}
        
        return self.store_memory(content, 'campaigns', context, metadata)
    
    def store_character_data(self, character_id: int, campaign_id: int, character_data: Dict[str, Any]) -> str:
        """Store character-specific data"""
        content = json.dumps(character_data, indent=2)
        context = {'campaign_id': campaign_id, 'character_id': character_id}
        metadata = {'data_type': 'character_sheet'}
        
        return self.store_memory(content, 'characters', context, metadata)
    
    def store_world_data(self, campaign_id: int, world_data: Dict[str, Any]) -> str:
        """Store world-building data"""
        content = json.dumps(world_data, indent=2)
        context = {'campaign_id': campaign_id, 'user_id': 'system'}
        metadata = {'data_type': 'world_building'}
        
        return self.store_memory(content, 'world', context, metadata)
    
    def store_session_data(self, session_id: int, campaign_id: int, session_data: Dict[str, Any]) -> str:
        """Store session-specific data"""
        content = json.dumps(session_data, indent=2)
        context = {'campaign_id': campaign_id, 'session_id': session_id}
        metadata = {'data_type': 'session_log'}
        
        return self.store_memory(content, 'sessions', context, metadata)
    
    def store_rules_data(self, campaign_id: int, rules_data: Dict[str, Any]) -> str:
        """Store game rules and system data"""
        content = json.dumps(rules_data, indent=2)
        context = {'campaign_id': campaign_id, 'user_id': 'system'}
        metadata = {'data_type': 'game_rules'}
        
        return self.store_memory(content, 'rules', context, metadata)
    
    def get_campaign_context(self, campaign_id: int, query: str = None) -> Dict[str, Any]:
        """Get comprehensive campaign context"""
        context = {
            'campaign_data': [],
            'characters': [],
            'world_data': [],
            'recent_sessions': [],
            'rules': []
        }
        
        # Get campaign data
        if query:
            context['campaign_data'] = self.retrieve_memories(query, 'campaigns', campaign_id, 3)
        else:
            # Get all campaign data
            try:
                collection = self._get_collection('campaigns')
                results = collection.get(where={"campaign_id": campaign_id})
                if results['documents']:
                    for i, doc in enumerate(results['documents']):
                        context['campaign_data'].append({
                            'content': doc,
                            'metadata': results['metadatas'][i] if results['metadatas'] else {}
                        })
            except Exception as e:
                logger.error(f"Error getting campaign data: {e}")
        
        # Get character data
        context['characters'] = self.retrieve_memories(query or "character", 'characters', campaign_id, 5)
        
        # Get world data
        context['world_data'] = self.retrieve_memories(query or "world", 'world', campaign_id, 3)
        
        # Get recent sessions
        context['recent_sessions'] = self.retrieve_memories(query or "session", 'sessions', campaign_id, 3)
        
        # Get rules
        context['rules'] = self.retrieve_memories(query or "rules", 'rules', campaign_id, 2)
        
        return context
    
    def get_rule_book_context(self, query: str, campaign_id: int, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Get relevant context from official rule books using semantic search.
        
        Args:
            query: The query to search for
            campaign_id: Campaign ID to filter by
            n_results: Number of chunks to retrieve
            
        Returns:
            List of relevant rule book chunks with metadata
        """
        try:
            collection = self._get_collection('rule_books')
            
            # Query the rule books collection
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"campaign_id": campaign_id},
                include=['documents', 'metadatas', 'distances']
            )
            
            rule_book_context = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    chunk = {
                        'content': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0.0,
                        'relevance': 1 - (results['distances'][0][i] if results['distances'] else 0.0)
                    }
                    rule_book_context.append(chunk)
            
            logger.info(f"Retrieved {len(rule_book_context)} rule book chunks for query: {query[:50]}...")
            return rule_book_context
            
        except Exception as e:
            logger.error(f"Error retrieving rule book context: {e}")
            return []
    
    def augment_prompt(self, prompt: str, campaign_id: int, user_id: int = None, include_rule_books: bool = True, n_rule_book_chunks: int = 5) -> str:
        """Augment prompt with relevant context from memory"""
        # Get campaign context
        context = self.get_campaign_context(campaign_id, prompt)
        
        # Build context string
        context_parts = []
        
        # Add campaign data
        if context['campaign_data']:
            context_parts.append("=== CAMPAIGN CONTEXT ===")
            for memory in context['campaign_data']:
                context_parts.append(memory['content'])
        
        # Add character data
        if context['characters']:
            context_parts.append("=== CHARACTERS ===")
            for memory in context['characters']:
                context_parts.append(memory['content'])
        
        # Add world data
        if context['world_data']:
            context_parts.append("=== WORLD SETTING ===")
            for memory in context['world_data']:
                context_parts.append(memory['content'])
        
        # Add recent sessions
        if context['recent_sessions']:
            context_parts.append("=== RECENT SESSIONS ===")
            for memory in context['recent_sessions']:
                context_parts.append(memory['content'])
        
        # Add rules
        if context['rules']:
            context_parts.append("=== GAME RULES ===")
            for memory in context['rules']:
                context_parts.append(memory['content'])
        
        # Add rule book context (NEW!)
        if include_rule_books:
            rule_book_context = self.get_rule_book_context(prompt, campaign_id, n_rule_book_chunks)
            if rule_book_context:
                context_parts.append("=== OFFICIAL RULE BOOKS ===")
                for chunk in rule_book_context:
                    source = f"[{chunk['metadata'].get('filename', 'Unknown')} p.{chunk['metadata'].get('page_number', '?')}]"
                    context_parts.append(f"{source}\n{chunk['content']}")
        
        # Combine with original prompt
        if context_parts:
            context_string = "\n\n".join(context_parts)
            augmented_prompt = f"{context_string}\n\n=== CURRENT REQUEST ===\n{prompt}"
        else:
            augmented_prompt = prompt
        
        return augmented_prompt
    
    def store_interaction(self, prompt: str, response: str, campaign_id: int, user_id: int, interaction_type: str = "general") -> str:
        """Store AI interaction for future reference"""
        interaction_data = {
            'prompt': prompt,
            'response': response,
            'interaction_type': interaction_type,
            'timestamp': datetime.now().isoformat()
        }
        
        content = json.dumps(interaction_data, indent=2)
        context = {'campaign_id': campaign_id, 'user_id': user_id}
        metadata = {'data_type': 'ai_interaction', 'interaction_type': interaction_type}
        
        return self.store_memory(content, 'sessions', context, metadata)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get RAG system status"""
        status = {
            'chromadb_connected': False,
            'collections': {},
            'total_memories': 0
        }
        
        try:
            # Test ChromaDB connection
            self.client.heartbeat()
            status['chromadb_connected'] = True
            
            # Get collection info
            for memory_type, collection_name in self.collections.items():
                try:
                    collection = self.client.get_collection(collection_name)
                    count = collection.count()
                    status['collections'][memory_type] = {
                        'name': collection_name,
                        'count': count
                    }
                    status['total_memories'] += count
                except Exception as e:
                    status['collections'][memory_type] = {
                        'name': collection_name,
                        'error': str(e)
                    }
            
        except Exception as e:
            status['error'] = str(e)
        
        return status

def create_rag_service(config: Dict[str, Any]) -> RAGService:
    """Create and initialize RAG service"""
    return RAGService(config)
