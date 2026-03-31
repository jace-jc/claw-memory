"""
Claw Memory Pydantic类型定义
提供标准的请求/响应类型校验
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class MemoryType:
    """记忆类型枚举"""
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    LESSON = "lesson"
    ENTITY = "entity"
    TASK_STATE = "task_state"
    
    @classmethod
    def values(cls):
        return [cls.FACT, cls.PREFERENCE, cls.DECISION, cls.LESSON, cls.ENTITY, cls.TASK_STATE]


class MemoryStoreRequest(BaseModel):
    """存储记忆请求"""
    content: str = Field(..., description="记忆内容", min_length=1, max_length=10000)
    type: Literal["fact", "preference", "decision", "lesson", "entity", "task_state"] = Field(
        default="fact", description="记忆类型"
    )
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性 0-1")
    scope: Optional[str] = Field(default=None, description="作用域哈希")
    metadata: Optional[dict] = Field(default=None, description="额外元数据")


class MemoryStoreResponse(BaseModel):
    """存储记忆响应"""
    success: bool
    id: Optional[str] = None
    message: str


class MemorySearchRequest(BaseModel):
    """搜索记忆请求"""
    query: str = Field(..., description="搜索查询", min_length=1)
    limit: int = Field(default=5, ge=1, le=100, description="返回数量")
    type_filter: Optional[Literal["fact", "preference", "decision", "lesson", "entity", "task_state"]] = Field(
        default=None, description="类型过滤"
    )
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    use_rrf: bool = Field(default=True, description="是否使用RRF融合")
    use_cache: bool = Field(default=True, description="是否使用缓存")


class MemorySearchResult(BaseModel):
    """单条搜索结果"""
    id: str
    content: str
    type: str
    importance: float
    score: float
    distance: Optional[float] = None
    metadata: Optional[dict] = None


class MemorySearchResponse(BaseModel):
    """搜索记忆响应"""
    success: bool
    query: str
    total: int
    results: List[MemorySearchResult]
    latency_ms: Optional[float] = None


class MemoryRecallRequest(BaseModel):
    """召回记忆请求"""
    entity_name: str = Field(..., description="实体名称")
    relation_type: Optional[str] = Field(default=None, description="关系类型")
    limit: int = Field(default=5, ge=1, le=50)


class MemoryForgetRequest(BaseModel):
    """删除记忆请求"""
    memory_id: str = Field(..., description="记忆ID")
    reason: Optional[str] = Field(default=None, description="删除原因")


class MemoryStatsResponse(BaseModel):
    """记忆统计响应"""
    total: int
    by_type: dict
    avg_importance: float
    oldest_memory: Optional[str] = None
    newest_memory: Optional[str] = None


class MemoryHealthResponse(BaseModel):
    """健康检查响应"""
    status: Literal["healthy", "degraded", "unhealthy"]
    total_memories: int
    vector_db_status: str
    knowledge_graph_status: str
    cache_hit_rate: Optional[float] = None
    avg_latency_ms: Optional[float] = None
    issues: List[str] = Field(default_factory=list)
