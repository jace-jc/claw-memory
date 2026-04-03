"""
MMR (Maximal Marginal Relevance) 多样性算法

防止相似结果在排序中主导，参考 memory-lancedb-pro 的实现

当余弦相似度 > threshold 时降权，避免重复结果主导
"""
import numpy as np
from typing import List, Dict, Tuple


class MMRreranker:
    """
    MMR多样性重排器
    
    原理：
    - 标准重排只考虑与query的相关性
    - MMR同时考虑：相关性 + 多样性
    - 选择那些既相关又与已选结果不同的结果
    
    公式：
    MMR = λ * sim(query, doc) - (1-λ) * max(sim(selected_doc, doc))
    
    其中 λ 是相关性与多样性的平衡参数（0-1）
    """
    
    def __init__(self, 
                 lambda_param: float = 0.5,
                 similarity_threshold: float = 0.85,
                 enabled: bool = True):
        """
        Args:
            lambda_param: 相关性权重 (0-1)，1=只考虑相关，0=只考虑多样
            similarity_threshold: 相似度阈值，超过此值降权
            enabled: 是否启用MMR
        """
        self.lambda_param = lambda_param
        self.similarity_threshold = similarity_threshold
        self.enabled = enabled
    
    def rerank(self, 
               query: str, 
               candidates: List[Dict], 
               limit: int = 5,
               get_similarity_fn=None) -> List[Dict]:
        """
        MMR重排
        
        Args:
            query: 查询字符串
            candidates: 候选结果列表，每项包含 content 和可选的 _similarity 字段
            limit: 返回数量
            get_similarity_fn: 可选的相似度计算函数
            
        Returns:
            重排后的结果列表
        """
        if not self.enabled or len(candidates) <= 1:
            return candidates[:limit]
        
        # 计算每个候选与query的相似度
        if get_similarity_fn is None:
            get_similarity_fn = self._default_similarity
        
        # 第一步：计算query与所有候选的相似度
        query_similarities = []
        for i, cand in enumerate(candidates):
            sim = get_similarity_fn(query, cand.get("content", ""))
            query_similarities.append(sim)
            cand["_query_similarity"] = sim
        
        # 第二步：执行MMR选择
        selected = []
        remaining = list(range(len(candidates)))
        
        while remaining and len(selected) < limit:
            best_score = -float("inf")
            best_idx = None
            
            for idx in remaining:
                # 相关性分数
                relevance = query_similarities[idx]
                
                # 多样性分数：与已选结果的最大相似度
                max_similarity_to_selected = 0.0
                for sel_idx in selected:
                    # 计算两个候选之间的相似度
                    sim_to_selected = self._content_similarity(
                        candidates[idx].get("content", ""),
                        candidates[sel_idx].get("content", "")
                    )
                    max_similarity_to_selected = max(max_similarity_to_selected, sim_to_selected)
                
                # MMR公式
                mmr_score = (self.lambda_param * relevance + 
                           (1 - self.lambda_param) * (1 - max_similarity_to_selected))
                
                # 如果与已选结果太相似，降低分数
                if max_similarity_to_selected > self.similarity_threshold:
                    mmr_score *= 0.5  # 降权50%
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            
            if best_idx is not None:
                selected.append(best_idx)
                remaining.remove(best_idx)
        
        # 构建结果
        result = [candidates[i] for i in selected]
        
        # 对未选中的结果也标记多样性分数
        for i, cand in enumerate(candidates):
            if i not in selected:
                cand["_mmr_score"] = None
                cand["_diversity_penalized"] = True
        
        return result
    
    def _default_similarity(self, query: str, content: str) -> float:
        """
        默认相似度计算：基于词重叠
        
        Returns:
            0-1之间的相似度分数
        """
        if not query or not content:
            return 0.0
        
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words or not content_words:
            return 0.0
        
        # Jaccard相似度
        intersection = len(query_words & content_words)
        union = len(query_words | content_words)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _content_similarity(self, content1: str, content2: str) -> float:
        """
        计算两个内容的相似度（用于MMR多样性）
        
        Returns:
            0-1之间的相似度分数
        """
        if not content1 or not content2:
            return 0.0
        
        # 简单的词重叠相似度
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def get_diversity_report(self, candidates: List[Dict]) -> Dict:
        """
        获取多样性报告
        
        Returns:
            多样性统计数据
        """
        if len(candidates) < 2:
            return {"status": "insufficient_data"}
        
        similarities = []
        for i in range(len(candidates)):
            for j in range(i+1, len(candidates)):
                sim = self._content_similarity(
                    candidates[i].get("content", ""),
                    candidates[j].get("content", "")
                )
                similarities.append(sim)
        
        if not similarities:
            return {"status": "no_pairs"}
        
        return {
            "num_candidates": len(candidates),
            "num_pairs": len(similarities),
            "avg_similarity": sum(similarities) / len(similarities),
            "max_similarity": max(similarities),
            "min_similarity": min(similarities),
            "high_similarity_pairs": sum(1 for s in similarities if s > self.similarity_threshold),
            "diversity_score": 1 - (sum(similarities) / len(similarities))  # 越高越多样
        }


# 全局单例
_mmr_reranker = None


def get_mmr_reranker() -> MMRreranker:
    """获取MMR重排器单例"""
    global _mmr_reranker
    if _mmr_reranker is None:
        _mmr_reranker = MMRreranker()
    return _mmr_reranker


def rerank_with_mmr(query: str, 
                    candidates: List[Dict], 
                    limit: int = 5,
                    lambda_param: float = 0.5) -> List[Dict]:
    """
    快捷函数：使用MMR重排
    
    Args:
        query: 查询字符串
        candidates: 候选结果
        limit: 返回数量
        lambda_param: 相关性权重
        
    Returns:
        重排后的结果
    """
    reranker = get_mmr_reranker()
    reranker.lambda_param = lambda_param
    return reranker.rerank(query, candidates, limit)
