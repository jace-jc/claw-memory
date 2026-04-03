"""
API: System functions - memory_tier, memory_tier_get, memory_tier_move, memory_tier_stats_v2, 
memory_stats, memory_temporal, memory_temporal_extract, memory_cache
Phase 3: Split from memory_main.py

Note: memory_health is already in api/health.py, imported below.
"""
import warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

from datetime import datetime


def get_db():
    """Lazy import to avoid circular dependency"""
    from memory_main import get_db as _get_db
    return _get_db()


def api_response(
    success: bool = True,
    data=None,
    error: str = None,
    message: str = None
):
    """统一API响应格式"""
    return {
        "success": success,
        "data": data,
        "error": error,
        "message": message
    }


def memory_tier(action: str = "view", tier: str = "ALL") -> dict:
    """
    查看或管理层级状态（4-Tier架构）
    
    层级说明:
    - HOT: 重要性 > 0.9, SESSION-STATE.md
    - WARM: 重要性 > 0.7, LanceDB
    - COLD: 重要性 > 0.5, MEMORY.md + Git
    - ARCHIVED: 重要性 <= 0.5, 可遗忘
    """
    from memory_tier import tier_manager
    from memory_session import session_state
    from memory_tier_manager import (
        get_tier_manager, TIER_HOT, TIER_WARM, TIER_COLD, TIER_ARCHIVED,
        get_tier, move_tier, get_tier_stats
    )
    from memory_config import CONFIG

    if action == "stats":
        # 返回新旧两种统计
        return {
            "legacy": tier_manager.stats(),
            "v2": get_tier_stats()
        }

    if action == "auto_tier":
        # 使用新的 reTier 功能
        mgr = get_tier_manager()
        if mgr.should_reTier():
            return mgr.reTier_all()
        else:
            return {"success": True, "message": "reTier未到期，跳过", "next_check": "1小时后"}

    if action == "rebalance":
        # 重新平衡所有记忆的层级
        mgr = get_tier_manager()
        return mgr.reTier_all()

    if action == "auto_archive":
        # 自动归档低价值记忆
        mgr = get_tier_manager()
        return mgr.auto_archive_low_value()

    # view action
    if tier == "HOT":
        summary = session_state.get_summary()
        return {
            "tier": "HOT",
            "summary": summary or "无活动会话",
            "file": str(session_state.file_path),
            "last_updated": session_state.data.get("last_updated", "never"),
            "threshold": "> 0.9",
            "location": "SESSION-STATE.md (RAM)"
        }
    elif tier == "WARM":
        db = get_db()
        stats = db.stats()
        return {
            "tier": "WARM",
            "stats": stats,
            "location": CONFIG.get("db_path"),
            "threshold": "> 0.7"
        }
    elif tier == "COLD":
        cold_memories = tier_manager.get_cold_memories(limit=20)
        return {
            "tier": "COLD",
            "recent_count": len(cold_memories),
            "memories": cold_memories,
            "location": str(tier_manager.cold_dir),
            "threshold": "> 0.5"
        }
    elif tier == "ARCHIVED":
        mgr = get_tier_manager()
        stats = mgr.get_tier_stats()
        return {
            "tier": "ARCHIVED",
            "count": stats.get("ARCHIVED", {}).get("count", 0),
            "location": str(mgr.archive_dir),
            "threshold": "<= 0.5",
            "message": "低价值记忆，可彻底删除"
        }
    else:
        # ALL - 返回完整统计
        return get_tier_stats()


def memory_tier_get(memory_id: str) -> dict:
    """
    【P2新增】获取记忆所在层级
    
    Args:
        memory_id: 记忆ID
        
    Returns:
        {
            "memory_id": str,
            "tier": str,
            "found": bool,
            "memory": dict,
            "location": str
        }
    """
    try:
        from memory_tier_manager import get_tier as v2_get_tier
        return v2_get_tier(memory_id)
    except Exception as e:
        return api_response(success=False, error=str(e))


def memory_tier_move(memory_id: str, tier: str, force: bool = False) -> dict:
    """
    【P2新增】移动记忆到指定层级
    
    Args:
        memory_id: 记忆ID
        tier: 目标层级 (HOT|WARM|COLD|ARCHIVED)
        force: 是否强制移动（忽略重要性检查）
        
    Returns:
        移动结果
    """
    try:
        from memory_tier_manager import move_tier as v2_move_tier
        result = v2_move_tier(memory_id, tier, force)
        return api_response(
            success=result.get("success", False),
            data=result,
            message=result.get("message"),
            error=None if result.get("success") else result.get("message")
        )
    except Exception as e:
        return api_response(success=False, error=str(e))


def memory_tier_stats_v2() -> dict:
    """
    【P2新增】获取各层级统计（新版4-Tier统计）
    
    Returns:
        {
            "HOT": {...},
            "WARM": {...},
            "COLD": {...},
            "ARCHIVED": {...},
            "total": int,
            "summary": str,
            "thresholds": {...},
            "ttl": {...}
        }
    """
    try:
        from memory_tier_manager import get_tier_stats as v2_stats
        return api_response(success=True, data=v2_stats())
    except Exception as e:
        return api_response(success=False, error=str(e))


def memory_stats() -> dict:
    """
    获取记忆统计【P0修复】统一响应格式
    """
    try:
        from memory_tier import tier_manager
        from memory_session import session_state
        from memory_config import CONFIG

        db = get_db()
        warm_stats = db.stats()
        cold_memories = tier_manager.get_cold_memories(limit=1000)

        data = {
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
        return api_response(success=True, data=data)
    except Exception as e:
        return api_response(success=False, error=str(e))


# memory_health is already in api/health.py
from api.health import memory_health


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


def memory_temporal_extract(text: str, reference_date: str = None) -> dict:
    """
    【P2新增】时序信息提取 - 从文本中提取时间信息
    
    支持:
    - 相对时间: "昨天"、"上周"、"上个月"、"明年"
    - 绝对时间: "2024年1月15日"、"周一"
    
    Args:
        text: 要分析的文本
        reference_date: 参考时间 ISO 格式（默认当前时间）
        
    Returns:
        时间信息列表
    """
    from temporal_extract import extract_temporal, temporal_to_timestamp
    
    ref = None
    if reference_date:
        try:
            from dateutil import parser
            ref = parser.parse(reference_date)
        except Exception:
            try:
                ref = datetime.fromisoformat(reference_date.replace('Z', '+00:00'))
            except Exception:
                return api_response(success=False, error=f"无法解析参考时间: {reference_date}")
    
    results = extract_temporal(text, reference_date=ref)
    
    # 转换为可存储格式
    for r in results:
        r["_storage"] = temporal_to_timestamp(r)
    
    return api_response(success=True, data={
        "text": text,
        "count": len(results),
        "temporal_info": results
    })


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


# Import memory_kg functions that are used here
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
