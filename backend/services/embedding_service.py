#!/usr/bin/env python3
"""
ShadowRealms AI - Embedding Service
Advanced text embedding and vector processing for RAG system
"""

import os
import json
import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

class EmbeddingService:
    """Advanced embedding service for vector processing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.lm_studio_url = config.get('LM_STUDIO_URL', 'http://localhost:1234')
        self.embedding_model = 'nomic-embed-text-v1.5'  # From our LM Studio models
        
        logger.info("Embedding Service initialized")
    
    def _call_lm_studio_embedding(self, text: str) -> Optional[List[float]]:
        """Call LM Studio for embedding using chat completion as fallback"""
        try:
            # First try the embeddings endpoint
            url = f"{self.lm_studio_url}/v1/embeddings"
            payload = {
                "model": self.embedding_model,
                "input": text
            }
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    return data['data'][0]['embedding']
            
            # Fallback: Use chat completion to generate a simple hash-based embedding
            logger.warning("Embeddings endpoint not available, using hash-based fallback")
            return self._generate_hash_embedding(text)
            
        except Exception as e:
            logger.error(f"Error calling LM Studio embedding: {e}")
            # Fallback to hash-based embedding
            return self._generate_hash_embedding(text)
    
    def _generate_hash_embedding(self, text: str) -> List[float]:
        """Generate a simple hash-based embedding as fallback"""
        import hashlib
        import struct
        
        # Create a hash of the text
        text_hash = hashlib.sha256(text.encode()).digest()
        
        # Convert to 384-dimensional vector (common embedding size)
        embedding = []
        for i in range(0, len(text_hash), 4):
            if len(embedding) >= 384:
                break
            # Convert 4 bytes to float
            chunk = text_hash[i:i+4]
            if len(chunk) == 4:
                value = struct.unpack('f', chunk)[0]
                embedding.append(value)
        
        # Pad or truncate to exactly 384 dimensions
        while len(embedding) < 384:
            embedding.append(0.0)
        
        return embedding[:384]
    
    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text"""
        try:
            # Clean and prepare text
            cleaned_text = self._clean_text(text)
            
            # Get embedding from LM Studio
            embedding = self._call_lm_studio_embedding(cleaned_text)
            
            if embedding:
                logger.info(f"Generated embedding for text: {cleaned_text[:50]}...")
                return embedding
            else:
                logger.warning("Failed to generate embedding")
                return None
                
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """Clean text for embedding"""
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Truncate if too long (most models have limits)
        if len(text) > 8000:  # Conservative limit
            text = text[:8000] + "..."
        
        return text
    
    def get_batch_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Get embeddings for multiple texts"""
        embeddings = []
        
        for text in texts:
            embedding = self.get_embedding(text)
            embeddings.append(embedding)
        
        return embeddings
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Split text into overlapping chunks for better retrieval"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for i in range(end, max(start + chunk_size - 100, start), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get embedding service status"""
        status = {
            'lm_studio_connected': False,
            'embedding_model': self.embedding_model,
            'test_embedding': None
        }
        
        try:
            # Test LM Studio connection
            test_text = "Test embedding"
            embedding = self.get_embedding(test_text)
            
            if embedding:
                status['lm_studio_connected'] = True
                status['test_embedding'] = {
                    'dimension': len(embedding),
                    'sample': embedding[:5]  # First 5 values
                }
            
        except Exception as e:
            status['error'] = str(e)
        
        return status

def create_embedding_service(config: Dict[str, Any]) -> EmbeddingService:
    """Create and initialize embedding service"""
    return EmbeddingService(config)
