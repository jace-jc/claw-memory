"""
记忆质量过滤器 - Memory Quality Filter
解决记忆质量问题的核心模块

三大功能：
1. 提取去噪：过滤系统提示词/心跳/噪音
2. 重要性阈值强制化：不够重要的记忆不存主检索
3. 矛盾检测：检测新旧记忆冲突，自动处理

基于行业痛点设计：
- 97.8%记忆是垃圾（Mem0生产审计）
- 52.7%来自系统提示词反复提取
- 11.5%来自心跳/cron噪音
- 矛盾记忆被直接删除而非更新
"""
import re
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


# ============================================================
# 第一部分：提取去噪过滤器
# ============================================================

class DenoiseFilter:
    """
    记忆提取去噪器
    
    过滤规则：
    1. 系统提示词片段不存储
    2. 心跳/cron消息不存储
    3. 重复内容（3次以上）降权
    4. 置信度<0.6的推断不存储
    5. 太短的内容不存储（<10字符）
    """
    
    # 心跳/cron关键词模式
    HEARTBEAT_PATTERNS = [
        r"^heartbeat",
        r"^cron",
        r"^scheduled",
        r"^triggered by",
        r"\[CRON\]",
        r"\[HEARTBEAT\]",
        r"\[SCHEDULED\]",
        r"自动任务",
        r"定时任务",
        r"心跳检测",
        r"system check",
        r"health check",
        r"ping check",
    ]
    
    # 系统提示词关键词
    SYSTEM_PROMPT_PATTERNS = [
        r"^you are a",
        r"^you are an",
        r"^as an? ai",
        r"^as a? assistant",
        r"system prompt",
        r"instruction:",
        r"角色设定",
        r"你是谁",
        r"请记住",
        r"always ",
        r"never ",
        r"based on the context",
        r"given the conversation",
        r"according to our conversation",
        r"remember that",
        r"note that",
    ]
    
    # 太通用/无意义的模式
    GENERIC_PATTERNS = [
        r"^好的",
        r"^好的，",
        r"^收到",
        r"^了解",
        r"^明白",
        r"^OK",
        r"^好的好的",
        r"^嗯",
        r"^是",
        r"^对",
        r"^没错",
        r"^是的是的",
        r"^哈哈",
        r"^嘿嘿",
        r"^请问",
        r"^你好",
        r"^您好",
    ]
    
    # 时间询问类（通常是噪音）
    TIME_QUERIES = [
        r"现在几点了",
        r"今天星期几",
        r"现在是几点",
        r"当前时间",
        r"what time is it",
        r"what's the time",
        r"current time",
        r"what day is it",
    ]
    
    def __init__(self):
        self._compile_patterns()
        # 最近存储的记忆哈希（用于检测重复）
        self._recent_hashes = defaultdict(list)  # {hash: [timestamp1, timestamp2]}
        self._hash_ttl = 3600 * 24  # 24小时内重复算重复
    
    def _compile_patterns(self):
        """预编译正则表达式"""
        self._heartbeat_re = [
            re.compile(p, re.IGNORECASE) for p in self.HEARTBEAT_PATTERNS
        ]
        self._system_prompt_re = [
            re.compile(p, re.IGNORECASE) for p in self.SYSTEM_PROMPT_PATTERNS
        ]
        self._generic_re = [
            re.compile(p, re.IGNORECASE) for p in self.GENERIC_PATTERNS
        ]
        self._time_query_re = [
            re.compile(p, re.IGNORECASE) for p in self.TIME_QUERIES
        ]
    
    def should_store(self, content: str, importance: float = None, confidence: float = None,
                    source: str = None, memory_type: str = None) -> Tuple[bool, str]:
        """
        判断记忆是否应该存储
        
        Args:
            content: 记忆内容
            importance: 重要性分数 (0-1)
            confidence: 置信度分数 (0-1)
            source: 来源
            memory_type: 记忆类型
            
        Returns:
            (should_store, reason)
            - should_store: True=应该存储, False=应该丢弃
            - reason: 原因说明
        """
        content = content.strip()
        
        # 1. 长度检查：太短不存储（中文按字符计，8字符约等于4个汉字）
        if len(content) < 8:
            return False, "内容太短(<8字符)"
        
        # 2. 长度检查：太长可能是日志/代码
        if len(content) > 5000:
            return False, "内容太长(>5000字符)，可能是日志"
        
        # 3. 心跳/cron检查
        for pattern in self._heartbeat_re:
            if pattern.search(content):
                return False, "心跳/cron消息，不存储"
        
        # 4. 系统提示词检查
        for pattern in self._system_prompt_re:
            if pattern.match(content[:100]):
                return False, "系统提示词片段，不存储"
        
        # 5. 时间询问检查（通常是噪音）
        for pattern in self._time_query_re:
            if pattern.search(content.lower()):
                return False, "时间询问类噪音，不存储"
        
        # 6. 置信度过低不存储
        if confidence is not None and confidence < 0.6:
            return False, f"置信度太低({confidence:.2f}<0.6)"
        
        # 7. 重要性过低不存储主检索
        if importance is not None and importance < 0.3:
            return False, f"重要性太低({importance:.2f}<0.3)"
        
        # 8. 重复检查：24小时内重复3次以上降权
        content_hash = self._hash_content(content)
        now = time.time()
        
        # 清理过期记录
        self._recent_hashes[content_hash] = [
            t for t in self._recent_hashes[content_hash]
            if now - t < self._hash_ttl
        ]
        
        repeat_count = len(self._recent_hashes[content_hash])
        if repeat_count >= 3:
            return False, f"24小时内重复{repeat_count}次，不再存储"
        
        # 9. 通用无意义内容检查
        for pattern in self._generic_re:
            if pattern.match(content[:20]):
                # 给一次机会，但标记为低优先级
                if importance is not None and importance < 0.5:
                    return False, "通用无意义内容，重要性不足"
        
        # 通过所有检查
        # 记录本次哈希
        self._recent_hashes[content_hash].append(now)
        
        return True, "通过所有检查"
    
    def _hash_content(self, content: str) -> str:
        """计算内容哈希"""
        # 归一化：去除空白字符
        normalized = re.sub(r'\s+', ' ', content).lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def get_filter_stats(self) -> Dict:
        """获取过滤器统计"""
        total_hashes = len(self._recent_hashes)
        total_recent = sum(len(v) for v in self._recent_hashes.values())
        
        return {
            "unique_contents_tracked": total_hashes,
            "total_recent_occurrences": total_recent,
            "ttl_seconds": self._hash_ttl
        }


