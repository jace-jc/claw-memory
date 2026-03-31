"""
Claw Memory 测试套件 - 独立运行版本
直接导入需要的模块，不依赖包结构
"""
import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import warnings
warnings.filterwarnings("ignore")


def test_api_response():
    """测试响应格式统一"""
    from memory_main import api_response
    
    # 成功响应
    success_resp = api_response(success=True, data={"key": "value"})
    assert success_resp["success"] == True
    assert "data" in success_resp
    
    # 失败响应
    error_resp = api_response(success=False, error="错误信息")
    assert error_resp["success"] == False
    assert "error" in error_resp
    print("✅ test_api_response 通过")


def test_intent_negation():
    """测试否定查询识别"""
    from intent_classifier import classify_query
    
    intent, conf = classify_query("用户不喜欢什么")
    assert intent.value == "negation", f"Expected negation, got {intent.value}"
    assert conf > 0.5
    print("✅ test_intent_negation 通过")


def test_intent_temporal():
    """测试时序查询识别"""
    from intent_classifier import classify_query
    
    intent, conf = classify_query("用户最近在做什么")
    assert intent.value == "temporal", f"Expected temporal, got {intent.value}"
    print("✅ test_intent_temporal 通过")


def test_query_expansion():
    """测试查询扩展"""
    from intent_classifier import expand_query
    
    queries = expand_query("用户的hangzhou联系方式")
    assert len(queries) > 1, f"Expected multiple queries, got {len(queries)}"
    assert any("杭州" in q for q in queries), "Expected '杭州' in expanded queries"
    print("✅ test_query_expansion 通过")


def test_memory_type_enum():
    """测试内存类型枚举"""
    from memory_types import MemoryType, Scope
    
    assert MemoryType.FACT == "fact"
    assert Scope.USER == "user"
    print("✅ test_memory_type_enum 通过")


def test_memory_dataclass():
    """测试Memory数据结构"""
    from memory_types import Memory, MemoryType
    
    mem = Memory(
        id="test123",
        content="测试记忆",
        type=MemoryType.FACT,
        importance=0.8
    )
    
    assert mem.id == "test123"
    assert mem.content == "测试记忆"
    assert mem.type == MemoryType.FACT
    print("✅ test_memory_dataclass 通过")


def test_config():
    """测试配置存在"""
    from memory_config import CONFIG
    
    assert CONFIG is not None
    assert "db_path" in CONFIG
    assert "embed_model" in CONFIG
    print("✅ test_config 通过")


def test_benchmark_tests_exist():
    """测试基准用例存在"""
    from benchmark_suite import BENCHMARK_TESTS, BENCHMARK_TESTS_EXTENDED
    
    assert len(BENCHMARK_TESTS) >= 12, f"Expected 12+ base tests, got {len(BENCHMARK_TESTS)}"
    assert len(BENCHMARK_TESTS_EXTENDED) >= 12, f"Expected 12+ extended tests, got {len(BENCHMARK_TESTS_EXTENDED)}"
    print("✅ test_benchmark_tests_exist 通过")


def test_mrr_calculation():
    """测试MRR计算"""
    from benchmark_suite import calculate_mrr
    
    test_case = {
        "relevant_keywords": ["张三", "名字"]
    }
    
    results = [
        {"content": "用户名字叫张三"},
        {"content": "用户在字节工作"}
    ]
    
    mrr = calculate_mrr(results, test_case)
    assert mrr == 1.0, f"Expected MRR=1.0, got {mrr}"  # 第一个结果就命中
    print("✅ test_mrr_calculation 通过")


if __name__ == "__main__":
    print("运行Claw Memory测试套件...\n")
    
    tests = [
        test_api_response,
        test_intent_negation,
        test_intent_temporal,
        test_query_expansion,
        test_memory_type_enum,
        test_memory_dataclass,
        test_config,
        test_benchmark_tests_exist,
        test_mrr_calculation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print(f"{'='*50}")
