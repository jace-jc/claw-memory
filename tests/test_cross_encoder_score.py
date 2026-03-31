"""
测试 P2-1: cross_encoder_score() 函数
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import warnings
warnings.filterwarnings("ignore")


def test_cross_encoder_score_function_exists():
    """测试 cross_encoder_score 函数存在"""
    from cross_encoder_rerank import cross_encoder_score
    assert callable(cross_encoder_score)
    print("✅ test_cross_encoder_score_function_exists")


def test_cross_encoder_score_with_dict_candidates():
    """测试使用字典格式的候选"""
    from cross_encoder_rerank import cross_encoder_score
    
    candidates = [
        {"id": "mem_001", "content": "用户住在上海"},
        {"id": "mem_002", "content": "用户喜欢Python"},
        {"id": "mem_003", "content": "用户工作于字节跳动"},
    ]
    
    scores = cross_encoder_score("用户住在哪个城市", candidates)
    
    # 返回格式检查
    assert isinstance(scores, list)
    assert all(isinstance(item, tuple) for item in scores)
    assert all(len(item) == 2 for item in scores)  # (doc_id, score)
    
    # 按分数降序
    score_values = [s for _, s in scores]
    assert score_values == sorted(score_values, reverse=True)
    
    # doc_id 检查
    doc_ids = [doc_id for doc_id, _ in scores]
    assert "mem_001" in doc_ids
    
    print("✅ test_cross_encoder_score_with_dict_candidates")


def test_cross_encoder_score_with_string_candidates():
    """测试使用字符串格式的候选"""
    from cross_encoder_rerank import cross_encoder_score
    
    candidates = [
        "用户住在上海",
        "用户喜欢Python",
        "用户工作于字节跳动"
    ]
    
    scores = cross_encoder_score("用户住在哪个城市", candidates)
    
    assert isinstance(scores, list)
    assert len(scores) == 3
    # 字符串格式时 doc_id 为 doc_0, doc_1, doc_2
    doc_ids = [doc_id for doc_id, _ in scores]
    assert "doc_0" in doc_ids
    
    print("✅ test_cross_encoder_score_with_string_candidates")


def test_cross_encoder_score_empty():
    """测试空输入"""
    from cross_encoder_rerank import cross_encoder_score
    
    scores = cross_encoder_score("测试", [])
    assert scores == []
    
    print("✅ test_cross_encoder_score_empty")


def test_cross_encoder_score_mixed_ids():
    """测试混合ID场景"""
    from cross_encoder_rerank import cross_encoder_score
    
    candidates = [
        {"content": "住在上海"},
        "住在杭州",  # 字符串无ID
        {"id": "mem_abc", "content": "住在深圳"},
    ]
    
    scores = cross_encoder_score("住在哪里", candidates)
    
    assert len(scores) == 3
    doc_ids = [doc_id for doc_id, _ in scores]
    assert "doc_1" in doc_ids  # 字符串格式
    assert "mem_abc" in doc_ids  # dict with id
    
    print("✅ test_cross_encoder_score_mixed_ids")


def test_cross_encoder_score_scores_method():
    """测试 CrossEncoderReranker.scores() 方法"""
    from cross_encoder_rerank import CrossEncoderReranker
    
    reranker = CrossEncoderReranker()
    
    candidates = [
        {"id": "a", "content": "hello world"},
        {"id": "b", "content": "goodbye world"},
    ]
    
    # 不要求模型加载成功，只检查方法签名
    result = reranker.scores("world", candidates)
    assert isinstance(result, list)
    assert all(isinstance(item, tuple) for item in result)
    
    print("✅ test_cross_encoder_score_scores_method")


def test_get_reranker():
    """测试全局单例"""
    from cross_encoder_rerank import get_reranker, CrossEncoderReranker
    
    r1 = get_reranker()
    r2 = get_reranker()
    
    assert isinstance(r1, CrossEncoderReranker)
    assert r1 is r2  # 同一个实例
    
    print("✅ test_get_reranker")


if __name__ == "__main__":
    tests = [
        test_cross_encoder_score_function_exists,
        test_cross_encoder_score_with_dict_candidates,
        test_cross_encoder_score_with_string_candidates,
        test_cross_encoder_score_empty,
        test_cross_encoder_score_mixed_ids,
        test_cross_encoder_score_scores_method,
        test_get_reranker,
    ]
    
    passed = 0
    failed = 0
    
    print("运行 P2-1 Cross-Encoder 测试...\n")
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
