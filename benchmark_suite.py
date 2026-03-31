"""
Claw Memory Benchmark评测套件
基于LOCOMO/DMR标准评测集

目标：量化检索质量，追踪改进效果
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


# 标准测试集
BENCHMARK_TESTS = [
    # 事实类查询
    {
        "id": "fact_001",
        "query": "用户的工作是什么",
        "type": "fact",
        "relevant_keywords": ["工作", "职位", "公司", "职业"],
        "expected_types": ["fact", "preference"],
        "test_memory": "用户在字节跳动工作，职位是高级前端工程师"
    },
    {
        "id": "fact_002", 
        "query": "用户的名字叫什么",
        "type": "fact",
        "relevant_keywords": ["名字", "姓名", "称呼"],
        "expected_types": ["fact"],
        "test_memory": "用户的名字叫张三，是一名软件工程师"
    },
    {
        "id": "fact_003",
        "query": "用户在哪里住",
        "type": "fact", 
        "relevant_keywords": ["住", "城市", "地址", "家"],
        "expected_types": ["fact"],
        "test_memory": "用户住在上海浦东新区，公司在徐汇区"
    },
    
    # 偏好类查询
    {
        "id": "pref_001",
        "query": "用户喜欢什么编程语言",
        "type": "preference",
        "relevant_keywords": ["喜欢", "偏好", "语言", "Python", "JavaScript"],
        "expected_types": ["preference"],
        "test_memory": "用户喜欢使用Python和JavaScript编程，偏爱React框架"
    },
    {
        "id": "pref_002",
        "query": "用户的饮食偏好",
        "type": "preference",
        "relevant_keywords": ["吃", "饮食", "喜欢", "食物", "菜"],
        "expected_types": ["preference"],
        "test_memory": "用户的饮食偏好是川菜和火锅，不喜欢辣的食物"
    },
    {
        "id": "pref_003",
        "query": "用户喜欢什么音乐",
        "type": "preference",
        "relevant_keywords": ["音乐", "歌", "喜欢", "歌手"],
        "expected_types": ["preference"],
        "test_memory": "用户喜欢听古典音乐和爵士乐，讨厌重金属"
    },
    
    # 实体类查询
    {
        "id": "entity_001",
        "query": "用户认识哪些人",
        "type": "entity",
        "relevant_keywords": ["认识", "朋友", "同事", "人"],
        "expected_types": ["entity"],
        "test_memory": "用户的朋友有小李、小王，同事有张工程师和王经理"
    },
    {
        "id": "entity_002",
        "query": "用户使用什么工具",
        "type": "entity",
        "relevant_keywords": ["工具", "使用", "软件", "框架"],
        "expected_types": ["entity"],
        "test_memory": "用户使用React、TypeScript、VSCode和Git开发"
    },
    
    # 时序类查询
    {
        "id": "temporal_001",
        "query": "用户最近在做什么项目",
        "type": "temporal",
        "relevant_keywords": ["最近", "项目", "当前", "进行中"],
        "expected_types": ["fact"],
        # 存储用于时序测试的记忆
        "test_memory": "用户最近在做React前端项目开发，使用TypeScript和Node.js"
    },
    {
        "id": "temporal_002",
        "query": "用户以前喜欢什么",
        "type": "temporal",
        "relevant_keywords": ["以前", "曾经", "过去", "之前"],
        "expected_types": ["preference"],
        "test_memory": "用户以前喜欢使用Vue框架开发，现在转向了React"
    },
    
    # 关系类查询（测试KG传递推理）
    {
        "id": "relation_001",
        "query": "用户工作用的技术栈",
        "type": "relation",
        "relevant_keywords": ["工作", "技术", "栈", "开发", "编程"],
        "expected_types": ["entity", "fact"],
        "test_memory": "用户在Google工作，使用React、TypeScript和Python技术栈"
    },
    {
        "id": "relation_002",
        "query": "用户朋友的爱好",
        "type": "relation",
        "relevant_keywords": ["朋友", "爱好", "喜欢"],
        "expected_types": ["entity", "preference"],
        "test_memory": "用户的朋友小李喜欢弹吉他，用户的朋友小王喜欢打篮球"
    },
]

# 新增：复杂查询测试
BENCHMARK_TESTS_EXTENDED = [
    # 多跳推理测试
    {
        "id": "multihop_001",
        "query": "用户朋友的朋友喜欢什么",
        "type": "relation",
        "relevant_keywords": ["朋友", "喜欢"],
        "expected_types": ["entity", "preference"],
        "test_memory": "用户的朋友小李的朋友小张喜欢画画"
    },
    {
        "id": "multihop_002",
        "query": "用户同事使用的技术",
        "type": "relation",
        "relevant_keywords": ["同事", "技术", "使用"],
        "expected_types": ["entity"],
        "test_memory": "用户的同事张工使用Java和Spring框架开发后端"
    },
    
    # 否定查询测试
    {
        "id": "negation_001",
        "query": "用户不喜欢什么食物",
        "type": "preference",
        "relevant_keywords": ["不喜欢", "讨厌", "食物"],
        "expected_types": ["preference"],
        "test_memory": "用户不喜欢吃香菜和榴莲，对海鲜过敏"
    },
    {
        "id": "negation_002",
        "query": "用户不擅长什么",
        "type": "preference",
        "relevant_keywords": ["不擅长", "不会", "困难"],
        "expected_types": ["preference"],
        "test_memory": "用户不擅长处理财务数据，对数字不敏感"
    },
    
    # 时间范围查询
    {
        "id": "timerange_001",
        "query": "用户2024年做了什么",
        "type": "temporal",
        "relevant_keywords": ["2024", "去年", "工作"],
        "expected_types": ["fact"],
        "test_memory": "用户在2024年完成了公司内部管理系统开发"
    },
    {
        "id": "timerange_002",
        "query": "用户这周的计划是什么",
        "type": "temporal",
        "relevant_keywords": ["这周", "计划", "安排"],
        "expected_types": ["task_state"],
        "test_memory": "用户这周计划完成API文档编写和代码评审"
    },
    
    # 模糊查询测试
    {
        "id": "fuzzy_001",
        "query": "用户的hangzhou联系方式",
        "type": "fact",
        "relevant_keywords": ["杭州", "联系", "电话"],
        "expected_types": ["fact"],
        "test_memory": "用户在杭州的联系电话是138xxxx1234"
    },
    {
        "id": "fuzzy_002",
        "query": "用户Phoebe的项目",
        "type": "entity",
        "relevant_keywords": ["Phoebe", "项目"],
        "expected_types": ["entity", "task_state"],
        "test_memory": "用户和Phoebe一起负责AI平台的架构设计"
    },
    
    # 决策类查询
    {
        "id": "decision_001",
        "query": "用户为什么选择这个方案",
        "type": "decision",
        "relevant_keywords": ["选择", "原因", "决定", "方案"],
        "expected_types": ["decision"],
        "test_memory": "用户选择React是因为它的生态完善且学习曲线平缓"
    },
    {
        "id": "decision_002",
        "query": "用户做过什么重要决定",
        "type": "decision",
        "relevant_keywords": ["决定", "选择", "决策", "重要"],
        "expected_types": ["decision"],
        "test_memory": "用户决定从上海搬到北京发展，已入职新公司"
    },
    
    # 经验教训查询
    {
        "id": "lesson_001",
        "query": "用户从错误中学到什么",
        "type": "lesson",
        "relevant_keywords": ["错误", "教训", "学习", "经验"],
        "expected_types": ["lesson"],
        "test_memory": "用户从数据库性能问题中学到要提前做索引优化"
    },
    {
        "id": "lesson_002",
        "query": "用户有什么开发经验",
        "type": "lesson",
        "relevant_keywords": ["经验", "教训", "总结"],
        "expected_types": ["lesson"],
        "test_memory": "用户总结出代码审查可以显著减少线上bug"
    },
]

# 评估指标计算
def calculate_recall(results: List[dict], test_case: dict) -> float:
    """计算Recall@K"""
    keywords = test_case.get("relevant_keywords", [])
    relevant_count = 0
    
    for r in results:
        content = r.get("content", "").lower()
        # 检查结果是否包含相关关键词
        for kw in keywords:
            if kw.lower() in content:
                relevant_count += 1
                break
    
    return relevant_count / max(1, len(keywords))


def calculate_mrr(results: List[dict], test_case: dict) -> float:
    """计算MRR（Mean Reciprocal Rank）"""
    keywords = test_case.get("relevant_keywords", [])
    
    for i, r in enumerate(results):
        content = r.get("content", "").lower()
        for kw in keywords:
            if kw.lower() in content:
                return 1.0 / (i + 1)
    
    return 0.0


def calculate_ndcg(results: List[dict], test_case: dict, k: int = 5) -> float:
    """计算NDCG@K"""
    keywords = test_case.get("relevant_keywords", [])
    
    dcg = 0.0
    for i, r in enumerate(results[:k]):
        content = r.get("content", "").lower()
        relevance = 0
        for kw in keywords:
            if kw.lower() in content:
                relevance = 1
                break
        dcg += relevance / (i + 1)
    
    # IDCG（理想情况下的DCG）
    idcg = sum(1.0 / (i + 1) for i in range(min(len(keywords), k)))
    
    if idcg == 0:
        return 0.0
    
    return dcg / idcg


def calculate_relevance_score(results: List[dict], test_case: dict) -> float:
    """计算综合相关性分数（0-1）"""
    keywords = test_case.get("relevant_keywords", [])
    if not keywords:
        return 0.0
    
    score = 0.0
    for r in results[:3]:  # 只看前3个结果
        content = r.get("content", "").lower()
        matched = sum(1 for kw in keywords if kw.lower() in content)
        score += matched / len(keywords)
    
    return min(1.0, score / 3.0)


class BenchmarkSuite:
    """
    Benchmark评测套件
    
    用法：
    suite = BenchmarkSuite()
    results = suite.run_all()
    suite.print_report()
    """
    
    def __init__(self, test_set: List[dict] = None):
        self.test_set = test_set or BENCHMARK_TESTS
        self.results = []
        self.db = None
    
    def _get_db(self):
        """懒加载数据库"""
        if self.db is None:
            from memory_main import get_db
            self.db = get_db()
        return self.db
    
    def setup_phase(self) -> List[str]:
        """
        【P0修复】设置阶段：存储测试记忆
        
        Returns:
            存储的测试记忆ID列表（用于后续清理）
        """
        db = self._get_db()
        stored_ids = []
        
        print("  [Setup] 存储测试记忆...")
        for test in self.test_set:
            if "test_memory" in test:
                memory_content = test["test_memory"]
                result = db.store({
                    "content": memory_content,
                    "type": test.get("type", "fact"),
                    "importance": 0.9,
                    "source": f"benchmark_{test['id']}"
                })
                if result:
                    # 存储成功，记录source便于后续清理
                    stored_ids.append(f"benchmark_{test['id']}")
        
        print(f"  [Setup] 已存储 {len(stored_ids)} 条测试记忆")
        return stored_ids
    
    def teardown_phase(self, source_ids: List[str]):
        """
        【P0修复】清理阶段：删除测试记忆
        
        Args:
            source_ids: 需要删除的记忆source列表
        """
        if not source_ids:
            return
        
        db = self._get_db()
        print(f"  [Teardown] 清理 {len(source_ids)} 条测试记忆...")
        
        # 通过source字段查找并删除测试记忆
        for source in source_ids:
            try:
                # 搜索并删除
                results = db.search(source.replace("benchmark_", ""), limit=10)
                for r in results:
                    if r.get("source") == source:
                        db.delete(r.get("id"))
            except Exception:
                pass
        
        print("  [Teardown] 清理完成")
    
    def run_single(self, test_case: dict, limit: int = 5) -> dict:
        """运行单个测试用例"""
        db = self._get_db()
        query = test_case["query"]
        
        start_time = time.time()
        
        # 执行搜索
        try:
            results = db.search_rrf(query, limit=limit)
        except Exception as e:
            results = []
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        # 计算指标
        recall = calculate_recall(results, test_case)
        mrr = calculate_mrr(results, test_case)
        ndcg = calculate_ndcg(results, test_case)
        relevance = calculate_relevance_score(results, test_case)
        
        return {
            "test_id": test_case["id"],
            "query": query,
            "type": test_case["type"],
            "results_count": len(results),
            "latency_ms": elapsed_ms,
            "recall": recall,
            "mrr": mrr,
            "ndcg": ndcg,
            "relevance": relevance,
            "top_result": results[0].get("content", "")[:50] if results else None
        }
    
    def run_all(self, limit: int = 5) -> List[dict]:
        """运行所有测试用例（自动设置和清理测试数据）"""
        print(f"开始运行 {len(self.test_set)} 个测试用例...")
        
        # 【P0修复】设置阶段：存储测试记忆
        test_memory_ids = self.setup_phase()
        
        try:
            results = []
            for i, test in enumerate(self.test_set):
                result = self.run_single(test, limit=limit)
                results.append(result)
                print(f"  [{i+1}/{len(self.test_set)}] {test['id']}: MRR={result['mrr']:.2f}, NDCG={result['ndcg']:.2f}")
            
            self.results = results
            return results
            
        finally:
            # 【P0修复】清理阶段：删除测试记忆
            self.teardown_phase(test_memory_ids)
    
    def get_summary(self) -> dict:
        """获取评测摘要"""
        if not self.results:
            return {}
        
        total = len(self.results)
        
        # 按类型分组
        by_type = {}
        for r in self.results:
            t = r["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(r)
        
        # 计算各维度平均
        def avg(lst, key):
            return sum(x[key] for x in lst) / max(1, len(lst))
        
        type_scores = {}
        for t, items in by_type.items():
            type_scores[t] = {
                "count": len(items),
                "avg_mrr": avg(items, "mrr"),
                "avg_ndcg": avg(items, "ndcg"),
                "avg_latency": avg(items, "latency_ms")
            }
        
        return {
            "total_tests": total,
            "overall": {
                "avg_mrr": avg(self.results, "mrr"),
                "avg_ndcg": avg(self.results, "ndcg"),
                "avg_latency": avg(self.results, "latency_ms"),
                "avg_relevance": avg(self.results, "relevance")
            },
            "by_type": type_scores
        }
    
    def print_report(self):
        """打印评测报告"""
        summary = self.get_summary()
        
        print()
        print("=" * 60)
        print("   Claw Memory Benchmark 评测报告")
        print("=" * 60)
        print()
        
        overall = summary.get("overall", {})
        print(f"总体评分:")
        print(f"  MRR (Mean Reciprocal Rank):     {overall.get('avg_mrr', 0):.3f}")
        print(f"  NDCG@5:                         {overall.get('avg_ndcg', 0):.3f}")
        print(f"  平均延迟:                        {overall.get('avg_latency', 0):.1f}ms")
        print(f"  相关性得分:                      {overall.get('avg_relevance', 0):.3f}")
        print()
        
        print("按类型评分:")
        by_type = summary.get("by_type", {})
        for t, scores in by_type.items():
            print(f"  [{t}] MRR={scores['avg_mrr']:.3f}, NDCG={scores['avg_ndcg']:.3f}, 样本数={scores['count']}")
        
        print()
        print("=" * 60)
        
        # 目标对比
        print()
        print("目标对比:")
        print(f"  Mem0 LOCOMO Benchmark: ~0.669 (66.9%)")
        print(f"  当前 MRR:                {overall.get('avg_mrr', 0):.3f} ({overall.get('avg_mrr', 0)*100:.1f}%)")
        print(f"  差距:                    {(0.669 - overall.get('avg_mrr', 0))*100:.1f}%")
    
    def save_results(self, path: str = None):
        """保存结果到文件"""
        if path is None:
            path = Path(__file__).parent / f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "summary": self.get_summary(),
            "results": self.results
        }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到: {path}")


def run_benchmark():
    """便捷函数：运行完整评测"""
    suite = BenchmarkSuite()
    suite.run_all()
    suite.print_report()
    suite.save_results()
    return suite.get_summary()


if __name__ == "__main__":
    run_benchmark()
