"""
两阶段去重模块

阶段1：向量相似度预过滤（≥0.7阈值）
阶段2：LLM语义决策（CREATE/MERGE/SKIP）

参考 memory-lancedb-pro 的 smart-extractor 两阶段去重设计
"""
import hashlib
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


_logger = logging.getLogger(__name__)


class DedupDecision(Enum):
    """去重决策"""
    CREATE = "CREATE"      # 创建新记忆
    MERGE = "MERGE"       # 合并到已有记忆
    SKIP = "SKIP"        # 跳过（完全重复）


@dataclass
class DedupResult:
    """去重结果"""
    decision: DedupDecision
    matched_memory_id: Optional[str] = None
    confidence: float = 0.0
    reason: str = ""


class TwoStageDedup:
    """
    两阶段去重器
    
    阶段1：向量相似度预过滤
    - 计算新内容与已有记忆的向量相似度
    - 相似度≥0.7的进入阶段2
    - 相似度<0.7的直接CREATE
    
    阶段2：LLM语义决策
    - 对于相似度≥0.7的候选，进行语义分析
    - 判断：CREATE / MERGE / SKIP
    """
    
    def __init__(self,
                 similarity_threshold: float = 0.7,
                 merge_threshold: float = 0.85,
                 use_llm: bool = True):
        """
        Args:
            similarity_threshold: 阶段1阈值，超过此值进入阶段2
            merge_threshold: 阶段2合并阈值，≥此值建议MERGE
            use_llm: 是否使用LLM进行阶段2决策（否则用规则）
        """
        self.similarity_threshold = similarity_threshold
        self.merge_threshold = merge_threshold
        self.use_llm = use_llm
        
        # 已有记忆存储（内存）
        self._memories: List[Dict] = []
        
        # 嵌入器
        self._embedder = None
    
    def set_embedder(self, embedder):
        """设置嵌入器（需要实现 embed(text) -> List[float] 方法）"""
        self._embedder = embedder
    
    def add_memory(self, memory: Dict) -> None:
        """
        添加已有记忆（用于后续去重判断）
        
        Args:
            memory: 记忆字典，需包含 id 和 content
        """
        self._memories.append(memory)
    
    def load_memories(self, memories: List[Dict]) -> None:
        """批量加载记忆"""
        self._memories = list(memories)
    
    def check(self, content: str, category: str = None) -> DedupResult:
        """
        检查内容是否应该去重
        
        Args:
            content: 新内容
            category: 可选，记忆类别（用于类别感知合并）
            
        Returns:
            DedupResult：去重决策
        """
        if not content:
            return DedupResult(
                decision=DedupDecision.SKIP,
                reason="空内容"
            )
        
        # 阶段1：向量相似度预过滤
        similar_memories = self._find_similar_memories(content)
        
        if not similar_memories:
            # 没有相似记忆，直接CREATE
            return DedupResult(
                decision=DedupDecision.CREATE,
                confidence=1.0,
                reason="无相似记忆，创建新记忆"
            )
        
        # 阶段2：LLM语义决策
        best_match = similar_memories[0]
        best_similarity = best_match.get("_similarity", 0.0)
        
        if self.use_llm:
            return self._llm_decision(content, best_match, best_similarity, category)
        else:
            return self._rule_decision(content, best_match, best_similarity, category)
    
    def _find_similar_memories(self, content: str) -> List[Dict]:
        """
        阶段1：向量相似度预过滤
        
        Returns:
            按相似度降序排列的相似记忆列表
        """
        if not self._embedder or not self._memories:
            return []
        
        try:
            # 计算新内容的向量
            new_embedding = self._embedder.embed(content)
            
            results = []
            for mem in self._memories:
                mem_content = mem.get("content", "")
                if not mem_content:
                    continue
                
                try:
                    # 计算相似度
                    mem_embedding = self._embedder.embed(mem_content)
                    similarity = self._cosine_similarity(new_embedding, mem_embedding)
                    
                    if similarity >= self.similarity_threshold:
                        results.append({
                            **mem,
                            "_similarity": similarity
                        })
                except:
                    continue
            
            # 按相似度降序排列
            results.sort(key=lambda x: x.get("_similarity", 0), reverse=True)
            return results
            
        except Exception as e:
            _logger.error(f"向量相似度计算失败: {e}")
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def _llm_decision(self, 
                      content: str, 
                      best_match: Dict, 
                      similarity: float,
                      category: str = None) -> DedupResult:
        """
        阶段2：LLM语义决策
        
        决策逻辑：
        - similarity ≥ merge_threshold (0.85): 建议MERGE
        - 0.7 ≤ similarity < 0.85: 需要语义判断
          - 内容相似但意图不同 → CREATE
          - 内容重复 → SKIP
        """
        matched_content = best_match.get("content", "")
        
        # 简单规则判断（实际应该用LLM）
        # 这里用启发式规则模拟LLM决策
        
        # 计算文本重叠度
        overlap = self._text_overlap(content, matched_content)
        
        # 如果高度重叠（>80%相同词）
        if overlap > 0.8:
            # 内容几乎相同 → SKIP
            return DedupResult(
                decision=DedupDecision.SKIP,
                matched_memory_id=best_match.get("id"),
                confidence=similarity,
                reason=f"内容高度重复（重叠率{overlap:.0%}），跳过"
            )
        
        # 如果是profile类别，始终MERGE
        if category == "profile":
            return DedupResult(
                decision=DedupDecision.MERGE,
                matched_memory_id=best_match.get("id"),
                confidence=similarity,
                reason="profile类别始终合并"
            )
        
        # 如果是events/cases类别，倾向于追加（CREATE）
        if category in ["events", "cases"]:
            return DedupResult(
                decision=DedupDecision.CREATE,
                matched_memory_id=best_match.get("id"),
                confidence=similarity,
                reason=f"{category}类别倾向于追加而非合并"
            )
        
        # 默认逻辑：相似度高但不完全重复 → MERGE
        if similarity >= self.merge_threshold:
            return DedupResult(
                decision=DedupDecision.MERGE,
                matched_memory_id=best_match.get("id"),
                confidence=similarity,
                reason=f"语义高度相似（{similarity:.2f}），建议合并"
            )
        
        # 相似但意图可能不同 → CREATE
        return DedupResult(
            decision=DedupDecision.CREATE,
            matched_memory_id=best_match.get("id"),
            confidence=similarity,
            reason=f"语义相似（{similarity:.2f}）但意图可能不同，创建新记忆"
        )
    
    def _rule_decision(self,
                       content: str,
                       best_match: Dict,
                       similarity: float,
                       category: str = None) -> DedupResult:
        """
        阶段2：基于规则的决策（当LLM不可用时）
        """
        overlap = self._text_overlap(content, best_match.get("content", ""))
        
        if overlap > 0.9:
            return DedupResult(
                decision=DedupDecision.SKIP,
                matched_memory_id=best_match.get("id"),
                confidence=similarity,
                reason="内容几乎完全相同"
            )
        
        if overlap > 0.7:
            return DedupResult(
                decision=DedupDecision.MERGE,
                matched_memory_id=best_match.get("id"),
                confidence=similarity,
                reason="内容高度相似，合并"
            )
        
        return DedupResult(
            decision=DedupDecision.CREATE,
            matched_memory_id=best_match.get("id"),
            confidence=similarity,
            reason="存在一定相似但可共存"
        )
    
    def _text_overlap(self, text1: str, text2: str) -> float:
        """计算两个文本的词重叠度"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def get_stats(self) -> Dict:
        """获取去重统计"""
        return {
            "total_memories": len(self._memories),
            "similarity_threshold": self.similarity_threshold,
            "merge_threshold": self.merge_threshold,
            "use_llm": self.use_llm
        }


# 全局单例
_two_stage_dedup = None


def get_two_stage_dedup() -> TwoStageDedup:
    """获取两阶段去重器单例"""
    global _two_stage_dedup
    if _two_stage_dedup is None:
        _two_stage_dedup = TwoStageDedup()
    return _two_stage_dedup


def check_dedup(content: str, category: str = None) -> DedupResult:
    """快捷函数：检查去重决策"""
    return get_two_stage_dedup().check(content, category)
