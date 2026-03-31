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
    from .performance import get_monitor, record_performance
    from .errors import MemoryErrorException, handle_memory_error, format_error_response
except ImportError:
    pass

# Convenience exports
__all__ = [
    # Core
    "get_db",
    "get_db_store",
    "Memory",
    "SearchResult", 
    "ApiResponse",
    "MemoryType",
    "Scope",
    # Intent
    "classify_query",
    "expand_query",
    # User
    "build_user_profile",
    "UserProfile",
    # Multimodal
    "store_image_memory",
    # Backup
    "start_auto_backup",
    "stop_auto_backup",
    "get_scheduler",
    # Performance
    "get_monitor",
    "record_performance",
    # Errors
    "MemoryErrorException",
    "handle_memory_error",
    "format_error_response",
    # Version
    "__version__",
]
