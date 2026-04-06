"""
Memory domain: Tier management operations
Phase 3: re-exports from memory_main.py for package structure

[DEPRECATED] This module is deprecated. Use memory.memory_tier_manager instead.
"""
import warnings
warnings.warn(
    "memory.tier is deprecated. Use memory.memory_tier_manager instead.",
    DeprecationWarning,
    stacklevel=2
)

def memory_tier(action: str = "view", tier: str = "ALL", **kwargs):
    """Memory tier management"""
    from memory.memory_tier_manager import get_tier_manager
    manager = get_tier_manager()
    if action == "view":
        return manager.get_tier_stats()
    elif action == "get":
        memory_id = kwargs.get("memory_id")
        return manager.get_tier(memory_id) if memory_id else {"error": "memory_id required"}
    elif action == "move":
        memory_id = kwargs.get("memory_id")
        target_tier = kwargs.get("tier")
        force = kwargs.get("force", False)
        return manager.move_tier(memory_id, target_tier, force) if memory_id and target_tier else {"error": "memory_id and tier required"}
    return {"error": f"Unknown action: {action}"}

def memory_tier_get(memory_id: str):
    """Get memory tier"""
    from memory_main import memory_tier_get as _func
    return _func(memory_id=memory_id)

def memory_tier_move(memory_id: str, tier: str, force: bool = False):
    """Move memory to different tier"""
    from memory_main import memory_tier_move as _func
    return _func(memory_id=memory_id, tier=tier, force=force)

def memory_tier_stats_v2():
    """Get tier statistics"""
    from memory_main import memory_tier_stats_v2 as _func
    return _func()

__all__ = [
    "memory_tier",
    "memory_tier_get",
    "memory_tier_move",
    "memory_tier_stats_v2",
]
