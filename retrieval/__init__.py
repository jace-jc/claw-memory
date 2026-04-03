"""
Retrieval package - Phase 2: re-export search functions from lancedb_store

Note: The search methods are still in LanceDBStore class in lancedb_store.py.
This package provides standalone access to search functionality.
"""
# Re-export search functions from lancedb_store (backward compat)
import lancedb_store as _store

# These are class methods, so we expose them as module-level functions via the store
def search(query: str, limit: int = 5, **kwargs):
    """Semantic search - wraps LanceDBStore.search()"""
    db = _store.get_db_store()
    return db.search(query, limit=limit, **kwargs)

def search_rrf(query: str, limit: int = 5, k: int = 60, **kwargs):
    """RRF fusion search - wraps LanceDBStore.search_rrf()"""
    db = _store.get_db_store()
    return db.search_rrf(query, limit=limit, k=k, **kwargs)

def search_cached(query: str, limit: int = 5, **kwargs):
    """Cached search - wraps LanceDBStore.search_cached()"""
    db = _store.get_db_store()
    return db.search_cached(query, limit=limit, **kwargs)

def search_rrf_cached(query: str, limit: int = 5, k: int = 60, **kwargs):
    """Cached RRF search - wraps LanceDBStore.search_rrf_cached()"""
    db = _store.get_db_store()
    return db.search_rrf_cached(query, limit=limit, k=k, **kwargs)

__all__ = [
    "search",
    "search_rrf",
    "search_cached",
    "search_rrf_cached",
]
