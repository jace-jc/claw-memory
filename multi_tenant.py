"""
多租户隔离模块 - Multi-Tenant Isolation
确保不同用户/项目的数据完全隔离

scope 隔离级别：
1. global - 全局共享
2. user - 用户私有（默认）
3. project - 项目私有
4. agent - Agent私有
5. session - 会话私有
6. channel - 频道私有
"""
from typing import Optional, List
from datetime import datetime


class TenantIsolation:
    """
    多租户隔离控制器
    
    确保数据访问遵循隔离规则：
    - user scope 只能访问相同 user_id 的数据
    - 不同 scope 之间完全隔离
    """
    
    def __init__(self, default_scope: str = "user"):
        self.default_scope = default_scope
        self._current_user_id = None
        self._current_scope_id = None
    
    def set_context(self, user_id: str, scope_id: str = None):
        """
        设置当前用户上下文
        
        Args:
            user_id: 用户ID
            scope_id: 范围ID（可选，用于project/agent等）
        """
        self._current_user_id = user_id
        self._current_scope_id = scope_id or user_id
    
    def get_scope_filter(self, scope: str = None) -> str:
        """
        获取范围过滤条件（用于数据库查询）
        
        Returns:
            SQL风格的过滤条件
        """
        if scope is None:
            scope = self.default_scope
        
        if scope == "global":
            return ""  # 不过滤
        
        if scope == "user":
            if not self._current_user_id:
                return "scope = 'user' AND scope_id = '__anonymous__'"
            return f"scope = 'user' AND scope_id = '{self._current_user_id}'"
        
        if scope == "project":
            if not self._current_scope_id:
                return "scope = 'project' AND scope_id = '__no_project__'"
            return f"scope = 'project' AND scope_id = '{self._current_scope_id}'"
        
        if scope == "agent":
            if not self._current_scope_id:
                return "scope = 'agent' AND scope_id = '__no_agent__'"
            return f"scope = 'agent' AND scope_id = '{self._current_scope_id}'"
        
        if scope == "session":
            if not self._current_scope_id:
                return "scope = 'session' AND scope_id = '__no_session__'"
            return f"scope = 'session' AND scope_id = '{self._current_scope_id}'"
        
        if scope == "channel":
            if not self._current_scope_id:
                return "scope = 'channel' AND scope_id = '__no_channel__'"
            return f"scope = 'channel' AND scope_id = '{self._current_scope_id}'"
        
        # 默认：只返回当前用户的数据
        return f"scope_id = '{self._current_user_id or '__default__'}'"
    
    def filter_memories(self, memories: List[dict], scope: str = None) -> List[dict]:
        """
        过滤记忆列表，确保只返回当前用户可访问的
        
        Args:
            memories: 记忆列表
            scope: 范围过滤
        
        Returns:
            过滤后的记忆列表
        """
        if scope is None:
            scope = self.default_scope
        
        if scope == "global":
            return memories
        
        filtered = []
        for mem in memories:
            mem_scope = mem.get("scope", "user")
            mem_scope_id = mem.get("scope_id", "")
            
            if mem_scope == "global":
                filtered.append(mem)
            elif mem_scope == "user":
                if mem_scope_id == self._current_user_id:
                    filtered.append(mem)
            elif mem_scope == "project" or mem_scope == "agent" or mem_scope == "session" or mem_scope == "channel":
                if mem_scope_id == self._current_scope_id:
                    filtered.append(mem)
        
        return filtered
    
    def validate_scope_write(self, memory: dict) -> bool:
        """
        验证写入权限
        
        Args:
            memory: 要写入的记忆
        
        Returns:
            是否允许写入
        """
        mem_scope = memory.get("scope", "user")
        mem_scope_id = memory.get("scope_id", "")
        
        if mem_scope == "global":
            return True  # 全局可写
        
        if mem_scope == "user":
            # 只能写入自己的用户空间
            return mem_scope_id == self._current_user_id
        
        if mem_scope in ("project", "agent", "session", "channel"):
            # 只能写入自己的范围空间
            return mem_scope_id == self._current_scope_id
        
        return False
    
    def anonymize_for_export(self, memories: List[dict]) -> List[dict]:
        """
        导出时匿名化用户标识
        
        Args:
            memories: 记忆列表
        
        Returns:
            匿名化后的记忆列表
        """
        import hashlib
        
        anonymized = []
        for mem in memories:
            mem_copy = mem.copy()
            
            # 哈希化 scope_id
            if "scope_id" in mem_copy and mem_copy["scope_id"]:
                mem_copy["scope_id"] = hashlib.sha256(
                    mem_copy["scope_id"].encode()
                ).hexdigest()[:16]
            
            # 移除敏感字段
            mem_copy.pop("transcript", None)
            
            anonymized.append(mem_copy)
        
        return anonymized


# 全局实例
_isolation = None


def get_isolation() -> TenantIsolation:
    """获取隔离控制器单例"""
    global _isolation
    if _isolation is None:
        _isolation = TenantIsolation()
    return _isolation
