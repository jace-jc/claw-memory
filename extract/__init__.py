"""
Extract package: Memory extraction utilities
Phase 4: re-exports from original locations
"""
from extract.memory_extract import extract_from_messages, is_noise, quick_extract, deep_extract
from extract.chinese_extract import ChineseEntityExtractor, get_chinese_extractor
from extract.auto_extract import AutoExtractor, get_auto_extractor, auto_extract

__all__ = [
    "extract_from_messages",
    "is_noise",
    "quick_extract",
    "deep_extract",
    "ChineseEntityExtractor",
    "get_chinese_extractor",
    "AutoExtractor",
    "get_auto_extractor",
    "auto_extract",
]
