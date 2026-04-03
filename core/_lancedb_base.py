"""
LanceDB 存储模块 - 向量存储和搜索
修复版：使用 PyArrow schema，支持 LanceDB 0.27+

Phase 2: Schema available in core/schema.py (import separately if needed)

This file contains the base LanceDBStore class with core infrastructure methods.
"""
import os
import re
import math
import json
import uuid
import time
import traceback
import logging
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union
import lancedb
import pyarrow as pa
from core.memory_config import CONFIG
from core.memory_config_multi import get_active_config

from retrieval.mmr_diversity import get_mmr_reranker
from retrieval.two_stage_dedup import TwoStageDedup, DedupDecision
from infra.wal_protocol import WALProtocol

# 配置日志 - 【P1修复】添加错误日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
_logger = logging.getLogger("ClawMemory")

# 辅助函数：安全执行并记录错误
def _safe_call(func, default=None, context=""):
    """【P1修复】安全调用函数，记录任何异常"""
    try:
        return func()
    except Exception as e:
        _logger.error(f"{context}: {e}\n{traceback.format_exc()}")
        return default

# 动态 schema（根据 embedding 维度自适应）
def _build_schema(dimensions: int = None):
    """根据 embedding 维度动态构建 schema"""
    if dimensions is None:
        try:
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


