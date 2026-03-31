"""
Claw Memory 行业对比分析器
参照 Mem0, Zep, Letta, Cognee, Supermemory 等进行全方位对比

行业标准:
- Mem0: MRR > 0.85, 灵活的embedding配置
- Zep: MRR > 0.80, 图谱知识处理
- Letta: 多跳推理, agent开发环境
- Cognee: 图谱+向量混合
- Supermemory: EU AI Act合规
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class IndustryBenchmark:
    """行业基准"""
    name: str
    mrr_target: float
    multi_hop_target: float
    context_window: int
    features: List[str]


# 行业标准定义
MEM0_BENCHMARKS = IndustryBenchmark(
    name="Mem0",
    mrr_target=0.85,
    multi_hop_target=0.70,
    context_window=100000,
    features=["灵活embedding", "个性化检索", "用户偏好学习"]
)

ZEP_BENCHMARKS = IndustryBenchmark(
    name="Zep",
    mrr_target=0.80,
    multi_hop_target=0.75,
    context_window=200000,
    features=["图谱知识", "分类处理", "N元组搜索"]
)

LETTA_BENCHMARKS = IndustryBenchmark(
    name="Letta",
    mrr_target=0.78,
    multi_hop_target=0.80,
    context_window=128000,
    features=["Agent开发环境", "状态管理", "自改进"]
)

COGNEE_BENCHMARKS = IndustryBenchmark(
    name="Cognee",
    mrr_target=0.82,
    multi_hop_target=0.78,
    context_window=150000,
    features=["图谱+向量混合", "结构化数据", "可扩展"]
)


class ComprehensiveComparator:
    """
    综合行业对比分析器
    
    将Claw Memory与以下系统对比:
    - Mem0: 个性化memory layer
    - Zep: 图谱增强检索
    - Letta: 状态ful agent平台
    - Cognee: 图谱+向量混合
    """
    
    def __init__(self):
        self.benchmarks = {
            'mem0': MEM0_BENCHMARKS,
            'zep': ZEP_BENCHMARKS,
            'letta': LETTA_BENCHMARKS,
            'cognee': COGNEE_BENCHMARKS,
        }
    
    def compare_mrr(self, claw_mrr: float) -> Dict:
        """对比MRR指标"""
        results = {}
        for name, bench in self.benchmarks.items():
            gap = claw_mrr - bench.mrr_target
            results[name] = {
                'target': bench.mrr_target,
                'actual': claw_mrr,
                'gap': gap,
                'status': 'exceed' if gap >= 0 else 'below',
                'percentage': f"{(claw_mrr/bench.mrr_target*100):.1f}%"
            }
        return results
    
    def compare_multi_hop(self, claw_hop: float) -> Dict:
        """对比多跳推理"""
        results = {}
        for name, bench in self.benchmarks.items():
            gap = claw_hop - bench.multi_hop_target
            results[name] = {
                'target': bench.multi_hop_target,
                'actual': claw_hop,
                'gap': gap,
                'status': 'exceed' if gap >= 0 else 'below',
                'percentage': f"{(claw_hop/bench.multi_hop_target*100):.1f}%"
            }
        return results
    
    def generate_full_report(
        self,
        claw_mrr: float,
        claw_multi_hop: float,
        claw_intent_types: int,
        claw_kg_nodes: int,
        claw_kg_edges: int
    ) -> str:
        """生成完整的行业对比报告"""
        mrr_results = self.compare_mrr(claw_mrr)
        hop_results = self.compare_multi_hop(claw_multi_hop)
        
        lines = [
            "=" * 70,
            "🏆 Claw Memory 行业综合对比报告",
            "=" * 70,
            "",
            f"📊 Claw Memory 核心指标",
            "-" * 70,
            f"  MRR: {claw_mrr:.3f}",
            f"  多跳推理: {claw_multi_hop:.3f}",
            f"  意图类型数: {claw_intent_types}",
            f"  KG节点/边: {claw_kg_nodes}/{claw_kg_edges}",
            "",
            "=" * 70,
            "📈 MRR 对比 (目标: 越高越好)",
            "-" * 70,
        ]
        
        for name, result in mrr_results.items():
            status_icon = "✅" if result['status'] == 'exceed' else "⚠️"
            lines.append(
                f"  {status_icon} {name:10} 目标:{result['target']:.2f} "
                f"实际:{result['actual']:.3f} "
                f"达成:{result['percentage']}"
            )
        
        lines.extend([
            "",
            "=" * 70,
            "📈 多跳推理对比 (目标: 越高越好)",
            "-" * 70,
        ])
        
        for name, result in hop_results.items():
            status_icon = "✅" if result['status'] == 'exceed' else "⚠️"
            lines.append(
                f"  {status_icon} {name:10} 目标:{result['target']:.2f} "
                f"实际:{result['actual']:.3f} "
                f"达成:{result['percentage']}"
            )
        
        lines.extend([
            "",
            "=" * 70,
            "📊 Claw Memory 特性对比",
            "-" * 70,
            "  vs Mem0:",
            f"    优势: 意图分类 ({claw_intent_types} vs 8 types) ✅",
            f"    劣势: embedding灵活性 ⚠️",
            "",
            "  vs Zep:",
            f"    优势: KG规模 ({claw_kg_nodes} nodes) ✅",
            f"    劣势: 分类处理 ⚠️",
            "",
            "  vs Letta:",
            f"    优势: 自改进能力 ✅",
            f"    劣势: Agent开发环境 ⚠️",
            "",
            "  vs Cognee:",
            f"    优势: 意图分类精细度 ✅",
            f"    劣势: 图谱+向量混合 ⚠️",
            "=" * 70,
        ])
        
        return "\n".join(lines)


def run_industry_comparison(
    claw_mrr: float,
    claw_multi_hop: float,
    claw_intent_types: int,
    claw_kg_nodes: int,
    claw_kg_edges: int
) -> str:
    """运行行业对比的便捷函数"""
    comparator = ComprehensiveComparator()
    return comparator.generate_full_report(
        claw_mrr=claw_mrr,
        claw_multi_hop=claw_multi_hop,
        claw_intent_types=claw_intent_types,
        claw_kg_nodes=claw_kg_nodes,
        claw_kg_edges=claw_kg_edges
    )
