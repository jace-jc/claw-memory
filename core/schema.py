"""
LanceDB Schema - PyArrow schema definitions for memory storage
Phase 2 refactor: split from lancedb_store.py
"""
import pyarrow as pa
import logging

# 动态 schema（根据 embedding 维度自适应）
def _build_schema(dimensions: int = None):
    """根据 embedding 维度动态构建 schema"""
    if dimensions is None:
        try:
            from memory_config_multi import get_active_config
            dimensions = get_active_config().get_embedding_config().get("dimensions", 1024)
        except Exception:
            dimensions = 1024
    return pa.schema([
        ("id", pa.string()),
        ("type", pa.string()),
        ("content", pa.string()),
        ("summary", pa.string()),
        ("importance", pa.float32()),
        ("source", pa.string()),
        ("transcript", pa.string()),
        ("tags", pa.string()),  # JSON string
        ("scope", pa.string()),
        ("scope_id", pa.string()),
        ("vector", pa.list_(pa.float32(), dimensions)),  # 动态维度
        ("created_at", pa.string()),
        ("updated_at", pa.string()),
        ("last_accessed", pa.string()),
        ("access_count", pa.int32()),
        ("revision_chain", pa.string()),  # JSON string
        ("superseded_by", pa.string()),
    ])

# 默认 schema (向后兼容，1024维)
SCHEMA = _build_schema(1024)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
_logger = logging.getLogger("ClawMemory")

# 辅助函数：安全执行并记录错误
def _safe_call(func, default=None, context=""):
    """安全调用函数，记录任何异常"""
    try:
        return func()
    except Exception as e:
        _logger.error(f"{context}: {e}")
        return default
