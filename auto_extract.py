"""
Claw Memory 自动提取模块
从对话中自动提取事实、偏好、决策
模仿 Mem0 的自动提取功能，但完全本地运行
"""
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import json


@dataclass
class ExtractedFact:
    """提取的事实"""
    type: str  # fact, preference, decision, lesson, goal
    content: str
    entities: List[str]
    confidence: float
    timestamp: str
    source: str  # conversation, explicit, inferred


class AutoExtractor:
    """
    自动提取器
    
    从对话中自动识别和提取：
    - 事实 (fact): "用户在北京工作"
    - 偏好 (preference): "用户喜欢喝咖啡"
    - 决策 (decision): "用户决定使用React"
    - 教训 (lesson): "用户从错误中学到了..."
    - 目标 (goal): "用户想要学习Python"
    """
    
    # 事实模式 (支持"用户"和"我")
    FACT_PATTERNS = [
        (r'(?:用户|我)(?:在|于|是|叫|住在)([^\s，,。]+)', 'location'),
        (r'(?:用户|我)(?:工作|任职|就职)于?([^\s，,。]+)', 'work'),
        (r'(?:用户|我).*?(?:使用|用)([^\s，,。]+)', 'tool'),
        (r'(?:用户|我)([^\s，,。]+)(?:岁|年龄)', 'age'),
        (r'(?:用户|我)(?:毕业[于]?)([^\s，,。]+)', 'education'),
        (r'(?:用户|我)(?:从事|做)([^\s，,。]+)', 'profession'),
    ]
    
    # 偏好模式 (支持"用户"和"我")
    PREFERENCE_PATTERNS = [
        (r'(?:用户|我).*?喜欢([^\s，,。]+)', 'like'),
        (r'(?:用户|我).*?讨厌([^\s，,。]+)', 'dislike'),
        (r'(?:用户|我).*?想要([^\s，,。]+)', 'want'),
        (r'(?:用户|我).*?倾向于([^\s，,。]+)', 'prefer'),
        (r'(?:用户|我).*?不(?:太?)?喜欢([^\s，,。]+)', 'not_like'),
        (r'(?:用户|我).*?(?:更?愿|比?较愿)意([^\s，,。]+)', 'prefer'),
    ]
    
    # 决策模式 (支持"用户"和"我")
    DECISION_PATTERNS = [
        (r'(?:用户|我).*?决定([^\s，,。]+)', 'decision'),
        (r'(?:用户|我).*?选择([^\s，,。]+)', 'decision'),
        (r'(?:用户|我).*?已[经]?采用([^\s，,。]+)', 'adopted'),
        (r'(?:用户|我).*?(?:将|会)使用([^\s，,。]+)', 'will_use'),
        (r'(?:用户|我).*?(?:准备|计划)(?:使用|采用)([^\s，,。]+)', 'plan_use'),
    ]
    
    # 目标模式 (支持"用户"和"我")
    GOAL_PATTERNS = [
        (r'(?:用户|我).*?想要([^\s，,。]+)', 'goal'),
        (r'(?:用户|我).*?希望([^\s，,。]+)', 'goal'),
        (r'(?:用户|我).*?的目标是([^\s，,。]+)', 'goal'),
        (r'(?:用户|我).*?打算([^\s，,。]+)', 'plan'),
        (r'(?:用户|我).*?正(?:在|准备)([^\s，,。]+)', 'in_progress'),
    ]
    
    # 教训模式 (支持"用户"和"我")
    LESSON_PATTERNS = [
        (r'(?:用户|我).*?从([^\s，,。]+)中学到', 'learned'),
        (r'(?:用户|我).*?(?:意识[到]?|发现)([^\s，,。]+)', 'discovered'),
        (r'(?:用户|我).*?(?:犯错|失误|失败)(?:于|在)([^\s，,。]+)', 'mistake'),
        (r'(?:用户|我).*?(?:经验|教训)(?:是|：)([^\s，,。]+)', 'lesson'),
    ]
    
    def __init__(self):
        self.last_extraction_time = None
        self.extraction_count = 0
    
    def extract_from_text(self, text: str, source: str = "conversation") -> List[ExtractedFact]:
        """
        从文本中提取所有事实
        
        Args:
            text: 输入文本
            source: 来源 (conversation, explicit, inferred)
            
        Returns:
            提取的事实列表
        """
        results = []
        
        # 提取事实
        for pattern, subtype in self.FACT_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                entity = match.group(1) if match.groups() else ""
                if entity and len(entity) > 1:
                    results.append(ExtractedFact(
                        type="fact",
                        content=f"用户{subtype}: {entity}",
                        entities=[entity],
                        confidence=0.85,
                        timestamp=datetime.now().isoformat(),
                        source=source
                    ))
        
        # 提取偏好
        for pattern, subtype in self.PREFERENCE_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                entity = match.group(1) if match.groups() else ""
                if entity and len(entity) > 1:
                    results.append(ExtractedFact(
                        type="preference",
                        content=f"用户{subtype}: {entity}",
                        entities=[entity],
                        confidence=0.80,
                        timestamp=datetime.now().isoformat(),
                        source=source
                    ))
        
        # 提取决策
        for pattern, subtype in self.DECISION_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                entity = match.group(1) if match.groups() else ""
                if entity and len(entity) > 1:
                    results.append(ExtractedFact(
                        type="decision",
                        content=f"用户{subtype}: {entity}",
                        entities=[entity],
                        confidence=0.90,
                        timestamp=datetime.now().isoformat(),
                        source=source
                    ))
        
        # 提取目标
        for pattern, subtype in self.GOAL_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                entity = match.group(1) if match.groups() else ""
                if entity and len(entity) > 1:
                    results.append(ExtractedFact(
                        type="goal",
                        content=f"用户{subtype}: {entity}",
                        entities=[entity],
                        confidence=0.75,
                        timestamp=datetime.now().isoformat(),
                        source=source
                    ))
        
        # 提取教训
        for pattern, subtype in self.LESSON_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                entity = match.group(1) if match.groups() else ""
                if entity and len(entity) > 1:
                    results.append(ExtractedFact(
                        type="lesson",
                        content=f"用户{subtype}: {entity}",
                        entities=[entity],
                        confidence=0.80,
                        timestamp=datetime.now().isoformat(),
                        source=source
                    ))
        
        # 去重
        seen = set()
        unique_results = []
        for fact in results:
            key = (fact.type, fact.content)
            if key not in seen:
                seen.add(key)
                unique_results.append(fact)
        
        # 【v2.9 P0新增】去噪过滤：应用重要性阈值和置信度检查
        try:
            from denoise_filter import should_store_memory
            
            filtered_results = []
            for fact in unique_results:
                should_store, reason = should_store_memory(
                    content=fact.content,
                    importance=fact.confidence,  # 用置信度作为重要性参考
                    confidence=fact.confidence,
                    source=fact.source
                )
                if should_store:
                    filtered_results.append(fact)
                else:
                    pass  # 被过滤的fact不加入结果
            
            unique_results = filtered_results
        except ImportError:
            pass  # 过滤器不可用，跳过
        
        self.extraction_count += len(unique_results)
        self.last_extraction_time = datetime.now().isoformat()
        
        return unique_results
    
    def extract_from_messages(self, messages: List[Dict]) -> List[ExtractedFact]:
        """
        从消息列表中提取
        
        Args:
            messages: 消息列表，每条消息包含 role 和 content
            
        Returns:
            提取的事实列表
        """
        all_facts = []
        
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            
            # 只从用户消息中提取
            if role in ['user', 'human']:
                facts = self.extract_from_text(content, source="conversation")
                all_facts.extend(facts)
        
        return all_facts
    
    def get_stats(self) -> Dict:
        """获取提取统计"""
        return {
            'total_extractions': self.extraction_count,
            'last_extraction': self.last_extraction_time,
        }


# 全局实例
_auto_extractor = None

def get_auto_extractor() -> AutoExtractor:
    """获取自动提取器单例"""
    global _auto_extractor
    if _auto_extractor is None:
        _auto_extractor = AutoExtractor()
    return _auto_extractor


def auto_extract(text: str) -> List[Dict]:
    """
    便捷函数：从文本自动提取
    
    用法:
        facts = auto_extract("用户在北京工作，喜欢喝咖啡")
    """
    extractor = get_auto_extractor()
    facts = extractor.extract_from_text(text)
    return [
        {
            'type': f.type,
            'content': f.content,
            'entities': f.entities,
            'confidence': f.confidence,
        }
        for f in facts
    ]
