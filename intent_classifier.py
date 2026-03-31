"""
Claw Memory 意图分类器
识别查询类型并动态调整检索策略
"""
import re
from typing import Dict, List, Tuple, Optional
from enum import Enum

class QueryIntent(str, Enum):
    """查询意图枚举"""
    FACT = "fact"
    PREFERENCE = "preference"
    NEGATION = "negation"  # 否定查询
    TEMPORAL = "temporal"
    ENTITY = "entity"
    RELATION = "relation"
    DECISION = "decision"
    LESSON = "lesson"
    FUZZY = "fuzzy"  # 模糊/拼写错误
    MULTIHOP = "multihop"  # 多跳推理

class IntentClassifier:
    """意图分类器"""
    
    # 否定词列表
    NEGATION_WORDS = [
        "不", "没", "无", "非", "别", "不要", "不会", "不是",
        "讨厌", "反感", "拒绝", "避免", "排除",
        "从没", "从未", "从不", "从来不"
    ]
    
    # 否定模式
    NEGATION_PATTERNS = [
        r"不(是|喜欢|会|能|知道|想|愿|应该)",
        r"(没|无|非)常",
        r"(讨厌|反感|拒绝|避免)",
        r"从(没|未|不)有",
    ]
    
    # 时间词
    TEMPORAL_WORDS = [
        "以前", "以前", "过去", "曾经", "刚才",
        "最近", "近来", "近日", "这阵子", "这阵子",
        "将来", "未来", "以后", "今后", "未来",
        "今年", "去年", "明年", "本月", "上月",
        "这周", "上周", "下周", "今天", "昨天", "明天",
        "2024", "2025", "2026", "星期", "周一", "周末"
    ]
    
    # lesson关键词
    LESSON_WORDS = [
        "学", "教训", "经验", "总结", "明白", "懂得",
        "学到", "学会", "掌握", "理解", "发现",
        "错误", "失败", "问题", "反思", "复盘"
    ]
    
    # decision关键词
    DECISION_WORDS = [
        "选择", "决定", "决策", "取舍", "取舍",
        "为什么选", "为什么决定", "原因", "理由"
    ]
    
    # 多跳模式
    MULTIHOP_PATTERNS = [
        r"朋友的", r"同事的", r"老板的", r"家人的",
        r".+的.+的",  # X的Y的Z
    ]
    
    # 拼音-中文映射（常见）
    PINYIN_MAP = {
        "hangzhou": "杭州",
        "shanghai": "上海",
        "beijing": "北京",
        "guangzhou": "广州",
        "shenzhen": "深圳",
        "nanjing": "南京",
        "chengdu": "成都",
        "xian": "西安",
        "wuhan": "武汉",
        "hangzhou": "杭州"
    }
    
    def classify(self, query: str) -> Tuple[QueryIntent, float]:
        """
        分类查询意图
        
        Args:
            query: 用户查询
            
        Returns:
            (意图类型, 置信度)
        """
        query_lower = query.lower()
        
        # 1. 检查否定模式
        if self._is_negation(query):
            return QueryIntent.NEGATION, 0.9
        
        # 2. 检查多跳模式
        if self._is_multihop(query):
            return QueryIntent.MULTIHOP, 0.85
        
        # 3. 检查模糊/拼音
        if self._is_fuzzy(query):
            return QueryIntent.FUZZY, 0.8
        
        # 4. 检查时间词
        if self._is_temporal(query):
            return QueryIntent.TEMPORAL, 0.85
        
        # 5. 检查lesson
        if self._is_lesson(query):
            return QueryIntent.LESSON, 0.8
        
        # 6. 检查decision
        if self._is_decision(query):
            return QueryIntent.DECISION, 0.8
        
        # 7. 基于关键词的简单分类
        intent, score = self._keyword_classify(query)
        return intent, score
    
    def _is_negation(self, query: str) -> bool:
        """检查是否是否定查询"""
        for pattern in self.NEGATION_PATTERNS:
            if re.search(pattern, query):
                return True
        for word in self.NEGATION_WORDS:
            if word in query:
                return True
        return False
    
    def _is_multihop(self, query: str) -> bool:
        """检查是否是多跳查询"""
        for pattern in self.MULTIHOP_PATTERNS:
            if re.search(pattern, query):
                return True
        # 检查"X的Y的Z"模式
        if query.count("的") >= 2:
            return True
        return False
    
    def _is_fuzzy(self, query: str) -> bool:
        """检查是否包含拼写错误或拼音"""
        # 检查拼音
        for pinyin, chinese in self.PINYIN_MAP.items():
            if pinyin in query.lower():
                return True
        # 检查全角转半角
        if any(ord(c) > 127 and c.isascii() is False for c in query):
            # 包含非ASCII字符（可能是中文或全角）
            pass
        return False
    
    def _is_temporal(self, query: str) -> bool:
        """检查是否包含时间词"""
        for word in self.TEMPORAL_WORDS:
            if word in query:
                return True
        return False
    
    def _is_lesson(self, query: str) -> bool:
        """检查是否是lesson查询"""
        count = sum(1 for word in self.LESSON_WORDS if word in query)
        return count >= 2
    
    def _is_decision(self, query: str) -> bool:
        """检查是否是decision查询"""
        for word in self.DECISION_WORDS:
            if word in query:
                return True
        return False
    
    def _keyword_classify(self, query: str) -> Tuple[QueryIntent, float]:
        """基于关键词分类"""
        scores = {}
        
        # FACT
        fact_words = ["什么", "是谁", "在哪", "叫什么", "哪个"]
        scores[QueryIntent.FACT] = sum(1 for w in fact_words if w in query)
        
        # PREFERENCE
        pref_words = ["喜欢", "偏好", "爱", "想", "要"]
        scores[QueryIntent.PREFERENCE] = sum(1 for w in pref_words if w in query)
        
        # ENTITY
        entity_words = ["认识", "朋友", "同事", "使用", "工具"]
        scores[QueryIntent.ENTITY] = sum(1 for w in entity_words if w in query)
        
        # 找最高分
        if scores:
            best = max(scores.items(), key=lambda x: x[1])
            if best[1] > 0:
                return best[0], 0.7
        
        return QueryIntent.FACT, 0.5
    
    def expand_query(self, query: str) -> List[str]:
        """
        扩展查询（同义词、拼写纠正等）
        
        Args:
            query: 原始查询
            
        Returns:
            扩展后的查询列表
        """
        queries = [query]
        
        # 拼音纠正
        query_lower = query.lower()
        for pinyin, chinese in self.PINYIN_MAP.items():
            if pinyin in query_lower:
                expanded = query_lower.replace(pinyin, chinese)
                queries.append(expanded)
        
        # 否定查询处理 - 提取否定目标
        if self._is_negation(query):
            # "用户不喜欢什么" -> 添加"不喜欢"的肯定形式
            for neg_word in ["喜欢", "吃", "做"]:
                if neg_word in query:
                    queries.append(query.replace("不" + neg_word, neg_word))
                    queries.append(query.replace("不喜欢", "喜欢"))
        
        return queries
    
    def get_channel_weights(self, intent: QueryIntent) -> Dict[str, float]:
        """
        根据意图获取推荐通道权重
        
        Args:
            intent: 查询意图
            
        Returns:
            各通道权重字典
        """
        # 默认权重
        default = {
            "vector": 0.40,
            "bm25": 0.20,
            "importance": 0.15,
            "kg": 0.10,
            "temporal": 0.15
        }
        
        # 根据意图调整
        weights_map = {
            QueryIntent.NEGATION: {
                "vector": 0.25,
                "bm25": 0.35,  # 关键词更重要
                "importance": 0.10,
                "kg": 0.10,
                "temporal": 0.20
            },
            QueryIntent.TEMPORAL: {
                "vector": 0.30,
                "bm25": 0.20,
                "importance": 0.10,
                "kg": 0.10,
                "temporal": 0.30  # 时序权重提高
            },
            QueryIntent.LESSON: {
                "vector": 0.35,
                "bm25": 0.25,
                "importance": 0.15,
                "kg": 0.15,
                "temporal": 0.10
            },
            QueryIntent.MULTIHOP: {
                "vector": 0.30,
                "bm25": 0.15,
                "importance": 0.10,
                "kg": 0.35,  # KG通道最重要
                "temporal": 0.10
            },
            QueryIntent.FUZZY: {
                "vector": 0.45,  # 向量匹配更适合模糊
                "bm25": 0.25,
                "importance": 0.10,
                "kg": 0.05,
                "temporal": 0.15
            },
            QueryIntent.DECISION: {
                "vector": 0.35,
                "bm25": 0.25,
                "importance": 0.15,
                "kg": 0.15,
                "temporal": 0.10
            }
        }
        
        return weights_map.get(intent, default)


# 全局实例
_classifier = None

def get_classifier() -> IntentClassifier:
    """获取分类器实例"""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


def classify_query(query: str) -> Tuple[QueryIntent, float]:
    """快速分类接口"""
    return get_classifier().classify(query)


def expand_query(query: str) -> List[str]:
    """快速扩展查询接口"""
    return get_classifier().expand_query(query)
