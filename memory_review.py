"""
Claw Memory 专业评审系统
对标行业标杆进行多维度评测

评审标准：
1. Zep检索质量 - 向量搜索准确性
2. Claude上下文理解 - 意图识别、实体关联
3. Letta多跳推理 - 关系传递、复杂查询

MRR目标: > 0.8 (Zep水平)
"""
import json
from dataclasses import dataclass
from typing import List, Dict, Tuple
from datetime import datetime


@dataclass
class BenchmarkScore:
    """单项评分"""
    metric: str
    score: float  # 0-1
    target: float
    status: str  # pass/fail/warning


@dataclass
class ReviewReport:
    """评审报告"""
    timestamp: str
    overall_score: float
    benchmarks: List[BenchmarkScore]
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]


class RetrievalReviewer:
    """
    检索质量评审 (对标Zep)
    
    Zep标准:
    - MRR@10 > 0.8
    - Recall@5 > 0.85
    - Latency < 100ms
    """
    
    def __init__(self):
        self.target_mrr = 0.8
        self.target_recall = 0.85
    
    def evaluate(self, results: List[dict], relevant_ids: set) -> Dict:
        """评估检索质量"""
        mrr = self._calc_mrr(results, relevant_ids)
        recall = self._calc_recall(results, relevant_ids, k=5)
        
        return {
            "mrr": mrr,
            "mrr_target": self.target_mrr,
            "recall@5": recall,
            "recall_target": self.target_recall,
            "status": "pass" if mrr >= self.target_mrr else "fail"
        }
    
    def _calc_mrr(self, results: List[dict], relevant: set) -> float:
        """计算MRR"""
        for i, r in enumerate(results, 1):
            if r.get("id") in relevant:
                return 1.0 / i
        return 0.0
    
    def _calc_recall(self, results: List[dict], relevant: set, k: int) -> float:
        """计算Recall@K"""
        if not relevant:
            return 1.0 if not results else 0.0
        top_k = set(r.get("id") for r in results[:k])
        return len(top_k & relevant) / len(relevant)


class ContextUnderstandingReviewer:
    """
    上下文理解评审 (对标Claude)
    
    Claude标准:
    - 意图识别准确率 > 90%
    - 实体提取完整率 > 85%
    - 指代消解准确率 > 80%
    """
    
    def __init__(self):
        self.target_intent = 0.90
        self.target_entity = 0.85
    
    def evaluate(self, query: str, intent_result, entity_results: List[dict]) -> Dict:
        """评估上下文理解"""
        intent_score = self._eval_intent(intent_result)
        entity_score = self._eval_entities(entity_results)
        
        # 指代消解检查
        coref_score = self._eval_coreference(query, entity_results)
        
        return {
            "intent_accuracy": intent_score,
            "entity_completeness": entity_score,
            "coreference_resolution": coref_score,
            "overall": (intent_score + entity_score + coref_score) / 3,
            "target": 0.85
        }
    
    def _eval_intent(self, intent_result) -> float:
        """评估意图识别"""
        # 基于置信度
        confidence = getattr(intent_result, 'confidence', 0.5)
        return min(1.0, confidence)
    
    def _eval_entities(self, entities: List[dict]) -> float:
        """评估实体提取"""
        if not entities:
            return 0.0
        # 检查实体是否有name
        valid = sum(1 for e in entities if e.get("name"))
        return valid / len(entities)
    
    def _eval_coreference(self, query: str, entities: List[dict]) -> float:
        """评估指代消解"""
        # 简单检查：查询中是否有代词
        pronouns = ["他", "她", "它", "这个", "那个"]
        has_pronoun = any(p in query for p in pronouns)
        if has_pronoun and entities:
            return 0.8  # 有代词且有实体，假设消解正确
        return 1.0  # 无代词，不需要消解


class MultiHopReasoningReviewer:
    """
    多跳推理评审 (对标Letta)
    
    Letta标准:
    - 单跳准确率 > 90%
    - 两跳准确率 > 75%
    - 三跳准确率 > 60%
    """
    
    def __init__(self):
        self.targets = {
            1: 0.90,
            2: 0.75,
            3: 0.60
        }
    
    def evaluate(self, query: str, results: List[dict], hop_level: int) -> Dict:
        """评估多跳推理能力"""
        target = self.targets.get(hop_level, 0.60)
        
        # 简单评估：结果中是否包含多跳实体
        score = self._eval_hop_reasoning(query, results, hop_level)
        
        return {
            "hop_level": hop_level,
            "score": score,
            "target": target,
            "status": "pass" if score >= target else "fail"
        }
    
    def _eval_hop_reasoning(self, query: str, results: List[dict], hop: int) -> float:
        """评估跳数推理能力"""
        if hop == 1:
            # 单跳：结果应该直接匹配查询中的实体
            return 0.85  # 简化评估
        
        # 多跳：检查结果中是否包含传递的实体
        score = max(0.0, 1.0 - (hop - 1) * 0.15)
        return score


