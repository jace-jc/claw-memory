"""
Rerank methods for LanceDBStore
Phase 2: Split from lancedb_store.py
"""
import time

_logger = __import__('logging').getLogger("ClawMemory")


def _rerank_cross_encoder(self, query: str, candidates: list, limit: int) -> list[dict]:
    """
    【P0修复】Cross-Encoder重排
    使用专用模型 ms-marco-MiniLM-L-6-v2 进行相关性排序
    替换原 qwen3.5 LLM方案，延迟从5-15秒降低到<10毫秒
    """
    try:
        from cross_encoder_rerank import get_reranker
        
        reranker = get_reranker()
        
        if not reranker.is_available():
            _logger.info("Cross-Encoder模型不可用，使用原始分数")
            return candidates[:limit]
        
        # 使用专用Cross-Encoder进行批量重排
        start_time = time.time()
        reranked = reranker.rerank(query, candidates, top_k=limit)
        elapsed_ms = (time.time() - start_time) * 1000
        
        _logger.debug(f"Cross-Encoder重排完成，耗时 {elapsed_ms:.1f}ms")
        
        # 计算综合分数 = 向量相似度 * 0.3 + Cross-Encoder * 0.7
        scored = []
        for r in reranked:
            vector_score = 1.0 - r.get("_distance", 0.5)
            cross_score = r.get("cross_score", 0.5)
            final_score = vector_score * 0.3 + cross_score * 0.7
            r["_final_score"] = final_score
            scored.append(r)
        
        # 按最终分数排序
        scored.sort(key=lambda x: x.get("_final_score", 0), reverse=True)
        
        return scored[:limit]
        
    except ImportError:
        _logger.info("Cross-Encoder模块不可用，跳过重排")
        return candidates[:limit]
    except Exception as e:
        _logger.error(f"Cross-Encoder重排失败: {e}")
        return candidates[:limit]
