"""
Search method for LanceDBStore
Phase 2: Split from lancedb_store.py
"""
import json
import traceback

_logger = __import__('logging').getLogger("ClawMemory")


def search(self, query: str, limit: int = 5, types: list = None, min_score: float = 0.3,
           scope: str = None, use_rerank: bool = False) -> list[dict]:
    """
    语义搜索记忆
    
    Args:
        query: 搜索查询
        limit: 返回数量
        types: 过滤类型列表
        min_score: 最低重要性分数
        scope: 【新增】范围过滤 - global|user|project|agent|session|channel
        use_rerank: 【新增】是否使用Cross-Encoder重排
    """
    if self.table is None:
        return []
    
    # 【v3.1 P0-D新增】自适应检索判断
    try:
        from adaptive_retrieval import should_retrieve, get_retrieval_reason
        if not should_retrieve(query):
            _logger.debug(f"[自适应检索] 跳过: {get_retrieval_reason(query)}")
            return []
    except ImportError:
        pass  # 跳过自适应检查
    
    try:
        # 生成查询向量 - 使用 MultiEmbedder
        from multi_embed import get_embedder
        query_vector = get_embedder().embed(query)
        
        if not query_vector:
            _logger.warning("failed to generate query embedding")
            return []
        
        # 向量搜索 - 多取一些用于重排
        search_limit = limit * 5 if use_rerank else limit * 3
        results = (
            self.table
            .search(query_vector, vector_column_name="vector")
            .limit(search_limit)
            .to_arrow()
            .to_pylist()
        )
        
        # 后处理
        filtered = []
        for r in results:
            if types and r.get("type") not in types:
                continue
            
            # 【新增】Scope过滤
            if scope and r.get("scope") != scope:
                continue
            
            # 检查重要性阈值
            importance = r.get("importance", 0)
            if importance < min_score:
                continue
            
            # 解析 tags
            tags_str = r.get("tags", "[]")
            try:
                r["tags_parsed"] = json.loads(tags_str) if tags_str else []
            except:
                r["tags_parsed"] = []
            
            filtered.append(r)
            
            if len(filtered) >= (limit * 3 if use_rerank else limit):
                break
        
        # 【v3.1 P0-B新增】Weibull衰减加权
        try:
            from weibull_decay import apply_decay_to_search_results
            filtered = apply_decay_to_search_results(filtered)
        except ImportError:
            # 没有衰减引擎，使用原始分数
            for r in filtered:
                r["_weighted_score"] = 1.0 - r.get("_distance", 0.5)
        
        # 【新增】重排：优先 MultiReranker（API方案A/B），回退到 Cross-Encoder（本地方案D）
        if use_rerank and filtered:
            # 优先尝试 API reranker（方案A/B）
            try:
                from multi_rerank import get_reranker
                api_reranker = get_reranker()
                if api_reranker.is_available():
                    _logger.debug(f"[Search] Using API reranker: {api_reranker}")
                    filtered = api_reranker.rerank(query, filtered, top_k=limit)
                else:
                    # 回退到本地 Cross-Encoder
                    filtered = self._rerank_cross_encoder(query, filtered, limit)
            except Exception as e:
                _logger.debug(f"[Search] API reranker unavailable, trying Cross-Encoder: {e}")
                try:
                    filtered = self._rerank_cross_encoder(query, filtered, limit)
                except Exception:
                    pass
        
        # 更新访问追踪（静默失败，不影响主流程）
        for r in filtered:
            try:
                self._update_access_safe(r["id"])
            except Exception:
                pass
        
        return filtered[:limit]
    except Exception as e:
        _logger.error(f"search error: {e}")
        import traceback
        traceback.print_exc()
        return []
