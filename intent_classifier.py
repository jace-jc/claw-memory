"""
Claw Memory 意图分类器
识别查询类型并动态调整检索策略
"""
import re
from typing import Dict, List, Tuple, Optional
from enum import Enum

class QueryIntent(str, Enum):
    """查询意图枚举"""
    # 基础类型
    FACT = "fact"  # 事实查询
    PREFERENCE = "preference"  # 偏好查询
    NEGATION = "negation"  # 否定查询
    TEMPORAL = "temporal"  # 时序查询
    ENTITY = "entity"  # 实体查询
    RELATION = "relation"  # 关系查询
    DECISION = "decision"  # 决策查询
    LESSON = "lesson"  # 经验教训
    FUZZY = "fuzzy"  # 模糊/拼写错误
    MULTIHOP = "multihop"  # 多跳推理
    # 新增类型 (扩展到15种)
    HABIT = "habit"  # 习惯查询
    SKILL = "skill"  # 技能查询
    GOAL = "goal"  # 目标查询
    HEALTH = "health"  # 健康查询
    WORK = "work"  # 工作查询

class IntentClassifier:
    """意图分类器"""
    
    # 否定词列表
    NEGATION_WORDS = [
        "不", "没", "无", "非", "别", "不要", "不会", "不是",
        "讨厌", "反感", "拒绝", "避免", "排除",
        "从没", "从未", "从不", "从来不",
        # 新增
        "不擅长", "不会", "不精", "不熟悉", "不习惯",
        "难以", "困难", "害怕", "担心", "顾虑"
    ]
    
    # 否定模式
    NEGATION_PATTERNS = [
        r"不(是|喜欢|会|能|知道|想|愿|应该|擅长)",
        r"(没|无|非)常",
        r"(讨厌|反感|拒绝|避免)",
        r"从(没|未|不)有",
        r"不.*什么$",  # 不擅长什么
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
        "错误", "失败", "问题", "反思", "复盘",
        # 新增
        "知道", "清楚", "了解", "体会", "领悟",
        "NOTE", "注意", "提醒", "警告"
    ]
    
    # decision关键词
    DECISION_WORDS = [
        "选择", "决定", "决策", "取舍", "取舍",
        "为什么选", "为什么决定", "原因", "理由",
        # 新增
        "最终", "最后", "采取", "采用", "用了",
        "用过", "用了什么"
    ]
    
    # 多跳模式
    MULTIHOP_PATTERNS = [
        r"朋友的", r"同事的", r"老板的", r"家人的",
        r".+的.+的",  # X的Y的Z
        r"使用的技术",  # A使用的B
    ]
    
    # 新增意图关键词
    HABIT_WORDS = [
        "习惯", "通常", "平时", "日常", "总是",
        "经常", "往往", "一般会", "动不动"
    ]
    
    SKILL_WORDS = [
        "会", "擅长", "精通", "掌握", "熟悉",
        "会用", "会做", "会写", "会说", "能力", "技能"
    ]
    
    GOAL_WORDS = [
        "目标", "计划", "想要", "希望", "打算",
        "愿望", "志向", "梦想", "将要", "未来想"
    ]
    
    HEALTH_WORDS = [
        "健康", "身体", "体检", "医生", "病",
        "过敏", "体质", "不舒服", "疼", "痛"
    ]
    
    WORK_WORDS = [
        "工作", "职位", "公司", "上班", "加班",
        "下班", "同事", "领导", "老板", "项目"
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
        
        # 3. 检查lesson（优先于关键词分类）
        if self._is_lesson(query):
            return QueryIntent.LESSON, 0.85
        
        # 4. 检查时间词
        if self._is_temporal(query):
            return QueryIntent.TEMPORAL, 0.85
        
        # 5. 检查模糊/拼音
        if self._is_fuzzy(query):
            return QueryIntent.FUZZY, 0.8
        
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
        # 经验、教训等直接触发
        if any(word in query for word in ["经验", "教训", "学到", "学会"]):
            return True
        count = sum(1 for word in self.LESSON_WORDS if word in query)
        return count >= 1
    
    def _is_decision(self, query: str) -> bool:
        """检查是否是decision查询"""
        for word in self.DECISION_WORDS:
            if word in query:
                return True
        return False
    
    def _keyword_classify(self, query: str) -> Tuple[QueryIntent, float]:
        """基于关键词分类"""
        scores = {}
        
        # 优先级：更具体的意图优先
        # 权重：具体意图2分，通用意图1分
        
        # HABIT (具体)
        habit_score = sum(2 for w in self.HABIT_WORDS if w in query)
        scores[QueryIntent.HABIT] = habit_score
        
        # SKILL (具体)
        skill_score = sum(2 for w in self.SKILL_WORDS if w in query)
        scores[QueryIntent.SKILL] = skill_score
        
        # GOAL (具体)
        goal_score = sum(2 for w in self.GOAL_WORDS if w in query)
        scores[QueryIntent.GOAL] = goal_score
        
        # HEALTH (具体)
        health_score = sum(2 for w in self.HEALTH_WORDS if w in query)
        scores[QueryIntent.HEALTH] = health_score
        
        # WORK (具体)
        work_score = sum(2 for w in self.WORK_WORDS if w in query)
        scores[QueryIntent.WORK] = work_score
        
        # FACT (通用意图，分数较低)
        fact_words = ["什么", "是谁", "在哪", "叫什么", "哪个"]
        scores[QueryIntent.FACT] = sum(1 for w in fact_words if w in query)
        
        # PREFERENCE
        pref_words = ["喜欢", "偏好", "爱", "想", "要"]
        scores[QueryIntent.PREFERENCE] = sum(1 for w in pref_words if w in query)
        
        # ENTITY
        entity_words = ["认识", "朋友", "同事", "使用", "工具"]
        scores[QueryIntent.ENTITY] = sum(1 for w in entity_words if w in query)
        
        # 找最高分（优先返回具体意图）
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                # 找所有得最高分的意图
                best_intents = [k for k, v in scores.items() if v == max_score]
                # 优先返回具体意图
                for intent in [QueryIntent.HABIT, QueryIntent.SKILL, QueryIntent.GOAL, 
                               QueryIntent.HEALTH, QueryIntent.WORK, QueryIntent.FACT]:
                    if intent in best_intents:
                        return intent, 0.75
        
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
        
        # 同义词扩展
        synonyms = {
            "经验": ["总结", "知道", "了解", "教训", "学"],
            "教训": ["错误", "失败", "问题", "反思"],
            "开发经验": ["开发", "代码", "编程", "开发过"],
            "擅长": ["会", "能", "精", "熟悉"],
            "不擅长": ["不会", "难以", "困难"],
            "做过": ["做", "完成", "进行", "参与"],
        }
        
        for word, syns in synonyms.items():
            if word in query:
                for syn in syns:
                    expanded = query.replace(word, syn)
                    if expanded not in queries:
                        queries.append(expanded)
        
        # 否定查询处理 - 提取否定目标
        if self._is_negation(query):
            # "用户不喜欢什么" -> 添加"不喜欢"的肯定形式
            for neg_word in ["喜欢", "吃", "做"]:
                if neg_word in query:
                    queries.append(query.replace("不" + neg_word, neg_word))
                    queries.append(query.replace("不喜欢", "喜欢"))
            
            # "不擅长什么" -> "擅长"
            if "不擅长" in query:
                queries.append(query.replace("不擅长", "擅长"))
                queries.append(query.replace("不擅长什么", "什么"))
        
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
