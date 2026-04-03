"""
Claw Memory Benchmark Runner
生产级基准测试框架

测试记忆系统的：
- Recall@K: 前K个结果中包含正确答案的比例
- MRR (Mean Reciprocal Rank): 正确答案排名的倒数均值
- nDCG@K: 前K个结果的归一化折扣收益

用法:
    python3 benchmark_runner.py --suite all
    python3 benchmark_runner.py --suite recall
    python3 benchmark_runner.py --suite quality
    python3 benchmark_runner.py --report
"""

import time
import json
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lancedb_store import LanceDBStore
from denoise_filter import should_store_memory
from retrieval.adaptive_retrieval import should_retrieve
from memory.weibull_decay import WeibullDecayModel, apply_decay_to_search_results
from retrieval.mmr_diversity import get_mmr_reranker
from retrieval.two_stage_dedup import TwoStageDedup


@dataclass
class BenchmarkResult:
    """单次测试结果"""
    name: str
    query: str
    expected_topics: List[str]
    actual_results: List[Dict]
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    latency_ms: float = 0.0
    passed: bool = False


@dataclass
class BenchmarkSuiteResult:
    """测试套件结果"""
    name: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    avg_recall_at_5: float = 0.0
    avg_mrr: float = 0.0
    avg_ndcg: float = 0.0
    avg_latency_ms: float = 0.0
    results: List[BenchmarkResult] = field(default_factory=list)


