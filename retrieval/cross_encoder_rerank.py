"""
Cross-Encoder Reranker - Dedicated model for fast memory reranking

Replaces LLM-based reranking (5-15s) with dedicated cross-encoder model (<100ms)

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (22M params, <10ms inference)
"""
import os
import time
import numpy as np
from typing import List, Dict, Optional
import logging

_logger = logging.getLogger(__name__)

# Global singleton instance
_cross_encoder_reranker = None


class CrossEncoderReranker:
    """
    Dedicated Cross-Encoder reranker using sentence-transformers.
    
    Replaces slow LLM-based reranking with fast local inference.
    Target latency: <100ms for 10 candidates.
    """
    
    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    def __init__(self, model_name: str = None):
        self.model_name = model_name or self.MODEL_NAME
        self._model = None
        self._enabled = True
        
    @property
    def model(self):
        """Lazy load model on first use"""
        if self._model is None:
            self._model = self._load_model()
        return self._model
    
    def is_available(self) -> bool:
        """Check if cross-encoder model is available for reranking"""
        # If _enabled is False, model failed to load
        if not self._enabled:
            return False
        # Try to load model if not yet loaded
        if self._model is None:
            self._model = self._load_model()
        return self._enabled and self._model is not None
    
    def _load_model(self):
        """Load cross-encoder model"""
        try:
            from sentence_transformers import CrossEncoder
            _logger.info(f"Loading Cross-Encoder model: {self.model_name}")
            model = CrossEncoder(self.model_name)
            _logger.info("Cross-Encoder model loaded successfully")
            return model
        except ImportError:
            _logger.warning("sentence-transformers not installed, using fallback scorer")
            self._enabled = False
            return None
        except Exception as e:
            _logger.error(f"Failed to load Cross-Encoder model: {e}")
            self._enabled = False
            return None
    
    def rerank(self, query: str, candidates: List[Dict], limit: int = 5, top_k: int = None) -> List[Dict]:
        """
        Rerank candidates using Cross-Encoder model.
        
        Args:
            query: Search query string
            candidates: List of memory dicts with 'content' field
            limit: Maximum number of results to return
            top_k: Alias for limit (compatibility)
            
        Returns:
            Reranked list of candidates (same structure, sorted by cross-score)
        """
        if top_k is not None:
            limit = top_k
        if not candidates:
            return []
        
        start_time = time.time()
        
        # Fallback if model not available
        if not self._enabled or self._model is None:
            return self._fallback_rerank(query, candidates, limit)
        
        try:
            # Build (query, document) pairs
            pairs = [(query, cand.get("content", "")) for cand in candidates]
            
            # Score all pairs
            scores = self.model.predict(pairs, show_progress_bar=False)
            
            # Normalize scores to 0-1 range (model outputs raw logits)
            if isinstance(scores, np.ndarray):
                scores = scores.tolist()
            
            max_score = max(scores) if max(scores) != min(scores) else 1.0
            min_score = min(scores)
            score_range = max_score - min_score if max_score != min_score else 1.0
            
            normalized_scores = [(s - min_score) / score_range for s in scores]
            
            # Attach cross-encoder score to each candidate
            for i, cand in enumerate(candidates):
                cross_score = normalized_scores[i]
                
                # Vector score from existing _distance field
                vector_score = 1.0 - cand.get("_distance", 0.5)
                
                # RRF fusion: vector weight 0.3, cross-encoder weight 0.7
                final_score = 0.3 * vector_score + 0.7 * cross_score
                
                cand["_cross_score"] = cross_score
                cand["_cross_raw"] = scores[i]
                cand["_final_score"] = final_score
            
            # Sort by final score
            candidates.sort(key=lambda x: x.get("_final_score", 0), reverse=True)
            
            elapsed_ms = (time.time() - start_time) * 1000
            _logger.debug(f"Cross-Encoder rerank: {len(candidates)} candidates in {elapsed_ms:.1f}ms")
            
            return candidates[:limit]
            
        except Exception as e:
            _logger.error(f"Cross-Encoder rerank failed: {e}")
            return self._fallback_rerank(query, candidates, limit)
    
    def _fallback_rerank(self, query: str, candidates: List[Dict], limit: int) -> List[Dict]:
        """
        Fallback reranking when Cross-Encoder is unavailable.
        Uses simple vector distance + length heuristic.
        """
        query_words = set(query.lower().split())
        
        for cand in candidates:
            content = cand.get("content", "")
            content_words = set(content.lower().split())
            
            # Word overlap score
            if query_words and content_words:
                overlap = len(query_words & content_words) / len(query_words)
            else:
                overlap = 0.0
            
            # Length penalty (prefer medium-length contents)
            length = len(content)
            length_score = 1.0 - abs(length - 200) / 400 if length < 400 else 0.5
            
            # Combine with vector distance
            vector_score = 1.0 - cand.get("_distance", 0.5)
            final_score = 0.5 * vector_score + 0.3 * overlap + 0.2 * length_score
            
            cand["_cross_score"] = overlap
            cand["_final_score"] = final_score
        
        candidates.sort(key=lambda x: x.get("_final_score", 0), reverse=True)
        return candidates[:limit]
    
    def get_latency_benchmark(self, query: str, num_candidates: int = 10) -> Dict:
        """
        Run latency benchmark for the reranker.
        
        Returns dict with timing statistics.
        """
        import random
        import string
        
        # Generate random candidates
        candidates = [
            {"content": "".join(random.choices(string.ascii_letters + " ", k=100)), "_distance": random.random()}
            for _ in range(num_candidates)
        ]
        
        timings = []
        for _ in range(5):
            start = time.time()
            self.rerank(query, candidates, num_candidates)
            elapsed = (time.time() - start) * 1000
            timings.append(elapsed)
        
        return {
            "model": self.model_name,
            "enabled": self._enabled,
            "num_candidates": num_candidates,
            "avg_ms": sum(timings) / len(timings),
            "min_ms": min(timings),
            "max_ms": max(timings),
            "target_ms": 100
        }


def get_cross_encoder_reranker() -> CrossEncoderReranker:
    """Get global CrossEncoderReranker singleton"""
    global _cross_encoder_reranker
    if _cross_encoder_reranker is None:
        _cross_encoder_reranker = CrossEncoderReranker()
    return _cross_encoder_reranker


# Compatibility alias for existing code that expects get_reranker()
def get_reranker():
    """Compatibility alias - returns CrossEncoderReranker singleton"""
    return get_cross_encoder_reranker()
