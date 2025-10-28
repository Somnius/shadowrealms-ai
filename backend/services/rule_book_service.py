#!/usr/bin/env python3
"""
Rule Book Service
Processes PDF rule books and integrates them with the RAG system for enhanced AI knowledge.
"""

import logging
import os
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pdfplumber
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class RuleBookProcessor:
    """Processes PDF rule books for RAG integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.books_dir = Path(config.get('BOOKS_DIR', 'books'))
        self.processed_dir = self.books_dir / 'processed'
        self.processed_dir.mkdir(exist_ok=True)
        
        # Rule book metadata
        self.rule_books = {
            'wod_2nd_ed': {
                'name': 'World of Darkness 2nd Edition',
                'file_patterns': ['WOD - World Of Darkness (2nd ed)', 'World Of Darkness (2nd ed)_flat'],
                'system': 'wod',
                'priority': 1,
                'chunk_size': 1000,
                'overlap': 200,
                'specific_path': 'books/oWoD/WOD - World Of Darkness (2nd ed)_flat.pdf'
            },
            'vampire_core': {
                'name': 'Vampire: The Masquerade Core',
                'file_patterns': ['vampire', 'masquerade', 'core'],
                'system': 'vampire',
                'priority': 2,
                'chunk_size': 1000,
                'overlap': 200
            },
            'werewolf_core': {
                'name': 'Werewolf: The Apocalypse Core',
                'file_patterns': ['werewolf', 'apocalypse', 'core'],
                'system': 'werewolf',
                'priority': 2,
                'chunk_size': 1000,
                'overlap': 200
            },
            'mage_core': {
                'name': 'Mage: The Ascension Core',
                'file_patterns': ['mage', 'ascension', 'core'],
                'system': 'mage',
                'priority': 2,
                'chunk_size': 1000,
                'overlap': 200
            },
            'changeling_core': {
                'name': 'Changeling: The Dreaming Core',
                'file_patterns': ['changeling', 'dreaming', 'core'],
                'system': 'changeling',
                'priority': 2,
                'chunk_size': 1000,
                'overlap': 200
            }
        }
    
    def find_rule_books(self, system: str = None) -> List[Dict[str, Any]]:
        """Find rule books in the books directory"""
        found_books = []
        
        for book_id, book_info in self.rule_books.items():
            if system and book_info['system'] != system:
                continue
            
            # Check for specific path first
            if 'specific_path' in book_info:
                specific_file = Path(book_info['specific_path'])
                if specific_file.exists():
                    found_books.append({
                        'book_id': book_id,
                        'book_info': book_info,
                        'file_path': specific_file,
                        'file_size': specific_file.stat().st_size
                    })
                    continue
            
            # Look for matching files
            matching_files = []
            for file_path in self.books_dir.rglob('*.pdf'):
                filename = file_path.name.lower()
                if any(pattern.lower() in filename for pattern in book_info['file_patterns']):
                    matching_files.append(file_path)
            
            if matching_files:
                # Use the most recent or largest file
                best_file = max(matching_files, key=lambda x: x.stat().st_size)
                found_books.append({
                    'book_id': book_id,
                    'book_info': book_info,
                    'file_path': best_file,
                    'file_size': best_file.stat().st_size
                })
        
        return sorted(found_books, key=lambda x: x['book_info']['priority'])
    
    def extract_text_from_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Extract text from PDF with page and section information"""
        pages_data = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text
                    text = page.extract_text()
                    if not text or not text.strip():
                        continue
                    
                    # Clean and process text
                    cleaned_text = self._clean_text(text)
                    
                    # Extract page metadata
                    page_info = {
                        'page_number': page_num + 1,
                        'text': cleaned_text,
                        'word_count': len(cleaned_text.split()),
                        'char_count': len(cleaned_text)
                    }
                    
                    pages_data.append(page_info)
                    
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return []
        
        return pages_data
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers and headers/footers
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Clean up common PDF artifacts
        text = re.sub(r'[^\w\s\.\,\!\?\;\:\-\(\)\[\]\{\}\"\'\/]', '', text)
        
        return text.strip()
    
    def chunk_text(self, pages_data: List[Dict[str, Any]], chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
        """Chunk text into manageable pieces for RAG"""
        chunks = []
        
        for page_data in pages_data:
            text = page_data['text']
            page_num = page_data['page_number']
            
            # Split into sentences first
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            # Create chunks
            current_chunk = ""
            current_sentences = []
            
            for sentence in sentences:
                if len(current_chunk + sentence) > chunk_size and current_chunk:
                    # Save current chunk
                    chunks.append({
                        'text': current_chunk.strip(),
                        'page_number': page_num,
                        'sentence_count': len(current_sentences),
                        'word_count': len(current_chunk.split()),
                        'chunk_id': hashlib.md5(current_chunk.encode()).hexdigest()[:8]
                    })
                    
                    # Start new chunk with overlap
                    overlap_text = ' '.join(current_sentences[-2:]) if len(current_sentences) >= 2 else current_chunk[-overlap:]
                    current_chunk = overlap_text + ' ' + sentence
                    current_sentences = current_sentences[-2:] + [sentence]
                else:
                    current_chunk += ' ' + sentence if current_chunk else sentence
                    current_sentences.append(sentence)
            
            # Add final chunk
            if current_chunk.strip():
                chunks.append({
                    'text': current_chunk.strip(),
                    'page_number': page_num,
                    'sentence_count': len(current_sentences),
                    'word_count': len(current_chunk.split()),
                    'chunk_id': hashlib.md5(current_chunk.encode()).hexdigest()[:8]
                })
        
        return chunks
    
    def process_rule_book(self, book_id: str, file_path: Path) -> Dict[str, Any]:
        """Process a single rule book"""
        logger.info(f"Processing rule book: {book_id} from {file_path}")
        
        # Check if already processed
        processed_file = self.processed_dir / f"{book_id}_processed.json"
        if processed_file.exists():
            logger.info(f"Rule book {book_id} already processed, loading from cache")
            with open(processed_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Extract text
        pages_data = self.extract_text_from_pdf(file_path)
        if not pages_data:
            logger.error(f"No text extracted from {file_path}")
            return None
        
        # Get book configuration
        book_info = self.rule_books[book_id]
        
        # Chunk text
        chunks = self.chunk_text(
            pages_data, 
            chunk_size=book_info['chunk_size'],
            overlap=book_info['overlap']
        )
        
        # Create processing result
        result = {
            'book_id': book_id,
            'book_name': book_info['name'],
            'system': book_info['system'],
            'file_path': str(file_path),
            'processed_at': datetime.now().isoformat(),
            'total_pages': len(pages_data),
            'total_chunks': len(chunks),
            'total_words': sum(page['word_count'] for page in pages_data),
            'chunks': chunks
        }
        
        # Save processed data
        with open(processed_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully processed {book_id}: {len(chunks)} chunks from {len(pages_data)} pages")
        return result
    
    def get_rule_book_chunks(self, book_id: str) -> List[Dict[str, Any]]:
        """Get processed chunks for a rule book"""
        processed_file = self.processed_dir / f"{book_id}_processed.json"
        
        if not processed_file.exists():
            logger.warning(f"Processed file not found for {book_id}")
            return []
        
        with open(processed_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('chunks', [])
    
    def search_rule_books(self, query: str, system: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search through processed rule books"""
        results = []
        
        for book_id, book_info in self.rule_books.items():
            if system and book_info['system'] != system:
                continue
            
            chunks = self.get_rule_book_chunks(book_id)
            if not chunks:
                continue
            
            # Simple text search (will be enhanced with vector search later)
            query_lower = query.lower()
            for chunk in chunks:
                if query_lower in chunk['text'].lower():
                    results.append({
                        'book_id': book_id,
                        'book_name': book_info['name'],
                        'system': book_info['system'],
                        'chunk': chunk,
                        'relevance_score': self._calculate_relevance(query, chunk['text'])
                    })
        
        # Sort by relevance and limit results
        results.sort(key=lambda x: x['relevance_score'], reverse=True)
        return results[:limit]
    
    def _calculate_relevance(self, query: str, text: str) -> float:
        """Calculate simple relevance score"""
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        
        if not query_words:
            return 0.0
        
        # Calculate word overlap
        overlap = len(query_words.intersection(text_words))
        return overlap / len(query_words)

class RuleBookRAGService:
    """Integrates rule books with ChromaDB RAG system"""
    
    def __init__(self, config: Dict[str, Any], rag_service, embedding_service):
        self.config = config
        self.rag_service = rag_service
        self.embedding_service = embedding_service
        self.processor = RuleBookProcessor(config)
        
        # Initialize rule books collection
        self.collection_name = 'rule_books'
        self._ensure_collection_exists()
    
    def _ensure_collection_exists(self):
        """Ensure rule books collection exists in ChromaDB"""
        try:
            # Use the existing collection initialization method
            self.rag_service._initialize_collections()
            logger.info(f"Rule books collection '{self.collection_name}' ready")
        except Exception as e:
            logger.error(f"Error ensuring rule books collection: {e}")
    
    def process_and_store_rule_book(self, book_id: str, file_path: Path) -> bool:
        """Process and store a rule book in ChromaDB"""
        try:
            # Process the rule book
            result = self.processor.process_rule_book(book_id, file_path)
            if not result:
                return False
            
            # Store chunks in ChromaDB
            chunks = result['chunks']
            texts = [chunk['text'] for chunk in chunks]
            
            # Get embeddings
            embeddings = self.embedding_service.get_batch_embeddings(texts)
            if not embeddings:
                logger.error(f"Failed to get embeddings for {book_id}")
                return False
            
            # Prepare metadata
            metadata_list = []
            for chunk in chunks:
                metadata = {
                    'book_id': book_id,
                    'book_name': result['book_name'],
                    'system': result['system'],
                    'page_number': chunk['page_number'],
                    'chunk_id': chunk['chunk_id'],
                    'word_count': chunk['word_count'],
                    'processed_at': result['processed_at']
                }
                metadata_list.append(metadata)
            
            # Store in ChromaDB using the existing RAG service
            for i, (text, embedding, metadata) in enumerate(zip(texts, embeddings, metadata_list)):
                if embedding:  # Only store if embedding was successful
                    # Provide proper context for rule books (global/system-wide)
                    context = {
                        'book_id': book_id, 
                        'chunk_id': metadata['chunk_id'],
                        'campaign_id': 0,  # Global rules available to all campaigns
                        'user_id': 0      # System content, not user-specific
                    }
                    
                    memory_id = self.rag_service.store_memory(
                        content=text,
                        memory_type=self.collection_name,
                        context=context,
                        metadata=metadata
                    )
                    
                    # Check if storage was successful
                    if not memory_id:
                        logger.error(f"Failed to store chunk {metadata['chunk_id']} from {book_id}")
                        return False
            
            logger.info(f"Successfully stored {len(chunks)} chunks from {book_id} in ChromaDB")
            return True
            
        except Exception as e:
            logger.error(f"Error processing and storing rule book {book_id}: {e}")
            return False
    
    def store_rule_book_chunk(self, content: str, book_id: str, chunk_id: str, metadata: Dict[str, Any]) -> bool:
        """Store a single rule book chunk with proper metadata handling"""
        try:
            # Get embedding for the content
            embedding = self.embedding_service.get_embedding(content)
            if not embedding:
                logger.error(f"Failed to generate embedding for chunk {chunk_id}")
                return False
            
            # Prepare context for rule books (global/system-wide)
            context = {
                'book_id': book_id,
                'chunk_id': chunk_id,
                'campaign_id': 0,  # Global rules available to all campaigns
                'user_id': 0      # System content, not user-specific
            }
            
            # Store using RAG service
            memory_id = self.rag_service.store_memory(
                content=content,
                memory_type=self.collection_name,
                context=context,
                metadata=metadata
            )
            
            if not memory_id:
                logger.error(f"Failed to store chunk {chunk_id} from {book_id}")
                return False
                
            logger.debug(f"Stored rule book chunk: {book_id} - {chunk_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing rule book chunk {chunk_id}: {e}")
            return False
    
    def search_rule_books(self, query: str, system: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search rule books using vector similarity"""
        try:
            # Get query embedding
            query_embeddings = self.embedding_service.get_batch_embeddings([query])
            if not query_embeddings:
                return []
            
            # Search in ChromaDB using the existing RAG service
            results = self.rag_service.retrieve_memories(
                query=query,
                memory_type=self.collection_name,
                campaign_id=0,  # Use 0 for rule books (global)
                limit=limit
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching rule books: {e}")
            return []
    
    def add_book_to_campaign(self, book_id: str, campaign_id: int, user_id: int) -> bool:
        """Add specific book rules to a campaign (admin command)"""
        try:
            # Search for all chunks from the specified book
            book_chunks = self.search_rule_books(f"book_id:{book_id}", limit=1000)
            
            if not book_chunks:
                logger.error(f"No chunks found for book {book_id}")
                return False
            
            # Store each chunk with campaign-specific context
            stored_count = 0
            for chunk in book_chunks:
                # Create campaign-specific context
                context = {
                    'book_id': book_id,
                    'chunk_id': chunk.get('chunk_id', 'unknown'),
                    'campaign_id': campaign_id,
                    'user_id': user_id,
                    'source': 'admin_add_book'
                }
                
                # Store in campaign memory
                memory_id = self.rag_service.store_memory(
                    content=chunk['content'],
                    memory_type='campaigns',  # Store in campaign memory
                    context=context,
                    metadata=chunk.get('metadata', {})
                )
                
                if memory_id:
                    stored_count += 1
                else:
                    logger.warning(f"Failed to store chunk {chunk.get('chunk_id')} for campaign {campaign_id}")
            
            logger.info(f"Added {stored_count}/{len(book_chunks)} chunks from {book_id} to campaign {campaign_id}")
            return stored_count > 0
            
        except Exception as e:
            logger.error(f"Error adding book {book_id} to campaign {campaign_id}: {e}")
            return False
    
    def get_rule_context(self, query: str, system: str = None, limit: int = 5) -> str:
        """Get relevant rule context for a query"""
        results = self.search_rule_books(query, system, limit)
        
        if not results:
            return ""
        
        context_parts = []
        for result in results:
            book_name = result.get('metadata', {}).get('book_name', 'Unknown')
            page_num = result.get('metadata', {}).get('page_number', '?')
            text = result.get('text', '')
            
            context_parts.append(f"[{book_name}, Page {page_num}]: {text}")
        
        return "\n\n".join(context_parts)

def create_rule_book_service(config: Dict[str, Any], rag_service, embedding_service) -> RuleBookRAGService:
    """Create rule book service instance"""
    return RuleBookRAGService(config, rag_service, embedding_service)
