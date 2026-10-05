#!/usr/bin/env python3
"""
ShadowRealms AI - RAG Service
Comprehensive memory system for campaign continuity and context awareness
"""

import os
import json
import logging
import hashlib
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import chromadb
import requests

logger = logging.getLogger(__name__)

# Rule-book share of the RAG budget when the message is about rules (placed first, so the
# memory sections are cut before the books are).
DEFAULT_RULE_BOOK_BUDGET_TOKENS = 1200


def rule_book_budget_tokens() -> int:
    """RULE_BOOK_BUDGET_TOKENS env, default 1,200."""
    try:
        return max(0, int(os.environ.get('RULE_BOOK_BUDGET_TOKENS', '') or DEFAULT_RULE_BOOK_BUDGET_TOKENS))
    except ValueError:
        return DEFAULT_RULE_BOOK_BUDGET_TOKENS


def embed_query(text: str) -> Optional[List[float]]:
    """
    The message's embedding with the app's embedder, or None when it is unavailable.
    One reply embeds the player's message once and passes it to every collection query
    (query_embeddings), instead of each query embedding the same text again.
    """
    from services.vector_store import embedding_function

    try:
        # Chroma's embedding-function wrapper hands back numpy float32 arrays, which
        # query_embeddings refuses: plain floats.
        return [float(x) for x in embedding_function()([str(text or '')])[0]]
    except Exception as e:  # noqa: BLE001 - retrieval must never break a reply
        logger.warning(f"Could not embed the query: {e}")
        return None


def _query_args(query: str, query_embedding: Optional[List[float]]) -> Dict[str, Any]:
    if query_embedding is not None:
        return {'query_embeddings': [query_embedding]}
    return {'query_texts': [query]}


def connect_chroma(config: Dict[str, Any]):
    """ChromaDB HTTP client from config/env (CHROMADB_HOST / CHROMADB_PORT)."""
    host = config.get('CHROMADB_HOST') or os.environ.get('CHROMADB_HOST') or 'localhost'
    port = int(config.get('CHROMADB_PORT') or os.environ.get('CHROMADB_PORT') or 8000)
    return chromadb.HttpClient(host=host, port=port)


