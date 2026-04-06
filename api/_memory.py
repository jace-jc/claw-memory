"""
API: Memory functions - memory_recall, memory_forget, memory_kg_extract, memory_disambiguate
Phase 3: Split from memory_main.py
"""
import warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")


def get_db():
    """Lazy import to avoid circular dependency"""
    from core._db import get_db as _get_core_db
    return _get_core_db()


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
        return api_response(success=True, data={
            "query": query,
            "count": 0,
            "recall_text": "",
            "results": []
        })

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

    return api_response(success=True, data={
        "query": query,
        "count": len(results),
        "recall_text": recall_text,
        "auto_inject": auto_inject,
        "results": clean_results
    })


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
            return api_response(
                success=False,
                error=f"记忆 {memory_id} 不存在"
            )
    
    success = db.delete(memory_id=memory_id, query=query)
    return api_response(
        success=success,
        message=f"记忆删除{'成功' if success else '失败'}"
    )


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
