"""
Weibull 遗忘机制模块
实现基于Weibull衰减的记忆重要性管理

Weibull衰减模型：
- 模拟人类记忆的自然遗忘曲线
- shape > 1: 初期衰减慢，后期衰减快
- 更符合真实遗忘模式
"""
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class WeibullDecay:
    """
    Weibull衰减遗忘机制
    
    公式: importance(t) = initial_importance * exp(-((t / scale) ^ shape))
    
    参数：
    - shape (k): 决定衰减曲线的形状
      - k < 1: 早期快速衰减，后期平缓
      - k = 1: 指数衰减
      - k > 1: 早期平缓，后期快速衰减（更符合人类记忆）
    - scale (λ): 特征时间尺度，决定衰减速度
    """
    
    def __init__(self, shape: float = 1.5, scale: float = 30.0):
        """
        Args:
            shape: 形状参数（默认1.5，更符合人类记忆）
            scale: 尺度参数（默认30天）
        """
        self.shape = shape
        self.scale = scale
    
    def calculate_decay(self, memory_age_days: float, initial_importance: float = 1.0) -> float:
        """
        计算经过时间后的记忆重要性
        
        Args:
            memory_age_days: 记忆年龄（天）
            initial_importance: 初始重要性
            
        Returns:
            当前重要性（0-1）
        """
        if memory_age_days <= 0:
            return initial_importance
        
        # Weibull衰减公式
        decay = math.exp(-((memory_age_days / self.scale) ** self.shape))
        return initial_importance * decay
    
    def should_forget(self, memory: Dict, threshold: float = 0.2) -> bool:
        """
        判断记忆是否应该被遗忘
        
        Args:
            memory: 记忆字典，包含 created_at 和 importance 字段
            threshold: 遗忘阈值（默认0.2）
            
        Returns:
            True 如果应该遗忘
        """
        try:
            # 计算记忆年龄
            created_at = memory.get("created_at", "")
            if not created_at:
                return False
            
            created_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now() - created_time).total_seconds() / 86400
            
            # 计算当前重要性
            initial = memory.get("importance", 0.5)
            current = self.calculate_decay(age_days, initial)
            
            return current < threshold
            
        except Exception:
            return False
    
    def get_importance_with_decay(self, memory: Dict) -> Dict:
        """
        获取记忆的衰减后重要性
        
        Returns:
            {
                "original": 0.8,
                "current": 0.45,
                "age_days": 15.3,
                "decay_rate": 0.56,
                "should_forget": False
            }
        """
        try:
            created_at = memory.get("created_at", "")
            initial = memory.get("importance", 0.5)
            
            if not created_at:
                return {
                    "original": initial,
                    "current": initial,
                    "age_days": 0,
                    "decay_rate": 1.0,
                    "should_forget": False
                }
            
            created_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now() - created_time).total_seconds() / 86400
            current = self.calculate_decay(age_days, initial)
            decay_rate = current / initial if initial > 0 else 0
            
            return {
                "original": round(initial, 3),
                "current": round(current, 3),
                "age_days": round(age_days, 1),
                "decay_rate": round(decay_rate, 3),
                "should_forget": current < 0.2
            }
            
        except Exception as e:
            return {
                "original": 0.5,
                "current": 0.5,
                "age_days": 0,
                "decay_rate": 1.0,
                "should_forget": False,
                "error": str(e)
            }
    
    def get_decay_curve(self, days: int = 90) -> List[Dict]:
        """
        生成衰减曲线数据（用于可视化）
        
        Args:
            days: 生成多少天的数据
            
        Returns:
            [{"day": 0, "importance": 1.0}, ...]
        """
        curve = []
        for day in range(0, days + 1):
            importance = self.calculate_decay(day, 1.0)
            curve.append({
                "day": day,
                "importance": round(importance, 4)
            })
        return curve


class AdaptiveForgetting:
    """
    自适应遗忘管理器
    
    根据记忆使用情况动态调整遗忘策略
    """
    
    def __init__(self, base_decay: WeibullDecay = None):
        self.decay = base_decay or WeibullDecay()
        self.access_boost = 0.1  # 每次访问提升的重要性
        self.max_importance = 1.0
    
    def should_forget_with_boost(self, memory: Dict, access_count: int = 0,
                                 last_accessed: str = "") -> bool:
        """
        判断记忆是否应该被遗忘（考虑访问提升）
        
        访问过的记忆会获得重要性提升
        """
        try:
            created_at = memory.get("created_at", "")
            initial = memory.get("importance", 0.5)
            
            if not created_at:
                return False
            
            created_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now() - created_time).total_seconds() / 86400
            
            # 计算基础衰减
            base_current = self.decay.calculate_decay(age_days, initial)
            
            # 计算访问提升
            # 访问越多，遗忘越慢
            boost_factor = 1.0 + (access_count * self.access_boost)
            boosted_current = min(base_current * boost_factor, self.max_importance)
            
            return boosted_current < 0.2
            
        except Exception:
            return False
    
    def calculate_forgetting_score(self, memory: Dict) -> float:
        """
        计算记忆的遗忘分数（越高越应该被遗忘）
        
        综合考虑：年龄、访问频率、初始重要性
        """
        try:
            created_at = memory.get("created_at", "")
            initial = memory.get("importance", 0.5)
            access_count = memory.get("access_count", 0)
            
            if not created_at:
                return 0.5
            
            created_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now() - created_time).total_seconds() / 86400
            
            # 年龄因子 (0-1, 越老越高)
            age_factor = min(age_days / 90.0, 1.0)  # 90天满
            
            # 访问因子 (0-1, 访问越多越低)
            access_factor = max(0, 1.0 - (access_count / 20.0))  # 20次访问后为0
            
            # 遗忘分数 = 年龄因子 * 0.5 + 访问因子 * 0.5 - 初始重要性 * 0.2
            forgetting_score = (
                age_factor * 0.5 +
                access_factor * 0.5 -
                initial * 0.2
            )
            
            return max(0, min(1, forgetting_score))
            
        except Exception:
            return 0.5


# 全局实例
_weibull = None


def get_weibull_decay() -> WeibullDecay:
    """获取Weibull衰减实例"""
    global _weibull
    if _weibull is None:
        _weibull = WeibullDecay()
    return _weibull


def get_adaptive_forgetting() -> AdaptiveForgetting:
    """获取自适应遗忘管理器"""
    return AdaptiveForgetting()
