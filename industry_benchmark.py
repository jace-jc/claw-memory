"""
Claw Memory 行业对标评测套件
对标Zep/Claude/Letta进行标准化评测

评测维度:
1. 检索质量 (对标Zep)
2. 上下文理解 (对标Claude)
3. 多跳推理 (对标Letta)

行业标准:
- Zep: MRR > 0.8, Recall@5 > 0.85
- Claude: 意图准确率 > 90%, 实体完整率 > 85%
- Letta: 单跳 > 90%, 两跳 > 75%, 三跳 > 60%
"""
from typing import List, Dict, Tuple
from dataclasses import dataclass
import json


@dataclass
class IndustryBenchmark:
    """行业对标基准"""
    name: str
    metric: str
    target: float
    weight: float  # 在综合评分中的权重


@dataclass
class BenchmarkResult:
    """单项评测结果"""
    benchmark: IndustryBenchmark
    actual: float
    status: str  # pass/fail
    gap: float  # 与目标的差距


@dataclass
class ComparativeAnalysis:
    """对比分析结果"""
    claw_score: float
    industry_leader: str
    leader_score: float
    gap: float
    analysis: str


# 行业基准定义
ZEP_BENCHMARKS = [
    IndustryBenchmark("Zep", "MRR@10", 0.80, 0.4),
    IndustryBenchmark("Zep", "Recall@5", 0.85, 0.3),
    IndustryBenchmark("Zep", "Latency(ms)", 100.0, 0.2),
    IndustryBenchmark("Zep", "Recall@10", 0.90, 0.1),
]

CLAUDE_BENCHMARKS = [
    IndustryBenchmark("Claude", "Intent Accuracy", 0.90, 0.35),
    IndustryBenchmark("Claude", "Entity Completeness", 0.85, 0.30),
    IndustryBenchmark("Claude", "Coreference Resolution", 0.80, 0.20),
    IndustryBenchmark("Claude", "Context Window", 200000, 0.15),  # tokens
]

LETTA_BENCHMARKS = [
    IndustryBenchmark("Letta", "Single-hop Accuracy", 0.90, 0.40),
    IndustryBenchmark("Letta", "Two-hop Accuracy", 0.75, 0.30),
    IndustryBenchmark("Letta", "Three-hop Accuracy", 0.60, 0.20),
    IndustryBenchmark("Letta", "Relation Extraction", 0.80, 0.10),
]