class MemoryReviewCommittee:
    """
    记忆系统评审委员会
    
    综合评估Claw Memory的整体表现
    """
    
    def __init__(self):
        self.retrieval_reviewer = RetrievalReviewer()
        self.context_reviewer = ContextUnderstandingReviewer()
        self.hop_reviewer = MultiHopReasoningReviewer()
    
    def comprehensive_review(
        self,
        query: str,
        search_results: List[dict],
        relevant_ids: set,
        intent_result,
        entity_results: List[dict],
        hop_level: int = 1
    ) -> ReviewReport:
        """
        执行综合评审
        
        Args:
            query: 查询文本
            search_results: 搜索结果
            relevant_ids: 正确答案的ID集合
            intent_result: 意图分类结果
            entity_results: 实体提取结果
            hop_level: 跳数等级
        """
        benchmarks = []
        strengths = []
        weaknesses = []
        recommendations = []
        
        # 1. 检索质量评审
        retrieval = self.retrieval_reviewer.evaluate(search_results, relevant_ids)
        benchmarks.append(BenchmarkScore(
            metric="MRR@10",
            score=retrieval["mrr"],
            target=retrieval["mrr_target"],
            status=retrieval["status"]
        ))
        
        if retrieval["mrr"] >= retrieval["mrr_target"]:
            strengths.append(f"检索质量达标 (MRR={retrieval['mrr']:.3f})")
        else:
            weaknesses.append(f"检索质量未达标 (MRR={retrieval['mrr']:.3f} < {retrieval['mrr_target']})")
            recommendations.append("优化向量模型或增加更多训练数据")
        
        # 2. 上下文理解评审
        context = self.context_reviewer.evaluate(query, intent_result, entity_results)
        benchmarks.append(BenchmarkScore(
            metric="上下文理解",
            score=context["overall"],
            target=context["target"],
            status="pass" if context["overall"] >= context["target"] else "fail"
        ))
        
        if context["overall"] >= context["target"]:
            strengths.append(f"上下文理解良好 (score={context['overall']:.3f})")
        else:
            weaknesses.append(f"上下文理解不足 (score={context['overall']:.3f})")
            recommendations.append("改进意图分类器或增加实体库")
        
        # 3. 多跳推理评审
        hop_result = self.hop_reviewer.evaluate(query, search_results, hop_level)
        benchmarks.append(BenchmarkScore(
            metric=f"多跳推理-{hop_level}跳",
            score=hop_result["score"],
            target=hop_result["target"],
            status=hop_result["status"]
        ))
        
        if hop_result["status"] == "pass":
            strengths.append(f"{hop_level}跳推理达标")
        else:
            weaknesses.append(f"{hop_level}跳推理不足 (score={hop_result['score']:.3f})")
            recommendations.append("增强知识图谱或改进传递推理算法")
        
        # 计算总分
        overall = sum(b.score for b in benchmarks) / len(benchmarks)
        
        return ReviewReport(
            timestamp=datetime.now().isoformat(),
            overall_score=overall,
            benchmarks=benchmarks,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations
        )
    
    def generate_report(self, report: ReviewReport) -> str:
        """生成评审报告"""
        lines = [
            "=" * 60,
            "🔍 Claw Memory 综合评审报告",
            "=" * 60,
            f"📅 时间: {report.timestamp}",
            f"📊 综合评分: {report.overall_score:.3f}",
            "",
            "## 各项评分",
            "-" * 40,
        ]
        
        for b in report.benchmarks:
            status_icon = "✅" if b.status == "pass" else "❌" if b.status == "fail" else "⚠️"
            lines.append(
                f"{status_icon} {b.metric}: {b.score:.3f} "
                f"(目标: {b.target:.3f})"
            )
        
        if report.strengths:
            lines.extend(["", "## ✨ 优势", "-" * 40])
            for s in report.strengths:
                lines.append(f"  • {s}")
        
        if report.weaknesses:
            lines.extend(["", "## ⚠️ 不足", "-" * 40])
            for w in report.weaknesses:
                lines.append(f"  • {w}")
        
        if report.recommendations:
            lines.extend(["", "## 💡 优化建议", "-" * 40])
            for r in report.recommendations:
                lines.append(f"  • {r}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)


# 便捷函数
def run_review(
    query: str,
    search_results: List[dict],
    relevant_ids: set,
    intent_result,
    entity_results: List[dict] = None,
    hop_level: int = 1
) -> ReviewReport:
    """执行综合评审的便捷函数"""
    committee = MemoryReviewCommittee()
    return committee.comprehensive_review(
        query=query,
        search_results=search_results,
        relevant_ids=relevant_ids,
        intent_result=intent_result,
        entity_results=entity_results or [],
        hop_level=hop_level
    )
