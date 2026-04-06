"""
core/_db.py - Shared database singleton to break circular imports.

This module provides a centralized get_db() function that lazily
initializes the LanceDB store, cutting circular dependency chains.
"""
from lancedb_store import get_db_store

_db_store = None


def get_db():
    """Lazy import to avoid circular dependency"""
    global _db_store
    if _db_store is None:
        _db_store = get_db_store()
    return _db_store
