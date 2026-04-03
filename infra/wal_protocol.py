"""
WAL Protocol (Write-Ahead Log) 实现

SESSION-STATE.md — 活跃工作记忆

参考 Elite Longterm Memory 的 WAL Protocol 设计：
- 在响应前写入，防止崩溃导致记忆丢失
- Survives compaction（压缩后仍然存在）

实现思路：
1. 每次响应前，将关键信息写入 SESSION-STATE.md
2. 即使 OpenClaw 压缩上下文，该文件仍然保留
3. 下次会话开始时，自动加载 SESSION-STATE.md
"""
import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


_logger = logging.getLogger(__name__)

# 默认路径
DEFAULT_SESSION_STATE_PATH = os.path.expanduser("~/.openclaw/workspace/memory/hot/SESSION-STATE.md")


@dataclass
class SessionTask:
    """当前任务"""
    description: str
    status: str  # in_progress / completed / pending
    started_at: str
    updated_at: str


@dataclass
class SessionContext:
    """会话上下文"""
    current_task: Optional[str] = None
    user_preferences: List[str] = None
    decisions_made: List[str] = None
    blockers: List[str] = None
    pending_actions: List[str] = None
    key_context: str = ""


class WALProtocol:
    """
    Write-Ahead Log Protocol for Session State
    
    核心原则：
    1. Write BEFORE responding — 响应前写入
    2. Survives compaction — 压缩后仍保留
    3. Atomic writes — 原子写入，防止损坏
    """
    
    def __init__(self, 
                 session_state_path: str = DEFAULT_SESSION_STATE_PATH,
                 auto_load: bool = True):
        """
        Args:
            session_state_path: SESSION-STATE.md 文件路径
            auto_load: 初始化时是否自动加载
        """
        self.session_state_path = Path(session_state_path)
        
        # 确保目录存在
        self.session_state_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 内存中的状态
        self._context = SessionContext()
        
        # 初始化
        if auto_load:
            self.load()
    
    def load(self) -> SessionContext:
        """从文件加载会话状态"""
        if not self.session_state_path.exists():
            _logger.debug("SESSION-STATE.md 不存在，创建新状态")
            return self._context
        
        try:
            content = self.session_state_path.read_text()
            self._context = self._parse_content(content)
            _logger.info(f"已加载 SESSION-STATE.md: {len(content)} bytes")
        except Exception as e:
            _logger.error(f"加载 SESSION-STATE.md 失败: {e}")
        
        return self._context
    
    def _parse_content(self, content: str) -> SessionContext:
        """解析 SESSION-STATE.md 内容"""
        ctx = SessionContext()
        
        current_section = None
        lines = content.split("\n")
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("## Current Task"):
                current_section = "task"
                ctx.current_task = ""
            elif line.startswith("## Key Context"):
                current_section = "context"
            elif line.startswith("## User Preferences"):
                current_section = "preferences"
                ctx.user_preferences = []
            elif line.startswith("## Decisions Made"):
                current_section = "decisions"
                ctx.decisions_made = []
            elif line.startswith("## Blockers"):
                current_section = "blockers"
                ctx.blockers = []
            elif line.startswith("## Pending Actions"):
                current_section = "actions"
                ctx.pending_actions = []
            elif line.startswith("- ") and current_section:
                item = line[2:].strip()
                if current_section == "preferences":
                    if ctx.user_preferences is None:
                        ctx.user_preferences = []
                    ctx.user_preferences.append(item)
                elif current_section == "decisions":
                    if ctx.decisions_made is None:
                        ctx.decisions_made = []
                    ctx.decisions_made.append(item)
                elif current_section == "blockers":
                    if ctx.blockers is None:
                        ctx.blockers = []
                    ctx.blockers.append(item)
                elif current_section == "actions":
                    if ctx.pending_actions is None:
                        ctx.pending_actions = []
                    ctx.pending_actions.append(item)
            elif line.startswith("### ") and current_section == "task":
                ctx.current_task = line[4:].strip()
        
        return ctx
    
    def save(self) -> bool:
        """
        原子写入 SESSION-STATE.md
        
        Returns:
            是否成功
        """
        try:
            content = self._context_to_markdown()
            
            # 原子写入：先写临时文件，再重命名
            temp_path = self.session_state_path.with_suffix(".tmp")
            temp_path.write_text(content)
            temp_path.rename(self.session_state_path)
            
            _logger.debug(f"已保存 SESSION-STATE.md: {len(content)} bytes")
            return True
            
        except Exception as e:
            _logger.error(f"保存 SESSION-STATE.md 失败: {e}")
            return False
    
    def _context_to_markdown(self) -> str:
        """将会话状态转换为 Markdown 格式"""
        ctx = self._context
        now = datetime.now().isoformat()
        
        lines = [
            "# SESSION-STATE.md — Active Working Memory",
            "",
            "> WAL Protocol: Write BEFORE responding. This file survives compaction.",
            "",
            f"Last updated: {now}",
            "",
            "---",
            "",
            "## Current Task",
        ]
        
        if ctx.current_task:
            lines.append(f"### {ctx.current_task}")
        else:
            lines.append("[What we're working on RIGHT NOW]")
        
        lines.extend([
            "",
            "## Key Context",
        ])
        
        if ctx.key_context:
            lines.append(ctx.key_context)
        else:
            lines.append("[Add key context here]")
        
        lines.extend([
            "",
            "## User Preferences",
        ])
        
        if ctx.user_preferences:
            for pref in ctx.user_preferences:
                lines.append(f"- {pref}")
        else:
            lines.append("- [Add user preferences here]")
        
        lines.extend([
            "",
            "## Decisions Made",
        ])
        
        if ctx.decisions_made:
            for decision in ctx.decisions_made:
                lines.append(f"- {decision}")
        else:
            lines.append("- [No decisions yet]")
        
        lines.extend([
            "",
            "## Blockers",
        ])
        
        if ctx.blockers:
            for blocker in ctx.blockers:
                lines.append(f"- {blocker}")
        else:
            lines.append("- [No blockers]")
        
        lines.extend([
            "",
            "## Pending Actions",
        ])
        
        if ctx.pending_actions:
            for action in ctx.pending_actions:
                lines.append(f"- [ ] {action}")
        else:
            lines.append("- [ ] [Add pending actions here]")
        
        lines.extend([
            "",
            "---",
            f"*Generated by WAL Protocol at {now}*",
        ])
        
        return "\n".join(lines)
    
    # ========== 操作方法 ==========
    
    def set_current_task(self, task: str) -> bool:
        """设置当前任务"""
        self._context.current_task = task
        return self.save()
    
    def add_preference(self, preference: str) -> bool:
        """添加用户偏好"""
        if self._context.user_preferences is None:
            self._context.user_preferences = []
        if preference not in self._context.user_preferences:
            self._context.user_preferences.append(preference)
        return self.save()
    
    def add_decision(self, decision: str) -> bool:
        """添加决策"""
        if self._context.decisions_made is None:
            self._context.decisions_made = []
        if decision not in self._context.decisions_made:
            self._context.decisions_made.append(decision)
        return self.save()
    
    def add_blocker(self, blocker: str) -> bool:
        """添加阻碍"""
        if self._context.blockers is None:
            self._context.blockers = []
        if blocker not in self._context.blockers:
            self._context.blockers.append(blocker)
        return self.save()
    
    def add_pending_action(self, action: str) -> bool:
        """添加待办"""
        if self._context.pending_actions is None:
            self._context.pending_actions = []
        if action not in self._context.pending_actions:
            self._context.pending_actions.append(action)
        return self.save()
    
    def complete_pending_action(self, action: str) -> bool:
        """标记待办完成"""
        if self._context.pending_actions is None:
            return False
        
        # 找到并移除
        new_actions = []
        for a in self._context.pending_actions:
            if action in a:
                continue  # 移除
            new_actions.append(a)
        
        self._context.pending_actions = new_actions
        return self.save()
    
    def update_context(self, context: str) -> bool:
        """更新关键上下文"""
        self._context.key_context = context
        return self.save()
    
    def clear(self) -> bool:
        """清空所有状态"""
        self._context = SessionContext()
        return self.save()
    
    def get_context(self) -> SessionContext:
        """获取当前上下文"""
        return self._context
    
    def get_summary(self) -> str:
        """获取状态摘要"""
        ctx = self._context
        parts = []
        
        if ctx.current_task:
            parts.append(f"任务: {ctx.current_task}")
        
        if ctx.key_context:
            parts.append(f"上下文: {ctx.key_context[:50]}...")
        
        if ctx.user_preferences:
            parts.append(f"偏好: {len(ctx.user_preferences)}项")
        
        if ctx.decisions_made:
            parts.append(f"决策: {len(ctx.decisions_made)}项")
        
        if ctx.blockers:
            parts.append(f"阻碍: {', '.join(ctx.blockers)}")
        
        if ctx.pending_actions:
            parts.append(f"待办: {len(ctx.pending_actions)}项")
        
        return " | ".join(parts) if parts else "无状态"


# 全局单例
_wal_protocol = None


def get_wal_protocol() -> WALProtocol:
    """获取WAL Protocol单例"""
    global _wal_protocol
    if _wal_protocol is None:
        _wal_protocol = WALProtocol()
    return _wal_protocol


def write_before_response() -> bool:
    """
    WAL Protocol 核心：在响应前调用
    
    使用示例：
    ```python
    # 用户输入后、响应前调用
    write_before_response()
    
    # 响应用户
    response = "..."
    ```
    """
    wal = get_wal_protocol()
    # 这里可以添加自动保存逻辑
    return True


def load_session_state() -> SessionContext:
    """快捷函数：加载会话状态"""
    return get_wal_protocol().load()


def save_session_state() -> bool:
    """快捷函数：保存会话状态"""
    return get_wal_protocol().save()
