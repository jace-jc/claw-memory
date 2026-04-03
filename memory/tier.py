"""
Memory domain: Tier management operations
Phase 3: re-exports from memory_main.py for package structure
"""
def memory_tier(action: str = "view", tier: str = "ALL", **kwargs):
    """Memory tier management"""
    from memory_main import memory_tier as _func
    return _func(action=action, tier=tier, **kwargs)

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
