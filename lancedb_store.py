"""
LanceDB 存储模块 - 向量存储和搜索
修复版：使用 PyArrow schema，支持 LanceDB 0.27+

Phase 2: This file is now a compatibility shim.
All implementation has been moved to core/ submodules.
Import from here for backward compatibility.
"""
import sys

# Import everything from core module for backward compatibility
from core import LanceDBStore, SCHEMA, _build_schema, _safe_call

# Re-export for方便直接导入
__all__ = [
    "LanceDBStore",
    "get_db_store",
    "SCHEMA",
    "_build_schema",
    "_safe_call",
]

# get_db_store is defined at module level (lazy singleton)
_db_store = None


def get_db_store():
    """懒加载单例"""
    global _db_store
    if _db_store is None:
        _db_store = LanceDBStore()
    return _db_store


# For backward compatibility with code that checks for these at module level
def __getattr__(name):
    if name == "LanceDBStore":
        return LanceDBStore
    if name == "get_db_store":
        return get_db_store
    if name == "SCHEMA":
        return SCHEMA
    if name == "_build_schema":
        return _build_schema
    if name == "_safe_call":
        return _safe_call
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
