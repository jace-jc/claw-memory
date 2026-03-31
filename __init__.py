"""
Claw Memory - AI Memory System

A local-first memory system with RRF search, knowledge graph, and temporal tracking.
"""

__version__ = "2.8.0"

# Try relative imports first, fall back to absolute for testing
try:
    from .memory_main import get_db, get_db_store
    from .memory_types import Memory, SearchResult, ApiResponse, MemoryType, Scope
except ImportError:
    # For testing when running pytest directly in the package directory
    from memory_main import get_db, get_db_store
    from memory_types import Memory, SearchResult, ApiResponse, MemoryType, Scope

# New modules exports
try:
    from .intent_classifier import classify_query, expand_query
    from .user_profile import build_user_profile, UserProfile
    from .multimodal import store_image_memory, multimodal_extractor
    from .auto_backup import start_auto_backup, stop_auto_backup, get_scheduler
except ImportError:
    pass

# Convenience exports
__all__ = [
    "get_db",
    "get_db_store",
    "Memory",
    "SearchResult", 
    "ApiResponse",
    "MemoryType",
    "Scope",
    "classify_query",
    "expand_query",
    "build_user_profile",
    "UserProfile",
    "store_image_memory",
    "start_auto_backup",
    "stop_auto_backup",
    "__version__",
]
