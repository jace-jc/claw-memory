"""
Claw Memory - AI Memory System

A local-first memory system with RRF search, knowledge graph, and temporal tracking.
"""

__version__ = "2.8.0"

# Core: LanceDBStore and get_db_store
try:
    from .lancedb_store import LanceDBStore, get_db_store
except ImportError:
    from lancedb_store import LanceDBStore, get_db_store

# Memory types
try:
    from .memory.memory_types import Memory, SearchResult, ApiResponse, MemoryType, Scope
except ImportError:
    from memory.memory_types import Memory, SearchResult, ApiResponse, MemoryType, Scope

# Intent classification
try:
    from .retrieval.intent_classifier import classify_query, expand_query
except ImportError:
    from retrieval.intent_classifier import classify_query, expand_query

# User profile
try:
    from .user_profile import build_user_profile, UserProfile
except ImportError:
    from user_profile import build_user_profile, UserProfile

# Multimodal
try:
    from .extract.multimodal import store_image_memory, multimodal_extractor
except ImportError:
    try:
        from extract.multimodal import store_image_memory, multimodal_extractor
    except (ImportError, ModuleNotFoundError):
        pass  # Not all builds include multimodal

# Backup
try:
    from .infra.auto_backup import start_auto_backup, stop_auto_backup, get_scheduler
except ImportError:
    try:
        from infra.auto_backup import start_auto_backup, stop_auto_backup, get_scheduler
    except (ImportError, ModuleNotFoundError):
        pass

# Performance
try:
    from .infra.performance import get_monitor, record_performance
except ImportError:
    try:
        from infra.performance import get_monitor, record_performance
    except (ImportError, ModuleNotFoundError):
        pass

# Errors
try:
    from .infra.errors import MemoryErrorException, handle_memory_error, format_error_response
except ImportError:
    try:
        from infra.errors import MemoryErrorException, handle_memory_error, format_error_response
    except (ImportError, ModuleNotFoundError):
        pass

# Denoise filter
try:
    from .denoise_filter import should_store_memory, DenoiseFilter
except ImportError:
    try:
        from denoise_filter import should_store_memory, DenoiseFilter
    except (ImportError, ModuleNotFoundError):
        pass

# Convenience exports
__all__ = [
    # Core
    "get_db",
    "get_db_store",
    "LanceDBStore",
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
    "multimodal_extractor",
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
    # Denoise
    "should_store_memory",
    "DenoiseFilter",
    # Version
    "__version__",
]
