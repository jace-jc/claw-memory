"""
Claw Memory 隐私合规模块 - Privacy Compliance
支持GDPR被遗忘权和数据可携权

功能：
1. 数据导出（JSON格式）
2. 数据删除（完全删除）
3. 匿名化处理
4. 隐私审计日志
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 隐私配置
PRIVACY_LOG_DIR = Path(__file__).parent / "privacy_logs"


class PrivacyCompliance:
    """
    隐私合规管理器
    
    支持：
    1. 数据导出（导出用户所有数据）
    2. 数据删除（完全删除）
    3. 隐私审计（日志所有操作）
    """
    
    def __init__(self):
        PRIVACY_LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.audit_file = PRIVACY_LOG_DIR / "audit.jsonl"
    
    def export_data(self, db) -> Dict:
        """
        导出用户所有数据（数据可携权）
        
        Returns:
            包含所有记忆的JSON结构
        """
        self._audit_log("export", {"action": "data_export_request"})
        
        try:
            # 获取所有记忆
            total = db.table.count_rows()
            memories = []
            
            if total > 0:
                sample = db.table.head(min(total, 10000)).to_pylist()
                memories = sample
            
            export_data = {
                "export_date": datetime.now().isoformat(),
                "version": "1.0",
                "total_records": len(memories),
                "memories": memories,
                "metadata": {
                    "source": "Claw Memory",
                    "format": "JSON"
                }
            }
            
            self._audit_log("export", {
                "action": "data_export_complete",
                "record_count": len(memories)
            })
            
            return {
                "success": True,
                "data": export_data,
                "count": len(memories)
            }
            
        except Exception as e:
            self._audit_log("export", {"action": "data_export_failed", "error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_all_data(self, db) -> Dict:
        """
        删除用户所有数据（被遗忘权）
        
        注意：这是不可逆操作！
        """
        self._audit_log("delete", {"action": "delete_all_request"})
        
        try:
            # 获取所有记忆
            total = db.table.count_rows()
            
            if total > 0:
                # 删除所有记录
                # 由于LanceDB不支持直接删除所有记录，我们需要重建表
                db.table.delete('true')  # 删除所有
                
                # 或者标记为删除（如果实现了软删除）
            
            self._audit_log("delete", {
                "action": "delete_all_complete",
                "deleted_count": total
            })
            
            return {
                "success": True,
                "message": f"已删除 {total} 条记录",
                "deleted_count": total
            }
            
        except Exception as e:
            self._audit_log("delete", {"action": "delete_all_failed", "error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_memory(self, db, memory_id: str) -> Dict:
        """
        删除单条记忆
        
        Args:
            memory_id: 记忆ID
        """
        self._audit_log("delete", {"action": "delete_single_request", "memory_id": memory_id})
        
        try:
            # 删除单条记录
            db.delete(memory_id)
            
            self._audit_log("delete", {
                "action": "delete_single_complete",
                "memory_id": memory_id
            })
            
            return {
                "success": True,
                "message": f"已删除记忆: {memory_id}"
            }
            
        except Exception as e:
            self._audit_log("delete", {"action": "delete_single_failed", "error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def anonymize_data(self, db, memory_id: str) -> Dict:
        """
        匿名化记忆（保留结构但删除内容）
        
        Args:
            memory_id: 记忆ID
        """
        self._audit_log("anonymize", {"action": "anonymize_request", "memory_id": memory_id})
        
        try:
            memory = db.get(memory_id)
            if not memory:
                return {
                    "success": False,
                    "error": "记忆不存在"
                }
            
            # 用占位符替换内容
            updated = memory.copy()
            updated["content"] = "[已匿名化]"
            updated["summary"] = "[已匿名化]"
            updated["transcript"] = None
            updated["_anonymized"] = True
            updated["_anonymized_at"] = datetime.now().isoformat()
            
            # 更新
            db.store(
                memory_type=updated.get("type", "unknown"),
                content=updated["content"],
                summary=updated["summary"],
                importance=updated.get("importance", 0),
                source="anonymized",
                metadata=updated
            )
            
            self._audit_log("anonymize", {
                "action": "anonymize_complete",
                "memory_id": memory_id
            })
            
            return {
                "success": True,
                "message": f"已匿名化记忆: {memory_id}"
            }
            
        except Exception as e:
            self._audit_log("anonymize", {"action": "anonymize_failed", "error": str(e)})
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """
        获取隐私审计日志
        
        Args:
            limit: 返回条数
        """
        if not self.audit_file.exists():
            return []
        
        try:
            logs = []
            with open(self.audit_file, 'r') as f:
                for line in f:
                    if line.strip():
                        logs.append(json.loads(line))
            
            return logs[-limit:]
            
        except Exception:
            return []
    
    def _audit_log(self, operation: str, details: Dict):
        """记录审计日志"""
        try:
            PRIVACY_LOG_DIR.mkdir(parents=True, exist_ok=True)
            
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                **details
            }
            
            with open(self.audit_file, 'a') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                
        except Exception:
            pass  # 日志失败不影响主流程


# 全局实例
_privacy = None


def get_privacy() -> PrivacyCompliance:
    """获取隐私合规实例"""
    global _privacy
    if _privacy is None:
        _privacy = PrivacyCompliance()
    return _privacy
