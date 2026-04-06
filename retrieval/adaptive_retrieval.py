"""
自适应检索判断模块

判断查询是否需要触发记忆检索

参考 memory-lancedb-pro 的 adaptive-retrieval 设计
"""
import re
from typing import Dict, List, Optional


# 记忆关键词（中英文）
MEMORY_KEYWORDS = [
    # 中文
    "记得", "之前", "上次", "过去", "曾经", "以前",
    "我的", "我之前", "我记得", "你记得吗",
    "曾经说", "过去说", "之前提到", "上次说",
    # 英文
    "remember", "before", "previously", "last time",
    "previously mentioned", "you said earlier",
    "my", "I previously", "I said before"
]

# 跳过的查询模式
SKIP_PATTERNS = [
    # 打招呼
    r"^(hi|hello|hey|你好|您好|嗨|哈喽)",
    # 斜杠命令
    r"^/",
    # 简单确认
    r"^(ok|好|yes|yeah|yep|okay|好的|可以)",
    # 纯表情
    r"^[😀-🙏]+$",
    # 简单感谢
    r"^(thanks|thank you|谢谢)",
]

# 强制检索的查询类型
FORCE_RETRIEVAL_PATTERNS = [
    r"(记得|记住|回忆|想起)",
    r"(之前|上次|过去|曾经|以前).*说",
    r"(我的|我之前|曾说过)",
]


class AdaptiveRetrieval:
    """
    自适应检索判断器
    
    判断逻辑：
    1. 如果匹配跳过模式 → 不检索
    2. 如果匹配强制检索模式 → 强制检索
    3. 如果查询长度足够（中文≥6字符，英文≥15字符）→ 检索
    4. 否则 → 不检索
    """
    
    def __init__(self, 
                 min_chinese_len: int = 6,
                 min_english_len: int = 15):
        """
        Args:
            min_chinese_len: 中文最小长度
            min_english_len: 英文最小长度
        """
        self.min_chinese_len = min_chinese_len
        self.min_english_len = min_english_len
    
    def should_retrieve(self, query: str) -> bool:
        """
        判断查询是否需要触发记忆检索
        
        Args:
            query: 用户查询
            
        Returns:
            True if should retrieve, False otherwise
        """
        query = query.strip()
        if not query:
            return False
        
        # 1. 检查跳过模式
        if self._matches_skip_pattern(query):
            return False
        
        # 2. 检查强制检索模式
        if self._matches_force_retrieval(query):
            return True
        
        # 3. 检查长度阈值
        if self._exceeds_length_threshold(query):
            return True
        
        # 4. 检查是否包含记忆关键词
        if self._contains_memory_keywords(query):
            return True
        
        # 【P0修复】短查询不跳过，改用BM25搜索
        # 原来: return False (导致短查询返回空)
        # 现在: return True (让BM25接管短查询)
        return True
    
    def _matches_skip_pattern(self, query: str) -> bool:
        """检查是否匹配跳过模式"""
        query_lower = query.lower()
        for pattern in SKIP_PATTERNS:
            if re.search(pattern, query_lower):
                return True
        return False
    
    def _matches_force_retrieval(self, query: str) -> bool:
        """检查是否匹配强制检索模式"""
        for pattern in FORCE_RETRIEVAL_PATTERNS:
            if re.search(pattern, query):
                return True
        return False
    
    def _exceeds_length_threshold(self, query: str) -> bool:
        """检查是否超过长度阈值"""
        # 统计中英文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', query))
        english_words = len(re.findall(r'[a-zA-Z]+', query))
        
        # 如果包含足够的中文或英文
        if chinese_chars >= self.min_chinese_len:
            return True
        if english_words >= self.min_english_len:
            return True
        
        return False
    
    def _contains_memory_keywords(self, query: str) -> bool:
        """检查是否包含记忆关键词"""
        query_lower = query.lower()
        for keyword in MEMORY_KEYWORDS:
            if keyword.lower() in query_lower:
                return True
        return False
    
    def get_reason(self, query: str) -> str:
        """
        获取判断理由
        
        Returns:
            判断原因描述
        """
        if not query.strip():
            return "空查询，跳过"
        
        if self._matches_skip_pattern(query):
            return "匹配跳过模式（打招呼/命令/确认/表情）"
        
        if self._matches_force_retrieval(query):
            return "匹配强制检索模式（记忆关键词）"
        
        if self._exceeds_length_threshold(query):
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', query))
            english_words = len(re.findall(r'[a-zA-Z]+', query))
            return f"长度达标（中文{ chinese_chars }字/英文{ english_words }词）"
        
        if self._contains_memory_keywords(query):
            return "包含记忆关键词"
        
        return "低于长度阈值，跳过"
    
    def classify_query_type(self, query: str) -> str:
        """
        分类查询类型
        
        Returns:
            查询类型：greeting/command/confirm/question/fact_query/memory_recall
        """
        query = query.strip().lower()
        
        # 打招呼
        if re.search(r"^(hi|hello|hey|你好|您好|嗨|哈喽)", query):
            return "greeting"
        
        # 命令
        if query.startswith("/"):
            return "command"
        
        # 确认
        if re.search(r"^(ok|好|yes|yeah|yep|okay|好的|可以|没问题)", query):
            return "confirm"
        
        # 简单提问
        if len(query) < 10:
            return "simple_question"
        
        # 记忆相关
        if self._contains_memory_keywords(query):
            return "memory_recall"
        
        # 事实查询
        if self._exceeds_length_threshold(query):
            return "fact_query"
        
        return "other"


# 全局单例
_adaptive_retrieval = None


def get_adaptive_retrieval() -> AdaptiveRetrieval:
    """获取自适应检索判断器单例"""
    global _adaptive_retrieval
    if _adaptive_retrieval is None:
        _adaptive_retrieval = AdaptiveRetrieval()
    return _adaptive_retrieval


def should_retrieve(query: str) -> bool:
    """快捷函数：判断是否需要检索"""
    return get_adaptive_retrieval().should_retrieve(query)


def get_retrieval_reason(query: str) -> str:
    """快捷函数：获取判断理由"""
    return get_adaptive_retrieval().get_reason(query)


def classify_query(query: str) -> str:
    """快捷函数：分类查询类型"""
    return get_adaptive_retrieval().classify_query_type(query)
