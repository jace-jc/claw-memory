"""
会话状态管理 - HOT RAM 层
管理 SESSION-STATE.md 文件
"""
import os
import re
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Optional
from core.memory_config import CONFIG

SESSION_STATE_TEMPLATE = """# SESSION-STATE.md — Active Working Memory

This file is the agent's "RAM" — survives compaction, restarts, distractions.

## Current Task
{current_task}

## Key Context
{key_context}

## Pending Actions
{pending_actions}

## Recent Decisions
{recent_decisions}

## User Preferences
{user_preferences}

## Important Facts
{important_facts}

---
*Last updated: {last_updated}*
"""

class SessionState:
    def __init__(self):
        self.file_path = Path(CONFIG["workspace_dir"]) / CONFIG.get("hot_file", "SESSION-STATE.md")
        self._ensure_file()
        self.data = self._load()
    
    def _ensure_file(self):
        """确保文件存在"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text(SESSION_STATE_TEMPLATE.format(
                current_task="[None]",
                key_context="[None yet]",
                pending_actions="- [ ] None",
                recent_decisions="[None yet]",
                user_preferences="[None yet]",
                important_facts="[None yet]",
                last_updated=datetime.now().strftime("%Y-%m-%d %H:%M")
            ))
    
    def _load(self) -> dict:
        """加载会话状态"""
        if not self.file_path.exists():
            return self._empty_state()
        
        try:
            content = self.file_path.read_text()
            return self._parse(content)
        except Exception as e:
            print(f"[SessionState] load error: {e}")
            return self._empty_state()
    
    def _empty_state(self) -> dict:
        """空状态"""
        return {
            "current_task": "[None]",
            "key_context": "[None yet]",
            "pending_actions": "- [ ] None",
            "recent_decisions": "[None yet]",
            "user_preferences": "[None yet]",
            "important_facts": "[None yet]",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    
    def _parse(self, content: str) -> dict:
        """解析文件内容"""
        data = self._empty_state()
        
        # 解析各个区块
        sections = {
            "current_task": r"## Current Task\s*\n(.*?)(?=\n## |---)",
            "key_context": r"## Key Context\s*\n(.*?)(?=\n## |---)",
            "pending_actions": r"## Pending Actions\s*\n(.*?)(?=\n## |---)",
            "recent_decisions": r"## Recent Decisions\s*\n(.*?)(?=\n## |---)",
            "user_preferences": r"## User Preferences\s*\n(.*?)(?=\n## |---)",
            "important_facts": r"## Important Facts\s*\n(.*?)(?=\n---)",
        }
        
        for key, pattern in sections.items():
            match = re.search(pattern, content, re.DOTALL)
            if match:
                data[key] = match.group(1).strip()
        
        return data
    
    def save(self):
        """保存会话状态（使用文件锁防止并发覆盖）"""
        try:
            self.data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            content = SESSION_STATE_TEMPLATE.format(**self.data)
            
            # 【修复#3-2】文件锁防止多进程竞争
            with open(self.file_path, 'a+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.seek(0)
                    f.write(content)
                    f.truncate()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception as e:
            print(f"[SessionState] save error: {e}")
    
    def update_task(self, task: str):
        """更新当前任务"""
        self.data["current_task"] = f"[{datetime.now().strftime('%H:%M')}] {task}"
        self.save()
    
    def add_context(self, context: str):
        """添加关键上下文"""
        current = self.data["key_context"]
        if current == "[None yet]" or current == "[None]":
            self.data["key_context"] = context
        else:
            self.data["key_context"] = f"{current}\n- {context}"
        self.save()
    
    def add_decision(self, decision: str):
        """添加决策"""
        current = self.data["recent_decisions"]
        if current == "[None yet]" or current == "[None]":
            self.data["recent_decisions"] = f"[{datetime.now().strftime('%H:%M')}] {decision}"
        else:
            self.data["recent_decisions"] = f"{current}\n- {decision}"
        self.save()
    
    def add_preference(self, preference: str):
        """添加用户偏好"""
        current = self.data["user_preferences"]
        if current == "[None yet]" or current == "[None]":
            self.data["user_preferences"] = f"- {preference}"
        else:
            self.data["user_preferences"] = f"{current}\n- {preference}"
        self.save()
    
    def add_fact(self, fact: str):
        """添加重要事实"""
        current = self.data["important_facts"]
        if current == "[None yet]" or current == "[None]":
            self.data["important_facts"] = f"- {fact}"
        else:
            self.data["important_facts"] = f"{current}\n- {fact}"
        self.save()
    
    def add_pending_action(self, action: str):
        """添加待办事项"""
        current = self.data["pending_actions"]
        # 替换 [ ] 为具体事项
        if "- [ ] None" in current:
            self.data["pending_actions"] = f"- [ ] {action}"
        else:
            self.data["pending_actions"] = f"{current}\n- [ ] {action}"
        self.save()
    
    def complete_action(self, action_text: str):
        """标记事项完成"""
        current = self.data["pending_actions"]
        self.data["pending_actions"] = current.replace(f"- [ ] {action_text}", f"- [x] {action_text}")
        self.save()
    
    def clear(self):
        """清空状态"""
        self.data = self._empty_state()
        self.save()
    
    def get_summary(self) -> str:
        """获取状态摘要"""
        lines = []
        if self.data.get("current_task") and "[None]" not in self.data["current_task"]:
            lines.append(f"📌 任务: {self.data['current_task']}")
        if self.data.get("key_context") and "[None]" not in self.data["key_context"]:
            lines.append(f"📎 上下文: {self.data['key_context'][:100]}")
        if self.data.get("pending_actions") and "[ ] None" not in self.data["pending_actions"]:
            lines.append(f"⏳ 待办: {self.data['pending_actions']}")
        return "\n".join(lines) if lines else ""

# 全局实例
session_state = SessionState()
