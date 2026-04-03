"""
Core package - Phase 2: re-export from new locations

This module re-exports LanceDBStore with all methods composed from submodules.
For backward compatibility, import LanceDBStore from here or from lancedb_store.
"""
# Use relative imports to avoid circular import
from ._lancedb_base import (
    LanceDBStore,
    SCHEMA,
    _build_schema,
    _safe_call,
)
from ._store import store
from ._search import search
from ._rerank import _rerank_cross_encoder
from ._search_rrf import (
    search_rrf,
    search_rrf_cached,
    _rrf_fusion,
    _get_bm25_scores,
    _get_importance_scores,
    _kg_aware_search,
    _temporal_search,
    _search_memories_by_entity,
)
from ._cache import search_cached

# Patch all methods onto LanceDBStore class
def _make_method(func):
    """Convert module-level function to instance method"""
    def method(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    method.__doc__ = func.__doc__
    method.__name__ = func.__name__
    return method

# Apply methods
LanceDBStore.store = store
LanceDBStore.search = search
LanceDBStore._rerank_cross_encoder = _rerank_cross_encoder
LanceDBStore.search_rrf = search_rrf
LanceDBStore.search_rrf_cached = search_rrf_cached
LanceDBStore._rrf_fusion = _rrf_fusion
LanceDBStore._get_bm25_scores = _get_bm25_scores
LanceDBStore._get_importance_scores = _get_importance_scores
LanceDBStore._kg_aware_search = _kg_aware_search
LanceDBStore._temporal_search = _temporal_search
LanceDBStore._search_memories_by_entity = _search_memories_by_entity
LanceDBStore.search_cached = search_cached

__all__ = [
    "LanceDBStore",
    "get_db_store",
    "SCHEMA",
    "_build_schema",
    "_safe_call",
]
