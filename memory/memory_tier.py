"""
记忆层级管理 - HOT/WARM/COLD 三层架构实现
包括：
- TTL 晋升机制
- COLD 归档层
- 定时整理任务

[DEPRECATED] 请使用 memory.memory_tier_manager.MemoryTierManagerV2
此模块保留用于向后兼容，未来版本将移除。
"""
import warnings
warnings.warn(
    "memory.memory_tier.MemoryTierManager is deprecated. Use memory.memory_tier_manager.MemoryTierManagerV2 instead.",
    DeprecationWarning,
    stacklevel=2
)

import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from core.memory_config import CONFIG
from memory.memory_session import session_state

logger = logging.getLogger(__name__)


class MemoryTierManager:
    def __init__(self):
        self.memory_dir = Path(CONFIG.get("memory_dir", str(Path.home() / ".openclaw/workspace/memory")))
        self.cold_dir = self.memory_dir / "cold"
        self.cold_dir.mkdir(parents=True, exist_ok=True)
    
    def archive_to_cold(self, memory: dict) -> bool:
        """将记忆归档到 COLD 层（Markdown 格式）"""
        try:
            # 生成文件名
            date = datetime.now().strftime("%Y-%m-%d")
            mem_id = memory.get("id", str(uuid.uuid4()))[:8]
            filename = f"{date}_{mem_id}.md"
            filepath = self.cold_dir / filename
            
            # 生成摘要（如果需要）
            content = memory.get("content", "")
            summary = memory.get("summary", "")
            if not summary and len(content) > 200:
                summary = content[:200] + "..."
            
            # 构建 Markdown
            md_content = f"""# Memory: {content[:50]}...

**ID:** {memory.get('id', 'N/A')}
**Type:** {memory.get('type', 'fact')}
**Importance:** {memory.get('importance', 0.5)}
**Created:** {memory.get('created_at', 'N/A')}
**Tags:** {', '.join(memory.get('tags', []))}

## Content

{content}

## Summary

{summary or content[:200]}

## Source

{memory.get('source', 'N/A')}

## Transcript

{memory.get('transcript', 'N/A')}

---
*Archived: {datetime.now().isoformat()}*
"""
            
            filepath.write_text(md_content)
            return True
        except Exception as e:
            print(f"[MemoryTier] archive_to_cold error: {e}")
            return False
    
    def promote_hot_to_warm(self, force: bool = False) -> dict:
        """
        将 SESSION-STATE.md 的内容晋升到 WARM 层
        
        触发条件：
        - 会话结束（用户说"再见"、"结束"等）
        - 或超过 HOT_TTL 时间
        """
        try:
            # 检查是否应该晋升
            last_updated = session_state.data.get("last_updated", "")
            if last_updated:
                last_time = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                ttl_hours = CONFIG.get("hot_ttl_hours", 24)
                if datetime.now() - last_time < timedelta(hours=ttl_hours) and not force:
                    return {
                        "success": False,
                        "message": f"HOT TTL not reached ({ttl_hours}h), skip promotion",
                        "promoted": 0
                    }
            
            # 检查是否有内容需要晋升
            summary = session_state.get_summary()
            if not summary or "[None]" in summary:
                return {
                    "success": True,
                    "message": "No content to promote",
                    "promoted": 0
                }
            
            # 晋升关键内容到 WARM
            from lancedb_store import get_db_store
            db = get_db_store()
            
            promoted = 0
            
            # 晋升决策
            decisions = session_state.data.get("recent_decisions", "")
            if decisions and "[None]" not in decisions:
                db.store({
                    "type": "decision",
                    "content": decisions,
                    "importance": 0.9,
                    "source": "session_state",
                })
                promoted += 1
            
            # 晋升偏好
            preferences = session_state.data.get("user_preferences", "")
            if preferences and "[None]" not in preferences:
                db.store({
                    "type": "preference",
                    "content": preferences,
                    "importance": 0.8,
                    "source": "session_state",
                })
                promoted += 1
            
            # 晋升重要事实
            facts = session_state.data.get("important_facts", "")
            if facts and "[None]" not in facts:
                db.store({
                    "type": "fact",
                    "content": facts,
                    "importance": 0.7,
                    "source": "session_state",
                })
                promoted += 1
            
            return {
                "success": True,
                "message": f"Promoted {promoted} items from HOT to WARM",
                "promoted": promoted
            }
        except Exception as e:
            print(f"[MemoryTier] promote_hot_to_warm error: {e}")
            return {"success": False, "message": str(e), "promoted": 0}
    
    def archive_warm_to_cold(self, days: int = None, importance_threshold: float = None) -> dict:
        """
        将 WARM 层长时间未访问的记忆归档到 COLD
        
        条件：
        - 超过指定天数未访问
        - 或重要性低于阈值
        """
        from lancedb_store import get_db_store
        db = get_db_store()
        
        days = days or CONFIG.get("warm_ttl_days", 30)
        importance_threshold = importance_threshold or CONFIG.get("min_importance", 0.3)
        
        # 获取符合条件的老记忆
        old_memories = db.get_old_memories(days=days)
        
        # 过滤重要性过低的
        to_archive = [
            m for m in old_memories
            if m.get("importance", 0) >= importance_threshold
        ]
        
        archived = 0
        deleted = 0
        
        for mem in to_archive:
            # 先归档到 COLD
            if self.archive_to_cold(mem):
                archived += 1
            
            # 从 WARM 删除
            if db.delete(memory_id=mem.get("id")):
                deleted += 1
        
        return {
            "success": True,
            "archived": archived,
            "deleted": deleted,
            "total_old": len(old_memories),
            "threshold_days": days,
            "importance_threshold": importance_threshold
        }
    
    def auto_tier(self) -> dict:
        """
        自动执行层级整理
        建议每天定时执行
        """
        results = {
            "hot_to_warm": None,
            "warm_to_cold": None,
            "timestamp": datetime.now().isoformat()
        }
        
        # 1. HOT -> WARM 晋升
        results["hot_to_warm"] = self.promote_hot_to_warm(force=False)
        
        # 2. WARM -> COLD 归档
        results["warm_to_cold"] = self.archive_warm_to_cold()
        
        return results
    
    def get_cold_memories(self, limit: int = 50) -> list[dict]:
        """获取 COLD 层记忆列表"""
        try:
            files = sorted(self.cold_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
            memories = []
            for f in files[:limit]:
                content = f.read_text()
                # 简单解析
                memories.append({
                    "file": f.name,
                    "path": str(f),
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    "preview": content[:100]
                })
            return memories
        except Exception as e:
            print(f"[MemoryTier] get_cold_memories error: {e}")
            return []
    
    def promote_cold_to_warm(self, filename: str = None, memory_id: str = None) -> dict:
        """
        【P0+P1修复】将 COLD 层记忆加载回 WARM 层
        - SQL注入防护
        - 路径遍历校验
        
        参数：
        - filename: COLD目录下的文件名
        - memory_id: 可选，用ID匹配文件
        
        返回：加载结果
        """
        try:
            from lancedb_store import get_db_store
            
            # 如果没有指定文件名，尝试用ID查找
            if not filename and memory_id:
                # 格式: YYYY-MM-DD_<id>.md
                files = list(self.cold_dir.glob(f"*_{memory_id[:8]}.md"))
                if files:
                    filename = files[0].name
            
            if not filename:
                return {"success": False, "message": "未指定文件名或未找到匹配文件"}
            
            # 【P1修复】路径遍历校验
            filepath = self.cold_dir / filename
            # 解析真实路径并验证在 cold_dir 内
            try:
                resolved = filepath.resolve()
                cold_dir_resolved = self.cold_dir.resolve()
                if not str(resolved).startswith(str(cold_dir_resolved)):
                    return {"success": False, "message": "非法路径"}
            except Exception as e:
                logger.warning(f"路径解析失败: {e}")
                return {"success": False, "message": "路径解析失败"}
            
            if not filepath.exists():
                return {"success": False, "message": f"文件不存在: {filename}"}
            
            # 解析 Markdown 文件
            content = filepath.read_text()
            
            # 简单提取 frontmatter 后的正文作为 content
            # 格式: # Memory: <title>\n**ID:** ...\n**Type:** ...\n## Content\n<actual content>
            lines = content.split("\n")
            actual_content = []
            in_content = False
            for line in lines:
                if line.startswith("## Content"):
                    in_content = True
                    continue
                if in_content and line.startswith("---"):
                    break
                if in_content:
                    actual_content.append(line)
            
            content_text = "\n".join(actual_content).strip()
            
            # 提取元信息
            id_line = [l for l in lines if l.startswith("**ID:**")]
            type_line = [l for l in lines if l.startswith("**Type:**")]
            imp_line = [l for l in lines if l.startswith("**Importance:**")]
            
            mem_id = id_line[0].replace("**ID:**", "").strip() if id_line else str(uuid.uuid4())
            mem_type = type_line[0].replace("**Type:**", "").strip() if type_line else "fact"
            importance = float(imp_line[0].replace("**Importance:**", "").strip()) if imp_line else 0.5
            
            # 存储回 WARM
            db = get_db_store()
            success = db.store({
                "id": mem_id,
                "type": mem_type,
                "content": content_text,
                "importance": importance,
                "source": "cold_resurrected",
            })
            
            if success:
                return {
                    "success": True,
                    "message": f"已恢复记忆: {content_text[:50]}...",
                    "memory_id": mem_id
                }
            else:
                return {"success": False, "message": "存储失败"}
                
        except Exception as e:
            print(f"[MemoryTier] promote_cold_to_warm error: {e}")
            return {"success": False, "message": str(e)}
    
    def stats(self) -> dict:
        """获取所有层级的统计"""
        from lancedb_store import get_db_store
        
        try:
            db = get_db_store()
            warm_stats = db.stats()
        except Exception as e:
            logger.warning(f"获取WARM层统计失败: {e}")
            warm_stats = {"total": 0, "by_type": {}}
        
        try:
            cold_files = list(self.cold_dir.glob("*.md"))
        except Exception as e:
            logger.warning(f"获取COLD层文件列表失败: {e}")
            cold_files = []
        
        return {
            "HOT": {
                "location": str(session_state.file_path),
                "has_content": bool(session_state.get_summary())
            },
            "WARM": {
                "location": CONFIG.get("db_path"),
                **warm_stats
            },
            "COLD": {
                "location": str(self.cold_dir),
                "count": len(cold_files)
            }
        }


# 全局实例
tier_manager = MemoryTierManager()
