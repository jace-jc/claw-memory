"""
Memory domain: Version history operations
Phase 3: re-exports from version_history.py for package structure
"""
def get_version_history():
    """Get version history manager"""
    from version_history import get_version_history as _func
    return _func()

def record_create(memory_id: str, content: str, memory_type: str = "fact"):
    """Record memory creation"""
    from version_history import record_create as _func
    return _func(memory_id=memory_id, content=content, memory_type=memory_type)

def record_update(memory_id: str, old_content: str, new_content: str, **kwargs):
    """Record memory update"""
    from version_history import record_update as _func
    return _func(memory_id=memory_id, old_content=old_content, new_content=new_content, **kwargs)

def record_delete(memory_id: str, reason: str = "MANUAL", trigger: str = "MANUAL"):
    """Record memory deletion"""
    from version_history import record_delete as _func
    return _func(memory_id=memory_id, reason=reason, trigger=trigger)

def recall_at(memory_id: str, date: str):
    """Recall memory at specific date"""
    from version_history import recall_at as _func
    return _func(memory_id=memory_id, date=date)

def get_history(memory_id: str):
    """Get version history for memory"""
    from version_history import get_history as _func
    return _func(memory_id=memory_id)

def get_changelog_entries(limit: int = 50):
    """Get changelog entries"""
    from version_history import get_changelog_entries as _func
    return _func(limit=limit)

__all__ = [
    "get_version_history",
    "record_create",
    "record_update",
    "record_delete",
    "recall_at",
    "get_history",
    "get_changelog_entries",
]