# ============================================================
# 第二部分：重要性阈值管理器
# ============================================================

class ImportanceThreshold:
    """
    重要性阈值管理器
    
    三级存储策略：
    - WARM层 (主检索): importance > 0.5
    - COLD层 (归档): 0.3 <= importance <= 0.5
    - 丢弃: importance < 0.3
    """
    
    # 阈值配置
    THRESHOLD_WARM = 0.5  # 进入主检索
    THRESHOLD_COLD = 0.3  # 进入冷存储
    THRESHOLD_DISCARD = 0.3  # 低于此值直接丢弃
    
    def __init__(self, warm_threshold: float = None, cold_threshold: float = None):
        self.warm_threshold = warm_threshold or self.THRESHOLD_WARM
        self.cold_threshold = cold_threshold or self.THRESHOLD_COLD
    
    def classify(self, importance: float) -> str:
        """
        根据重要性分类存储位置
        
        Returns:
            "warm": 主检索层（WARM）
            "cold": 冷存储层（COLD）
            "discard": 丢弃
        """
        if importance > self.warm_threshold:
            return "warm"
        elif importance >= self.cold_threshold:
            return "cold"
        else:
            return "discard"
    
    def should_store(self, importance: float) -> bool:
        """判断是否应该存储"""
        return importance >= self.cold_threshold
    
    def get_storage_tier(self, importance: float) -> str:
        """获取存储层级"""
        return self.classify(importance)


# ============================================================
# 第三部分：矛盾检测器
# ============================================================

