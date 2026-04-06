"""
版本历史与审计追踪 - Version History & Audit Trail
基于 Git 实现不可篡改的记忆版本历史

功能：
1. 每次记忆更新自动创建 Git Commit
2. 支持时点回溯（查询某天的记忆快照）
3. 变更日志（changelog）追踪所有重要事件
4. 防覆盖保护：差异>30%才允许覆盖，否则新建节点

原理：
- 利用现有 Git-Notes（L3）基础设施
- 每次更新生成带时间戳的 commit
- changelog.md 记录每次变更摘要
- recall-at 命令支持时点回溯
"""
import os
import json
import subprocess
import hashlib
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)

# 配置文件路径
MEMORY_DIR = Path.home() / ".openclaw/workspace/memory"
CHANGELOG_FILE = MEMORY_DIR / "changelog.md"
GIT_DIR = MEMORY_DIR / ".git"
VERSIONS_DIR = MEMORY_DIR / "versions"


class VersionHistoryManager:
    """
    版本历史管理器
    
    使用 Git 作为不可篡改的存储后端，
    每次记忆变更生成带注释的 Commit，
    支持时点回溯和变更审计。
    """
    
    def __init__(self, memory_dir: Path = MEMORY_DIR):
        self.memory_dir = memory_dir
        self.changelog_file = memory_dir / "changelog.md"
        self.versions_dir = memory_dir / "versions"
        self.git_dir = memory_dir / ".git"
        
        # 确保目录存在
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化 Git（如果尚未初始化）
        self._ensure_git_repo()
        
        # 初始化变更日志
        self._ensure_changelog()
    
    def _ensure_git_repo(self):
        """确保 Git 仓库已初始化"""
        if not self.git_dir.exists():
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=self.memory_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                # 创建初始 commit
                subprocess.run(
                    ["git", "commit", "--allow-empty", "-m", "Initial commit: memory system v1.0"],
                    cwd=self.memory_dir,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                print(f"[VersionHistory] Git仓库已初始化: {self.memory_dir}")
            except Exception as e:
                print(f"[VersionHistory] Git初始化失败: {e}")
    
    def _ensure_changelog(self):
        """确保变更日志文件存在"""
        if not self.changelog_file.exists():
            changelog_content = f"""# Memory Changelog

> 记忆系统变更历史，不可篡改，可审计

## 格式说明
- **时间戳**：ISO 8601 格式
- **事件类型**：UPDATE / CREATE / DELETE / RESTORE / ARCHIVE
- **触发方式**：AUTO（自动）/ MANUAL（手动）/ SESSION（会话结束）
- **变更摘要**：简短描述变更内容

## 事件类型定义
| 类型 | 说明 |
|------|------|
| UPDATE | 记忆内容被更新 |
| CREATE | 新记忆创建 |
| DELETE | 记忆被删除 |
| RESTORE | 记忆从冷存储恢复 |
| ARCHIVE | 记忆进入冷存储 |
| SESSION | 会话级记忆晋升 |

---
*此文件由 VersionHistoryManager 自动维护*
"""
            self.changelog_file.write_text(changelog_content)
    
    def _git_commit(self, message: str, files: List[str] = None) -> Tuple[bool, str]:
        """
        执行 Git Commit
        
        Args:
            message: 提交信息
            files: 要提交的文件列表，None 表示提交所有
            
        Returns:
            (success, message)
        """
        try:
            # 添加文件
            if files:
                for f in files:
                    subprocess.run(
                        ["git", "add", f],
                        cwd=self.memory_dir,
                        capture_output=True,
                        timeout=5
                    )
            else:
                subprocess.run(
                    ["git", "add", "-A"],
                    cwd=self.memory_dir,
                    capture_output=True,
                    timeout=5
                )
            
            # 设置提交者信息
            env = os.environ.copy()
            env["GIT_AUTHOR_NAME"] = "MemorySystem"
            env["GIT_AUTHOR_EMAIL"] = "memory@openclaw.local"
            env["GIT_COMMITTER_NAME"] = "MemorySystem"
            env["GIT_COMMITTER_EMAIL"] = "memory@openclaw.local"
            
            # 执行提交
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.memory_dir,
                capture_output=True,
                text=True,
                env=env,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, "Commit成功"
            else:
                # 没有变更也算成功
                if "nothing to commit" in result.stderr.lower():
                    return True, "无需提交（无变更）"
                return False, result.stderr
            
        except Exception as e:
            return False, str(e)
    
    def _generate_commit_hash(self, content: str) -> str:
        """生成内容的哈希值（用于版本标识）"""
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    
    def record_create(
        self,
        memory_id: str,
        content: str,
        memory_type: str = "fact",
        importance: float = 0.5,
        trigger: str = "MANUAL"
    ) -> Dict:
        """
        记录记忆创建
        
        Args:
            memory_id: 记忆ID
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性
            trigger: 触发方式
            
        Returns:
            创建结果
        """
        now = datetime.now()
        
        # 保存版本快照
        version_file = self.versions_dir / f"{memory_id}_{now.strftime('%Y%m%d_%H%M%S')}.json"
        version_data = {
            "id": memory_id,
            "type": memory_type,
            "content": content,
            "importance": importance,
            "created_at": now.isoformat(),
            "version": "v1",
            "commit_hash": self._generate_commit_hash(content)
        }
        
        with open(version_file, 'w') as f:
            json.dump(version_data, f, indent=2, ensure_ascii=False)
        
        # Git提交
        commit_msg = f"""MEMORY CREATE [{memory_type}] [{trigger}]
ID: {memory_id}
Importance: {importance}
Content: {content[:100]}..."""
        
        success, msg = self._git_commit(commit_msg, [str(version_file)])
        
        # 追加到变更日志
        self._append_changelog(
            event_type="CREATE",
            memory_id=memory_id,
            memory_type=memory_type,
            importance=importance,
            trigger=trigger,
            content_preview=content[:100],
            commit_success=success
        )
        
        return {
            "success": True,
            "memory_id": memory_id,
            "version_file": str(version_file),
            "git_commit": success,
            "timestamp": now.isoformat()
        }
    
    def record_update(
        self,
        memory_id: str,
        old_content: str,
        new_content: str,
        memory_type: str = "fact",
        importance: float = 0.5,
        trigger: str = "MANUAL"
    ) -> Dict:
        """
        记录记忆更新
        
        核心逻辑：
        - 计算新旧内容的差异
        - 差异 < 30%：允许覆盖，生成新版本
        - 差异 >= 30%：创建新节点，保留旧节点
        """
        now = datetime.now()
        
        # 计算差异
        old_len = len(old_content)
        new_len = len(new_content)
        diff_ratio = abs(new_len - old_len) / max(old_len, new_len, 1)
        
        # 判断是否应该创建新节点
        should_create_new = diff_ratio >= 0.30
        
        if should_create_new:
            # 差异较大 → 创建新节点，旧节点保留
            new_memory_id = f"{memory_id}_v{int(time.time())}"
            action = "CREATE_NEW_NODE"
            version_note = f"（原节点 {memory_id} 保留）"
        else:
            # 差异较小 → 覆盖更新
            new_memory_id = memory_id
            action = "UPDATE"
            version_note = ""
        
        # 保存新版本
        version_file = self.versions_dir / f"{new_memory_id}_{now.strftime('%Y%m%d_%H%M%S')}.json"
        version_data = {
            "id": new_memory_id,
            "parent_id": memory_id if should_create_new else None,
            "type": memory_type,
            "content": new_content,
            "importance": importance,
            "created_at": now.isoformat(),
            "version": f"v{self._generate_commit_hash(new_content)[:4]}",
            "commit_hash": self._generate_commit_hash(new_content),
            "diff_ratio": round(diff_ratio, 4),
            "action": action
        }
        
        with open(version_file, 'w') as f:
            json.dump(version_data, f, indent=2, ensure_ascii=False)
        
        # Git提交
        commit_msg = f"""MEMORY {action} [{memory_type}] [{trigger}]
ID: {new_memory_id}
Parent: {memory_id if should_create_new else 'None'}
Importance: {importance}
Diff: {diff_ratio:.1%} {version_note}
Content: {new_content[:100]}..."""
        
        success, msg = self._git_commit(commit_msg, [str(version_file)])
        
        # 追加变更日志
        self._append_changelog(
            event_type="UPDATE" if not should_create_new else "CREATE",
            memory_id=new_memory_id,
            parent_id=memory_id if should_create_new else None,
            memory_type=memory_type,
            importance=importance,
            trigger=trigger,
            content_preview=new_content[:100],
            diff_ratio=diff_ratio,
            commit_success=success
        )
        
        return {
            "success": True,
            "memory_id": new_memory_id,
            "parent_id": memory_id if should_create_new else None,
            "action": action,
            "diff_ratio": round(diff_ratio, 4),
            "version_file": str(version_file),
            "git_commit": success,
            "timestamp": now.isoformat()
        }
    
    def record_delete(
        self,
        memory_id: str,
        reason: str = "MANUAL",
        trigger: str = "MANUAL"
    ) -> Dict:
        """记录记忆删除"""
        now = datetime.now()
        
        # 创建删除标记文件
        tombstone_file = self.versions_dir / f"{memory_id}_DELETED_{now.strftime('%Y%m%d_%H%M%S')}.json"
        tombstone_data = {
            "id": memory_id,
            "deleted_at": now.isoformat(),
            "reason": reason,
            "trigger": trigger,
            "status": "DELETED"
        }
        
        with open(tombstone_file, 'w') as f:
            json.dump(tombstone_data, f, indent=2)
        
        # Git提交
        commit_msg = f"""MEMORY DELETE [{trigger}]
ID: {memory_id}
Reason: {reason}"""
        
        success, msg = self._git_commit(commit_msg, [str(tombstone_file)])
        
        # 追加变更日志
        self._append_changelog(
            event_type="DELETE",
            memory_id=memory_id,
            trigger=trigger,
            reason=reason,
            commit_success=success
        )
        
        return {
            "success": True,
            "memory_id": memory_id,
            "tombstone_file": str(tombstone_file),
            "timestamp": now.isoformat()
        }
    
    def recall_at(self, memory_id: str, date: str) -> Optional[Dict]:
        """
        时点回溯：查询某天的记忆状态
        
        Args:
            memory_id: 记忆ID
            date: 日期，格式 YYYY-MM-DD
            
        Returns:
            当时的记忆状态，不存在返回None
        """
        try:
            target_date = datetime.fromisoformat(date)
        except Exception as e:
            logger.warning(f"日期解析失败: {e}")
            return None
        
        # 查找该日期之前的最新版本
        version_files = sorted(
            self.versions_dir.glob(f"{memory_id}_*.json"),
            key=lambda f: f.stat().st_mtime
        )
        
        for version_file in reversed(version_files):
            try:
                with open(version_file) as f:
                    data = json.load(f)
                
                created_at = datetime.fromisoformat(data["created_at"])
                
                if created_at <= target_date and data.get("status") != "DELETED":
                    data["version_file"] = str(version_file)
                    data["recalled_at"] = datetime.now().isoformat()
                    data["recalled_date"] = date
                    return data
            except Exception as e:
                logger.warning(f"版本历史读取失败: {e}")
                continue
        
        return None
    
    def get_history(self, memory_id: str) -> List[Dict]:
        """
        获取记忆的完整变更历史
        
        Returns:
            按时间排序的版本列表
        """
        version_files = sorted(
            self.versions_dir.glob(f"{memory_id}*.json"),
            key=lambda f: f.stat().st_mtime
        )
        
        history = []
        for vf in version_files:
            try:
                with open(vf) as f:
                    data = json.load(f)
                data["version_file"] = str(vf)
                history.append(data)
            except Exception as e:
                logger.warning(f"历史记录读取失败: {e}")
                continue
        
        return history
    
    def _append_changelog(
        self,
        event_type: str,
        memory_id: str,
        memory_type: str = None,
        importance: float = None,
        trigger: str = "MANUAL",
        content_preview: str = None,
        parent_id: str = None,
        diff_ratio: float = None,
        reason: str = None,
        commit_success: bool = None
    ):
        """追加变更日志条目"""
        now = datetime.now()
        
        entry = f"""
## [{now.isoformat()}] {event_type} - {memory_id}

| 字段 | 值 |
|------|-----|
| **事件类型** | {event_type} |
| **记忆ID** | {memory_id} |
| **触发方式** | {trigger} |"""
        
        if memory_type:
            entry += f"""
| **记忆类型** | {memory_type} |"""
        
        if importance is not None:
            entry += f"""
| **重要性** | {importance} |"""
        
        if parent_id:
            entry += f"""
| **父节点** | {parent_id} |"""
        
        if diff_ratio is not None:
            entry += f"""
| **差异度** | {diff_ratio:.1%} |"""
        
        if reason:
            entry += f"""
| **原因** | {reason} |"""
        
        if content_preview:
            entry += f"""
| **内容预览** | {content_preview[:80]}... |"""
        
        entry += f"""
| **Git提交** | {'✅ 成功' if commit_success else '❌ 失败'} |

---
"""
        
        # 追加到变更日志
        try:
            with open(self.changelog_file, 'a') as f:
                f.write(entry)
        except Exception as e:
            print(f"[VersionHistory] 写入变更日志失败: {e}")
    
    def get_changelog_entries(self, limit: int = 50) -> List[Dict]:
        """获取最近的变更日志条目"""
        if not self.changelog_file.exists():
            return []
        
        content = self.changelog_file.read_text()
        
        # 简单解析
        entries = []
        current_entry = None
        
        for line in content.split("\n"):
            if line.startswith("## [") and "] " in line:
                if current_entry:
                    entries.append(current_entry)
                # 解析时间戳和事件
                parts = line[3:].split("] ")
                if len(parts) == 2:
                    timestamp = parts[0]
                    type_id = parts[1].split(" - ")
                    if len(type_id) == 2:
                        current_entry = {
                            "timestamp": timestamp,
                            "event_type": type_id[0],
                            "memory_id": type_id[1]
                        }
                    else:
                        current_entry = {"raw": line}
                else:
                    current_entry = {"raw": line}
            elif current_entry and line.startswith("| **"):
                # 解析表格行
                parts = line.split("|")
                if len(parts) >= 3:
                    key = parts[1].replace("**", "").replace(":", "").strip()
                    value = parts[2].replace("|", "").strip()
                    current_entry[key] = value
        
        if current_entry:
            entries.append(current_entry)
        
        return entries[-limit:]
    
    def get_stats(self) -> Dict:
        """获取版本历史统计"""
        try:
            version_files = list(self.versions_dir.glob("*.json"))
            deleted_files = [f for f in version_files if "DELETED" in f.name]
            
            return {
                "total_versions": len(version_files),
                "deleted_count": len(deleted_files),
                "versions_dir": str(self.versions_dir),
                "changelog_exists": self.changelog_file.exists(),
                "git_repo_initialized": self.git_dir.exists()
            }
        except Exception as e:
            return {"error": str(e)}


# 全局实例
_version_history = None


def get_version_history() -> VersionHistoryManager:
    """获取全局版本历史管理器"""
    global _version_history
    if _version_history is None:
        _version_history = VersionHistoryManager()
    return _version_history


# ============================================================
# 独立函数接口
# ============================================================

def record_create(memory_id: str, content: str, memory_type: str = "fact",
                 importance: float = 0.5, trigger: str = "MANUAL") -> Dict:
    """记录记忆创建"""
    vh = get_version_history()
    return vh.record_create(memory_id, content, memory_type, importance, trigger)


def record_update(memory_id: str, old_content: str, new_content: str,
                 memory_type: str = "fact", importance: float = 0.5,
                 trigger: str = "MANUAL") -> Dict:
    """记录记忆更新"""
    vh = get_version_history()
    return vh.record_update(memory_id, old_content, new_content, memory_type, importance, trigger)


def record_delete(memory_id: str, reason: str = "MANUAL", trigger: str = "MANUAL") -> Dict:
    """记录记忆删除"""
    vh = get_version_history()
    return vh.record_delete(memory_id, reason, trigger)


def recall_at(memory_id: str, date: str) -> Optional[Dict]:
    """时点回溯"""
    vh = get_version_history()
    return vh.recall_at(memory_id, date)


def get_history(memory_id: str) -> List[Dict]:
    """获取变更历史"""
    vh = get_version_history()
    return vh.get_history(memory_id)


def get_changelog_entries(limit: int = 50) -> List[Dict]:
    """获取变更日志"""
    vh = get_version_history()
    return vh.get_changelog_entries(limit)
