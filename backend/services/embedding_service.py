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

DEFAULT_EMBEDDING_MODEL = "text-embedding-bge-m3"


def configured_embedding_model() -> str:
    """EMBEDDING_MODEL env (LM Studio model id); default bge-m3 (good for English and Greek)."""
    return (os.environ.get("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL).strip()


class EmbeddingError(Exception):
    pass


class EmbeddingService:
    """Text embeddings from LM Studio's /v1/embeddings (model: EMBEDDING_MODEL)."""

    BATCH = 32

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.lm_studio_url = (config.get('LM_STUDIO_URL') or os.environ.get('LM_STUDIO_URL')
                              or 'http://localhost:1234').rstrip('/')
        self.api_key = (config.get('LM_STUDIO_API_KEY') or os.environ.get('LM_STUDIO_API_KEY') or '').strip()
        self.embedding_model = configured_embedding_model()
        self.timeout = 120

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """One vector per text, in order. Raises EmbeddingError (no fake vectors: they'd poison the index)."""
        out: List[List[float]] = []
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        for i in range(0, len(texts), self.BATCH):
            batch = [self._clean_text(t) or " " for t in texts[i:i + self.BATCH]]
            try:
                r = requests.post(f"{self.lm_studio_url}/v1/embeddings",
                                  json={"model": self.embedding_model, "input": batch},
                                  headers=headers, timeout=self.timeout)
            except requests.RequestException as e:
                raise EmbeddingError(f"LM Studio embeddings unreachable: {e}") from e
            if r.status_code != 200:
                raise EmbeddingError(f"LM Studio embeddings HTTP {r.status_code}: {r.text[:200]}")
            data = sorted(r.json().get('data') or [], key=lambda d: d.get('index', 0))
            if len(data) != len(batch):
                raise EmbeddingError(f"LM Studio returned {len(data)} embeddings for {len(batch)} inputs")
            out.extend(d['embedding'] for d in data)
        return out

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Embedding for one text, or None when the embedder is unavailable."""
        try:
            return self.embed_texts([text])[0]
        except EmbeddingError as e:
            logger.error(f"Embedding failed: {e}")
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
        """Embeddings for several texts; all None when the embedder is unavailable."""
        try:
            return self.embed_texts(texts)
        except EmbeddingError as e:
            logger.error(f"Batch embedding failed: {e}")
            return [None] * len(texts)

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
