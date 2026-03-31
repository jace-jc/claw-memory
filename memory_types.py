"""
Claw Memory 类型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Union

class MemoryType(str, Enum):
    """记忆类型枚举"""
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    LESSON = "lesson"
    ENTITY = "entity"
    TASK_STATE = "task_state"

class Scope(str, Enum):
    """作用域枚举"""
    GLOBAL = "global"
    USER = "user"
    PROJECT = "project"
    AGENT = "agent"
    SESSION = "session"
    CHANNEL = "channel"

@dataclass
class Memory:
    """记忆数据结构"""
    id: str
    content: str
    type: MemoryType
    importance: float = 0.5
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    source_id: Optional[str] = None
    scope: Scope = Scope.USER
    access_count: int = 0
    last_access: Optional[datetime] = None
    encrypted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    content: str
    type: MemoryType
    score: float
    importance: float
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ApiResponse:
    """统一API响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None

# 兼容旧格式：dict别名
MemoryDict = Dict[str, Any]
SearchResultList = List[SearchResult]
