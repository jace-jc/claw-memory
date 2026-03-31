"""
Claw Memory 严格专业评审系统
由多Agent专家团队进行深度对标评测

评审团队:
├── 🔬 向量检索专家 (对标Zep)
├── 🧠 上下文理解专家 (对标Claude)
├── 🔄 知识图谱专家 (对标Letta)
└── 📊 评分委员会
"""

from typing import List, Dict, Tuple
from dataclasses import dataclass
import json


@dataclass
class ExpertOpinion:
    """专家意见"""
    expert: str
    area: str
    score: float
    findings: List[str]
    recommendations: List[str]


@dataclass
class FinalVerdict:
    """最终裁决"""
    overall_score: float
    industry_position: str  # leader/competitive/emerging
    gap_analysis: Dict
    prioritized_recommendations: List[Dict]


class VectorRetrievalExpert:
    """
    向量检索专家 - 对标Zep
    
    Zep核心能力分析:
    1. 混合检索 (向量 + BM25 + 关键词)
    2. 实时索引更新
    3. 语义重排序
    4. 多租户隔离
    
    评估维度:
    - 召回率 (Recall)
    - MRR (Mean Reciprocal Rank)
    - Latency
    - 语义相关性
    """
    
    ZEP_MRR_TARGET = 0.80
    ZEP_RECALL_TARGET = 0.85
    ZEP_LATENCY_TARGET = 100  # ms
    
    def analyze(self, test_results: List[Dict]) -> ExpertOpinion:
        """深度分析向量检索能力"""
        findings = []
        recommendations = []
        
        # 分析各项指标
        mrr_scores = [r.get('mrr', 0) for r in test_results]
        recall_scores = [r.get('recall', 0) for r in test_results]
        
        avg_mrr = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0
        avg_recall = sum(recall_scores) / len(recall_scores) if recall_scores else 0
        
        # Zep对标分析
        mrr_gap = avg_mrr - self.ZEP_MRR_TARGET
        recall_gap = avg_recall - self.ZEP_RECALL_TARGET
        
        findings.append(f"MRR: {avg_mrr:.3f} (Zep目标: {self.ZEP_MRR_TARGET}, 差距: {mrr_gap:+.3f})")
        findings.append(f"Recall: {avg_recall:.3f} (Zep目标: {self.ZEP_RECALL_TARGET}, 差距: {recall_gap:+.3f})")
        
        # 严格评判
        if mrr_gap < -0.1:
            score = 0.5
            recommendations.append("【严重】MRR差距超过0.1，建议更换或微调向量模型")
        elif mrr_gap < 0:
            score = 0.7
            recommendations.append("【警告】MRR略低于Zep，建议增加hard negative mining")
        else:
            score = 0.9
            recommendations.append("【优秀】MRR已达到Zep水平")
        
        # 检查BM25融合
        has_bm25 = any(r.get('has_bm25', False) for r in test_results)
        if not has_bm25:
            findings.append("⚠️ 未检测到BM25融合，Zep强调混合检索的重要性")
            recommendations.append("【必须】添加BM25通道与向量检索的RRF融合")
        
        # 检查语义重排
        has_rerank = any(r.get('has_cross_encoder', False) for r in test_results)
        if not has_rerank:
            findings.append("⚠️ 未检测到Cross-Encoder重排")
            recommendations.append("【必须】添加语义重排提升Top-K准确性")
        
        return ExpertOpinion(
            expert="向量检索专家",
            area="Retrieval",
            score=score,
            findings=findings,
            recommendations=recommendations
        )


