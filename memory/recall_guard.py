"""
Recall Guard - Prevents hallucination feedback loops

Problem: Recalled memories can re-enter extraction pipeline, amplifying false memories.
Solution: Track recalled content hashes and block re-extraction of recently recalled content.

Example: 808 false "User prefers Vim" memories in Mem0 production.
"""
import os
import json
import time
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Set
from pathlib import Path

_logger = logging.getLogger(__name__)

# Global singleton
_recall_guard = None

# Default TTL: 24 hours
DEFAULT_TTL_SECONDS = 24 * 60 * 60


class RecallGuard:
    """
    Prevents hallucination amplification by blocking re-extraction of recalled content.
    
    Mechanism:
    1. When content is recalled, mark it with timestamp
    2. When new content is about to be stored/extracted, check if recently recalled
    3. If recently recalled (within TTL), skip storage/extraction to prevent loop
    
    TTL: 24 hours default (configurable)
    """
    
    def __init__(self, storage_path: str = None, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        """
        Initialize RecallGuard.
        
        Args:
            storage_path: Path to JSON file for persistence
            ttl_seconds: Time-to-live for recall markers (default: 24 hours)
        """
        self.storage_path = Path(storage_path or "/Users/claw/.openclaw/workspace/memory/recall_guard.json")
        self.ttl_seconds = ttl_seconds
        
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory index: content_hash -> recall timestamp
        self._recalled: dict = {}
        
        # Load existing data
        self._load()
        
        # Cleanup expired entries on init
        self._cleanup_expired()
    
    def _load(self):
        """Load recall log from disk"""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self._recalled = data.get("recalled", {})
                _logger.debug(f"Loaded {len(self._recalled)} recall entries")
            except Exception as e:
                _logger.warning(f"Failed to load recall guard data: {e}")
                self._recalled = {}
    
    def _save(self):
        """Persist recall log to disk"""
        try:
            data = {
                "recalled": self._recalled,
                "updated_at": datetime.now().isoformat()
            }
            self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception as e:
            _logger.error(f"Failed to save recall guard data: {e}")
    
    def _cleanup_expired(self):
        """Remove expired entries from memory and disk"""
        now = time.time()
        expired_keys = [
            h for h, entry in self._recalled.items()
            if now - entry.get("timestamp", 0) > self.ttl_seconds
        ]
        
        if expired_keys:
            for key in expired_keys:
                del self._recalled[key]
            _logger.debug(f"Cleaned up {len(expired_keys)} expired recall entries")
            self._save()
    
    @staticmethod
    def compute_hash(content: str) -> str:
        """Compute SHA256 hash of content"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    
    def mark_recalled(self, memory_id: str, content: str) -> None:
        """
        Mark content as recently recalled.
        
        Args:
            memory_id: Memory ID (for logging/debugging)
            content: The recalled content text
        """
        content_hash = self.compute_hash(content)
        self._recalled[content_hash] = {
            "memory_id": memory_id,
            "timestamp": time.time(),
            "content_preview": content[:50] if len(content) > 50 else content
        }
        self._save()
        _logger.debug(f"Marked recall: {memory_id} (hash={content_hash[:16]}...)")
    
    def was_recently_recalled(self, content_hash: str) -> bool:
        """
        Check if content was recently recalled (within TTL).
        
        Args:
            content_hash: SHA256 hash of content
            
        Returns:
            True if content was recalled within TTL window
        """
        if content_hash not in self._recalled:
            return False
        
        entry = self._recalled[content_hash]
        age = time.time() - entry["timestamp"]
        
        if age > self.ttl_seconds:
            # Expired, remove
            del self._recalled[content_hash]
            self._save()
            return False
        
        return True
    
    def is_recently_recalled(self, content: str) -> bool:
        """
        Check if content was recently recalled (by content string).
        
        Args:
            content: The content to check
            
        Returns:
            True if content was recalled within TTL window
        """
        content_hash = self.compute_hash(content)
        return self.was_recently_recalled(content_hash)
    
    def get_recall_age(self, content: str) -> Optional[float]:
        """
        Get age of recall in seconds (None if not found).
        
        Args:
            content: The content to check
            
        Returns:
            Age in seconds, or None if not recently recalled
        """
        content_hash = self.compute_hash(content)
        if content_hash not in self._recalled:
            return None
        
        entry = self._recalled[content_hash]
        return time.time() - entry["timestamp"]
    
    def clear(self):
        """Clear all recall history"""
        self._recalled = {}
        self._save()
        _logger.info("Cleared all recall history")
    
    def get_stats(self) -> dict:
        """Get recall guard statistics"""
        self._cleanup_expired()
        timestamps = [e.get("timestamp") for e in self._recalled.values() if e.get("timestamp")]
        return {
            "total_recalls": len(self._recalled),
            "ttl_seconds": self.ttl_seconds,
            "storage_path": str(self.storage_path),
            "oldest_entry": min(timestamps) if timestamps else None,
            "newest_entry": max(timestamps) if timestamps else None
        }


def get_recall_guard() -> RecallGuard:
    """Get global RecallGuard singleton"""
    global _recall_guard
    if _recall_guard is None:
        _recall_guard = RecallGuard()
    return _recall_guard


# Convenience functions for integration
def mark_content_recalled(memory_id: str, content: str) -> None:
    """Mark content as recently recalled"""
    guard = get_recall_guard()
    guard.mark_recalled(memory_id, content)


def is_content_recalled(content: str) -> bool:
    """Check if content was recently recalled"""
    guard = get_recall_guard()
    return guard.is_recently_recalled(content)


def should_block_extraction(content: str) -> bool:
    """
    Determine if content should be blocked from extraction.
    
    Used in auto_extract.py to prevent hallucination amplification.
    
    Returns:
        True if content should be blocked (was recently recalled)
    """
    return is_content_recalled(content)
