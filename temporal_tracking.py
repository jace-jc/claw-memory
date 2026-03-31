"""
时序追踪模块 - Temporal Memory Tracking
支持记忆的时间范围追踪、版本管理和历史追溯
"""
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path
from memory_config import CONFIG


class TemporalMemory:
    """
    时序记忆管理器
    
    功能：
    1. 追踪记忆的时间范围 (valid_from, valid_until)
    2. 版本管理和superseded_by链
    3. "截至X时间点"的查询
    4. 偏好变化历史追踪
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or CONFIG.get("db_path")
        self.version_file = Path(self.db_path).parent / "temporal_versions.json"
        self._ensure_dir()
        self.versions = self._load_versions()
    
    def _ensure_dir(self):
        """确保目录存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _load_versions(self) -> dict:
        """加载版本历史"""
        if self.version_file.exists():
            try:
                with open(self.version_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {"versions": {}, "superseded": {}}
    
    def _save_versions(self):
        """保存版本历史"""
        with open(self.version_file, 'w', encoding='utf-8') as f:
            json.dump(self.versions, f, ensure_ascii=False, indent=2)
    
    def add_with_temporal(self, memory: dict, force: bool = False) -> dict:
        """
        添加带时间戳的记忆
        
        Args:
            memory: 记忆字典（包含id, type, content等）
            force: 是否强制创建新版本（忽略已存在）
            
        Returns:
            更新后的记忆（添加了temporal字段）
        """
        memory_id = memory.get("id")
        content = memory.get("content", "")
        now = datetime.now().isoformat()
        
        # 检查是否已有同类记忆需要设置为过期
        if not force and memory_id in self.versions["versions"]:
            # 已存在，跳过
            return memory
        
        # 检查是否存在相同内容的记忆
        existing_id = self._find_existing_content(content)
        
        if existing_id and not force:
            # 内容相同，更新原记忆的访问时间
            if existing_id in self.versions["versions"]:
                self.versions["versions"][existing_id]["last_accessed"] = now
                self._save_versions()
            return memory
        
        # 设置时间字段
        memory["temporal"] = {
            "valid_from": now,
            "valid_until": None,  # None表示当前有效
            "created_at": now,
            "last_accessed": now,
            "version": 1,
            "superseded_by": None,
            "supersedes": None  # 记录这个记忆替代了哪个
        }
        
        # 如果之前有同类记忆，自动设置失效时间
        previous = self._find_previous_similar(content, memory.get("type"))
        if previous:
            self._supersede(previous, memory_id)
            memory["temporal"]["supersedes"] = previous
            memory["temporal"]["version"] = self.versions["versions"].get(previous, {}).get("version", 0) + 1
        
        # 保存版本
        self.versions["versions"][memory_id] = memory["temporal"].copy()
        self._save_versions()
        
        return memory
    
    def _find_existing_content(self, content: str) -> Optional[str]:
        """查找是否存在相同内容的记忆"""
        for vid, vdata in self.versions["versions"].items():
            # 通过记忆ID在数据库中查找内容对比
            pass  # 需要配合主存储使用
        return None
    
    def _find_previous_similar(self, content: str, memory_type: str) -> Optional[str]:
        """查找之前相似的记忆"""
        # 简单实现：查找同类型的有效记忆
        for vid, vdata in self.versions["versions"].items():
            if vdata.get("valid_until") is None and vdata.get("type") == memory_type:
                return vid
        return None
    
    def _supersede(self, old_id: str, new_id: str):
        """设置旧记忆被新记忆替代"""
        if old_id in self.versions["versions"]:
            self.versions["versions"][old_id]["valid_until"] = datetime.now().isoformat()
            self.versions["versions"][old_id]["superseded_by"] = new_id
            
            # 记录替代关系
            if new_id not in self.versions["superseded"]:
                self.versions["superseded"][new_id] = []
            self.versions["superseded"][new_id].append(old_id)
    
    def get_temporal(self, memory_id: str) -> Optional[dict]:
        """获取记忆的时序信息"""
        return self.versions["versions"].get(memory_id)
    
    def query_as_of(self, entity_or_content: str, as_of: datetime = None) -> List[dict]:
        """
        查询截至as_of时间点有效的记忆
        
        Args:
            entity_or_content: 实体名或记忆内容关键词
            as_of: 查询时间点，默认为当前时间
            
        Returns:
            在as_of时刻有效的记忆列表
        """
        if as_of is None:
            as_of = datetime.now()
        
        as_of_iso = as_of.isoformat()
        valid_memories = []
        
        # 遍历所有版本，找出版本链的头部
        for memory_id, tdata in self.versions["versions"].items():
            # 跳过被替代的记忆
            if tdata.get("valid_until") is not None:
                continue
            
            # 检查是否在时间范围内
            if tdata.get("valid_from", "") <= as_of_iso:
                valid_memories.append({
                    "memory_id": memory_id,
                    "valid_from": tdata.get("valid_from"),
                    "version": tdata.get("version", 1),
                    "superseded_by": tdata.get("superseded_by")
                })
        
        return valid_memories
    
    def get_history(self, memory_id: str) -> dict:
        """
        获取记忆的完整历史（版本链）
        
        Returns:
            {"current": {...}, "history": [...]}
        """
        result = {
            "current": memory_id,
            "history": [],
            "chain_length": 0
        }
        
        # 沿着superseded_by链向上追溯
        current_id = memory_id
        visited = set()
        
        while current_id:
            if current_id in visited:
                break  # 避免循环
            visited.add(current_id)
            
            tdata = self.versions["versions"].get(current_id)
            if not tdata:
                break
            
            result["history"].append({
                "memory_id": current_id,
                "valid_from": tdata.get("valid_from"),
                "valid_until": tdata.get("valid_until"),
                "version": tdata.get("version", 1)
            })
            
            current_id = tdata.get("supersedes")  # 向上追溯
        
        result["chain_length"] = len(result["history"])
        result["history"].reverse()  # 从旧到新
        
        return result
    
    def get_change_log(self, days: int = 30) -> List[dict]:
        """
        获取最近N天的变更日志
        
        Returns:
            [{"date": "...", "changes": [...]}]
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        changes = []
        for memory_id, tdata in self.versions["versions"].items():
            # 记录变更
            created = tdata.get("created_at", "")
            if created >= cutoff:
                changes.append({
                    "type": "created",
                    "memory_id": memory_id,
                    "date": created,
                    "version": tdata.get("version", 1)
                })
            
            # 记录替代
            superseded = tdata.get("superseded_by")
            if superseded and tdata.get("valid_until", "") >= cutoff:
                changes.append({
                    "type": "superseded",
                    "memory_id": memory_id,
                    "superseded_by": superseded,
                    "date": tdata.get("valid_until", ""),
                    "version": tdata.get("version", 1)
                })
        
        # 按日期排序
        changes.sort(key=lambda x: x["date"], reverse=True)
        return changes
    
    def get_preference_timeline(self, entity: str = None) -> dict:
        """
        获取偏好变化时间线
        
        用于追踪用户偏好的历史变化
        """
        timeline = []
        
        for memory_id, tdata in self.versions["versions"].items():
            if tdata.get("type") == "preference":
                timeline.append({
                    "memory_id": memory_id,
                    "valid_from": tdata.get("valid_from"),
                    "valid_until": tdata.get("valid_until"),
                    "is_current": tdata.get("valid_until") is None
                })
        
        return {
            "entity": entity or "user",
            "total_changes": len(timeline),
            "current_preferences": sum(1 for t in timeline if t["is_current"]),
            "timeline": sorted(timeline, key=lambda x: x["valid_from"], reverse=True)
        }
    
    def prune_old_versions(self, keep_days: int = 90) -> int:
        """
        清理过老的历史版本
        
        Args:
            keep_days: 保留最近N天的历史
            
        Returns:
            清理的记忆数量
        """
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
        pruned = 0
        
        to_remove = []
        for memory_id, tdata in self.versions["versions"].items():
            # 只清理已被替代且超过保留期的
            if tdata.get("valid_until"):
                if tdata.get("valid_until", "") < cutoff:
                    to_remove.append(memory_id)
        
        for memory_id in to_remove:
            del self.versions["versions"][memory_id]
            pruned += 1
        
        if pruned > 0:
            self._save_versions()
        
        return pruned


# 全局实例
_temporal = None


def get_temporal() -> TemporalMemory:
    """获取时序记忆实例"""
    global _temporal
    if _temporal is None:
        _temporal = TemporalMemory()
    return _temporal
