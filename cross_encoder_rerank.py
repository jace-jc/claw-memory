"""
Cross-Encoder 重排模块 - 使用专用模型进行相关性排序
修复P0问题：替换qwen3.5为专用Cross-Encoder模型

模型: cross-encoder/ms-marco-MiniLM-L-6-v2
- 参数量: 22M (vs qwen3.5的270亿)
- 延迟: <10ms (vs qwen3.5的5-15秒)
- 精度: 专门训练的相关性排序
"""
import time
from typing import List, Dict, Optional


class CrossEncoderReranker:
    """
    专用Cross-Encoder重排器
    
    使用 HuggingFace 的 ms-marco-MiniLM-L-6-v2 模型，
    专为相关性排序任务训练，比大语言模型更快更准。
    """
    
    def __init__(self, model_name_or_path: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        """
        Args:
            model_name_or_path: HuggingFace模型名或本地路径
        """
        self.model_name = model_name_or_path
        self.model = None
        self._lazy_load()
    
    def _lazy_load(self):
        """延迟加载模型，首次使用时初始化"""
        if self.model is None:
            try:
                from sentence_transformers import CrossEncoder
                self.model = CrossEncoder(model_name_or_path=self.model_name)
                print(f"[CrossEncoderReranker] 模型加载成功: {self.model_name}")
            except Exception as e:
                print(f"[CrossEncoderReranker] 模型加载失败: {e}")
                self.model = None
    
    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        对候选记忆进行相关性重排
        
        Args:
            query: 查询字符串
            candidates: 候选记忆列表 [{"id": "...", "content": "...", ...}]
            top_k: 返回前k条
            
        Returns:
            重排后的记忆列表，添加了 cross_score 字段
        """
        if not candidates:
            return []
        
        if self.model is None:
            print("[CrossEncoderReranker] 模型不可用，保留原顺序")
            return candidates[:top_k]
        
        try:
            # 构建 query-document 对
            pairs = [(query, candidate.get("content", "")) for candidate in candidates]
            
            # 批量预测相关性分数
            start_time = time.time()
            scores = self.model.predict(pairs)
            elapsed_ms = (time.time() - start_time) * 1000
            
            print(f"[CrossEncoderReranker] 重排 {len(candidates)} 条，耗时 {elapsed_ms:.1f}ms")
            
            # 添加分数到候选
            for i, candidate in enumerate(candidates):
                candidate["cross_score"] = float(scores[i])
            
            # 按cross_score排序
            reranked = sorted(candidates, key=lambda x: x.get("cross_score", 0), reverse=True)
            
            return reranked[:top_k]
            
        except Exception as e:
            print(f"[CrossEncoderReranker] 重排失败: {e}")
            return candidates[:top_k]
    
    def score_pair(self, query: str, document: str) -> float:
        """
        对单个 query-document 对评分
        
        Args:
            query: 查询
            document: 文档内容
            
        Returns:
            相关性分数 (0-1)
        """
        if self.model is None:
            return 0.5
        
        try:
            score = self.model.predict([(query, document)])[0]
            return float(score)
        except Exception as e:
            print(f"[CrossEncoderReranker] 评分失败: {e}")
            return 0.5
    
    def scores(self, query: str, candidates: List[Dict]) -> List[tuple]:
        """
        对候选记忆批量评分，返回 (doc_id, score) 元组列表
        
        Args:
            query: 查询字符串
            candidates: 候选记忆列表 [{"id": "...", "content": "...", ...}]
            
        Returns:
            [(doc_id, score), ...] 按分数降序排列
        """
        if not candidates:
            return []
        
        if self.model is None:
            # 模型不可用时返回均匀分数
            return [(c.get("id", f"doc_{i}"), 0.5) for i, c in enumerate(candidates)]
        
        try:
            pairs = [(query, c.get("content", "")) for c in candidates]
            scores = self.model.predict(pairs)
            results = [
                (c.get("id", f"doc_{i}"), float(scores[i]))
                for i, c in enumerate(candidates)
            ]
            # 按分数降序
            results.sort(key=lambda x: x[1], reverse=True)
            return results
        except Exception as e:
            print(f"[CrossEncoderReranker] 批量评分失败: {e}")
            return [(c.get("id", f"doc_{i}"), 0.5) for i, c in enumerate(candidates)]
    
    def is_available(self) -> bool:
        """检查模型是否可用"""
        return self.model is not None


# 全局实例
_reranker = None


def get_reranker() -> CrossEncoderReranker:
    """获取全局重排器实例"""
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoderReranker()
    return _reranker


# ============================================================
# P2-1: 独立的 cross_encoder_score() 函数
# ============================================================

def cross_encoder_score(
    query: str,
    candidates: list,
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
) -> list[tuple]:
    """
    对候选文档进行 Cross-Encoder 相关性评分
    
    Args:
        query: 查询字符串
        candidates: 候选文档列表，支持两种格式：
                   - [{"id": "...", "content": "..."}, ...]  (dict格式)
                   - ["文档内容1", "文档内容2", ...]         (字符串格式)
        model_name: HuggingFace Cross-Encoder 模型名
        
    Returns:
        [(doc_id, score), ...] 按分数降序排列
        - doc_id: 来自 candidates[i]["id"]，字符串格式则用 f"doc_0" 编号
        - score:  float, 相关性分数
        
    Example:
        >>> candidates = [
        ...     {"id": "mem_001", "content": "用户住在上海"},
        ...     {"id": "mem_002", "content": "用户喜欢Python"},
        ... ]
        >>> scores = cross_encoder_score("用户住在哪里", candidates)
        >>> print(scores)
        [('mem_001', 0.87), ('mem_002', 0.12)]
    """
    if not candidates:
        return []
    
    # 标准化输入：统一为 [{"id": ..., "content": ...}] 格式
    normalized = []
    for i, c in enumerate(candidates):
        if isinstance(c, dict):
            normalized.append({
                "id": c.get("id", f"doc_{i}"),
                "content": c.get("content", str(c))
            })
        else:
            normalized.append({"id": f"doc_{i}", "content": str(c)})
    
    # 获取重排器
    reranker = get_reranker()
    
    # 如果传入的模型名与默认不同，创建专用实例
    if reranker.model_name != model_name:
        reranker = CrossEncoderReranker(model_name_or_path=model_name)
    
    return reranker.scores(query, normalized)
