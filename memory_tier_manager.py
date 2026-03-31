"""
Memory Tier Manager - 分层架构优化实现
==========================================

4-Tier 分层架构:
- HOT (importance > 0.9): 当前会话相关，SESSION-STATE.md
- WARM (importance > 0.7): 最近使用，LanceDB (向量+BM25+KG)
- COLD (importance > 0.5): 永久记忆，MEMORY.md + Git
- ARCHIVED (importance <= 0.5): 低价值记忆，可遗忘

自动分层规则:
1. 新记忆默认 WARM
2. 定期重新评估重要性
3. 低价值记忆自动归档

工具函数:
- get_tier(memory_id)       # 获取记忆所在层级
- move_tier(memory_id, tier) # 移动记忆到指定层级
- get_tier_stats()          # 获取各层级统计
"""
import os
import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

from memory_config import CONFIG
from memory_session import session_state

# ==================== 层级定义 ====================

TIER_HOT = "HOT"
TIER_WARM = "WARM"
TIER_COLD = "COLD"
TIER_ARCHIVED = "ARCHIVED"
TIER_ALL = "ALL"

TIER_LEVELS = [TIER_HOT, TIER_WARM, TIER_COLD, TIER_ARCHIVED]

# 重要性阈值
IMPORTANCE_THRESHOLDS = {
    TIER_HOT: 0.9,
    TIER_WARM: 0.7,
    TIER_COLD: 0.5,
    TIER_ARCHIVED: 0.0,  # <= 0.5
}

# 层级存储位置
TIER_LOCATIONS = {
    TIER_HOT: "SESSION-STATE.md (RAM)",
    TIER_WARM: "LanceDB (向量+BM25+KG)",
    TIER_COLD: "MEMORY.md + Git",
    TIER_ARCHIVED: "归档目录 (可遗忘)",
}

# 默认 TTL（存活时间）
TIER_TTL = {
    TIER_HOT: timedelta(hours=24),      # 会话级
    TIER_WARM: timedelta(days=30),       # 30天
    TIER_COLD: timedelta(days=365),     # 永久
    TIER_ARCHIVED: timedelta(days=90),   # 90天后可彻底删除
}


def get_tier_by_importance(importance: float) -> str:
    """根据重要性值获取对应层级"""
    if importance > IMPORTANCE_THRESHOLDS[TIER_HOT]:
        return TIER_HOT
    elif importance > IMPORTANCE_THRESHOLDS[TIER_WARM]:
        return TIER_WARM
    elif importance > IMPORTANCE_THRESHOLDS[TIER_COLD]:
        return TIER_COLD
    else:
        return TIER_ARCHIVED


def is_importance_for_tier(importance: float, tier: str) -> bool:
    """检查重要性是否满足指定层级"""
    return importance > IMPORTANCE_THRESHOLDS.get(tier, 0.0)


# ==================== 核心管理器 ====================

