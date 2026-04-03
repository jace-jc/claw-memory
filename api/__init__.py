"""
API package - Phase 3: re-export from api submodules

Functions are imported from api submodules to avoid circular imports.
"""
import warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

# Import all functions from submodules
from api._main import (
    memory_store,
    memory_search,
    memory_search_rrf,
    memory_adaptive,
    api_response,
)

from api._memory import (
    memory_recall,
    memory_forget,
    memory_kg_extract_and_link,
    memory_disambiguate,
)

from api._system import (
    memory_tier,
    memory_tier_get,
    memory_tier_move,
    memory_tier_stats_v2,
    memory_stats,
    memory_temporal,
    memory_temporal_extract,
    memory_cache,
    memory_kg,
    memory_health,
)

from api._auto import (
    memory_auto_extract,
    auto_capture,
    auto_recall,
    memory_batch,
    memory_extract_session,
    memory_transaction_stats,
)

# Import from api.health (already broken out)
from api.health import memory_health as _health, get_health

# Re-export for backward compatibility
# memory_health might be imported from both _system and health, use health version
memory_health = _health

__all__ = [
    # Main
    "memory_store",
    "memory_search", 
    "memory_search_rrf",
    "memory_adaptive",
    "api_response",
    # Memory
    "memory_recall",
    "memory_forget",
    "memory_kg_extract_and_link",
    "memory_disambiguate",
    # System
    "memory_tier",
    "memory_tier_get",
    "memory_tier_move",
    "memory_tier_stats_v2",
    "memory_stats",
    "memory_temporal",
    "memory_temporal_extract",
    "memory_cache",
    "memory_kg",
    "memory_health",
    # Auto
    "memory_auto_extract",
    "auto_capture",
    "auto_recall",
    "memory_batch",
    "memory_extract_session",
    "memory_transaction_stats",
    # Health
    "get_health",
]