class RAGService:
    """Retrieval-Augmented Generation service for campaign memory"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.chroma_host = config.get('CHROMADB_HOST', 'localhost')
        self.chroma_port = config.get('CHROMADB_PORT', 8000)
        
        # Initialize ChromaDB client with retry logic
        max_retries = 10
        retry_delay = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                self.client = connect_chroma(config)
                logger.info(f"✅ Connected to ChromaDB at {self.chroma_host}:{self.chroma_port}")
                break
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(f"ChromaDB connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect to ChromaDB after {max_retries} attempts: {e}")
                    raise RuntimeError(f"Could not connect to ChromaDB at {self.chroma_host}:{self.chroma_port}") from last_error
        
        # Collection names for different types of memory
        self.collections = {
            'campaigns': 'campaign_memory',
            'characters': 'character_memory', 
            'world': 'world_memory',
            'sessions': 'session_memory',
            'rules': 'rules_memory',
            'messages': 'message_memory',
        }
        
        # Initialize collections
        self._initialize_collections()
        
        logger.info("RAG Service initialized with ChromaDB")
    
    def _initialize_collections(self):
        """Get or create every collection with the shared embedder (services/vector_store.py)."""
        from services.vector_store import get_rag_collection

        for collection_name in self.collections.values():
            try:
                get_rag_collection(self.client, collection_name)
            except ValueError as e:
                # Built with another embedder: the startup / admin re-embed rebuilds it.
                logger.warning(f"Collection {collection_name} needs re-embedding: {e}")
            except Exception as e:
                logger.error(f"Could not open collection {collection_name}: {e}")
    
    def _get_collection(self, memory_type: str):
        """Get collection by memory type (shared embedder; ValueError if it needs re-embedding)."""
        from services.vector_store import get_rag_collection

        collection_name = self.collections.get(memory_type, 'campaign_memory')
        return get_rag_collection(self.client, collection_name)
    
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
    
    def retrieve_memories(self, query: str, memory_type: str, campaign_id: int, limit: int = 5,
                          query_embedding: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant memories for a query (query_embedding: the query already embedded)"""
        try:
            collection = self._get_collection(memory_type)
            
            # Query with campaign filter
            results = collection.query(
                **_query_args(query, query_embedding),
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
    
    def store_message_embedding(self, message_id: int, campaign_id: int, location_id: int, 
                                  user_id: int, content: str, role: str, character_name: str = None) -> str:
        """Store a chat message embedding for semantic search"""
        try:
            if 'messages' not in self.collections:
                self.collections['messages'] = 'message_memory'
            
            # Build metadata
            metadata = {
                'campaign_id': campaign_id,
                'location_id': location_id,
                'user_id': user_id,
                'message_id': message_id,
                'role': role,
                'timestamp': datetime.now().isoformat()
            }
            
            if character_name:
                metadata['character_name'] = character_name
            
            # Store in ChromaDB
            collection = self._get_collection('messages')
            doc_id = f"msg_{message_id}_{campaign_id}"
            
            collection.add(
                documents=[content],
                metadatas=[metadata],
                ids=[doc_id]
            )
            
            logger.info(f"Stored message embedding for message {message_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Error storing message embedding: {e}")
            return None

    def delete_message_embeddings(self, message_ids: List[int], campaign_id: int) -> None:
        """Drop the embeddings of deleted chat messages (ids as store_message_embedding made them)."""
        if not message_ids:
            return
        try:
            if 'messages' not in self.collections:
                self.collections['messages'] = 'message_memory'
            collection = self._get_collection('messages')
            collection.delete(ids=[f"msg_{int(mid)}_{int(campaign_id)}" for mid in message_ids])
        except Exception as e:
            logger.warning(f"Could not delete message embeddings: {e}")

    def retrieve_relevant_messages(self, query: str, campaign_id: int, location_id: int = None, 
                                     limit: int = 5, min_relevance: float = 0.7,
                                     query_embedding: Optional[List[float]] = None) -> List[Dict[str, Any]]:
        """Retrieve semantically relevant messages from conversation history"""
        try:
            # Ensure messages collection exists
            if 'messages' not in self.collections:
                self.collections['messages'] = 'message_memory'
            
            collection = self._get_collection('messages')
            
            # Build where clause
            # Chroma wants one operator per where: several fields go under $and.
            where_clause = {"campaign_id": campaign_id}
            if location_id:
                where_clause = {"$and": [{"campaign_id": campaign_id}, {"location_id": location_id}]}
            
            # Query for relevant messages
            results = collection.query(
                **_query_args(query, query_embedding),
                n_results=limit * 2,  # Get extra results to filter by relevance
                where=where_clause
            )
            
            relevant_messages = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    distance = results['distances'][0][i] if results['distances'] else 1.0
                    relevance = 1.0 - distance  # Convert distance to relevance score
                    
                    # Only include if above relevance threshold
                    if relevance >= min_relevance:
                        message = {
                            'content': doc,
                            'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                            'relevance': relevance
                        }
                        relevant_messages.append(message)
                
                # Limit to requested number of results
                relevant_messages = relevant_messages[:limit]
            
            logger.info(f"Retrieved {len(relevant_messages)} relevant messages (threshold: {min_relevance})")
            return relevant_messages
            
        except Exception as e:
            logger.error(f"Error retrieving relevant messages: {e}")
            return []
    
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
    
    def get_campaign_context(self, campaign_id: int, query: str = None,
                             query_embedding: Optional[List[float]] = None) -> Dict[str, Any]:
        """Get comprehensive campaign context (query_embedding: `query` already embedded)"""
        context = {
            'campaign_data': [],
            'characters': [],
            'world_data': [],
            'recent_sessions': [],
            'rules': []
        }
        
        # Get campaign data
        if query:
            context['campaign_data'] = self.retrieve_memories(query, 'campaigns', campaign_id, 3, query_embedding)
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
        
        emb = query_embedding if query else None
        context['characters'] = self.retrieve_memories(query or "character", 'characters', campaign_id, 5, emb)
        context['world_data'] = self.retrieve_memories(query or "world", 'world', campaign_id, 3, emb)
        context['recent_sessions'] = self.retrieve_memories(query or "session", 'sessions', campaign_id, 3, emb)
        context['rules'] = self.retrieve_memories(query or "rules", 'rules', campaign_id, 2, emb)
        
        return context
    
    def _rule_book_collection(self, name: str):
        """A rule book collection (written by books/import_books.py), or None when missing."""
        from services.vector_store import embedding_function

        try:
            return self.client.get_collection(name, embedding_function=embedding_function())
        except Exception as e:  # noqa: BLE001 - not imported yet, or Chroma down
            logger.debug(f"Rule book collection {name} unavailable: {e}")
            return None

    def get_rule_book_context(
        self,
        query: str,
        campaign_id: int,
        rules_edition: Optional[str] = None,
        game_system: Optional[str] = None,
        intent: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
        plan: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rule book chunks for one message (docs/rules/RULE_BOOKS_RAG.md).

        Laya's intent picks the kinds and how many (services.rules_edition.rule_book_plan;
        general → nothing, no query at all). Searches the edition's global books, filtered
        to the chronicle's game line or 'all', plus the books attached to this chronicle;
        drops chunks farther than the plan's cosine distance; best first, at most k.
        """
        from services.rules_edition import rule_book_plan, rule_book_queries

        plan = plan if plan is not None else rule_book_plan(intent)
        if not plan:
            return []
        targets = []
        for name, where in rule_book_queries(campaign_id, rules_edition, game_system, plan['kinds']):
            col = self._rule_book_collection(name)
            if col is not None:
                targets.append((name, col, where))
        if not targets:
            return []
        if query_embedding is None:
            query_embedding = embed_query(query)
            if query_embedding is None:
                return []

        chunks = []
        for name, col, where in targets:
            try:
                res = col.query(
                    query_embeddings=[query_embedding], n_results=plan['k'], where=where,
                    include=['documents', 'metadatas', 'distances'],
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"Error querying {name}: {e}")
                continue
            docs = (res.get('documents') or [[]])[0] or []
            metas = (res.get('metadatas') or [[]])[0] or []
            dists = (res.get('distances') or [[]])[0] or []
            for i, doc in enumerate(docs):
                dist = float(dists[i]) if i < len(dists) and dists[i] is not None else 1.0
                if dist > plan['max_distance']:
                    continue
                meta = (metas[i] if i < len(metas) else None) or {}
                chunks.append({'content': doc, 'metadata': meta, 'distance': dist,
                               'relevance': 1 - dist, 'collection': name})
        chunks.sort(key=lambda c: (c['distance'], c['metadata'].get('precedence', 99)))
        chunks = chunks[:plan['k']]
        logger.info(
            "Rule books: %d chunks (kinds %s, cutoff %.2f) for: %s",
            len(chunks), ",".join(plan['kinds']), plan['max_distance'], (query or '')[:50],
        )
        return chunks

    @staticmethod
    def format_rule_book_chunks(chunks: List[Dict[str, Any]]) -> List[str]:
        """Prompt lines for rule book chunks: '[Title › heading_path, p. N]' then the text."""
        from services.rules_edition import rule_book_citation, rule_book_text

        return [f"[{rule_book_citation(c['metadata'])}]\n{rule_book_text(c['content'], c['metadata'])}"
                for c in chunks]

    @staticmethod
    def _fit(parts: List[str], max_tokens: Optional[int]) -> List[str]:
        """Keep whole parts in order while they fit; cut the last one; no dangling header."""
        if max_tokens is None or not parts:
            return parts
        from services.storyteller_prompt import estimate_tokens, truncate_to_tokens

        kept, used = [], 0
        for part in parts:
            cost = estimate_tokens(part) + 1
            if used + cost > max_tokens:
                room = max_tokens - used
                if room > 80 and not part.startswith("==="):
                    kept.append(truncate_to_tokens(part, room))
                break
            kept.append(part)
            used += cost
        while kept and kept[-1].startswith("==="):
            kept.pop()
        return kept

    def augment_prompt(self, prompt: str, campaign_id: int, user_id: int = None, include_rule_books: bool = True,
                       rules_edition: Optional[str] = None, max_tokens: Optional[int] = None,
                       game_system: Optional[str] = None, intent: Optional[Dict[str, Any]] = None,
                       query_embedding: Optional[List[float]] = None) -> str:
        """
        Augment prompt with relevant context from memory.

        The campaign record itself is not added: callers put the campaign header in the
        system prompt already. max_tokens caps the added sections (whole sections/chunks are
        dropped from the end, the last one is cut); the request itself is always kept.

        The prompt is embedded once (or query_embedding is used) for every query here.
        Rule books follow Laya's intent (services.rules_edition.rule_book_plan). For a rules
        message they come first with their own budget (RULE_BOOK_BUDGET_TOKENS, within
        max_tokens), so the memory sections are cut before them; lore chunks go last.
        """
        from services.rules_edition import rule_book_plan

        if query_embedding is None:
            query_embedding = embed_query(prompt)
        context = self.get_campaign_context(campaign_id, prompt, query_embedding=query_embedding)

        memory_parts = []
        for key, header in (('characters', 'CHARACTERS'), ('world_data', 'WORLD SETTING'),
                            ('recent_sessions', 'RECENT SESSIONS'), ('rules', 'GAME RULES')):
            if context[key]:
                memory_parts.append(f"=== {header} ===")
                memory_parts.extend(m['content'] for m in context[key])

        book_parts = []
        plan = rule_book_plan(intent) if include_rule_books else None
        if plan:
            chunks = self.get_rule_book_context(
                prompt, campaign_id, rules_edition=rules_edition, game_system=game_system,
                query_embedding=query_embedding, plan=plan,
            )
            if chunks:
                book_parts = ["=== OFFICIAL RULE BOOKS ==="] + self.format_rule_book_chunks(chunks)

        if plan and plan['rules'] and book_parts:
            book_budget = rule_book_budget_tokens()
            if max_tokens is not None:
                book_budget = min(book_budget, max_tokens)
            book_parts = self._fit(book_parts, book_budget)
            if max_tokens is not None:
                from services.storyteller_prompt import estimate_tokens

                left = max_tokens - sum(estimate_tokens(p) + 1 for p in book_parts)
                memory_parts = self._fit(memory_parts, max(0, left))
            context_parts = book_parts + memory_parts
        else:
            context_parts = self._fit(memory_parts + book_parts, max_tokens)

        if context_parts:
            context_string = "\n\n".join(context_parts)
            return f"{context_string}\n\n=== CURRENT REQUEST ===\n{prompt}"
        return prompt
    
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
        from services.embedding_service import configured_embedding_model

        status = {
            'chromadb_connected': False,
            'embedding_model': configured_embedding_model(),
            'collections': {},
            'total_memories': 0
        }
        
        try:
            # Test ChromaDB connection
            self.client.heartbeat()
            status['chromadb_connected'] = True
            
            # Get collection info
            from services.rules_edition import ALL_RULE_BOOK_COLLECTIONS

            names = list(self.collections.items()) + [(n, n) for n in ALL_RULE_BOOK_COLLECTIONS]
            for memory_type, collection_name in names:
                try:
                    collection = self.client.get_collection(collection_name)  # count only: any embedder
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


_shared_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Shared RAG service built from the Flask app config (message memory, location cleanup)."""
    global _shared_rag_service
    if _shared_rag_service is None:
        from flask import current_app
        _shared_rag_service = create_rag_service(current_app.config)
    return _shared_rag_service