class MemoryTierManagerV2:
    """
    分层管理器 V2 - 支持 4-Tier 架构
    
    功能:
    - 自动分层 (importance-based)
    - 层级移动
    - 定期重新评估
    - 统计查询
    """
    
    def __init__(self):
        self.memory_dir = Path(CONFIG.get("memory_dir", "/Users/claw/.openclaw/workspace/memory"))
        self.archive_dir = self.memory_dir / "archived"
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # 上次重新评估时间
        self._last_reTier_time = None
        # 重新评估间隔（默认1小时）
        self._reTier_interval = timedelta(hours=1)
    
    # ==================== 核心 API ====================
    
    def get_tier(self, memory_id: str) -> Dict[str, Any]:
        """
        获取记忆所在层级
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            {
                "memory_id": str,
                "tier": str,  # HOT/WARM/COLD/ARCHIVED
                "memory": dict,  # 记忆详情
                "location": str  # 存储位置描述
            }
        """
        # 1. 检查 HOT (SESSION-STATE.md)
        hot_result = self._check_hot(memory_id)
        if hot_result["found"]:
            return hot_result
        
        # 2. 检查 WARM (LanceDB)
        warm_result = self._check_warm(memory_id)
        if warm_result["found"]:
            return warm_result
        
        # 3. 检查 COLD (MEMORY.md + Git)
        cold_result = self._check_cold(memory_id)
        if cold_result["found"]:
            return cold_result
        
        # 4. 检查 ARCHIVED
        archived_result = self._check_archived(memory_id)
        if archived_result["found"]:
            return archived_result
        
        return {
            "memory_id": memory_id,
            "tier": None,
            "found": False,
            "message": f"记忆 {memory_id} 不存在"
        }
    
    def move_tier(self, memory_id: str, target_tier: str, force: bool = False) -> Dict[str, Any]:
        """
        移动记忆到指定层级
        
        Args:
            memory_id: 记忆ID
            target_tier: 目标层级 (HOT/WARM/COLD/ARCHIVED)
            force: 是否强制移动（忽略重要性检查）
            
        Returns:
            {
                "success": bool,
                "message": str,
                "memory_id": str,
                "from_tier": str,
                "to_tier": str
            }
        """
        if target_tier not in TIER_LEVELS:
            return {
                "success": False,
                "message": f"无效的层级: {target_tier}",
                "memory_id": memory_id
            }
        
        # 获取当前层级
        current = self.get_tier(memory_id)
        if not current["found"]:
            return {
                "success": False,
                "message": f"记忆 {memory_id} 不存在",
                "memory_id": memory_id
            }
        
        from_tier = current["tier"]
        if from_tier == target_tier:
            return {
                "success": True,
                "message": f"记忆已在 {target_tier} 层",
                "memory_id": memory_id,
                "from_tier": from_tier,
                "to_tier": target_tier
            }
        
        # 重要性检查（除非强制）
        memory = current["memory"]
        if not force:
            importance = memory.get("importance", 0.0)
            if not is_importance_for_tier(importance, target_tier):
                return {
                    "success": False,
                    "message": f"重要性 {importance} 不满足 {target_tier} 层要求 (需 > {IMPORTANCE_THRESHOLDS.get(target_tier, 0)})",
                    "memory_id": memory_id,
                    "from_tier": from_tier,
                    "to_tier": target_tier
                }
        
        # 执行移动
        return self._do_move(memory, from_tier, target_tier)
    
    def get_tier_stats(self) -> Dict[str, Any]:
        """
        获取各层级统计信息
        
        Returns:
            {
                "HOT": {"count": int, "location": str, ...},
                "WARM": {"count": int, "location": str, ...},
                "COLD": {"count": int, "location": str, ...},
                "ARCHIVED": {"count": int, "location": str, ...},
                "total": int,
                "summary": str
            }
        """
        from lancedb_store import get_db_store
        
        stats = {}
        
        # HOT 统计
        hot_summary = session_state.get_summary()
        stats[TIER_HOT] = {
            "count": 1 if hot_summary else 0,
            "location": TIER_LOCATIONS[TIER_HOT],
            "has_content": bool(hot_summary),
            "last_updated": session_state.data.get("last_updated", "never")
        }
        
        # WARM 统计 (LanceDB)
        try:
            db = get_db_store()
            warm_data = db.stats()
            stats[TIER_WARM] = {
                "count": warm_data.get("total", 0),
                "location": TIER_LOCATIONS[TIER_WARM],
                "by_type": warm_data.get("by_type", {}),
                "db_path": CONFIG.get("db_path")
            }
        except Exception as e:
            stats[TIER_WARM] = {"count": 0, "error": str(e)}
        
        # COLD 统计 (Git + MEMORY.md)
        cold_memories = self._get_cold_memories_count()
        stats[TIER_COLD] = {
            "count": cold_memories,
            "location": TIER_LOCATIONS[TIER_COLD],
            "memory_file": str(self.memory_dir / "MEMORY.md")
        }
        
        # ARCHIVED 统计
        archived_files = list(self.archive_dir.glob("*.md"))
        stats[TIER_ARCHIVED] = {
            "count": len(archived_files),
            "location": str(self.archive_dir),
            "oldest": self._get_oldest_archived() if archived_files else None
        }
        
        # 总计
        total = sum(s.get("count", 0) for s in stats.values())
        
        return {
            **stats,
            "total": total,
            "summary": self._format_stats_summary(stats),
            "thresholds": IMPORTANCE_THRESHOLDS,
            "ttl": {k: str(v) for k, v in TIER_TTL.items()}
        }
    
    # ==================== 分层操作 ====================
    
    def assign_tier(self, memory: dict) -> str:
        """
        为新记忆自动分配层级
        
        Args:
            memory: 记忆字典
            
        Returns:
            分配的层级 (默认 WARM)
        """
        importance = memory.get("importance", 0.5)
        tier = get_tier_by_importance(importance)
        
        # 新记忆默认不进入 HOT（HOT 是会话级）
        if tier == TIER_HOT:
            return TIER_WARM
        
        return tier
    
    def should_reTier(self, force: bool = False) -> bool:
        """
        检查是否需要重新分层
        
        Args:
            force: 强制重新分层
            
        Returns:
            bool
        """
        if force:
            return True
        
        if self._last_reTier_time is None:
            return True
        
        elapsed = datetime.now() - self._last_reTier_time
        return elapsed >= self._reTier_interval
    
    def reTier_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        重新评估所有记忆的层级
        
        Args:
            dry_run: 只返回将要执行的操作，不实际执行
            
        Returns:
            {
                "evaluated": int,
                "moved": int,
                "archived": int,
                "resurrected": int,
                "actions": list  # 即将执行的操作列表
            }
        """
        from lancedb_store import get_db_store
        
        db = get_db_store()
        actions = []
        stats = {"evaluated": 0, "moved": 0, "archived": 0, "resurrected": 0}
        
        try:
            # 获取所有 WARM 层记忆
            table = db.table
            records = table.to_pylist()
            
            for memory in records:
                stats["evaluated"] += 1
                current_tier = memory.get("tier", TIER_WARM)
                importance = memory.get("importance", 0.5)
                correct_tier = get_tier_by_importance(importance)
                
                if current_tier != correct_tier:
                    action = {
                        "memory_id": memory.get("id"),
                        "content_preview": memory.get("content", "")[:50],
                        "from_tier": current_tier,
                        "to_tier": correct_tier,
                        "importance": importance
                    }
                    actions.append(action)
                    
                    if not dry_run:
                        self._do_move(memory, current_tier, correct_tier)
                        stats["moved"] += 1
                        
                        if correct_tier == TIER_ARCHIVED:
                            stats["archived"] += 1
                        elif correct_tier in (TIER_COLD, TIER_WARM) and current_tier == TIER_ARCHIVED:
                            stats["resurrected"] += 1
                
                # 更新 last_reTier_time
                self._last_reTier_time = datetime.now()
            
            # 更新 last_reTier_time 即使是 dry_run
            if dry_run:
                self._last_reTier_time = datetime.now()
                
        except Exception as e:
            return {"error": str(e), **stats}
        
        return {**stats, "actions": actions[:20] if dry_run else actions}  # dry_run 只返回前20条
    
    def auto_archive_low_value(self, threshold: float = 0.3, batch_size: int = 50) -> Dict[str, Any]:
        """
        自动归档低价值记忆
        
        Args:
            threshold: 重要性阈值，默认 0.3
            batch_size: 每批处理数量
            
        Returns:
            归档结果
        """
        from lancedb_store import get_db_store
        
        db = get_db_store()
        archived = 0
        errors = []
        
        try:
            table = db.table
            records = table.to_pylist()
            
            to_archive = [
                m for m in records
                if m.get("importance", 1.0) < threshold
                and m.get("tier", TIER_WARM) != TIER_ARCHIVED
            ][:batch_size]
            
            for memory in to_archive:
                try:
                    # 归档到 ARCHIVED
                    if self._archive_memory(memory):
                        # 从 WARM 删除
                        db.delete(memory_id=memory.get("id"))
                        archived += 1
                except Exception as e:
                    errors.append({"id": memory.get("id"), "error": str(e)})
                    
        except Exception as e:
            return {"success": False, "error": str(e), "archived": 0}
        
        return {
            "success": True,
            "archived": archived,
            "threshold": threshold,
            "total_low_value": len(to_archive),
            "errors": errors if errors else None
        }
    
    # ==================== 私有方法 ====================
    
    def _check_hot(self, memory_id: str) -> Dict[str, Any]:
        """检查 HOT 层"""
        # HOT 层不通过 ID 查询，而是检查会话状态
        # 这里返回 not found，实际使用 get_summary() 查看 HOT 内容
        return {"found": False, "tier": TIER_HOT, "memory": None}
    
    def _check_warm(self, memory_id: str) -> Dict[str, Any]:
        """检查 WARM 层 (LanceDB)"""
        from lancedb_store import get_db_store
        
        try:
            db = get_db_store()
            memory = db.get(memory_id)
            if memory:
                return {
                    "found": True,
                    "tier": memory.get("tier", TIER_WARM),
                    "memory": memory,
                    "location": TIER_LOCATIONS.get(memory.get("tier", TIER_WARM), "LanceDB")
                }
        except Exception:
            pass
        
        return {"found": False, "tier": TIER_WARM, "memory": None}
    
    def _check_cold(self, memory_id: str) -> Dict[str, Any]:
        """检查 COLD 层 (MEMORY.md)"""
        # 检查 MEMORY.md 文件
        memory_file = self.memory_dir / "MEMORY.md"
        if memory_file.exists():
            try:
                content = memory_file.read_text()
                # 简单查找（实际应该解析）
                if memory_id in content:
                    return {
                        "found": True,
                        "tier": TIER_COLD,
                        "memory": {"id": memory_id, "source": "MEMORY.md"},
                        "location": TIER_LOCATIONS[TIER_COLD]
                    }
            except Exception:
                pass
        
        return {"found": False, "tier": TIER_COLD, "memory": None}
    
    def _check_archived(self, memory_id: str) -> Dict[str, Any]:
        """检查 ARCHIVED 层"""
        # 格式: YYYY-MM-DD_<id>.md
        files = list(self.archive_dir.glob(f"*_{memory_id[:8]}.md"))
        if files:
            try:
                content = files[0].read_text()
                return {
                    "found": True,
                    "tier": TIER_ARCHIVED,
                    "memory": {"id": memory_id, "file": str(files[0]), "content": content[:200]},
                    "location": str(files[0])
                }
            except Exception:
                pass
        
        return {"found": False, "tier": TIER_ARCHIVED, "memory": None}
    
    def _get_cold_memories_count(self) -> int:
        """获取 COLD 层记忆数量"""
        memory_file = self.memory_dir / "MEMORY.md"
        if memory_file.exists():
            try:
                content = memory_file.read_text()
                # 简单计数（按 ## 标题）
                return content.count("\n## ")
            except Exception:
                pass
        return 0
    
    def _get_oldest_archived(self) -> Optional[str]:
        """获取最老的归档文件时间"""
        files = sorted(self.archive_dir.glob("*.md"), key=lambda f: f.stat().st_mtime)
        if files:
            return datetime.fromtimestamp(files[0].stat().st_mtime).isoformat()
        return None
    
    def _do_move(self, memory: dict, from_tier: str, to_tier: str) -> Dict[str, Any]:
        """
        执行记忆移动
        
        Args:
            memory: 记忆字典
            from_tier: 源层级
            to_tier: 目标层级
            
        Returns:
            移动结果
        """
        from lancedb_store import get_db_store
        
        memory_id = memory.get("id")
        db = get_db_store()
        
        try:
            # 1. 从源层移除
            if from_tier == TIER_WARM:
                # WARM -> 其他：先保留数据
                pass
            
            # 2. 目标层处理
            if to_tier == TIER_ARCHIVED:
                # 归档到文件
                self._archive_memory(memory)
                # 从 WARM 删除（如果在的话）
                if from_tier == TIER_WARM:
                    db.delete(memory_id=memory_id)
                    
            elif to_tier == TIER_COLD:
                # 写入 MEMORY.md
                self._append_to_cold(memory)
                # 更新 tier 标记
                db.update(memory_id, {"tier": TIER_COLD})
                
            elif to_tier == TIER_WARM:
                # 确保在 LanceDB 中
                if from_tier != TIER_WARM:
                    memory["tier"] = TIER_WARM
                    memory["updated_at"] = datetime.now().isoformat()
                    db.update(memory_id, {"tier": TIER_WARM})
                else:
                    db.update(memory_id, {"tier": TIER_WARM})
            
            elif to_tier == TIER_HOT:
                # 写入 SESSION-STATE.md
                self._append_to_hot(memory)
                # 从 WARM 移除
                if from_tier == TIER_WARM:
                    db.delete(memory_id=memory_id)
            
            return {
                "success": True,
                "message": f"记忆已从 {from_tier} 移动到 {to_tier}",
                "memory_id": memory_id,
                "from_tier": from_tier,
                "to_tier": to_tier
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"移动失败: {str(e)}",
                "memory_id": memory_id,
                "from_tier": from_tier,
                "to_tier": to_tier
            }
    
    def _archive_memory(self, memory: dict) -> bool:
        """归档记忆到 ARCHIVED 目录"""
        try:
            date = datetime.now().strftime("%Y-%m-%d")
            mem_id = memory.get("id", str(uuid.uuid4()))[:8]
            filename = f"{date}_{mem_id}.md"
            filepath = self.archive_dir / filename
            
            content = memory.get("content", "")
            md = f"""# Archived Memory