class ContextUnderstandingExpert:
    """
    上下文理解专家 - 对标Claude
    
    Claude核心能力分析:
    1. 意图识别 (Intent Classification)
    2. 实体提取 (Entity Extraction)
    3. 指代消解 (Coreference Resolution)
    4. 上下文窗口管理
    
    评估维度:
    - 意图识别准确率
    - 实体召回率
    - 实体消解准确率
    - 上下文敏感度
    """
    
    CLAUDE_INTENT_TARGET = 0.90
    CLAUDE_ENTITY_TARGET = 0.85
    CLAUDE_COREF_TARGET = 0.80
    
    def analyze(self, test_results: List[Dict]) -> ExpertOpinion:
        """深度分析上下文理解能力"""
        findings = []
        recommendations = []
        
        intent_scores = [r.get('intent_accuracy', 0) for r in test_results]
        entity_scores = [r.get('entity_recall', 0) for r in test_results]
        
        avg_intent = sum(intent_scores) / len(intent_scores) if intent_scores else 0
        avg_entity = sum(entity_scores) / len(entity_scores) if entity_scores else 0
        
        # Claude对标分析
        intent_gap = avg_intent - self.CLAUDE_INTENT_TARGET
        entity_gap = avg_entity - self.CLAUDE_ENTITY_TARGET
        
        findings.append(f"意图识别: {avg_intent:.3f} (Claude目标: {self.CLAUDE_INTENT_TARGET}, 差距: {intent_gap:+.3f})")
        findings.append(f"实体召回: {avg_entity:.3f} (Claude目标: {self.CLAUDE_ENTITY_TARGET}, 差距: {entity_gap:+.3f})")
        
        # 严格评判
        if intent_gap < -0.1:
            score = 0.4
            recommendations.append("【严重】意图识别差距超过0.1，需要重新设计分类器")
        elif intent_gap < 0:
            score = 0.65
            recommendations.append("【警告】意图识别略低于Claude，建议增加训练数据")
        else:
            score = 0.85
            recommendations.append("【良好】意图识别接近Claude水平")
        
        # 检查意图分类数量
        intent_types = set()
        for r in test_results:
            intent_types.add(r.get('detected_intent', 'unknown'))
        
        if len(intent_types) < 5:
            findings.append(f"⚠️ 仅检测到{len(intent_types)}种意图类型，Claude通常支持10+种")
            recommendations.append("【建议】扩展意图分类数量，支持更多查询类型")
        
        # 检查实体提取
        if avg_entity < 0.7:
            findings.append("⚠️ 实体召回率偏低")
            recommendations.append("【必须】改进中文实体提取器，可能需要LLM辅助")
        
        return ExpertOpinion(
            expert="上下文理解专家",
            area="Context",
            score=score,
            findings=findings,
            recommendations=recommendations
        )


class KnowledgeGraphExpert:
    """
    知识图谱专家 - 对标Letta
    
    Letta核心能力分析:
    1. 实体关系抽取
    2. 多跳推理 (Multi-hop Reasoning)
    3. 动态图更新
    4. 传递闭包计算
    
    评估维度:
    - 单跳准确率
    - 两跳准确率
    - 三跳准确率
    - 图覆盖度
    """
    
    LETTA_SINGLE_TARGET = 0.90
    LETTA_TWO_TARGET = 0.75
    LETTA_THREE_TARGET = 0.60
    
    def analyze(self, test_results: List[Dict]) -> ExpertOpinion:
        """深度分析多跳推理能力"""
        findings = []
        recommendations = []
        
        single_scores = [r.get('single_hop', 0) for r in test_results]
        two_hop_scores = [r.get('two_hop', 0) for r in test_results]
        three_hop_scores = [r.get('three_hop', 0) for r in test_results]
        
        avg_single = sum(single_scores) / len(single_scores) if single_scores else 0
        avg_two = sum(two_hop_scores) / len(two_hop_scores) if two_hop_scores else 0
        avg_three = sum(three_hop_scores) / len(three_hop_scores) if three_hop_scores else 0
        
        findings.append(f"单跳准确率: {avg_single:.3f} (目标: {self.LETTA_SINGLE_TARGET})")
        findings.append(f"两跳准确率: {avg_two:.3f} (目标: {self.LETTA_TWO_TARGET})")
        findings.append(f"三跳准确率: {avg_three:.3f} (目标: {self.LETTA_THREE_TARGET})")
        
        # Letta对标分析
        two_hop_gap = avg_two - self.LETTA_TWO_TARGET
        
        if avg_two < self.LETTA_TWO_TARGET - 0.15:
            score = 0.45
            recommendations.append("【严重】两跳推理差距超过0.15，需要增强知识图谱")
        elif avg_two < self.LETTA_TWO_TARGET:
            score = 0.7
            recommendations.append("【警告】两跳推理略低于Letta，建议增加传递推理")
        else:
            score = 0.9
            recommendations.append("【优秀】多跳推理已达到Letta水平")
        
        # 检查知识图谱状态
        kg_nodes = test_results[0].get('kg_nodes', 0) if test_results else 0
        kg_edges = test_results[0].get('kg_edges', 0) if test_results else 0
        
        findings.append(f"知识图谱: {kg_nodes}节点, {kg_edges}边")
        
        if kg_nodes < 50:
            findings.append("⚠️ 知识图谱节点数过少，Letta通常有数千节点")
            recommendations.append("【必须】批量填充知识图谱实体和关系")
        
        if kg_edges < kg_nodes:
            findings.append("⚠️ 知识图谱关系稀疏，平均连接度<1")
            recommendations.append("【必须】增强实体间关系抽取")
        
        return ExpertOpinion(
            expert="知识图谱专家",
            area="KnowledgeGraph",
            score=score,
            findings=findings,
            recommendations=recommendations
        )


