"""
多提供者统一 Reranker
支持 Jina / SiliconFlow

由 memory_config_multi.py 驱动，自动适配当前部署方案。
仅在方案A和方案B中激活。
"""
import os
import logging
from typing import Optional, List, Dict, Any

_logger = logging.getLogger("ClawMemory.MultiRerank")

# 全局 reranker 实例
_reranker = None


class MultiReranker:
    """
    统一重排器。
    根据 memory_config_multi.py 的激活方案自动选择提供者。
    当前支持: jina, siliconflow
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            from core.memory_config_multi import get_active_config
            cfg = get_active_config()
            config = cfg.get_reranker_config()
        
        self.enabled = config is not None
        self.provider = config.get("provider") if config else None
        self.model = config.get("model") if config else None
        self.url = config.get("url") if config else None
        self._is_available = None
    
    def is_available(self) -> bool:
        """检查 reranker 是否可用"""
        if not self.enabled:
            return False
        if self._is_available is not None:
            return self._is_available
        
        try:
            # 测试调用
            self.rerank("test", [{"id": "1", "content": "hello world"}], top_k=1)
            self._is_available = True
        except Exception as e:
            _logger.warning(f"[MultiReranker] Health check failed: {e}")
            self._is_available = False
        return self._is_available
    
    def rerank(
        self,
        query: str,
        candidates: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """
        对候选记忆进行重排。
        
        Args:
            query: 查询字符串
            candidates: 候选列表 [{"id": "...", "content": "...", ...}]
            top_k: 返回前k条
        
        Returns:
            重排后的列表，添加了 rerank_score 字段
        """
        if not candidates or not self.enabled:
            return candidates[:top_k]
        
        try:
            if self.provider == "jina":
                return self._rerank_jina(query, candidates, top_k)
            elif self.provider == "siliconflow":
                return self._rerank_siliconflow(query, candidates, top_k)
            else:
                _logger.warning(f"[MultiReranker] Unknown provider: {self.provider}")
                return candidates[:top_k]
        except Exception as e:
            _logger.error(f"[MultiReranker] rerank error ({self.provider}): {e}")
            return candidates[:top_k]
    
    def _rerank_jina(
        self,
        query: str,
        candidates: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """Jina Reranker API"""
        import requests
        api_key = os.environ.get("JINA_API_KEY")
        if not api_key:
            raise ValueError("JINA_API_KEY not set")
        
        docs = [c.get("content", "") for c in candidates]
        resp = requests.post(
            self.url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "query": query,
                "documents": docs
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        
        # 构建 id -> score 映射
        scores = {}
        for item in data.get("results", []):
            idx = item.get("index")
            if idx is not None and idx < len(candidates):
                scores[candidates[idx]["id"]] = item.get("relevance_score", 0)
        
        # 按 rerank_score 降序排列
        reranked = []
        for c in candidates:
            c = dict(c)
            c["rerank_score"] = scores.get(c["id"], 0)
            reranked.append(c)
        
        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]
    
    def _rerank_siliconflow(
        self,
        query: str,
        candidates: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """SiliconFlow Reranker API"""
        import requests
        api_key = os.environ.get("SILICONFLOW_API_KEY")
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY not set")
        
        docs = [c.get("content", "") for c in candidates]
        resp = requests.post(
            self.url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "query": query,
                "documents": docs,
                "top_n": top_k
            },
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        
        # SiliconFlow 返回 {results: [{index, relevance_score}]}
        scores = {}
        for item in data.get("results", []):
            idx = item.get("index")
            if idx is not None and idx < len(candidates):
                scores[candidates[idx]["id"]] = item.get("relevance_score", 0)
        
        reranked = []
        for c in candidates:
            c = dict(c)
            c["rerank_score"] = scores.get(c["id"], 0)
            reranked.append(c)
        
        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]
    
    def __repr__(self):
        if not self.enabled:
            return "MultiReranker(disabled)"
        return f"MultiReranker(provider={self.provider}, model={self.model})"


def get_reranker() -> MultiReranker:
    """获取全局 MultiReranker 单例"""
    global _reranker
    if _reranker is None:
        _reranker = MultiReranker()
    return _reranker
