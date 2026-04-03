"""
Extract package: Memory extraction utilities
Phase 4: re-exports from original locations
"""
from memory_extract import extract_from_messages, is_noise, quick_extract, deep_extract
from chinese_extract import ChineseEntityExtractor, get_chinese_extractor
from auto_extract import AutoExtractor, get_auto_extractor, auto_extract

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
