"""
Core package - Phase 2: re-export from new locations

This module re-exports LanceDBStore with all methods composed from submodules.
For backward compatibility, import LanceDBStore from here or from lancedb_store.
"""
import sys as _sys

# Re-export schema and helpers from base
from core._lancedb_base import (
    LanceDBStore,
    SCHEMA,
    _build_schema,
    _safe_call,
)

# Import methods from split modules
from core._store import store
from core._search import search
from core._rerank import _rerank_cross_encoder
from core._search_rrf import (
    search_rrf,
    search_rrf_cached,
    _rrf_fusion,
    _get_bm25_scores,
    _get_importance_scores,
    _kg_aware_search,
    _temporal_search,
    _search_memories_by_entity,
)
from core._cache import search_cached

# Patch all methods onto LanceDBStore class
# Note: We need to use proper method wrapping to preserve self reference
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

# get_db_store is defined at module level, not in base class
# It's re-exported from lancedb_store.py (the original location)
# For core/__init__.py, we need to define it here or import from the patched module

# Re-export from core.schema (Phase 2 refactor) if available
try:
    from core.schema import SCHEMA as _SCHEMA, _build_schema as __build_schema, _safe_call as __safe_call
except ImportError:
    pass

__all__ = [
    "LanceDBStore",
    "get_db_store",
    "SCHEMA",
    "_build_schema",
    "_safe_call",
]
