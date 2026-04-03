"""
Memory domain: Temporal tracking operations
Phase 3: re-exports from memory_main.py for package structure
"""
def memory_temporal(action: str = "changes", memory_id: str = None, days: int = 30, **kwargs):
    """Temporal tracking operations"""
    from memory_main import memory_temporal as _func
    return _func(action=action, memory_id=memory_id, days=days, **kwargs)

def memory_temporal_extract(text: str, reference_date: str = None):
    """Extract temporal information from text"""
    from memory_main import memory_temporal_extract as _func
    return _func(text=text, reference_date=reference_date)

__all__ = [
    "memory_temporal",
    "memory_temporal_extract",
]