class ContradictionDetector:
    """
    记忆矛盾检测器
    
    功能：
    1. 检测新记忆与旧记忆是否矛盾
    2. 矛盾时：保留旧记忆，标记为已更新，存储新记忆
    3. 防止关键信息在"改口"时丢失
    
    矛盾类型：
    - 直接否定：之前说X，现在说"不X"
    - 属性变更：之前X是Y，现在X是Z
    - 偏好反转：从喜欢X变成不喜欢X
    """
    
    # 否定词模式
    NEGATION_PATTERNS = [
        (r"不喜欢", r"喜欢"),  # 不喜欢 → 之前喜欢？
        (r"不是", r"是"),      # 不是 → 之前是？
        (r"没有", r"有"),      # 没有 → 之前有？
        (r"不", r""),          # 通用否定前缀
        (r"从不", r"偶尔"),    # 从不 → 之前偶尔？
        (r"讨厌", r"喜欢"),    # 讨厌 → 之前喜欢？
    ]
    
    # 矛盾关键词（当这些词出现时触发矛盾检测）
    CONTRADICTION_TRIGGERS = [
        r"实际上",
        r"其实",
        r"不对",
        r"错了",
        r"更正",
        r"纠正",
        r"改口",
        r"之前.*说错了",
        r"不是.*而是",
        r"之前说.*现在",
    ]
    
    def __init__(self):
        self._compile_patterns()
        # 近期存储的记忆（用于矛盾检测）
        self._recent_memories = []  # [{"content": ..., "type": ..., "importance": ...}]
    
    def _compile_patterns(self):
        """预编译正则"""
        self._negation_pairs = [
            (re.compile(old, re.IGNORECASE), new) 
            for old, new in self.NEGATION_PATTERNS
        ]
        self._trigger_re = [
            re.compile(p, re.IGNORECASE) for p in self.CONTRADICTION_TRIGGERS
        ]
    
    def check(self, new_content: str, new_type: str = None) -> Optional[Dict]:
        """
        检查新记忆是否与旧记忆矛盾
        
        Args:
            new_content: 新记忆内容
            new_type: 新记忆类型
            
        Returns:
            如果矛盾：{
                "is_contradiction": True,
                "old_memory": {...},
                "contradiction_type": "negation|attribute|preference",
                "action": "supersede|merge|keep_both"
            }
            如果不矛盾：None
        """
        new_content = new_content.strip()
        
        # 1. 检查是否触发矛盾关键词
        is_contradiction_triggered = any(
            pattern.search(new_content) for pattern in self._trigger_re
        )
        
        if not is_contradiction_triggered:
            # 检查否定模式
            negation_found = False
            for neg_re, pos_word in self._negation_pairs:
                neg_match = neg_re.search(new_content)
                if neg_match:
                    # 提取否定后的核心词
                    negated_phrase = neg_match.group(1) if neg_match.groups() else new_content
                    negation_found = True
                    
                    # 在旧记忆中查找对应的肯定陈述
                    for old_mem in reversed(self._recent_memories):
                        old_content = old_mem.get("content", "")
                        if pos_word.lower() in old_content.lower():
                            return self._create_contradiction_result(
                                old_mem, new_content, new_type, "negation"
                            )
            
            if not negation_found:
                return None
        
        # 2. 如果触发了矛盾关键词，查找相似旧记忆
        for old_mem in reversed(self._recent_memories):
            old_content = old_mem.get("content", "")
            old_type = old_mem.get("type", "")
            
            # 类型相同或相关，可能是矛盾
            if old_type == new_type or (old_type and new_type and 
                    old_type.split("_")[0] == new_type.split("_")[0]):
                
                # 检查是否高度相似但有否定
                if self._is_contradiction(new_content, old_content):
                    return self._create_contradiction_result(
                        old_mem, new_content, new_type, "similar_negation"
                    )
        
        return None
    
    def _is_contradiction(self, new_content: str, old_content: str) -> bool:
        """判断两个内容是否矛盾"""
        # 提取核心实体
        new_entities = set(re.findall(r'[\w\u4e00-\u9fff]+', new_content.lower()))
        old_entities = set(re.findall(r'[\w\u4e00-\u9fff]+', old_content.lower()))
        
        # 找共同实体
        common = new_entities & old_entities
        if not common:
            return False
        
        # 检查是否有否定关系
        for neg_re, pos_word in self._negation_pairs:
            # 新内容有否定
            if neg_re.search(new_content):
                # 旧内容有肯定词
                if pos_word.lower() in old_content.lower():
                    return True
        
        return False
    
    def _create_contradiction_result(self, old_memory: Dict, new_content: str,
                                     new_type: str, contradiction_type: str) -> Dict:
        """创建矛盾处理结果"""
        return {
            "is_contradiction": True,
            "old_memory": old_memory,
            "new_content": new_content,
            "new_type": new_type,
            "contradiction_type": contradiction_type,
            "action": "keep_both_mark_updated",  # 保留两个，标记旧记忆已更新
            "timestamp": datetime.now().isoformat()
        }
    
    def register_memory(self, memory: Dict):
        """注册已存储的记忆（用于后续矛盾检测）"""
        self._recent_memories.append({
            "content": memory.get("content", ""),
            "type": memory.get("type", ""),
            "importance": memory.get("importance", 0.5),
            "timestamp": datetime.now().isoformat()
        })
        # 只保留最近100条
        if len(self._recent_memories) > 100:
            self._recent_memories = self._recent_memories[-100:]


