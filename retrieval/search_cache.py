"""
搜索缓存模块 - Search Cache
提升频繁查询的响应速度
"""
import hashlib
import time
import json
import logging
from typing import Optional, List, Dict
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)


class SearchCache:
    """
    搜索结果缓存
    
    特性：
    1. LRU淘汰策略
    2. TTL过期
    3. 线程安全
    4. 查询签名
    """
    
    def __init__(self, max_size: int = 500, ttl: int = 3600):
        """
        Args:
            max_size: 最大缓存条目数
            ttl: 过期时间（秒）
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache = OrderedDict()  # key -> (result, timestamp)
        self._lock = Lock()
        self._hits = 0
        self._misses = 0
    
    def _make_key(self, query: str, **kwargs) -> str:
        """生成缓存键"""
        # 组合query和参数
        data = json.dumps({"query": query, "params": kwargs}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def get(self, query: str, **kwargs) -> Optional[List[dict]]:
        """
        获取缓存结果
        
        Args:
            query: 查询字符串
            **kwargs: 其他搜索参数
            
        Returns:
            缓存结果或None
        """
        key = self._make_key(query, **kwargs)
        
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            result, timestamp = self._cache[key]
            
            # 检查TTL
            if time.time() - timestamp > self.ttl:
                del self._cache[key]
                self._misses += 1
                return None
            
            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            self._hits += 1
            return result
    
    def set(self, query: str, result: List[dict], **kwargs):
        """
        设置缓存
        
        Args:
            query: 查询字符串
            result: 搜索结果
            **kwargs: 其他搜索参数
        """
        key = self._make_key(query, **kwargs)
        
        with self._lock:
            # 如果已存在，移到末尾
            if key in self._cache:
                self._cache.move_to_end(key)
            
            # 如果缓存满，淘汰最旧的
            elif len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = (result, time.time())
    
    def invalidate(self, pattern: str = None):
        """
        使缓存失效
        
        Args:
            pattern: 可选，只清除匹配模式的缓存
        """
        with self._lock:
            if pattern is None:
                self._cache.clear()
            else:
                # 清除包含pattern的缓存
                to_remove = [k for k in self._cache.keys() if pattern in k]
                for k in to_remove:
                    del self._cache[k]
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate * 100, 2)
            }
    
    def prune_expired(self):
        """删除所有过期条目"""
        now = time.time()
        with self._lock:
            expired = [
                k for k, (_, ts) in self._cache.items()
                if now - ts > self.ttl
            ]
            for k in expired:
                del self._cache[k]
            return len(expired)
    
    def prefetch(self, queries: list, search_func):
        """
        【P3新增】预取常见查询
        
        Args:
            queries: 查询列表
            search_func: 搜索函数(query, limit) -> [results]
        
        返回:
            成功预取的查询数
        """
        prefetched = 0
        for query in queries:
            key = self._make_key(query, limit=5)  # 默认预取limit=5
            if key not in self._cache:
                try:
                    results = search_func(query, limit=5)
                    self.set(query, results, limit=5)
                    prefetched += 1
                except Exception as e:
                    logger.warning(f"预热缓存失败: {e}")
        return prefetched


# 全局缓存实例
_search_cache = None


def get_search_cache() -> SearchCache:
    """获取搜索缓存实例"""
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchCache(max_size=500, ttl=3600)
    return _search_cache


class EmbeddingCache:
    """
    向量嵌入缓存
    
    缓存频繁使用的文本嵌入结果
    """
    
    def __init__(self, max_size: int = 2000, ttl: int = 7200):
        """
        Args:
            max_size: 最大缓存条目数
            ttl: 过期时间（秒）
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache = OrderedDict()
        self._lock = Lock()
    
    def _make_key(self, text: str) -> str:
        """生成缓存键（使用文本哈希）"""
        return hashlib.sha256(text.encode()).hexdigest()[:24]
    
    def get(self, text: str) -> Optional[List[float]]:
        """获取缓存的嵌入向量"""
        key = self._make_key(text)
        
        with self._lock:
            if key not in self._cache:
                return None
            
            vector, timestamp = self._cache[key]
            
            if time.time() - timestamp > self.ttl:
                del self._cache[key]
                return None
            
            self._cache.move_to_end(key)
            return vector
    
    def set(self, text: str, vector: List[float]):
        """缓存嵌入向量"""
        key = self._make_key(text)
        
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
            
            self._cache[key] = (vector, time.time())
    
    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()


# 全局嵌入缓存
_embedding_cache = None


def get_embedding_cache() -> EmbeddingCache:
    """获取嵌入缓存实例"""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = EmbeddingCache(max_size=2000, ttl=7200)
    return _embedding_cache
