"""
Claw Memory 主入口 - 工具注册和调度（修复版）
"""
import warnings
# 压制 SSL 警告（urllib3 v2 与 LibreSSL 兼容性问题，不影响功能）
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List, Union
from memory_extract import extract_from_messages, is_noise, quick_extract, deep_extract
from memory_config import CONFIG

# 懒加载，避免循环导入
_db_store = None


def get_db():
    global _db_store
    if _db_store is None:
        from lancedb_store import get_db_store
        _db_store = get_db_store()
    return _db_store


# ==================== 统一响应格式 ====================
# 【P0修复】解决API返回格式不统一的问题

def api_response(
    success: bool = True,
    data: Any = None,
    error: Optional[str] = None,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    统一API响应格式
    
    所有memory_*函数应返回此格式：
    {
        "success": bool,      # 操作是否成功
        "data": any,          # 成功时返回的数据
        "error": str,         # 失败时的错误信息
        "message": str         # 附加消息
    }
    
    示例：
        return api_response(success=True, data={"count": 5})
        return api_response(success=False, error="记忆不存在")
    """
    return {
        "success": success,
        "data": data,
        "error": error,
        "message": message
    }


# ==================== 工具定义 ====================

TOOLS = {
    "memory_store": {
        "description": "存储新记忆到记忆系统",
        "params": {
            "content": {"type": "string", "required": True, "description": "记忆内容"},
            "type": {"type": "string", "description": "类型: fact|preference|decision|lesson|entity|task_state"},
            "importance": {"type": "number", "description": "重要性 0.0-1.0"},
            "tags": {"type": "array", "description": "标签列表"},
            "source_id": {"type": "string", "description": "来源消息ID"},
            "scope": {"type": "string", "description": "范围: global|user|project|agent|session|channel"},
        }
    },
    "memory_search": {
        "description": "搜索记忆（支持Cross-Encoder重排和多范围隔离）",
        "params": {
            "query": {"type": "string", "required": True, "description": "搜索查询"},
            "limit": {"type": "number", "description": "返回数量限制"},
            "types": {"type": "array", "description": "过滤类型"},
            "min_score": {"type": "number", "description": "最低重要性分数"},
            "scope": {"type": "string", "description": "范围过滤: global|user|project|agent|session|channel"},
            "use_rerank": {"type": "boolean", "description": "是否使用Cross-Encoder重排"},
        }
    },
    "memory_search_rrf": {
        "description": "【P0新增】RRF融合搜索 - 4通道融合（Vector+BM25+Importance+KG）",
        "params": {
            "query": {"type": "string", "required": True, "description": "搜索查询"},
            "limit": {"type": "number", "description": "返回数量限制（默认5）"},
            "k": {"type": "number", "description": "RRF参数k（默认60，越小越激进）"},
        }
    },
    "memory_recall": {
        "description": "召回相关记忆（自动注入上下文）",
        "params": {
            "query": {"type": "string", "required": True, "description": "召回查询"},
            "auto_inject": {"type": "boolean", "description": "是否自动注入上下文"},
        }
    },
    "memory_forget": {
        "description": "删除记忆",
        "params": {
            "memory_id": {"type": "string", "description": "记忆ID"},
            "query": {"type": "string", "description": "按内容查询删除"},
        }
    },
    "memory_tier": {
        "description": "查看或管理记忆层级",
        "params": {
            "action": {"type": "string", "description": "操作: view|stats|auto_tier"},
            "tier": {"type": "string", "description": "层级: HOT|WARM|COLD|ALL"},
        }
    },
    "memory_stats": {
        "description": "获取记忆统计",
        "params": {}
    },
    "memory_kg": {
        "description": "知识图谱查询（新增）",
        "params": {
            "action": {"type": "string", "description": "操作: search|network|stats|suggest"},
            "entity": {"type": "string", "description": "实体名称"},
            "depth": {"type": "number", "description": "探索深度（默认2）"},
        }
    },
    "memory_disambiguate": {
        "description": "【P1新增】实体消歧 - 判断实体是否已存在并合并",
        "params": {
            "entity_name": {"type": "string", "required": True, "description": "实体名称"},
            "entity_type": {"type": "string", "description": "实体类型: person|company|project|tool|concept|location"},
            "context": {"type": "string", "description": "上下文信息"},
        }
    },
    "memory_health": {
        "description": "记忆健康度仪表盘（新增）",
        "params": {
            "action": {"type": "string", "description": "操作: report|dashboard|score"},
        }
    },
    "memory_temporal": {
        "description": "【P2新增】时序追踪 - 记忆版本管理和历史",
        "params": {
            "action": {"type": "string", "description": "操作: history|as_of|changes|prune"},
            "memory_id": {"type": "string", "description": "记忆ID（history时必填）"},
            "days": {"type": "number", "description": "天数（changes时使用，默认30）"},
        }
    },
    "memory_cache": {
        "description": "【P3新增】搜索缓存管理",
        "params": {
            "action": {"type": "string", "description": "操作: stats|clear|invalidate"},
        }
    },
    "memory_forgetting": {
        "description": "【P2新增】Weibull遗忘机制 - 智能记忆衰减",
        "params": {
            "action": {"type": "string", "description": "操作: decay_curve|should_forget|analyze"},
            "memory_id": {"type": "string", "description": "记忆ID（should_forget时必填）"},
            "threshold": {"type": "number", "description": "遗忘阈值（默认0.2）"},
        }
    },
    "memory_extract_session": {
        "description": "从当前会话消息中抽取记忆",
        "params": {
            "messages": {"type": "array", "required": True, "description": "消息列表"},
        }
    },
}

# ==================== 核心函数 ====================

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
    from memory_extract import is_noise
    if is_noise(content):
        return {
            "success": False,
            "memory_id": None,
            "message": "噪音内容已过滤（问候/确认/纯emoji）"
        }
    
    # 【修复#3-4】Ollama离线检查
    from ollama_embed import embedder
    test_vec = embedder.embed("test")
    if not test_vec:
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
        "message": f"记忆存储{'成功' if success else '失败'}"
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
                "tags": r.get("tags_parsed", []),
                "scope": r.get("scope"),
                "rrf_score": r.get("_rrf_score"),
                "channel_count": r.get("_total_channels"),
                "bm25_score": r.get("bm25_score"),
                "kg_score": r.get("kg_score"),
                "created_at": r.get("created_at"),
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


def memory_privacy(action: str = "audit", memory_id: str = None) -> dict:
    """
    【P1新增】隐私合规管理（GDPR支持）
    
    Args:
        action: 操作
            - export: 导出所有数据（数据可携权）
            - delete: 删除单条记忆
            - delete_all: 删除所有数据（被遗忘权）
            - anonymize: 匿名化单条记忆
            - audit: 获取隐私审计日志
        memory_id: 记忆ID（delete/anonymize时必填）
    
    Returns:
        操作结果
    """
    try:
        from memory_privacy import get_privacy
        
        privacy = get_privacy()
        db = get_db()
        
        if action == "export":
            # 导出所有数据
            result = privacy.export_data(db)
            return api_response(
                success=result.get("success", False),
                data=result if result.get("success") else None,
                error=result.get("error"),
                message=f"已导出 {result.get('count', 0)} 条记录"
            )
        
        elif action == "delete":
            # 删除单条记忆
            if not memory_id:
                return api_response(success=False, error="memory_id必填")
            
            result = privacy.delete_memory(db, memory_id)
            return api_response(
                success=result.get("success", False),
                message=result.get("message"),
                error=result.get("error")
            )
        
        elif action == "delete_all":
            # 删除所有数据（危险操作，需要确认）
            result = privacy.delete_all_data(db)
            return api_response(
                success=result.get("success", False),
                message=result.get("message"),
                error=result.get("error")
            )
        
        elif action == "anonymize":
            # 匿名化单条记忆
            if not memory_id:
                return api_response(success=False, error="memory_id必填")
            
            result = privacy.anonymize_data(db, memory_id)
            return api_response(
                success=result.get("success", False),
                message=result.get("message"),
                error=result.get("error")
            )
        
        elif action == "audit":
            # 获取审计日志
            logs = privacy.get_audit_log(limit=50)
            return api_response(success=True, data={
                "logs": logs,
                "count": len(logs)
            })
        
        else:
            return api_response(success=False, error=f"未知action: {action}")
            
    except Exception as e:
        return api_response(success=False, error=str(e))


def memory_recall(query: str, auto_inject: bool = True, similarity_threshold: float = 0.3,
                  scope: str = None, use_rerank: bool = False) -> dict:
    """
    召回相关记忆，可选择自动注入上下文
    
    Args:
        query: 召回查询
        auto_inject: 是否自动注入上下文
        similarity_threshold: 最低相似度阈值
        scope: 范围过滤 - global|user|project|agent|session|channel
        use_rerank: 是否使用Cross-Encoder重排
    """
    db = get_db()
    # 传入 min_score 参数进行相似度过滤
    results = db.search(query, limit=5, min_score=similarity_threshold, 
                        scope=scope, use_rerank=use_rerank)

    if not results:
        return {
            "query": query,
            "count": 0,
            "recall_text": "",
            "results": []
        }

    # 构造召回文本
    lines = ["📚 相关记忆："]
    for r in results:
        lines.append(f"\n[{r.get('type')}] {r.get('content')}")

    recall_text = "\n".join(lines)

    # 清理结果，移除大向量数据
    clean_results = []
    for r in results:
        clean_results.append({
            "id": r.get("id"),
            "type": r.get("type"),
            "content": r.get("content"),
            "importance": r.get("importance"),
            "tags": r.get("tags_parsed", []),
            "created_at": r.get("created_at"),
        })

    return {
        "query": query,
        "count": len(results),
        "recall_text": recall_text,
        "auto_inject": auto_inject,
        "results": clean_results
    }


def memory_forget(memory_id: str = None, query: str = None) -> dict:
    """
    删除记忆
    【修复#3-6】验证删除结果
    """
    db = get_db()
    
    # 先检查是否存在
    if memory_id:
        existing = db.get(memory_id)
        if not existing:
            return {
                "success": False,
                "message": f"记忆 {memory_id} 不存在"
            }
    
    success = db.delete(memory_id=memory_id, query=query)
    return {
        "success": success,
        "message": f"记忆删除{'成功' if success else '失败'}"
    }


def memory_tier(action: str = "view", tier: str = "ALL") -> dict:
    """
    查看或管理层级状态
    """
    from memory_tier import tier_manager
    from memory_session import session_state

    if action == "stats":
        return tier_manager.stats()

    if action == "auto_tier":
        return tier_manager.auto_tier()

    # view action
    if tier == "HOT":
        summary = session_state.get_summary()
        return {
            "tier": "HOT",
            "summary": summary or "无活动会话",
            "file": str(session_state.file_path),
            "last_updated": session_state.data.get("last_updated", "never")
        }
    elif tier == "WARM":
        db = get_db()
        stats = db.stats()
        return {
            "tier": "WARM",
            "stats": stats,
            "location": CONFIG.get("db_path")
        }
    elif tier == "COLD":
        cold_memories = tier_manager.get_cold_memories(limit=20)
        return {
            "tier": "COLD",
            "recent_count": len(cold_memories),
            "memories": cold_memories,
            "location": str(tier_manager.cold_dir)
        }
    else:
        # ALL
        return tier_manager.stats()


def memory_stats() -> dict:
    """
    获取记忆统计【P0修复】移除敏感信息泄露
    """
    from memory_tier import tier_manager
    from memory_session import session_state

    db = get_db()
    warm_stats = db.stats()
    cold_memories = tier_manager.get_cold_memories(limit=1000)

    return {
        "warm_store": warm_stats,
        "cold_store": {"count": len(cold_memories)},
        "hot_store": {
            "has_content": bool(session_state.get_summary())
        },
        "config": {
            "hot_ttl": f"{CONFIG.get('hot_ttl_hours', 24)}h",
            "warm_ttl": f"{CONFIG.get('warm_ttl_days', 30)}d",
            "min_importance": CONFIG.get("min_importance", 0.3),
        }
    }


def memory_kg(action: str = "stats", entity: str = None, depth: int = 2,
             entity2: str = None) -> dict:
    """
    知识图谱查询【新增】
    
    Args:
        action: 操作
            - stats: 图谱统计
            - network: 实体网络
            - search: 搜索实体
            - suggest: 建议
            - path: 传递推理路径（需要entity和entity2）
            - common: 共同邻居
            - infer: 关系推理
            - by_type: 按类型查找
        entity: 实体名称
        entity2: 第二个实体（用于path和common）
        depth: 探索深度
    """
    from kg_networkx import get_kg_nx
    
    kg = get_kg_nx()
    
    if action == "stats":
        return api_response(success=True, data=kg.get_stats())
    
    elif action == "network":
        if not entity:
            return api_response(success=False, error="entity参数必填")
        result = kg.get_entity_network(entity, depth)
        return api_response(success=True, data=result)
    
    elif action == "search":
        if not entity:
            return api_response(success=False, error="entity参数必填")
        results = kg.search_entities(entity, limit=10)
        return api_response(success=True, data={"results": results})
    
    elif action == "path":
        # 【新增】传递推理：查找两个实体间的路径
        if not entity or not entity2:
            return api_response(success=False, error="entity和entity2参数必填")
        paths = kg.find_path(entity, entity2, max_depth=depth)
        return api_response(success=True, data={
            "from": entity,
            "to": entity2,
            "paths": paths,
            "count": len(paths)
        })
    
    elif action == "common":
        # 【新增】共同邻居
        if not entity or not entity2:
            return api_response(success=False, error="entity和entity2参数必填")
        common = kg.find_common_neighbors(entity, entity2)
        return api_response(success=True, data={
            "entity1": entity,
            "entity2": entity2,
            "common_neighbors": common,
            "count": len(common)
        })
    
    elif action == "infer":
        # 【新增】关系推理
        if not entity:
            return api_response(success=False, error="entity参数必填")
        inferences = kg.infer_relations(entity, max_depth=depth)
        return api_response(success=True, data={
            "entity": entity,
            "inferences": inferences,
            "count": len(inferences)
        })
    
    elif action == "by_type":
        # 【新增】按类型查找实体
        if not entity:
            return api_response(success=False, error="entity参数必填（实体类型）")
        results = kg.find_by_type(entity, limit=10)
        return api_response(success=True, data={
            "type": entity,
            "entities": results,
            "count": len(results)
        })
    
    elif action == "suggest":
        # 返回所有建议连接
        stats = kg.get_stats()
        return api_response(success=True, data={
            "total_entities": stats["total_entities"],
            "total_relations": stats["total_relations"],
            "message": "使用 memory_kg(action='extract', content='...') 提取建议"
        })
    
    elif action == "extract":
        # 这个由memory_store调用
        return api_response(success=False, error="extract由memory_store自动调用")
    
    else:
        return api_response(success=False, error=f"未知action: {action}")


def memory_kg_extract_and_link(memory_content: str, memory_id: str = None) -> dict:
    """
    从记忆内容中提取实体和关系并添加到图谱【新增】
    由memory_store自动调用
    """
    from memory_kg import get_kg
    
    kg = get_kg()
    result = kg.extract_and_link(memory_content, memory_id)
    
    # 添加建议的新连接
    suggestions = kg.suggest_connections(memory_content)
    result["suggestions"] = suggestions
    
    return result


def memory_disambiguate(entity_name: str, entity_type: str = None, 
                       context: str = "") -> dict:
    """
    【P1新增】实体消歧
    
    判断实体是否已存在于知识图谱中，如果存在则合并，否则创建新实体。
    
    Args:
        entity_name: 实体名称
        entity_type: 实体类型 (person/company/project/tool/concept/location)
        context: 上下文信息
        
    Returns:
        {"action": "merged"|"existing"|"new", "entity_id": "...", "confidence": 0.xx}
    """
    from memory_kg import get_kg
    
    kg = get_kg()
    result = kg.disambiguate_entity(entity_name, entity_type, context)
    
    return {
        "entity_name": entity_name,
        "entity_type": entity_type or "concept",
        "action": result["action"],
        "entity_id": result.get("entity_id"),
        "confidence": result.get("confidence", 1.0 if result["action"] == "new" else 0.0),
        "merged_into": result.get("entity_name") if result["action"] == "merged" else None
    }


def memory_health(action: str = "report") -> dict:
    """
    记忆健康度仪表盘【新增】
    
    Args:
        action: 操作 - report|dashboard|score
    """
    from memory_health import get_health
    
    health = get_health()
    
    if action == "score":
        report = health.generate_report()
        return {"score": report["health_score"], "status": report["status"]}
    
    elif action == "dashboard":
        return health.get_dashboard()
    
    else:  # report
        return health.generate_report()


def memory_temporal(action: str = "changes", memory_id: str = None, days: int = 30) -> dict:
    """
    【P2新增】时序追踪 API
    
    Args:
        action: 操作 - history|as_of|changes|prune|timeline
        memory_id: 记忆ID（history时必填）
        days: 查询天数（changes时使用）
    """
    from temporal_tracking import get_temporal
    
    temporal = get_temporal()
    
    if action == "history":
        if not memory_id:
            return api_response(success=False, error="memory_id必填")
        result = temporal.get_history(memory_id)
        return api_response(success=True, data=result)
    
    elif action == "as_of":
        # 查询截至当前时刻有效的记忆（需要指定关键词）
        # 默认查询所有记忆的有效时间
        result = temporal.query_as_of("*")
        return api_response(success=True, data={
            "as_of": datetime.now().isoformat(),
            "current_valid": len(result),
            "memories": result
        })
    
    elif action == "changes":
        changes = temporal.get_change_log(days=days)
        return api_response(success=True, data={
            "days": days,
            "changes": changes
        })
    
    elif action == "prune":
        pruned = temporal.prune_old_versions(keep_days=90)
        return api_response(success=True, message=f"清理了{pruned}条过期历史", data={"pruned_count": pruned})
    
    elif action == "timeline":
        result = temporal.get_preference_timeline()
        return api_response(success=True, data=result)
    
    else:
        return api_response(success=False, error=f"未知action: {action}")


def memory_cache(action: str = "stats") -> dict:
    """
    【P3新增】搜索缓存管理 API
    
    Args:
        action: 操作 - stats|clear|invalidate|perf
    """
    try:
        from search_cache import get_search_cache, get_embedding_cache
        
        cache = get_search_cache()
        
        if action == "stats":
            return api_response(success=True, data={
                "search_cache": cache.get_stats(),
            })
        
        elif action == "clear":
            cache.clear()
            return api_response(success=True, message="搜索缓存已清空")
        
        elif action == "invalidate":
            cache.invalidate()
            return api_response(success=True, message="缓存已失效")
        
        elif action == "perf":
            # 【P3新增】性能统计
            stats = cache.get_stats()
            return api_response(success=True, data={
                "cache_hits": stats.get("hits", 0),
                "cache_misses": stats.get("misses", 0),
                "hit_rate": f"{stats.get('hit_rate', 0)*100:.1f}%",
                "size": stats.get("size", 0)
            })
        
        else:
            return api_response(success=False, error=f"未知action: {action}")
            
    except ImportError:
        return api_response(success=False, error="缓存模块不可用")


# 【P3新增】常见查询预取列表
COMMON_QUERIES = [
    "用户偏好",
    "用户信息",
    "项目进度",
    "工作安排",
    "会议内容",
    "任务状态",
    "联系人",
    "重要事项",
    "待办",
    "今天",
    "明天",
    "本周",
    "生日",
    "纪念日",
    "习惯",
    "爱好",
]


def memory_prefetch(action: str = "common", queries: list = None) -> dict:
    """
    【P3新增】预取查询 API
    
    Args:
        action: 操作 - common|list|custom
        queries: 自定义查询列表（custom时使用）
    """
    try:
        from search_cache import get_search_cache
        
        cache = get_search_cache()
        
        # 确定要预取的查询列表
        if action == "common":
            to_prefetch = COMMON_QUERIES
        elif action == "custom" and queries:
            to_prefetch = queries
        elif action == "list":
            # 只是列出常见查询，不执行预取
            return api_response(success=True, data={
                "common_queries": COMMON_QUERIES,
                "count": len(COMMON_QUERIES)
            })
        else:
            return api_response(success=False, error=f"未知action: {action}")
        
        # 获取搜索函数
        def do_search(query, limit):
            db = get_db()
            return db.search(query, limit=limit)
        
        # 执行预取
        prefetched = cache.prefetch(to_prefetch, do_search)
        
        return api_response(success=True, message=f"预取了 {prefetched} 个查询", data={
            "prefetched": prefetched,
            "total_queries": len(to_prefetch),
            "cache_size": cache.get_stats().get("size", 0)
        })
        
    except Exception as e:
        return api_response(success=False, error=str(e))


def memory_forgetting(action: str = "decay_curve", memory_id: str = None,
                     threshold: float = 0.2) -> dict:
    """
    【P2新增】Weibull遗忘机制 API
    
    Args:
        action: 操作 - decay_curve|should_forget|analyze
        memory_id: 记忆ID（should_forget时必填）
        threshold: 遗忘阈值（默认0.2）
    """
    from weibull_forgetting import get_weibull_decay, get_adaptive_forgetting
    
    decay = get_weibull_decay()
    
    if action == "decay_curve":
        curve = decay.get_decay_curve(days=90)
        return api_response(success=True, data={
            "shape": decay.shape,
            "scale": decay.scale,
            "curve": curve
        })
    
    elif action == "should_forget":
        if not memory_id:
            return api_response(success=False, error="memory_id必填")
        
        db = get_db()
        memory = db.get(memory_id)
        
        if not memory:
            return api_response(success=False, error=f"记忆 {memory_id} 不存在")
        
        should = decay.should_forget(memory, threshold)
        info = decay.get_importance_with_decay(memory)
        
        return api_response(success=True, data={
            "memory_id": memory_id,
            "should_forget": should,
            "threshold": threshold,
            "analysis": info
        })
    
    elif action == "analyze":
        # 分析所有记忆的遗忘情况
        db = get_db()
        stats = db.stats()
        total = stats.get("warm_store", {}).get("total", 0)
        
        # 获取样本进行分析
        try:
            all_memories = db.table.to_arrow().to_pylist()[:100]  # 最多100条
        except:
            all_memories = []
        
        forget_count = 0
        decay_scores = []
        
        for mem in all_memories:
            if decay.should_forget(mem, threshold):
                forget_count += 1
            info = decay.get_importance_with_decay(mem)
            decay_scores.append({
                "id": mem.get("id", "")[:8],
                "current": info["current"],
                "age_days": info["age_days"]
            })
        
        # 按current重要性排序
        decay_scores.sort(key=lambda x: x["current"])
        
        return api_response(success=True, data={
            "total_analyzed": len(all_memories),
            "should_forget_count": forget_count,
            "forget_ratio": round(forget_count / max(1, len(all_memories)), 3),
            "threshold": threshold,
            "low_importance_memories": decay_scores[:10]  # 最应该遗忘的10条
        })
    
    else:
        return api_response(success=False, error=f"未知action: {action}")


def memory_batch(operations: list, use_transaction: bool = True) -> dict:
    """
    【P1新增】批量操作API（支持事务）
    
    Args:
        operations: 操作列表
        use_transaction: 是否使用事务（默认True，失败自动回滚）
    """
    try:
        from transaction import with_transaction
        
        db = get_db()
        
        if use_transaction:
            try:
                with with_transaction(db) as txn:
                    results = []
                    for op in operations:
                        op_type = op.get("op")
                        if op_type == "store":
                            txn.store(op.get("data", {}))
                            results.append({"op": "store", "success": True})
                        elif op_type == "delete":
                            txn.delete(op.get("memory_id"))
                            results.append({"op": "delete", "success": True})
                        elif op_type == "update":
                            txn.update(op.get("memory_id"), op.get("updates", {}))
                            results.append({"op": "update", "success": True})
                        else:
                            results.append({"op": op_type, "success": False, "error": "未知操作"})
                    
                    return api_response(success=True, data={
                        "total": len(operations),
                        "committed": True,
                        "results": results
                    })
            except Exception as e:
                return api_response(success=False, error=f"事务回滚: {str(e)}")
        else:
            results = []
            for op in operations:
                op_type = op.get("op")
                try:
                    if op_type == "store":
                        db.store(op.get("data", {}))
                        results.append({"op": "store", "success": True})
                    elif op_type == "delete":
                        db.delete(memory_id=op.get("memory_id"))
                        results.append({"op": "delete", "success": True})
                    elif op_type == "update":
                        db.update(op.get("memory_id"), op.get("updates", {}))
                        results.append({"op": "update", "success": True})
                except Exception as e:
                    results.append({"op": op_type, "success": False, "error": str(e)})
            
            return api_response(success=True, data={
                "total": len(operations),
                "committed": True,
                "results": results
            })
            
    except Exception as e:
        return api_response(success=False, error=str(e))


def memory_transaction_stats() -> dict:
    """【P1新增】获取事务统计"""
    try:
        from transaction import TransactionLog
        log = TransactionLog()
        stats = log.get_stats()
        return api_response(success=True, data=stats)
    except Exception as e:
        return api_response(success=False, error=str(e))


def memory_extract_session(messages: list) -> dict:
    """
    从会话消息中抽取记忆
    """
    memories = extract_from_messages(messages)

    # 批量存储
    stored = 0
    for mem in memories:
        result = memory_store(
            content=mem["content"],
            type=mem.get("type", "fact"),
            importance=mem.get("importance", 0.5),
            tags=mem.get("tags", []),
            source_id=mem.get("source_id", ""),
            transcript=mem.get("transcript", "")
        )
        if result["success"]:
            stored += 1

    return {
        "extracted": len(memories),
        "stored": stored,
        "memories": memories
    }


# ==================== 自动钩子 ====================

def auto_capture(message: dict) -> list:
    """
    自动捕获 - 从单条消息中快速抽取并存储
    返回已存储的记忆数量
    """
    content = message.get("content", "")
    if is_noise(content):
        return []

    quick_results = quick_extract(content)
    
    # 【P0修复】实际存储抽取到的记忆
    stored = []
    for r in quick_results:
        result = memory_store(
            content=r["content"],
            type=r.get("type", "fact"),
            importance=r.get("importance", 0.5),
            tags=r.get("tags", []),
            source_id=message.get("id", ""),
            transcript=content[:200]
        )
        if result["success"]:
            stored.append(result["memory_id"])
    
    return stored


def auto_recall(query: str, similarity_threshold: float = None) -> str:
    """
    自动召回 - 搜索相关记忆并返回文本
    【P0修复】从CONFIG读取相似度阈值
    """
    if similarity_threshold is None:
        similarity_threshold = CONFIG.get("similarity_threshold", 0.3)
    
    result = memory_recall(query, auto_inject=True, similarity_threshold=similarity_threshold)
    if result["count"] > 0:
        return result["recall_text"]
    return ""


# ==================== CLI 入口 ====================

if __name__ == "__main__":
    import sys
    import warnings
    
    # 压制 SSL 警告
    warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("""Claw Memory CLI - 本地优先的AI记忆系统

用法: python memory_main.py <command> [args]

命令:
  store <内容>          存储新记忆
  search <查询>         语义搜索记忆
  recall <查询>         召回相关记忆（用于AI上下文）
  forget <关键词>       删除相关记忆
  tier [action] [层]   层级管理 (view/promote/archive)
  stats                显示统计信息
  auto_tier            自动执行层级整理

示例:
  python memory_main.py store "用户喜欢喝咖啡"
  python memory_main.py recall "咖啡"
  python memory_main.py stats
""")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "store":
        content = " ".join(sys.argv[2:])
        result = memory_store(content)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "search":
        query = " ".join(sys.argv[2:])
        result = memory_search(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "recall":
        query = " ".join(sys.argv[2:])
        result = memory_recall(query)
        print(result["recall_text"] if result["count"] > 0 else "无相关记忆")

    elif cmd == "forget":
        query = " ".join(sys.argv[2:])
        result = memory_forget(query=query)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "tier":
        action = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else "view"
        tier = sys.argv[3] if len(sys.argv) > 3 else "ALL"
        result = memory_tier(action=action, tier=tier)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "stats":
        result = memory_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "auto_tier":
        from memory_tier import tier_manager
        result = tier_manager.auto_tier()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Available commands: store, search, recall, forget, tier, stats, auto_tier")
        sys.exit(1)
