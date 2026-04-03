"""
事务管理模块 - Transaction Management
支持批量操作的原子性

功能：
1. 批量操作的事务性
2. 操作失败时回滚
3. 记录操作日志用于审计
"""
import json
import copy
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from threading import Lock


class Transaction:
    """
    事务包装器
    
    使用方式：
    with Transaction(db) as txn:
        txn.store(memory1)
        txn.store(memory2)
        txn.delete(memory_id)
        # 如果任何操作失败，自动回滚
    """
    
    def __init__(self, db_store):
        self.db = db_store
        self._operations = []  # 待执行的操作
        self._snapshots = {}   # 操作前的快照（用于回滚）
        self._committed = False
        self._lock = Lock()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # 发生异常，回滚
            self.rollback()
            return False
        if not self._committed:
            self.commit()
        return True
    
    def store(self, memory: dict) -> bool:
        """
        添加存储操作到事务
        
        Args:
            memory: 记忆数据
        
        Returns:
            是否成功添加（不是是否执行）
        """
        with self._lock:
            # 记录操作前状态（如果存在）
            memory_id = memory.get("id")
            if memory_id:
                existing = self.db.get(memory_id)
                self._snapshots[memory_id] = copy.deepcopy(existing)
            
            self._operations.append({
                "type": "store",
                "data": copy.deepcopy(memory),
                "timestamp": datetime.now().isoformat()
            })
            return True
    
    def delete(self, memory_id: str) -> bool:
        """
        添加删除操作到事务
        
        Args:
            memory_id: 要删除的记忆ID
        
        Returns:
            是否成功添加
        """
        with self._lock:
            # 记录操作前状态
            existing = self.db.get(memory_id)
            if existing:
                self._snapshots[memory_id] = copy.deepcopy(existing)
            
            self._operations.append({
                "type": "delete",
                "memory_id": memory_id,
                "timestamp": datetime.now().isoformat()
            })
            return True
    
    def update(self, memory_id: str, updates: dict) -> bool:
        """
        添加更新操作到事务
        
        Args:
            memory_id: 记忆ID
            updates: 要更新的字段
        
        Returns:
            是否成功添加
        """
        with self._lock:
            # 记录操作前状态
            existing = self.db.get(memory_id)
            self._snapshots[memory_id] = copy.deepcopy(existing)
            
            self._operations.append({
                "type": "update",
                "memory_id": memory_id,
                "updates": copy.deepcopy(updates),
                "timestamp": datetime.now().isoformat()
            })
            return True
    
    def commit(self):
        """
        提交事务
        执行所有待定操作
        """
        with self._lock:
            if self._committed:
                return
            
            committed = []
            
            try:
                for op in self._operations:
                    if op["type"] == "store":
                        self.db.store(op["data"])
                        committed.append(("store", op["data"].get("id")))
                    
                    elif op["type"] == "delete":
                        self.db.delete(memory_id=op["memory_id"])
                        committed.append(("delete", op["memory_id"]))
                    
                    elif op["type"] == "update":
                        self.db.update(op["memory_id"], op["updates"])
                        committed.append(("update", op["memory_id"]))
                
                self._committed = True
                
                # 记录已提交的操作（用于审计）
                self._log_commit(committed)
                
            except Exception as e:
                # 提交失败，回滚
                self._rollback_operations(committed)
                raise e
    
    def rollback(self):
        """
        回滚事务
        恢复所有被操作影响的数据
        """
        with self._lock:
            self._rollback_operations(self._get_committed_operations())
    
    def _get_committed_operations(self) -> List:
        """获取已提交的操作列表"""
        committed = []
        for op in self._operations:
            if op["type"] == "store":
                committed.append(("store", op["data"].get("id")))
            elif op["type"] == "delete":
                committed.append(("delete", op["memory_id"]))
            elif op["type"] == "update":
                committed.append(("update", op["memory_id"]))
        return committed
    
    def _rollback_operations(self, committed: List):
        """
        回滚已执行的操作
        
        Args:
            committed: 已执行的操作列表 [(type, id), ...]
        """
        # 逆序回滚
        for op_type, op_id in reversed(committed):
            try:
                if op_type == "store":
                    # 删除刚存储的
                    self.db.delete(memory_id=op_id)
                elif op_type == "delete":
                    # 恢复已删除的
                    if op_id in self._snapshots:
                        self.db.store(self._snapshots[op_id])
                elif op_type == "update":
                    # 恢复原始值
                    if op_id in self._snapshots:
                        self.db.store(self._snapshots[op_id])
            except Exception as e:
                _logger.error(f"Rollback failed for {op_type} {op_id}: {e}")
    
    def _log_commit(self, operations: List):
        """记录提交日志"""
        try:
            log_dir = Path(__file__).parent / "transaction_logs"
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / "commits.jsonl"
            
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "operations": len(operations),
                "details": operations
            }
            
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            _logger.warning(f"Failed to log transaction: {e}")


class TransactionLog:
    """
    事务日志查看器
    """
    
    def __init__(self):
        self.log_dir = Path(__file__).parent / "transaction_logs"
        self.log_file = self.log_dir / "commits.jsonl"
    
    def get_recent(self, limit: int = 50) -> List[Dict]:
        """获取最近的事务日志"""
        if not self.log_file.exists():
            return []
        
        logs = []
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
            
            return logs[-limit:]
        except Exception:
            return []
    
    def get_stats(self) -> Dict:
        """获取事务统计"""
        logs = self.get_recent(1000)
        
        return {
            "total_transactions": len(logs),
            "total_operations": sum(l.get("operations", 0) for l in logs),
            "last_transaction": logs[-1].get("timestamp") if logs else None
        }


# 便捷函数
def with_transaction(db_store) -> Transaction:
    """创建事务上下文"""
    return Transaction(db_store)