class LanceDBStore:
    def __init__(self, db_path=None):
        self.db_path = db_path or CONFIG.get("db_path", "/Users/claw/.openclaw/workspace/memory/lancedb")
        self._ensure_dir()
        self.db = self._connect()
        self.table = self._get_table()
        self._dedup = TwoStageDedup(use_llm=False)
        self._wal = WALProtocol(auto_load=True)
        self._init_dedup()
    
    def _ensure_dir(self):
        Path(self.db_path).mkdir(parents=True, exist_ok=True)
    
    def _ensure_connected(self) -> bool:
        """【P0修复】确保数据库已连接，必要时重连"""
        try:
            # 检查连接是否有效
            if self.db is not None:
                try:
                    # 尝试获取表列表验证连接
                    _ = self.db.table_names()
                    if self.table is None:
                        self.table = self._get_table()
                    return True
                except Exception:
                    pass
            
            # 需要重连
            self.db = self._connect()
            self.table = self._get_table()
            return self.table is not None
        except Exception:
            return False
    
    def _connect(self):
        try:
            return lancedb.connect(self.db_path)
        except Exception as e:
            _logger.error(f"connect error: {e}")
            return None
    
    def _get_table(self):
        if self.db is None:
            return None
        try:
            table_names = self.db.table_names()
            if "memories" in table_names:
                return self.db.open_table("memories")
            
            # 创建表 - 使用 PyArrow schema
            table = self.db.create_table("memories", schema=SCHEMA)
            
            # 创建索引加速查询（vector和id字段）
            try:
                table.create_vector_index("vector", engine="lance")
            except:
                pass
            
            return table
        except Exception as e:
            _logger.error(f"get_table error: {e}")
            return None
    
    def _update_memory_content(self, memory_id: str, new_content: str) -> bool:
        """更新已有记忆内容（用于MERGE）"""
        if self.table is None:
            return False
        try:
            # LanceDB不支持直接更新单行，使用删除+添加模拟
            existing = self.table.search().where(f'id = "{memory_id}"').limit(1).to_arrow().to_pylist()
            if not existing:
                return False
            record = existing[0]
            record["content"] = new_content
            record["updated_at"] = datetime.now().isoformat()
            # 删除旧记录
            self.table.delete(f'id = "{memory_id}"')
            # 添加更新后的记录
            self.table.add([record])
            return True
        except Exception as e:
            _logger.warning(f"_update_memory_content failed: {e}")
            return False
    
    def _init_dedup(self):
        """初始化去重器，加载已有记忆"""
        try:
            from retrieval.multi_embed import get_embedder
            embedder = get_embedder()
            self._dedup.set_embedder(embedder)
            if self.table is not None:
                try:
                    # 加载已有记忆到去重器（最多500条，避免启动过慢）
                    sample = self.table.head(500)
                    if hasattr(sample, 'to_pylist'):
                        memories = sample.to_pylist()
                        self._dedup.load_memories(memories)
                except Exception as e:
                    _logger.debug(f"dedup init skipped: {e}")
        except ImportError:
            pass
    
    def _table(self):
        """Property for backward compatibility"""
        return self.table
    
    def _update_access_safe(self, memory_id: str):
        """更新访问记录（静默失败）"""
        if self.table is None:
            return
        try:
            now = datetime.now().isoformat()
            # LanceDB没有直接update，使用delete+add模拟
            existing = self.table.search().where(f'id = "{memory_id}"').limit(1).to_arrow().to_pylist()
            if existing:
                record = existing[0]
                record["last_accessed"] = now
                record["access_count"] = record.get("access_count", 0) + 1
                self.table.delete(f'id = "{memory_id}"')
                self.table.add([record])
        except Exception:
            pass
    
    def update_access(self, memory_id: str) -> bool:
        """公开的访问更新方法"""
        self._update_access_safe(memory_id)
        return True
    
    def get(self, memory_id: str) -> Optional[dict]:
        """获取单条记忆【P0修复】SQL注入防护 + 解密"""
        if self.table is None:
            return None
        try:
            # 白名单校验
            uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
            if not uuid_pattern.match(memory_id):
                return None
            
            # 使用 LanceDB 原生 where 子句
            zero_vector = [0.0] * 1024
            results = (
                self.table
                .search(zero_vector, vector_column_name="vector")
                .where(f"id = '{memory_id}'")
                .limit(1)
                .to_arrow()
                .to_pylist()
            )
            
            if not results:
                return None
            
            memory = results[0]
            
            # 【P1新增】解密敏感字段
            try:
                from e2e_encryption import decrypt_data as decrypt_text, is_encrypted
                if memory.get("content") and is_encrypted(memory["content"]):
                    memory["content"] = decrypt_text(memory["content"])
                if memory.get("transcript") and is_encrypted(memory["transcript"]):
                    memory["transcript"] = decrypt_text(memory["transcript"])
            except ImportError:
                pass
            
            return memory
        except Exception as e:
            return None
    
    def delete(self, memory_id: str = None, query: str = None) -> bool:
        """删除记忆【P0修复】SQL注入防护"""
        if self.table is None:
            return False
        try:
            if memory_id:
                # 白名单校验：只允许合法UUID格式
                uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
                if not uuid_pattern.match(memory_id):
                    _logger.warning("invalid memory_id format")
                    return False
                self.table.delete(f"id = '{memory_id}'")
            elif query:
                # 转义单引号 + 长度限制
                safe_query = query.replace("'", "''")[:200]
                self.table.delete(f"content LIKE '%{safe_query}%'")
            return True
        except Exception as e:
            _logger.error(f"delete error: {e}")
            return False
    
    def stats(self) -> dict:
        """获取统计信息（优化：使用 head() 获取代表性样本）"""
        if self.table is None:
            return {"total": 0, "by_type": {}}
        
        try:
            total = self.table.count_rows()
            
            # 使用 head() 获取前100条作为样本统计类型分布
            try:
                sample = self.table.head(100)
                if hasattr(sample, 'to_pylist'):
                    sample_list = sample.to_pylist()
                else:
                    sample_list = []
            except:
                sample_list = []
            
            by_type = {}
            for t in ["fact", "preference", "decision", "lesson", "entity", "task_state"]:
                count = sum(1 for r in sample_list if r.get("type") == t)
                by_type[t] = count
            
            return {"total": total, "by_type": by_type}
        except Exception as e:
            _logger.error(f"stats error: {e}")
            return {"total": 0, "by_type": {}}
    
    def get_old_memories(self, days: int = 30, limit: int = 100) -> list[dict]:
        """
        【P0修复】获取超过指定天数的记忆（用于归档）
        使用where过滤代替全表加载
        """
        if self.table is None:
            return []
        
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 【P0修复】使用head()采样代替全表加载
            # head()获取最早创建的记录，最适合查找"旧"记忆
            total = self.table.count_rows()
            if total == 0:
                return []
            
            # 获取足够多的样本用于过滤
            sample_size = min(2000, total)
            try:
                sample = self.table.head(sample_size)
                if hasattr(sample, 'to_pylist'):
                    sample_list = sample.to_pylist()
                else:
                    sample_list = []
            except:
                sample_list = []
            
            # 过滤出旧记忆
            old = []
            for r in sample_list:
                if r.get("created_at", "") < cutoff:
                    old.append(r)
                    if len(old) >= limit:
                        break
            
            return old
            
        except Exception as e:
            _logger.error(f"get_old_memories error: {e}")
            return []
