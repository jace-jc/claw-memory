"""
Cache methods for LanceDBStore
Phase 2: Split from lancedb_store.py
"""
_logger = __import__('logging').getLogger("ClawMemory")


def search_cached(self, query: str, limit: int = 5, use_cache: bool = True, **kwargs) -> list:
    """
    【P3新增】带缓存的搜索
    
    Args:
        query: 搜索查询
        limit: 返回数量
        use_cache: 是否使用缓存
        **kwargs: 其他search参数
    """
    if not use_cache:
        return self.search(query, limit=limit, **kwargs)
    
    try:
        from retrieval.search_cache import get_search_cache
        cache = get_search_cache()
        
        # 尝试从缓存获取
        cached = cache.get(query, limit=limit, **kwargs)
        if cached is not None:
            return cached
        
        # 执行搜索
        results = self.search(query, limit=limit, **kwargs)
        
        # 缓存结果
        cache.set(query, results, limit=limit, **kwargs)
        
        return results
    except ImportError:
        # 缓存模块不可用，降级到普通搜索
        return self.search(query, limit=limit, **kwargs)
    except Exception as e:
        _logger.error(f"cache error: {e}")
        return self.search(query, limit=limit, **kwargs)
