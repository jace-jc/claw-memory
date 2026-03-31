"""
Claw Memory - AI Memory System

A local-first memory system with RRF search, knowledge graph, and temporal tracking.
"""

__version__ = "2.7.1"

# Core exports
from .memory_main import get_db, get_db_store

# Type exports
from .memory_types import (
    MemoryStoreRequest,
    MemorySearchRequest,
    MemoryRecallRequest,
    MemoryForgetRequest,
    MemoryStatsResponse,
    MemoryHealthResponse,
    MemoryType,
)

# Configuration
from .memory_config import CONFIG

__all__ = [
    # Core
    "get_db",
    "get_db_store",
    # Types
    "MemoryStoreRequest",
    "MemorySearchRequest",
    "MemoryRecallRequest",
    "MemoryForgetRequest",
    "MemoryStatsResponse",
    "MemoryHealthResponse",
    "MemoryType",
    # Config
    "CONFIG",
    # Version
    "__version__",
]
