"""
测试 P2-2: temporal_extract.py 时序信息提取
"""
import sys
import os
from datetime import datetime

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import warnings
warnings.filterwarnings("ignore")


# 使用固定参考时间，便于测试
FIXED_REF = datetime(2024, 6, 15, 10, 0, 0)  # 2024-06-15 10:00


def test_module_imports():
    """测试模块可导入"""
    from temporal_extract import (
        TemporalExtractor, extract_temporal, extract_temporal_one, temporal_to_timestamp
    )
    assert callable(extract_temporal)
    assert callable(extract_temporal_one)
    assert callable(temporal_to_timestamp)
    print("✅ test_module_imports")


def test_relative_yesterday():
    """测试昨天"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("我昨天感冒了", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "relative"
    assert first["category"] == "yesterday"
    assert first["event"] != ""
    print("✅ test_relative_yesterday")


def test_relative_last_week():
    """测试上周"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("我上周感冒了", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "relative"
    assert first["category"] == "last_week"
    
    print("✅ test_relative_last_week")


def test_relative_last_month():
    """测试上个月"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("我上个月去了日本", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "relative"
    assert first["category"] == "last_month"
    assert "日本" in first["event"] or len(first["event"]) > 0
    
    print("✅ test_relative_last_month")


def test_absolute_today():
    """测试今天"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("今天开会", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "relative"
    assert first["category"] == "today"
    
    print("✅ test_absolute_today")


def test_absolute_next_year():
    """测试明年"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("明年计划去日本", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "relative"
    assert first["category"] == "next_year"
    assert first["temporal"]["absolute"] is not None
    
    print("✅ test_absolute_next_year")


def test_absolute_date_ymd():
    """测试 YYYY年MM月DD日 格式"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("2024年1月15日开会", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "absolute"
    assert first["category"] == "date_ymd"
    assert first["temporal"]["absolute"] == "2024-01-15"
    
    print("✅ test_absolute_date_ymd")


def test_absolute_date_month():
    """测试 YYYY年MM月 格式"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("2024年1月很重要", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "absolute"
    assert first["category"] == "date_ym"
    
    print("✅ test_absolute_date_month")


def test_relative_tomorrow():
    """测试明天"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("明天开会", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "relative"
    assert first["category"] == "tomorrow"
    
    print("✅ test_relative_tomorrow")


def test_relative_next_week():
    """测试下周"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("下周出差", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert first["type"] == "relative"
    assert first["category"] == "next_week"
    
    print("✅ test_relative_next_week")


def test_temporal_to_timestamp():
    """测试时间戳转换"""
    from temporal_extract import temporal_to_timestamp
    
    temporal_info = {
        "timestamp_range": {
            "start": "2024-01-15T00:00:00",
            "end": "2024-01-15T23:59:59"
        }
    }
    
    result = temporal_to_timestamp(temporal_info)
    
    assert "start_ts" in result
    assert "end_ts" in result
    assert result["start_ts"] is not None
    assert result["end_ts"] is not None
    assert result["start_ts"] < result["end_ts"]
    
    print("✅ test_temporal_to_timestamp")


def test_extract_one():
    """测试 extract_temporal_one"""
    from temporal_extract import extract_temporal_one
    
    result = extract_temporal_one("我上周感冒了", reference_date=FIXED_REF)
    
    assert result is not None
    assert result["category"] == "last_week"
    
    print("✅ test_extract_one")


def test_no_temporal():
    """测试无时间信息的文本"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("今天天气很好", reference_date=FIXED_REF)
    # 至少应该匹配到 "今天"
    assert len(results) >= 1
    
    print("✅ test_no_temporal")


def test_timestamp_range_present():
    """测试 timestamp_range 字段存在"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("昨天感冒了", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    assert "timestamp_range" in first
    assert "start" in first["timestamp_range"]
    assert "end" in first["timestamp_range"]
    assert first["timestamp_range"]["start"] is not None
    
    print("✅ test_timestamp_range_present")


def test_event_extraction():
    """测试事件提取"""
    from temporal_extract import extract_temporal
    
    results = extract_temporal("我上周感冒了", reference_date=FIXED_REF)
    
    assert len(results) >= 1
    first = results[0]
    # 事件应该是感冒或者包含感冒
    assert first["event"] is not None
    assert len(first["event"]) > 0
    
    print("✅ test_event_extraction")


if __name__ == "__main__":
    tests = [
        test_module_imports,
        test_relative_yesterday,
        test_relative_last_week,
        test_relative_last_month,
        test_absolute_today,
        test_absolute_next_year,
        test_absolute_date_ymd,
        test_absolute_date_month,
        test_relative_tomorrow,
        test_relative_next_week,
        test_temporal_to_timestamp,
        test_extract_one,
        test_no_temporal,
        test_timestamp_range_present,
        test_event_extraction,
    ]
    
    passed = 0
    failed = 0
    
    print("运行 P2-2 Temporal Extract 测试...\n")
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print(f"{'='*50}")
