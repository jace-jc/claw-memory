"""
API: Main functions - memory_store, memory_search, memory_search_rrf, memory_adaptive
Phase 3: Split from memory_main.py
"""
import warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import json
import uuid
from datetime import datetime
from typing import Optional, Any, Dict, List
from extract.memory_extract import extract_from_messages, is_noise, quick_extract, deep_extract
from core.memory_config import CONFIG


def get_db():
    """Lazy import to avoid circular dependency"""
    from memory_main import get_db as _get_db
    return _get_db()


def api_response(
    success: bool = True,
    data: Any = None,
    error: Optional[str] = None,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """统一API响应格式"""
    return {
        "success": success,
        "data": data,
        "error": error,
        "message": message
    }


def memory_store(
    content: str,
    type: str = "fact",
    importance: float = 0.5,
    tags: Optional[List[str]] = None,
    source_id: str = "",
    transcript: str = "",
    scope: str = "user"
) -> Dict[str, Any]:
    """
    存储新记忆
    
    Args:
        content: 记忆内容
        type: 类型 - fact|preference|decision|lesson|entity|task_state
        importance: 重要性 0.0-1.0
        tags: 标签列表
        source_id: 来源消息ID
        scope: 范围 - global|user|project|agent|session|channel
    """
    # 【修复#3-1】噪音过滤：CLI调用也要检查
    from extract.memory_extract import is_noise
    if is_noise(content):
        return {
            "success": False,
            "memory_id": None,
            "message": "噪音内容已过滤（问候/确认/纯emoji）"
        }
    
    # 【P0优化】使用连接池检查Ollama健康状态，避免频繁embed调用
    from ollama_pool import get_pool
    pool = get_pool()
    if not pool.is_healthy():
        return {
            "success": False,
            "memory_id": None,
            "message": "⚠️ Ollama未运行或无法连接。记忆存储失败。"
        }
    
    memory = {
        "id": str(uuid.uuid4()),
        "type": type,
        "content": content,
        "importance": importance,
        "tags": tags or [],
        "source": source_id,
        "transcript": transcript,
        "scope": scope,  # 可配置: global|user|project|agent|session|channel
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # 【P2新增】自动分配层级
    try:
        from memory_tier_manager import assign_tier_for_memory, TIER_WARM
        assigned_tier = assign_tier_for_memory(memory)
        memory["tier"] = assigned_tier
    except Exception:
        memory["tier"] = TIER_WARM  # 默认 WARM

    # 存储到 LanceDB
    db = get_db()
    success = db.store(memory)

    # 【新增】自动关联知识图谱
    if success:
        try:
            from memory_kg import get_kg
            kg = get_kg()
            kg_result = kg.extract_and_link(content, memory["id"])
            if kg_result.get("entities") or kg_result.get("relations"):
                memory["_kg_entities"] = kg_result["entities"]
                memory["_kg_relations"] = kg_result["relations"]
        except Exception:
            pass  # 知识图谱失败不影响主流程

    # 同时更新 HOT RAM
    from memory_session import session_state
    if success:
        if type == "preference":
            session_state.add_preference(content)
        elif type == "decision":
            session_state.add_decision(content)
        elif type == "fact":
            session_state.add_fact(content)

    return {
        "success": success,
        "memory_id": memory["id"],
        "message": f"记忆存储{'成功' if success else '失败'}",
        "tier": memory.get("tier", "WARM"),  # 【P2新增】返回分配的层级
        "importance": importance
    }


def memory_search(
    query: str,
    limit: int = 5,
    types: Optional[List[str]] = None,
    min_score: float = 0.3,
    scope: str = None, use_rerank: bool = False) -> dict:
    """
    语义搜索记忆
    
    Args:
        query: 搜索查询
        limit: 返回数量
        types: 过滤类型列表
        min_score: 最低重要性分数
        scope: 范围过滤 - global|user|project|agent|session|channel
        use_rerank: 是否使用Cross-Encoder重排
    """
    db = get_db()
    results = db.search(query, limit=limit, types=types, min_score=min_score, 
                        scope=scope, use_rerank=use_rerank)

    return {
        "query": query,
        "count": len(results),
        "reranked": use_rerank,
        "scope_filter": scope,
        "results": [
            {
                "id": r.get("id"),
                "type": r.get("type"),
                "content": r.get("content"),
                "importance": r.get("importance"),
                "tags": r.get("tags_parsed", []),
                "scope": r.get("scope"),
                "cross_score": r.get("_cross_score"),
                "final_score": r.get("_final_score"),
                "created_at": r.get("created_at"),
            }
            for r in results
        ]
    }


def memory_search_rrf(
    query: str,
    limit: int = 5,
    k: int = 60,
    use_adaptive: bool = True
) -> Dict[str, Any]:
    """
    【P0新增】RRF融合搜索 - 4通道融合
    
    融合通道:
    1. Vector similarity (语义相似度)
    2. BM25 (关键词匹配)
    3. Importance score (重要性)
    4. Knowledge Graph (实体关联)
    
    Args:
        query: 搜索查询
        limit: 返回数量
        k: RRF参数 (默认60, 越小越激进地融合)
        use_adaptive: 是否使用自适应权重 (默认True)
    """
    db = get_db()
    results = db.search_rrf(query, limit=limit, k=k, use_adaptive=use_adaptive)

    # 获取当前权重
    weights = None
    if use_adaptive:
        try:
            from adaptive_rerank import get_adaptive_rrf
            adaptive = get_adaptive_rrf()
            weights = adaptive.get_weights()
        except:
            pass

    # 计算通道贡献
    channel_stats = {
        "vector": 0,
        "bm25": 0,
        "importance": 0,
        "kg": 0
    }
    
    for r in results:
        if "bm25_score" in r:
            channel_stats["bm25"] += 1
        if "importance_score" in r:
            channel_stats["importance"] += 1
        if "kg_score" in r:
            channel_stats["kg"] += 1
        if "_distance" in r:
            channel_stats["vector"] += 1

    return api_response(success=True, data={
        "query": query,
        "count": len(results),
        "rrf_k": k,
        "use_adaptive": use_adaptive,
        "weights": weights,
        "channel_stats": channel_stats,
        "results": [
            {
                "id": r.get("id"),
                "type": r.get("type"),
                "content": r.get("content"),
                "importance": r.get("importance"),
                "final_score": r.get("_final_score"),
                "rrf_score": r.get("_rrf_score"),
                "channel_scores": r.get("_channel_scores", {}),
            }
            for r in results
        ]
    })


def memory_adaptive(action: str = "weights", memory_id: str = None, query: str = None) -> dict:
    """
    【P1新增】自适应RRF权重管理
    
    Args:
        action: 操作 - weights|click|stats|reset
        memory_id: 记忆ID（click时必填）
        query: 查询词（click时必填）
    """
    try:
        from adaptive_rerank import get_adaptive_rrf
        
        adaptive = get_adaptive_rrf()
        
        if action == "weights":
            # 获取当前权重
            weights = adaptive.get_weights()
            stats = adaptive.get_stats()
            return api_response(success=True, data={
                "weights": weights,
                "confidence": stats.get("confidence", 0),
                "total_feedback": stats.get("total_feedback", 0)
            })
        
        elif action == "click":
            # 记录用户点击
            if not memory_id or not query:
                return api_response(success=False, error="memory_id和query必填")
            
            db = get_db()
            # 获取搜索结果用于记录反馈
            results = db.search_rrf(query, limit=10, use_adaptive=False)
            
            adaptive.record_click(memory_id, query, results)
            
            return api_response(success=True, message=f"已记录点击反馈: {memory_id}")
        
        elif action == "stats":
            # 获取统计信息
            stats = adaptive.get_stats()
            return api_response(success=True, data=stats)
        
        elif action == "reset":
            # 重置权重
            adaptive.reset_weights()
            return api_response(success=True, message="已重置为默认权重")
        
        else:
            return api_response(success=False, error=f"未知action: {action}")
            
    except Exception as e:
        return api_response(success=False, error=str(e))