**ID:** {memory.get('id', 'N/A')}
**Original Tier:** {memory.get('tier', 'unknown')}
**Type:** {memory.get('type', 'fact')}
**Importance:** {memory.get('importance', 0.5)}
**Created:** {memory.get('created_at', 'N/A')}
**Archived:** {datetime.now().isoformat()}

## Content

{content}

## Tags

{', '.join(memory.get('tags', []))}

## Source

{memory.get('source', 'N/A')}

---
*Archived by MemoryTierManager V2*
"""
            filepath.write_text(md)
            return True
        except Exception as e:
            print(f"[MemoryTierManagerV2] _archive_memory error: {e}")
            return False
    
    def _append_to_cold(self, memory: dict):
        """追加记忆到 COLD 层 (MEMORY.md)"""
        memory_file = self.memory_dir / "MEMORY.md"
        
        # 格式化记忆
        content = memory.get("content", "")
        entry = f"""

## Memory: {content[:80]}{'...' if len(content) > 80 else ''}

- **ID:** {memory.get('id', 'N/A')}
- **Type:** {memory.get('type', 'fact')}
- **Importance:** {memory.get('importance', 0.5)}
- **Created:** {memory.get('created_at', 'N/A')}
- **Tags:** {', '.join(memory.get('tags', []))}