# ============================================================
# 全局实例
# ============================================================

_denoise_filter = None
_importance_threshold = None
_contradiction_detector = None


def get_denoise_filter() -> DenoiseFilter:
    """获取全局去噪过滤器"""
    global _denoise_filter
    if _denoise_filter is None:
        _denoise_filter = DenoiseFilter()
    return _denoise_filter


def get_importance_threshold() -> ImportanceThreshold:
    """获取全局重要性阈值管理器"""
    global _importance_threshold
    if _importance_threshold is None:
        _importance_threshold = ImportanceThreshold()
    return _importance_threshold


def get_contradiction_detector() -> ContradictionDetector:
    """获取全局矛盾检测器"""
    global _contradiction_detector
    if _contradiction_detector is None:
        _contradiction_detector = ContradictionDetector()
    return _contradiction_detector


# ============================================================
# 独立函数接口
# ============================================================

def should_store_memory(content: str, importance: float = None, confidence: float = None,
                       source: str = None) -> Tuple[bool, str]:
    """
    判断记忆是否应该存储（联合检查）
    
    综合去噪 + 重要性阈值检查
    
    Args:
        content: 记忆内容
        importance: 重要性分数
        confidence: 置信度分数
        source: 来源
        
    Returns:
        (should_store, reason)
    """
    filter_ = get_denoise_filter()
    
    # 1. 去噪检查
    should_store, reason = filter_.should_store(content, importance, confidence, source)
    if not should_store:
        return False, f"[去噪] {reason}"
    
    # 2. 重要性阈值检查
    threshold = get_importance_threshold()
    if not threshold.should_store(importance):
        tier = threshold.classify(importance)
        return False, f"[阈值] 重要性{importance:.2f}低于阈值({threshold.cold_threshold})，进入{tier}层"
    
    return True, "通过所有检查"


def check_contradiction(content: str, memory_type: str = None) -> Optional[Dict]:
    """
    检查记忆是否矛盾
    
    Returns:
        矛盾结果或None
    """
    detector = get_contradiction_detector()
    return detector.check(content, memory_type)


def register_stored_memory(memory: Dict):
    """
    注册已存储的记忆（用于后续矛盾检测）
    
    重要：每次存储记忆后调用此函数
    """
    detector = get_contradiction_detector()
    detector.register_memory(memory)


def get_quality_filter_stats() -> Dict:
    """获取所有过滤器的统计信息"""
    filter_ = get_denoise_filter()
    threshold = get_importance_threshold()
    
    return {
        "denoise": filter_.get_filter_stats(),
        "threshold": {
            "warm_threshold": threshold.warm_threshold,
            "cold_threshold": threshold.cold_threshold
        }
    }
