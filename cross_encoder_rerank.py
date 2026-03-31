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
