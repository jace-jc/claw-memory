"""
Memory domain: Knowledge Graph operations
Phase 3: re-exports from memory_main.py for package structure
"""
# Lazy imports to avoid circular dependency
def memory_kg(action: str = "stats", entity: str = None, depth: int = 2, **kwargs):
    """Knowledge graph operations"""
    from memory_main import memory_kg as _func
    return _func(action=action, entity=entity, depth=depth, **kwargs)

def memory_kg_extract_and_link(memory_content: str, memory_id: str = None):
    """Extract and link entities to knowledge graph"""
    from memory_main import memory_kg_extract_and_link as _func
    return _func(memory_content=memory_content, memory_id=memory_id)

__all__ = [
    "memory_kg",
    "memory_kg_extract_and_link",
]