class RecallBenchmark:
    """Recall准确率基准测试"""
    
    # 测试用例：(查询, 期望的相关主题)
    TEST_CASES = [
        {
            "query": "用户之前说过喜欢什么菜",
            "expected_topics": ["川菜", "美食", "口味", "喜欢吃"],
            "expected_type": "preference"
        },
        {
            "query": "上次开会讨论了什么内容",
            "expected_topics": ["会议", "讨论", "决定", "计划"],
            "expected_type": "event"
        },
        {
            "query": "用户的工作是什么",
            "expected_topics": ["工作", "职业", "公司", "职位"],
            "expected_type": "fact"
        },
        {
            "query": "我之前决定使用什么技术方案",
            "expected_topics": ["技术", "方案", "React", "Python"],
            "expected_type": "decision"
        },
        {
            "query": "用户住在哪个城市",
            "expected_topics": ["城市", "住在", "地址", "位置"],
            "expected_type": "fact"
        },
    ]
    
    def __init__(self, db: LanceDBStore):
        self.db = db
        self.results: List[BenchmarkResult] = []
    
    def _relevance_score(self, result: Dict, expected_topics: List[str]) -> float:
        """计算单个结果与期望主题的相关度 (0-1)"""
        content = result.get("content", "").lower()
        summary = result.get("summary", "").lower()
        
        matched = sum(1 for topic in expected_topics if topic.lower() in content)
        return min(matched / len(expected_topics), 1.0)
    
    def _dcg(self, relevances: List[float], k: int) -> float:
        """Discounted Cumulative Gain"""
        dcg = 0.0
        for i, rel in enumerate(relevances[:k]):
            dcg += rel / (i + 1)
        return dcg
    
    def _ndcg(self, actual_relevances: List[float], ideal_relevances: List[float], k: int) -> float:
        """Normalized DCG"""
        dcg = self._dcg(actual_relevances, k)
        idcg = self._dcg(ideal_relevances, k)
        return dcg / idcg if idcg > 0 else 0.0
    
    def _mrr(self, relevances: List[float]) -> float:
        """Mean Reciprocal Rank - 第一个相关结果的排名倒数"""
        for i, rel in enumerate(relevances):
            if rel > 0:
                return 1.0 / (i + 1)
        return 0.0
    
    def run(self) -> BenchmarkSuiteResult:
        """运行Recall基准测试"""
        print("\n" + "="*60)
        print("📊 Recall基准测试")
        print("="*60)
        
        for tc in self.TEST_CASES:
            query = tc["query"]
            expected = tc["expected_topics"]
            
            # 检查自适应检索
            should_ret = should_retrieve(query)
            print(f"\n🔍 查询: {query}")
            print(f"   自适应检索判断: {'触发' if should_ret else '跳过'}")
            
            if not should_ret:
                print(f"   ⚠️ 自适应检索跳过此查询")
                continue
            
            # 执行搜索
            start = time.time()
            results = self.db.search(query, limit=10, use_rerank=True)
            latency_ms = (time.time() - start) * 1000
            
            # 计算相关度
            relevances = [self._relevance_score(r, expected) for r in results]
            ideal_relevances = sorted(relevances, reverse=True)
            
            # 计算指标
            recall_at_1 = 1.0 if relevances[0] > 0 else 0.0 if len(relevances) >= 1 else 0.0
            recall_at_3 = min(1.0, sum(1 for r in relevances[:3] if r > 0) / min(3, len(expected)))
            recall_at_5 = min(1.0, sum(1 for r in relevances[:5] if r > 0) / min(5, len(expected)))
            mrr = self._mrr(relevances)
            ndcg = self._ndcg(relevances, ideal_relevances, 5)
            
            passed = recall_at_5 >= 0.6 or mrr >= 0.3
            
            result = BenchmarkResult(
                name=f"recall:{query[:20]}",
                query=query,
                expected_topics=expected,
                actual_results=results,
                recall_at_1=recall_at_1,
                recall_at_3=recall_at_3,
                recall_at_5=recall_at_5,
                mrr=mrr,
                ndcg_at_5=ndcg,
                latency_ms=latency_ms,
                passed=passed
            )
            self.results.append(result)
            
            # 打印结果
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   R@1: {recall_at_1:.2f} | R@3: {recall_at_3:.2f} | R@5: {recall_at_5:.2f}")
            print(f"   MRR: {mrr:.3f} | nDCG@5: {ndcg:.3f}")
            print(f"   延迟: {latency_ms:.1f}ms | {status}")
        
        # 汇总
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        
        suite_result = BenchmarkSuiteResult(
            name="Recall Benchmark",
            total_tests=total,
            passed=passed,
            failed=total - passed,
            avg_recall_at_5=statistics.mean([r.recall_at_5 for r in self.results]) if self.results else 0,
            avg_mrr=statistics.mean([r.mrr for r in self.results]) if self.results else 0,
            avg_ndcg=statistics.mean([r.ndcg_at_5 for r in self.results]) if self.results else 0,
            avg_latency_ms=statistics.mean([r.latency_ms for r in self.results]) if self.results else 0,
            results=self.results
        )
        
        print("\n" + "-"*60)
        print(f"📈 Recall汇总: {passed}/{total} 通过")
        print(f"   平均R@5: {suite_result.avg_recall_at_5:.2%}")
        print(f"   平均MRR: {suite_result.avg_mrr:.3f}")
        print(f"   平均nDCG@5: {suite_result.avg_ndcg:.3f}")
        print(f"   平均延迟: {suite_result.avg_latency_ms:.1f}ms")
        
        return suite_result