class ReviewCommittee:
    """
    评审委员会 - 综合裁决
    """
    
    def __init__(self):
        self.vector_expert = VectorRetrievalExpert()
        self.context_expert = ContextUnderstandingExpert()
        self.kg_expert = KnowledgeGraphExpert()
    
    def conduct_review(self, test_data: Dict) -> Tuple[FinalVerdict, List[ExpertOpinion]]:
        """
        执行全面评审
        
        Args:
            test_data: 包含各类测试结果的数据
                - retrieval_results: 向量检索测试结果
                - context_results: 上下文理解测试结果
                - kg_results: 知识图谱测试结果
        """
        # 各专家独立评审
        vector_opinion = self.vector_expert.analyze(test_data.get('retrieval_results', []))
        context_opinion = self.context_expert.analyze(test_data.get('context_results', []))
        kg_opinion = self.kg_expert.analyze(test_data.get('kg_results', []))
        
        opinions = [vector_opinion, context_opinion, kg_opinion]
        
        # 综合评分 (加权平均)
        weights = {
            'Retrieval': 0.40,
            'Context': 0.35,
            'KnowledgeGraph': 0.25
        }
        
        overall_score = (
            vector_opinion.score * weights['Retrieval'] +
            context_opinion.score * weights['Context'] +
            kg_opinion.score * weights['KnowledgeGraph']
        )
        
        # 行业定位
        if overall_score >= 0.85:
            industry_position = "leader"
        elif overall_score >= 0.70:
            industry_position = "competitive"
        elif overall_score >= 0.50:
            industry_position = "emerging"
        else:
            industry_position = "nascent"
        
        # 差距分析
        gap_analysis = {
            'vs_zep': vector_opinion.score - 0.85,  # Zep是检索leader
            'vs_claude': context_opinion.score - 0.85,  # Claude是理解leader
            'vs_letta': kg_opinion.score - 0.80,  # Letta是多跳leader
            'overall_gap': overall_score - 0.80  # vs行业平均
        }
        
        # 按优先级排序建议
        all_recommendations = []
        for opinion in opinions:
            for rec in opinion.recommendations:
                priority = "【严重】" in rec
                all_recommendations.append({
                    'priority': priority,
                    'expert': opinion.expert,
                    'recommendation': rec
                })
        
        # 按优先级排序
        all_recommendations.sort(key=lambda x: not x['priority'])
        prioritized = all_recommendations[:10]  # 取前10条
        
        verdict = FinalVerdict(
            overall_score=overall_score,
            industry_position=industry_position,
            gap_analysis=gap_analysis,
            prioritized_recommendations=prioritized
        )
        
        return verdict, opinions
    
    def generate_report(self, verdict: FinalVerdict, opinions: List[ExpertOpinion]) -> str:
        """生成完整评审报告"""
        lines = [
            "=" * 70,
            "🔬 Claw Memory 严格专业评审报告",
            "=" * 70,
            "",
            f"📊 综合评分: {verdict.overall_score:.3f}",
            f"🏷️  行业定位: {verdict.industry_position.upper()}",
            "",
        ]
        
        # 各专家意见
        for opinion in opinions:
            status = "✅" if opinion.score >= 0.7 else "⚠️" if opinion.score >= 0.5 else "❌"
            lines.extend([
                f"",
                f"{'='*70}",
                f"{status} {opinion.expert} ({opinion.area})",
                f"{'='*70}",
                f"评分: {opinion.score:.3f}",
                "",
                "🔍 发现:",
            ])
            for finding in opinion.findings:
                lines.append(f"  • {finding}")
            
            if opinion.recommendations:
                lines.extend(["", "💡 建议:"])
                for rec in opinion.recommendations:
                    lines.append(f"  → {rec}")
        
        # 差距分析
        lines.extend([
            "",
            "=" * 70,
            "📉 差距分析",
            "=" * 70,
            f"  vs Zep (检索):     {verdict.gap_analysis['vs_zep']:+.3f}",
            f"  vs Claude (理解): {verdict.gap_analysis['vs_claude']:+.3f}",
            f"  vs Letta (推理):   {verdict.gap_analysis['vs_letta']:+.3f}",
            f"  vs 行业平均:       {verdict.gap_analysis['overall_gap']:+.3f}",
        ])
        
        # 优先建议
        if verdict.prioritized_recommendations:
            lines.extend([
                "",
                "=" * 70,
                "🎯 优先改进建议 (按优先级排序)",
                "=" * 70,
            ])
            for i, rec in enumerate(verdict.prioritized_recommendations[:5], 1):
                priority_marker = "🔴" if rec['priority'] else "🟡"
                lines.append(f"  {i}. {priority_marker} [{rec['expert']}] {rec['recommendation']}")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)


def run_strict_review(test_data: Dict) -> str:
    """执行严格评审的便捷函数"""
    committee = ReviewCommittee()
    verdict, opinions = committee.conduct_review(test_data)
    return committee.generate_report(verdict, opinions)