class IndustryComparator:
    """
    行业对比分析器
    
    将Claw Memory与行业标杆进行对比
    """
    
    def __init__(self):
        self.zep_benchmarks = ZEP_BENCHMARKS
        self.claude_benchmarks = CLAUDE_BENCHMARKS
        self.letta_benchmarks = LETTA_BENCHMARKS
    
    def evaluate_zep_comparison(self, metrics: Dict[str, float]) -> ComparativeAnalysis:
        """
        对比Zep的检索质量
        
        Args:
            metrics: 包含 MRR, Recall@5, Latency 等指标
        """
        claw_mrr = metrics.get("mrr", 0)
        zep_mrr = 0.80
        
        gap = claw_mrr - zep_mrr
        
        if gap >= 0:
            analysis = f"Claw Memory检索质量已超越Zep (MRR: {claw_mrr:.3f} vs {zep_mrr:.3f})"
        elif gap >= -0.1:
            analysis = f"Claw Memory接近Zep水平 (差距: {abs(gap):.3f})，建议优化向量模型"
        else:
            analysis = f"Claw Memory与Zep有显著差距 (差距: {abs(gap):.3f})，需要重大改进"
        
        return ComparativeAnalysis(
            claw_score=claw_mrr,
            industry_leader="Zep",
            leader_score=zep_mrr,
            gap=gap,
            analysis=analysis
        )
    
    def evaluate_claude_comparison(self, metrics: Dict[str, float]) -> ComparativeAnalysis:
        """
        对比Claude的上下文理解
        
        Args:
            metrics: 包含 Intent Accuracy, Entity Completeness 等指标
        """
        intent_score = metrics.get("intent_accuracy", 0)
        claude_intent = 0.90
        
        gap = intent_score - claude_intent
        
        if gap >= 0:
            analysis = f"Claw Memory上下文理解已超越Claude (准确率: {intent_score:.3f})"
        elif gap >= -0.1:
            analysis = f"接近Claude水平 (差距: {abs(gap):.3f})"
        else:
            analysis = f"与Claude有差距 (差距: {abs(gap):.3f})，需要改进意图分类"
        
        return ComparativeAnalysis(
            claw_score=intent_score,
            industry_leader="Claude",
            leader_score=claude_intent,
            gap=gap,
            analysis=analysis
        )
    
    def evaluate_letta_comparison(self, metrics: Dict[str, float]) -> ComparativeAnalysis:
        """
        对比Letta的多跳推理
        
        Args:
            metrics: 包含 Single-hop, Two-hop, Three-hop Accuracy
        """
        two_hop = metrics.get("two_hop_accuracy", 0)
        letta_two_hop = 0.75
        
        gap = two_hop - letta_two_hop
        
        if gap >= 0:
            analysis = f"Claw Memory多跳推理已超越Letta (两跳准确率: {two_hop:.3f})"
        elif gap >= -0.15:
            analysis = f"接近Letta水平 (差距: {abs(gap):.3f})"
        else:
            analysis = f"与Letta有差距 (差距: {abs(gap):.3f})，需要增强传递推理"
        
        return ComparativeAnalysis(
            claw_score=two_hop,
            industry_leader="Letta",
            leader_score=letta_two_hop,
            gap=gap,
            analysis=analysis
        )
    
    def generate_comparative_report(
        self,
        retrieval_metrics: Dict,
        context_metrics: Dict,
        reasoning_metrics: Dict
    ) -> str:
        """
        生成行业对比报告
        """
        zep_result = self.evaluate_zep_comparison(retrieval_metrics)
        claude_result = self.evaluate_claude_comparison(context_metrics)
        letta_result = self.evaluate_letta_comparison(reasoning_metrics)
        
        # 计算综合评分
        overall = (
            zep_result.claw_score * 0.35 +
            claude_result.claw_score * 0.35 +
            letta_result.claw_score * 0.30
        )
        
        lines = [
            "=" * 70,
            "🏆 Claw Memory 行业对比分析报告",
            "=" * 70,
            "",
            f"📊 综合评分: {overall:.3f}",
            "",
            "-" * 70,
            "1️⃣  检索质量对比 (对标Zep)",
            "-" * 70,
            f"   行业领袖: Zep (MRR@10 = {zep_result.leader_score:.3f})",
            f"   Claw Memory: {zep_result.claw_score:.3f}",
            f"   差距: {zep_result.gap:+.3f}",
            f"   分析: {zep_result.analysis}",
            "",
            "-" * 70,
            "2️⃣  上下文理解对比 (对标Claude)",
            "-" * 70,
            f"   行业领袖: Claude (意图准确率 = {claude_result.leader_score:.3f})",
            f"   Claw Memory: {claude_result.claw_score:.3f}",
            f"   差距: {claude_result.gap:+.3f}",
            f"   分析: {claude_result.analysis}",
            "",
            "-" * 70,
            "3️⃣  多跳推理对比 (对标Letta)",
            "-" * 70,
            f"   行业领袖: Letta (两跳准确率 = {letta_result.leader_score:.3f})",
            f"   Claw Memory: {letta_result.claw_score:.3f}",
            f"   差距: {letta_result.gap:+.3f}",
            f"   分析: {letta_result.analysis}",
            "",
            "=" * 70,
        ]
        
        return "\n".join(lines)


# 便捷函数
def compare_with_industry(
    retrieval_metrics: Dict,
    context_metrics: Dict,
    reasoning_metrics: Dict
) -> str:
    """生成行业对比报告的便捷函数"""
    comparator = IndustryComparator()
    return comparator.generate_comparative_report(
        retrieval_metrics,
        context_metrics,
        reasoning_metrics
    )