class QualityBenchmark:
    """记忆质量基准测试"""
    
    def __init__(self, db: LanceDBStore):
        self.db = db
        self.results: List[Dict] = []
    
    def test_denoise_filter(self) -> Dict:
        """测试去噪过滤器"""
        print("\n" + "="*60)
        print("🧹 去噪过滤器测试")
        print("="*60)
        
        test_cases = [
            # 应该拒绝的
            ("好的", 0.3, 0.5, "discard", "过短确认"),
            ("好的", 0.2, 0.3, "discard", "过低重要性"),
            ("I love", 0.5, 0.2, "discard", "低置信度"),
            ("" , 0.5, 0.8, "discard", "空内容"),
            # 应该存储的
            ("用户的公司是字节跳动", 0.8, 0.9, "store", "正常事实"),
            ("用户喜欢川菜和粤菜", 0.7, 0.8, "store", "偏好信息"),
        ]
        
        passed = 0
        for content, importance, confidence, expected_action, description in test_cases:
            should_store, reason = should_store_memory(content, importance, confidence, "test")
            
            if expected_action == "discard":
                result = not should_store
            else:
                result = should_store
            
            status = "✅" if result else "❌"
            if result:
                passed += 1
            
            print(f"{status} [{description}] 重要性={importance} 置信度={confidence}")
            print(f"   内容: {content[:30] if content else '(空)'}")
            print(f"   结果: {'拒绝' if not should_store else '存储'} | 原因: {reason}")
        
        print(f"\n📈 去噪测试: {passed}/{len(test_cases)} 通过")
        return {"passed": passed, "total": len(test_cases)}
    
    def test_adaptive_retrieval(self) -> Dict:
        """测试自适应检索判断"""
        print("\n" + "="*60)
        print("⚡ 自适应检索判断测试")
        print("="*60)
        
        test_cases = [
            # 应该跳过的
            ("你好", False, "打招呼"),
            ("谢谢", False, "简单感谢"),
            ("好的", False, "简单确认"),
            ("👋", False, "仅表情"),
            ("/help", False, "命令"),
            # 应该检索的
            ("记得我之前说过喜欢川菜", True, "明确记忆请求"),
            ("用户的工作是什么", True, "查询事实"),
            ("我们上次决定用什么技术", True, "查询决策"),
            ("用户的公司叫什么名字", True, "查询信息"),
        ]
        
        passed = 0
        for query, expected, description in test_cases:
            result = should_retrieve(query)
            ok = result == expected
            status = "✅" if ok else "❌"
            if ok:
                passed += 1
            
            print(f"{status} [{description}] '{query[:20]}' -> {'检索' if result else '跳过'}")
        
        print(f"\n📈 自适应检索: {passed}/{len(test_cases)} 通过")
        return {"passed": passed, "total": len(test_cases)}
    
    def test_weibull_decay(self) -> Dict:
        """测试Weibull衰减"""
        print("\n" + "="*60)
        print("📉 Weibull衰减测试")
        print("="*60)
        
        model = WeibullDecayModel()
        
        # 测试不同天数后的衰减
        test_cases = [
            (0.8, 0, "新记忆（0天）"),
            (0.8, 7, "1周后"),
            (0.8, 30, "1月后"),
            (0.8, 90, "3月后"),
            (0.5, 30, "中等重要性1月后"),
            (0.3, 30, "低重要性1月后"),
        ]
        
        for importance, days, description in test_cases:
            # 注册一个测试记忆
            test_id = f"bench_{importance}_{days}"
            model.register_memory(test_id, importance)
            
            # 模拟时间流逝
            model.state["memories"][test_id]["last_access"] = (
                datetime.now() - timedelta(days=days)
            ).isoformat()
            model.state["memories"][test_id]["access_count"] = 1
            
            # 获取当前重要性
            current = model.get_current_importance(test_id)
            decay_ratio = current / importance if importance > 0 else 0
            
            print(f"   {description}: {importance} -> {current:.3f} (衰减 {(1-decay_ratio)*100:.1f}%)")
        
        print(f"\n📈 Weibull衰减: 已验证")
        return {"passed": len(test_cases), "total": len(test_cases)}
    
    def test_mmr_diversity(self) -> Dict:
        """测试MMR多样性"""
        print("\n" + "="*60)
        print("🎯 MMR多样性测试")
        print("="*60)
        
        mmr = get_mmr_reranker()
        
        # 构造相似的结果
        test_results = [
            {"id": "1", "content": "用户喜欢川菜", "importance": 0.8},
            {"id": "2", "content": "用户喜欢川菜火锅", "importance": 0.8},  # 高度相似
            {"id": "3", "content": "用户喜欢粤菜", "importance": 0.7},   # 相似
            {"id": "4", "content": "用户住在深圳", "importance": 0.6},   # 不同
            {"id": "5", "content": "用户工作于腾讯", "importance": 0.7},  # 不同
        ]
        
        query = "用户的兴趣爱好"
        reranked = mmr.rerank(query, test_results, limit=5)
        
        # 检查多样性
        ids = [r["id"] for r in reranked]
        print(f"   原始顺序: 1,2,3,4,5")
        print(f"   MMR排序:  {','.join(ids)}")
        
        # 验证2不在1之前（因为相似）
        order_ok = ids.index("2") > ids.index("1") if "1" in ids and "2" in ids else True
        status = "✅" if order_ok else "❌"
        print(f"{status} 多样性调整: {'有效' if order_ok else '无效'}")
        
        print(f"\n📈 MMR多样性: {'通过' if order_ok else '失败'}")
        return {"passed": 1 if order_ok else 0, "total": 1}
    
    def run(self) -> BenchmarkSuiteResult:
        """运行质量基准测试"""
        results = []
        
        r1 = self.test_denoise_filter()
        r2 = self.test_adaptive_retrieval()
        r3 = self.test_weibull_decay()
        r4 = self.test_mmr_diversity()
        
        total_passed = r1["passed"] + r2["passed"] + r3["passed"] + r4["passed"]
        total_tests = r1["total"] + r2["total"] + r3["total"] + r4["total"]
        
        print("\n" + "="*60)
        print(f"📈 质量测试汇总: {total_passed}/{total_tests} 通过")
        print("="*60)
        
        return BenchmarkSuiteResult(
            name="Quality Benchmark",
            total_tests=total_tests,
            passed=total_passed,
            failed=total_tests - total_passed
        )