### Content

{content}

### Summary

{memory.get('summary', content[:200])}

*This memory is stored permanently in COLD tier.*

---
"""
        
        with open(memory_file, "a", encoding="utf-8") as f:
            f.write(entry)
    
    def _append_to_hot(self, memory: dict):
        """追加记忆到 HOT 层 (SESSION-STATE.md)"""
        content = memory.get("content", "")
        m_type = memory.get("type", "fact")
        
        if m_type == "preference":
            session_state.add_preference(content)
        elif m_type == "decision":
            session_state.add_decision(content)
        elif m_type == "fact":
            session_state.add_fact(content)
    
    def _format_stats_summary(self, stats: Dict[str, Any]) -> str:
        """格式化统计摘要"""
        lines = [
            "📊 Memory Tier Statistics",
            "=" * 40,
            f"HOT (会话级):     {stats[TIER_HOT].get('count', 0)} 项",
            f"WARM (常用):      {stats[TIER_WARM].get('count', 0)} 项",
            f"COLD (永久):      {stats[TIER_COLD].get('count', 0)} 项",
            f"ARCHIVED (归档):  {stats[TIER_ARCHIVED].get('count', 0)} 项",
            "=" * 40,
            f"总计: {stats.get('total', 0)} 项记忆",
            "",
            "💡 重要性阈值:",
            f"  HOT      > 0.9",
            f"  WARM     > 0.7",
            f"  COLD     > 0.5",
            f"  ARCHIVED <= 0.5",
        ]
        return "\n".join(lines)


# ==================== 便捷函数 ====================

# 全局实例
_tier_manager = None


def get_tier_manager() -> MemoryTierManagerV2:
    """获取全局分层管理器实例"""
    global _tier_manager
    if _tier_manager is None:
        _tier_manager = MemoryTierManagerV2()
    return _tier_manager


def get_tier(memory_id: str) -> Dict[str, Any]:
    """获取记忆所在层级"""
    return get_tier_manager().get_tier(memory_id)


def move_tier(memory_id: str, tier: str, force: bool = False) -> Dict[str, Any]:
    """移动记忆到指定层级"""
    return get_tier_manager().move_tier(memory_id, tier, force)


def get_tier_stats() -> Dict[str, Any]:
    """获取各层级统计"""
    return get_tier_manager().get_tier_stats()


def assign_tier_for_memory(memory: dict) -> str:
    """为记忆分配层级"""
    return get_tier_manager().assign_tier(memory)


def reTier_memories(force: bool = False) -> Dict[str, Any]:
    """重新评估所有记忆的层级"""
    return get_tier_manager().reTier_all(dry_run=False)


def reTier_memories_dry_run() -> Dict[str, Any]:
    """预演重新分层（不实际执行）"""
    return get_tier_manager().reTier_all(dry_run=True)


def auto_archive(threshold: float = 0.3) -> Dict[str, Any]:
    """自动归档低价值记忆"""
    return get_tier_manager().auto_archive_low_value(threshold=threshold)


# ==================== 向后兼容 ====================

# 保留旧的 tier_manager 实例用于向后兼容
from memory_tier import tier_manager as old_tier_manager

# 如果旧管理器没有新的方法，添加兼容包装
if not hasattr(old_tier_manager, 'get_tier'):
    old_tier_manager.get_tier = get_tier
if not hasattr(old_tier_manager, 'move_tier'):
    old_tier_manager.move_tier = move_tier
if not hasattr(old_tier_manager, 'get_tier_stats'):
    old_tier_manager.get_tier_stats = get_tier_stats
