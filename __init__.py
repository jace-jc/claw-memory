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

# Convenience exports
__all__ = [
    "get_db",
    "get_db_store",
    "Memory",
    "SearchResult", 
    "ApiResponse",
    "MemoryType",
    "Scope",
    "__version__",
]