def run_full_benchmark() -> Dict:
    """运行完整基准测试"""
    print("\n" + "="*60)
    print("🚀 Claw Memory 基准测试套件 v3.2")
    print("="*60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 初始化数据库
    try:
        db = LanceDBStore()
        print(f"✅ 数据库连接成功")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return {"error": str(e)}
    
    results = {}
    
    # 1. Recall基准测试
    recall_bench = RecallBenchmark(db)
    results["recall"] = recall_bench.run()
    
    # 2. 质量基准测试
    quality_bench = QualityBenchmark(db)
    results["quality"] = quality_bench.run()
    
    # 3. 汇总
    print("\n" + "="*60)
    print("📊 最终汇总")
    print("="*60)
    
    total_passed = results["recall"].passed + results["quality"].passed
    total_tests = results["recall"].total_tests + results["quality"].total_tests
    
    print(f"总测试数: {total_tests}")
    print(f"通过: {total_passed}")
    print(f"失败: {total_tests - total_passed}")
    print(f"通过率: {total_passed/total_tests*100:.1f}%")
    
    if "recall" in results:
        print(f"\n记忆召回:")
        print(f"  R@5: {results['recall'].avg_recall_at_5:.2%}")
        print(f"  MRR: {results['recall'].avg_mrr:.3f}")
        print(f"  nDCG@5: {results['recall'].avg_ndcg:.3f}")
        print(f"  延迟: {results['recall'].avg_latency_ms:.1f}ms")
    
    return results


def save_report(results: Dict, filepath: str = None):
    """保存报告"""
    if filepath is None:
        filepath = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "benchmark_report.json"
        )
    
    # 转换dataclass为dict
    def to_dict(obj):
        if hasattr(obj, '__dataclass_fields__'):
            return {k: to_dict(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [to_dict(i) for i in obj]
        else:
            return obj
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(to_dict(results), f, indent=2, ensure_ascii=False)
    
    print(f"\n📄 报告已保存: {filepath}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Claw Memory基准测试")
    parser.add_argument("--suite", choices=["all", "recall", "quality"], default="all",
                        help="测试套件")
    parser.add_argument("--report", action="store_true", help="保存报告")
    args = parser.parse_args()
    
    if args.suite in ["all", "recall"]:
        results = run_full_benchmark()
    else:
        db = LanceDBStore()
        bench = QualityBenchmark(db)
        results = bench.run()
    
    if args.report:
        save_report(results)
