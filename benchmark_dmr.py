"""
DMR Benchmark 评测系统
用于评估记忆系统的检索质量

DMR (Deep Memory Retrieval) Benchmark:
- Recall@K: 正确结果出现在前K个的比例
- MRR (Mean Reciprocal Rank): 平均倒数排名
- NDCG (Normalized Discounted Cumulative Gain): 归一化折损累计增益
"""
import json
import time
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class BenchmarkResult:
    """评测结果"""
    metric: str
    score: float
    details: str


class DMRBenchmark:
    """
    DMR Benchmark 评测器
    
    评测指标：
    1. Recall@K - 召回率
    2. MRR - 平均倒数排名
    3. NDCG - 归一化折损累计增益
    """
    
    def __init__(self):
        self.results = []
    
    def _calculate_recall_at_k(self, relevant: set, retrieved: list, k: int) -> float:
        """计算Recall@K"""
        if not relevant:
            return 1.0 if not retrieved else 0.0
        
        retrieved_k = set(retrieved[:k])
        intersection = relevant & retrieved_k
        return len(intersection) / len(relevant)
    
    def _calculate_mrr(self, relevant: set, retrieved: list) -> float:
        """计算MRR"""
        for i, doc_id in enumerate(retrieved, 1):
            if doc_id in relevant:
                return 1.0 / i
        return 0.0
    
    def _calculate_ndcg(self, relevant: set, retrieved: list, k: int = 10) -> float:
        """计算NDCG@K"""
        # DCG
        dcg = 0.0
        for i, doc_id in enumerate(retrieved[:k], 1):
            if doc_id in relevant:
                dcg += 1.0 / self._log_base(i, base=2)
        
        # IDCG (ideal DCG)
        idcg = 0.0
        for i in range(1, min(len(relevant), k) + 1):
            idcg += 1.0 / self._log_base(i, base=2)
        
        if idcg == 0:
            return 1.0 if not relevant else 0.0
        
        return dcg / idcg
    
    def _log_base(self, n: int, base: float) -> float:
        """计算对数"""
        import math
        return math.log(n + 1, base)
    
    def evaluate(self, query: str, relevant_ids: set, retrieved_ids: list,
                  k_values: List[int] = [1, 3, 5, 10]) -> Dict[str, float]:
        """
        评估单个查询的检索质量
        
        Args:
            query: 查询字符串
            relevant_ids: 相关的记忆ID集合
            retrieved_ids: 系统返回的记忆ID列表（按相关性排序）
            k_values: 评估的K值列表
            
        Returns:
            各指标得分
        """
        scores = {}
        
        # Recall@K
        for k in k_values:
            recall = self._calculate_recall_at_k(relevant_ids, retrieved_ids, k)
            scores[f"Recall@{k}"] = recall
        
        # MRR
        scores["MRR"] = self._calculate_mrr(relevant_ids, retrieved_ids)
        
        # NDCG@K
        for k in [5, 10]:
            ndcg = self._calculate_ndcg(relevant_ids, retrieved_ids, k)
            scores[f"NDCG@{k}"] = ndcg
        
        return scores
    
    def run_benchmark(self, test_cases: List[Dict]) -> Dict:
        """
        运行完整Benchmark
        
        Args:
            test_cases: 测试用例列表
            [
                {
                    "query": "用户的技术偏好",
                    "relevant_ids": {"mem1", "mem2"},
                    "retrieved_ids": ["mem3", "mem1", "mem2"]
                },
                ...
            ]
            
        Returns:
            汇总结果
        """
        all_scores = {
            "Recall@1": [], "Recall@3": [], "Recall@5": [], "Recall@10": [],
            "MRR": [],
            "NDCG@5": [], "NDCG@10": []
        }
        
        for case in test_cases:
            scores = self.evaluate(
                case["query"],
                set(case["relevant_ids"]),
                case["retrieved_ids"]
            )
            
            for metric, score in scores.items():
                all_scores[metric].append(score)
        
        # 计算平均值
        avg_scores = {}
        for metric, scores in all_scores.items():
            if scores:
                avg_scores[metric] = sum(scores) / len(scores)
            else:
                avg_scores[metric] = 0.0
        
        # 计算总体评分 (综合指标)
        # 综合评分 = 0.3*MRR + 0.3*Recall@5 + 0.2*NDCG@5 + 0.2*Recall@10
        overall = (
            0.3 * avg_scores.get("MRR", 0) +
            0.3 * avg_scores.get("Recall@5", 0) +
            0.2 * avg_scores.get("NDCG@5", 0) +
            0.2 * avg_scores.get("Recall@10", 0)
        )
        
        return {
            "overall_score": round(overall * 100, 2),  # 转换为百分制
            "metrics": {k: round(v * 100, 2) for k, v in avg_scores.items()},
            "test_cases": len(test_cases),
            "passed": sum(1 for s in all_scores["MRR"] if s > 0),
            "failed": sum(1 for s in all_scores["MRR"] if s == 0)
        }


# 内置测试用例
DEFAULT_TEST_CASES = [
    {
        "query": "用户的技术栈",
        "relevant_ids": [],  # 用户需要填充
        "retrieved_ids": [],
        "description": "查询用户使用的技术"
    },
    {
        "query": "用户的工作经历",
        "relevant_ids": [],
        "retrieved_ids": [],
        "description": "查询用户的工作公司"
    },
    {
        "query": "用户的偏好",
        "relevant_ids": [],
        "retrieved_ids": [],
        "description": "查询用户偏好"
    }
]


def create_test_case_from_memory(query: str, memory_ids: List[str], 
                                 search_func) -> Dict:
    """
    从记忆创建测试用例
    
    Args:
        query: 测试查询
        memory_ids: 应该被召回的记忆ID
        search_func: 搜索函数
        
    Returns:
        测试用例字典
    """
    # 执行搜索
    results = search_func(query, limit=10)
    retrieved_ids = [r.get("id") for r in results]
    
    return {
        "query": query,
        "relevant_ids": set(memory_ids),
        "retrieved_ids": retrieved_ids
    }


def run_auto_benchmark(memory_system) -> Dict:
    """
    自动生成测试用例并运行Benchmark
    
    Args:
        memory_system: 记忆系统（需要有 search 方法）
        
    Returns:
        Benchmark结果
    """
    # 获取所有记忆
    stats = memory_system.stats()
    total = stats.get("warm_store", {}).get("total", 0)
    
    if total == 0:
        return {"error": "记忆库为空，无法运行Benchmark"}
    
    # 生成测试查询
    test_queries = [
        "用户",
        "技术",
        "偏好",
        "工作",
        "项目",
    ]
    
    # 创建测试用例
    test_cases = []
    for query in test_queries:
        results = memory_system.search(query, limit=10)
        retrieved_ids = [r.get("id") for r in results]
        
        # 假设前3个结果是对的（简化处理）
        relevant_ids = set(retrieved_ids[:3]) if len(retrieved_ids) >= 3 else set(retrieved_ids)
        
        test_cases.append({
            "query": query,
            "relevant_ids": relevant_ids,
            "retrieved_ids": retrieved_ids
        })
    
    # 运行评测
    benchmark = DMRBenchmark()
    return benchmark.run_benchmark(test_cases)
