"""
提取-召回双缓冲架构 - Recall/Extraction Isolation
解决反馈循环放大幻觉的核心模块

问题：recall的记忆会重新进入提取管道，形成无限放大循环
- Mem0生产案例：808条"User prefers Vim"幻觉记忆
- LLM幻觉了一个虚假偏好，被存储后每次对话都被recall，再次提取，再次存储

解决：双缓冲架构
- 召回池（Recall Pool）：只读，不参与提取
- 提取池（Extraction Pool）：新记忆来源，与召回池完全隔离
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class DualBufferArchitecture:
    """
    双缓冲记忆架构
    
    两个独立存储池：
    1. Recall Pool（召回池）：所有被召回的记忆，但不参与提取
    2. Extraction Pool（提取池）：只包含原始输入的记忆，用于提取
    
    核心原则：
    - 从Recall Pool召回的记忆，永远不会重新进入提取管道
    - 只有Extraction Pool中的原始记忆才会被提取
    """
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or str(Path.home() / ".openclaw/workspace/memory"))
        self.recall_pool_path = self.base_path / "recall_pool"
        self.extraction_pool_path = self.base_path / "extraction_pool"
        
        # 确保目录存在
        self.recall_pool_path.mkdir(parents=True, exist_ok=True)
        self.extraction_pool_path.mkdir(parents=True, exist_ok=True)
        
        # 内存索引
        self._recall_index = {}  # memory_id -> metadata
        self._extraction_index = {}  # memory_id -> metadata
        
        # 加载已有索引
        self._load_indices()
    
    def _load_indices(self):
        """加载索引"""
        # 召回池索引
        recall_meta = self.recall_pool_path / "index.json"
        if recall_meta.exists():
            try:
                self._recall_index = json.loads(recall_meta.read_text())
            except Exception as e:
                logger.warning(f"加载召回池索引失败: {e}")
                self._recall_index = {}
        
        # 提取池索引
        extraction_meta = self.extraction_pool_path / "index.json"
        if extraction_meta.exists():
            try:
                self._extraction_index = json.loads(extraction_meta.read_text())
            except Exception as e:
                logger.warning(f"加载提取池索引失败: {e}")
                self._extraction_index = {}
    
    def _save_indices(self):
        """保存索引"""
        # 召回池索引
        recall_meta = self.recall_pool_path / "index.json"
        recall_meta.write_text(json.dumps(self._recall_index, indent=2, ensure_ascii=False))
        
        # 提取池索引
        extraction_meta = self.extraction_pool_path / "index.json"
        extraction_meta.write_text(json.dumps(self._extraction_index, indent=2, ensure_ascii=False))
    
    def add_to_recall_pool(self, memory: Dict) -> bool:
        """
        添加记忆到召回池
        
        Args:
            memory: 记忆数据，包含 id, content, type 等
            
        Returns:
            是否成功
        """
        memory_id = memory.get("id")
        if not memory_id:
            return False
        
        # 检查是否已在提取池（确保不是从提取池召回的）
        if memory_id in self._extraction_index:
            # 允许：同一记忆可以同时在两个池
            pass
        
        # 记录到召回池
        self._recall_index[memory_id] = {
            "added_at": datetime.now().isoformat(),
            "type": memory.get("type", "fact"),
            "content_preview": memory.get("content", "")[:100],
            "source": "recall",
            "recalled_count": self._recall_index.get(memory_id, {}).get("recalled_count", 0) + 1
        }
        
        self._save_indices()
        return True
    
    def add_to_extraction_pool(self, memory: Dict) -> bool:
        """
        添加记忆到提取池（仅限原始输入）
        
        重要：只有真正来自用户输入的记忆才能进入提取池
        被召回的记忆永远不能进入提取池
        
        Args:
            memory: 记忆数据，包含 id, content, type 等
            
        Returns:
            是否成功
        """
        memory_id = memory.get("id")
        if not memory_id:
            return False
        
        # 如果已在召回池，拒绝添加（防止循环）
        if memory_id in self._recall_index:
            # 检查来源
            recall_entry = self._recall_index[memory_id]
            if recall_entry.get("source") == "recall":
                # 这是被召回的记忆，不能再进入提取池
                return False
        
        # 记录到提取池
        self._extraction_index[memory_id] = {
            "added_at": datetime.now().isoformat(),
            "type": memory.get("type", "fact"),
            "content_preview": memory.get("content", "")[:100],
            "source": "original",  # 标记为原始输入
            "importance": memory.get("importance", 0.5)
        }
        
        self._save_indices()
        return True
    
    def is_in_extraction_pool(self, memory_id: str) -> bool:
        """检查记忆是否在提取池（是否可以参与提取）"""
        if memory_id not in self._extraction_index:
            return False
        
        entry = self._extraction_index[memory_id]
        return entry.get("source") == "original"
    
    def is_in_recall_pool(self, memory_id: str) -> bool:
        """检查记忆是否在召回池"""
        return memory_id in self._recall_index
    
    def get_extraction_pool_ids(self) -> Set[str]:
        """获取所有可以参与提取的记忆ID"""
        return {
            mid for mid, entry in self._extraction_index.items()
            if entry.get("source") == "original"
        }
    
    def get_recall_pool_count(self) -> int:
        """获取召回池记忆数量"""
        return len(self._recall_index)
    
    def get_extraction_pool_count(self) -> int:
        """获取提取池记忆数量"""
        return len(self._extraction_index)
    
    def get_stats(self) -> Dict:
        """获取双缓冲统计"""
        original_count = sum(
            1 for e in self._extraction_index.values()
            if e.get("source") == "original"
        )
        
        return {
            "recall_pool_total": len(self._recall_index),
            "extraction_pool_total": len(self._extraction_index),
            "extraction_pool_original": original_count,
            "extraction_pool_recalled": len(self._extraction_index) - original_count,
            "isolation_status": "✅ 正常" if original_count > 0 else "⚠️ 池为空"
        }
    
    def clear_recall_pool(self):
        """清空召回池（通常在会话结束后调用）"""
        self._recall_index = {}
        self._save_indices()
    
    def verify_isolation(self) -> Dict:
        """
        验证双缓冲隔离是否正常
        
        检测是否有记忆同时出现在两个池，且来源标记错误
        """
        issues = []
        
        # 检查：召回池中的记忆是否正确标记
        for memory_id, entry in self._recall_index.items():
            if entry.get("source") != "recall":
                issues.append(f"召回池记忆 {memory_id} 来源标记错误: {entry.get('source')}")
        
        # 检查：提取池中是否有被召回的记忆（不应该有）
        for memory_id, entry in self._extraction_index.items():
            if entry.get("source") == "recall":
                issues.append(f"提取池中发现召回记忆 {memory_id}，违反隔离原则")
        
        return {
            "isolated": len(issues) == 0,
            "issues": issues,
            "total_checks": len(self._recall_index) + len(self._extraction_index)
        }


# ============================================================
# 与LanceDB的集成接口
# ============================================================

class RecallExtractionIsolation:
    """
    提取-召回隔离管理器
    
    与LanceDB配合使用，在store和recall时自动处理双缓冲逻辑
    """
    
    def __init__(self, db_store=None):
        self.db = db_store  # LanceDBStore实例
        self.dual_buffer = DualBufferArchitecture()
    
    def store_with_isolation(self, memory: Dict) -> Dict:
        """
        存储记忆（带隔离检查）
        
        逻辑：
        1. 检查是否应该存储（去噪 + 阈值）
        2. 添加到提取池（如果是原始输入）
        3. 存储到LanceDB
        4. 返回结果
        """
        from denoise_filter import should_store_memory, register_stored_memory
        
        memory_id = memory.get("id")
        content = memory.get("content", "")
        importance = memory.get("importance", 0.5)
        confidence = memory.get("confidence", 0.8)
        
        # 1. 去噪和阈值检查
        should_store, reason = should_store_memory(
            content, importance, confidence
        )
        
        if not should_store:
            return {
                "success": False,
                "reason": reason,
                "memory_id": memory_id
            }
        
        # 2. 添加到提取池（只有通过检查的记忆才能进入）
        in_extraction_pool = self.dual_buffer.add_to_extraction_pool(memory)
        
        # 3. 存储到LanceDB
        if self.db:
            try:
                success = self.db.store(memory)
                if success:
                    # 注册到矛盾检测器
                    register_stored_memory(memory)
                    return {
                        "success": True,
                        "reason": reason,
                        "memory_id": memory.get("id"),
                        "in_extraction_pool": in_extraction_pool
                    }
                else:
                    return {
                        "success": False,
                        "reason": "数据库存储失败",
                        "memory_id": memory_id
                    }
            except Exception as e:
                return {
                    "success": False,
                    "reason": f"存储异常: {str(e)}",
                    "memory_id": memory_id
                }
        
        return {
            "success": True,
            "reason": "跳过数据库（未配置）",
            "memory_id": memory_id,
            "in_extraction_pool": in_extraction_pool
        }
    
    def recall_with_isolation(self, memory: Dict) -> Dict:
        """
        召回记忆（带隔离标记）
        
        逻辑：
        1. 添加到召回池
        2. 返回记忆（带隔离标记）
        """
        memory_id = memory.get("id")
        
        # 添加到召回池
        in_recall_pool = self.dual_buffer.add_to_recall_pool(memory)
        
        return {
            "memory": memory,
            "in_recall_pool": in_recall_pool,
            "is_from_extraction_pool": self.dual_buffer.is_in_extraction_pool(memory_id)
        }
    
    def get_isolation_status(self) -> Dict:
        """获取隔离状态"""
        return self.dual_buffer.get_stats()


# 全局实例
_recall_extraction_isolation = None


def get_recall_extraction_isolation(db_store=None) -> RecallExtractionIsolation:
    """获取全局隔离管理器"""
    global _recall_extraction_isolation
    if _recall_extraction_isolation is None:
        _recall_extraction_isolation = RecallExtractionIsolation(db_store)
    return _recall_extraction_isolation
