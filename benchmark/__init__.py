"""
Benchmark package
Phase 4: re-exports from original locations
"""
from benchmark.benchmark_suite import (
    BenchmarkSuite, BENCHMARK_TESTS, BENCHMARK_TESTS_EXTENDED, BENCHMARK_TESTS_COMPREHENSIVE,
    run_benchmark, calculate_recall, calculate_mrr, calculate_ndcg, calculate_relevance_score
)
from benchmark.benchmark_runner import (
    run_full_benchmark, BenchmarkResult, BenchmarkSuiteResult,
    RecallBenchmark, QualityBenchmark
)
from benchmark.benchmark_improvements import (
    test_weibull_decay, test_version_history, test_attachment_store,
    test_parallel_search, test_cross_encoder, test_end_to_end_mrr,
    main as benchmark_improvements_main
)

__all__ = [
    "BenchmarkSuite",
    "BENCHMARK_TESTS",
    "BENCHMARK_TESTS_EXTENDED",
    "BENCHMARK_TESTS_COMPREHENSIVE",
    "run_benchmark",
    "calculate_recall",
    "calculate_mrr",
    "calculate_ndcg",
    "calculate_relevance_score",
    "run_full_benchmark",
    "BenchmarkResult",
    "BenchmarkSuiteResult",
    "RecallBenchmark",
    "QualityBenchmark",
    "test_weibull_decay",
    "test_version_history",
    "test_attachment_store",
    "test_parallel_search",
    "test_cross_encoder",
    "test_end_to_end_mrr",
    "benchmark_improvements_main",
]
