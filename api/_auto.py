"""
API: Auto functions - memory_auto_extract, auto_capture, auto_recall, 
memory_batch, memory_extract_session, memory_transaction_stats
Phase 3: Split from memory_main.py
"""
import warnings
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

from typing import Optional, Any, Dict, List


def get_db():
    """Lazy import to avoid circular dependency"""
    from core._db import get_db as _get_core_db
    return _get_core_db()


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


def memory_batch(operations: list, use_transaction: bool = True) -> dict:
    """
    【P1新增】批量操作API（支持事务）
    
    Args:
        operations: 操作列表
        use_transaction: 是否使用事务（默认True，失败自动回滚）
    """
    try:
        from infra.transaction import with_transaction
        
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
        from infra.transaction import TransactionLog
        log = TransactionLog()
        stats = log.get_stats()
        return api_response(success=True, data=stats)
    except Exception as e:
        return api_response(success=False, error=str(e))


def memory_extract_session(messages: list) -> dict:
    """
    从会话消息中抽取记忆
    """
    from extract.memory_extract import extract_from_messages
    from memory_main import memory_store
    
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


def memory_auto_extract(text: str = "", messages: list = None) -> dict:
    """
    【新增】自动从对话中提取事实、偏好、决策、目标、教训
    
    模仿 Mem0 的自动提取功能，但完全本地运行
    
    Args:
        text: 要分析的文本（直接传入文本）
        messages: 消息列表（替代text，包含role和content字段）
    
    Returns:
        提取的事实列表，包含类型、内容、实体、置信度
    """
    from extract.auto_extract import get_auto_extractor
    
    extractor = get_auto_extractor()
    
    if messages:
        # 从消息列表提取
        facts = extractor.extract_from_messages(messages)
    elif text:
        # 从文本提取
        facts = extractor.extract_from_text(text)
    else:
        return api_response(success=False, error="必须提供text或messages")
    
    # 转换为字典格式
    result = [
        {
            "type": f.type,
            "content": f.content,
            "entities": f.entities,
            "confidence": f.confidence,
            "timestamp": f.timestamp,
        }
        for f in facts
    ]
    
    return api_response(
        success=True,
        data={
            "extracted": len(result),
            "facts": result,
            "stats": extractor.get_stats(),
        }
    )


# ==================== 自动钩子 ====================

def auto_capture(message: dict) -> list:
    """
    自动捕获 - 从单条消息中快速抽取并存储
    返回已存储的记忆数量
    """
    from extract.memory_extract import is_noise, quick_extract
    from memory_main import memory_store
    
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
    from core.memory_config import CONFIG
    from memory_main import memory_recall
    
    if similarity_threshold is None:
        similarity_threshold = CONFIG.get("similarity_threshold", 0.3)
    
    result = memory_recall(query, auto_inject=True, similarity_threshold=similarity_threshold)
    if result["count"] > 0:
        return result["recall_text"]
    return ""
