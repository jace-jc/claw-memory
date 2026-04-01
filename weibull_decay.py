"""
Weibull 衰减遗忘模型 - Weibull Decay/Forgetting Model
参考 memory-lancedb-pro 的衰减机制

原理：
- 记忆的重要性随时间衰减，遵循 Weibull 分布
- 重要记忆衰减慢，噪声记忆快速消散
- 低于阈值进入「冷存储」而非直接删除

Weibull 衰减函数：
  survival(t) = exp(-(t/λ)^k)
  
其中：
- t = 自上次访问以来的时间（天）
- λ (lambda) = 尺度参数，控制平均寿命
- k (kappa) = 形状参数，控制衰减速度
  - k < 1：早期快速衰减，后期缓慢
  - k = 1：指数衰减
  - k > 1：晚期快速衰减，早期缓慢

默认配置（参考 memory-lancedb-pro）：
- 尺度参数 λ = 30天（平均30天后重要性减半）
- 形状参数 k = 0.5（早期快速遗忘）
- 重要性阈值 = 0.2（低于此值进入冷存储）
"""
import os
import json
import math
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

# 配置文件路径
CONFIG_DIR = Path(__file__).parent
DECAY_STATE_FILE = CONFIG_DIR / "weibull_decay_state.json"

# 默认参数
DEFAULT_LAMBDA = 30.0   # 尺度参数：平均30天重要性减半
DEFAULT_KAPPA = 0.5    # 形状参数：早期快速遗忘
DEFAULT_THRESHOLD = 0.2  # 低于此值进入冷存储
DEFAULT_BOOST_ON_ACCESS = 0.1  # 每次访问提升的重要性


class WeibullDecayModel:
    """
    Weibull 衰减遗忘模型
    
    为每条记忆追踪：
    - importance_score: 原始重要性（0-1）
    - access_count: 访问次数
    - last_access: 上次访问时间
    - decay_rate: 衰减率（由Weibull计算）
    - current_importance: 当前重要性（随时间衰减）
    """
    
    def __init__(
        self,
        lambda_param: float = DEFAULT_LAMBDA,
        kappa: float = DEFAULT_KAPPA,
        threshold: float = DEFAULT_THRESHOLD,
        boost: float = DEFAULT_BOOST_ON_ACCESS
    ):
        self.lambda_param = lambda_param  # 尺度参数
        self.kappa = kappa               # 形状参数
        self.threshold = threshold        # 冷存储阈值
        self.boost = boost               # 访问时提升量
        
        # 加载衰减状态
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """加载衰减状态"""
        if DECAY_STATE_FILE.exists():
            try:
                with open(DECAY_STATE_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"memories": {}, "stats": {"total": 0, "cold_storage": 0}}
    
    def _save_state(self):
        """保存衰减状态"""
        with open(DECAY_STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _calculate_weibull_survival(self, days_elapsed: float) -> float:
        """
        计算 Weibull 生存概率
        
        survival(t) = exp(-(t/λ)^k)
        
        Args:
            days_elapsed: 自上次访问以来的天数
            
        Returns:
            生存概率 (0-1)，1=完全未衰减，0=完全衰减
        """
        if days_elapsed < 0:
            return 1.0
        
        # Weibull 生存函数
        t_lambda = days_elapsed / self.lambda_param
        survival = math.exp(-(t_lambda ** self.kappa))
        
        return survival
    
    def register_memory(
        self,
        memory_id: str,
        initial_importance: float = 0.5,
        memory_type: str = "fact"
    ) -> Dict:
        """
        注册新记忆，初始化衰减状态
        
        Args:
            memory_id: 记忆唯一ID
            initial_importance: 初始重要性 (0-1)
            memory_type: 记忆类型 (fact/preference/decision等)
            
        Returns:
            初始衰减状态
        """
        now = datetime.now()
        
        state = {
            "id": memory_id,
            "initial_importance": initial_importance,
            "current_importance": initial_importance,
            "memory_type": memory_type,
            "access_count": 0,
            "created_at": now.isoformat(),
            "last_access": now.isoformat(),
            "next_decay_check": (now + timedelta(days=1)).isoformat(),
            "decay_events": [],
            "boost_events": []
        }
        
        self.state["memories"][memory_id] = state
        self.state["stats"]["total"] += 1
        self._save_state()
        
        return state
    
    def access_memory(self, memory_id: str) -> Optional[Dict]:
        """
        访问记忆，触发重要性提升
        
        访问时：
        1. 计算当前衰减后的重要性
        2. 应用访问提升
        3. 重置衰减计时器
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            更新后的状态，记忆不存在返回None
        """
        if memory_id not in self.state["memories"]:
            return None
        
        state = self.state["memories"][memory_id]
        now = datetime.now()
        
        # 1. 计算当前衰减后的重要性
        last_access = datetime.fromisoformat(state["last_access"])
        days_elapsed = (now - last_access).total_seconds() / 86400
        survival = self._calculate_weibull_survival(days_elapsed)
        decayed_importance = state["initial_importance"] * survival
        
        # 2. 应用访问提升（正向反馈）
        new_importance = min(1.0, decayed_importance + self.boost)
        
        # 3. 记录提升事件
        boost_event = {
            "timestamp": now.isoformat(),
            "days_elapsed": round(days_elapsed, 2),
            "survival_before": round(survival, 4),
            "decayed_importance": round(decayed_importance, 4),
            "boost_applied": round(self.boost, 4),
            "new_importance": round(new_importance, 4)
        }
        state["boost_events"].append(boost_event)
        
        # 4. 更新状态
        state["current_importance"] = new_importance
        state["last_access"] = now.isoformat()
        state["access_count"] += 1
        state["next_decay_check"] = (now + timedelta(days=1)).isoformat()
        
        self._save_state()
        return state
    
    def get_current_importance(self, memory_id: str) -> Optional[float]:
        """
        获取记忆当前重要性（实时计算，考虑时间衰减）
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            当前重要性 (0-1)，不存在返回None
        """
        if memory_id not in self.state["memories"]:
            return None
        
        state = self.state["memories"][memory_id]
        
        # 计算时间衰减
        last_access = datetime.fromisoformat(state["last_access"])
        days_elapsed = (datetime.now() - last_access).total_seconds() / 86400
        survival = self._calculate_weibull_survival(days_elapsed)
        
        # 实时计算当前重要性
        current = state["initial_importance"] * survival
        
        # 加上访问提升（尚未持久化的）
        boost_sum = sum(e["boost_applied"] for e in state.get("boost_events", [])[-10:])
        current = min(1.0, current + boost_sum)
        
        return current
    
    def check_for_cold_storage(self) -> List[Dict]:
        """
        检查需要进入冷存储的记忆
        
        Returns:
            需要冷存储的记忆列表
        """
        candidates = []
        now = datetime.now()
        
        for memory_id, state in self.state["memories"].items():
            # 检查是否到达检查时间
            next_check = datetime.fromisoformat(state["next_decay_check"])
            if now < next_check:
                continue
            
            # 计算当前重要性
            current = self.get_current_importance(memory_id)
            if current is None:
                continue
            
            # 检查是否低于阈值
            if current < self.threshold:
                candidates.append({
                    "memory_id": memory_id,
                    "current_importance": current,
                    "threshold": self.threshold,
                    "access_count": state["access_count"],
                    "days_elapsed": (now - datetime.fromisoformat(state["last_access"])).total_seconds() / 86400
                })
        
        return candidates
    
    def get_stats(self) -> Dict:
        """获取衰减统计"""
        total = len(self.state["memories"])
        if total == 0:
            return {
                "total_memories": 0,
                "in_cold_storage": self.state["stats"]["cold_storage"],
                "avg_importance": 0.0,
                "avg_access_count": 0.0,
                "lambda": self.lambda_param,
                "kappa": self.kappa,
                "threshold": self.threshold
            }
        
        current_scores = []
        access_counts = []
        
        for state in self.state["memories"].values():
            current = self.get_current_importance(state["id"])
            if current is not None:
                current_scores.append(current)
            access_counts.append(state["access_count"])
        
        return {
            "total_memories": total,
            "in_cold_storage": self.state["stats"]["cold_storage"],
            "avg_importance": round(sum(current_scores) / len(current_scores), 4) if current_scores else 0.0,
            "avg_access_count": round(sum(access_counts) / len(access_counts), 2) if access_counts else 0.0,
            "lambda": self.lambda_param,
            "kappa": self.kappa,
            "threshold": self.threshold,
            "model_description": f"Weibull(λ={self.lambda_param}, k={self.kappa})"
        }
    
    def get_decay_curve(self, days_range: int = 90) -> List[Dict]:
        """
        获取衰减曲线数据（用于可视化）
        
        Args:
            days_range: 计算多少天的曲线
            
        Returns:
            每天的重要性衰减数据
        """
        curve = []
        for day in range(days_range + 1):
            survival = self._calculate_weibull_survival(float(day))
            importance_095 = 0.95 * survival  # 高重要性记忆
            importance_085 = 0.85 * survival  # 较高重要性记忆
            importance_080 = 0.80 * survival  # 较高重要性记忆
            importance_070 = 0.70 * survival  # 中等重要性记忆
            importance_050 = 0.50 * survival  # 低重要性记忆
            
            curve.append({
                "day": day,
                "survival": round(survival, 4),
                "importance_0.95": round(importance_095, 4),
                "importance_0.85": round(importance_085, 4),
                "importance_0.80": round(importance_080, 4),
                "importance_0.70": round(importance_070, 4),
                "importance_0.50": round(importance_050, 4)
            })
        
        return curve
    
    def remove_memory(self, memory_id: str) -> bool:
        """移除记忆的衰减状态"""
        if memory_id in self.state["memories"]:
            del self.state["memories"][memory_id]
            self._save_state()
            return True
        return False


# ============================================================
# 全局实例
# ============================================================

_weibull_model = None


def get_weibull_model() -> WeibullDecayModel:
    """获取全局Weibull模型实例"""
    global _weibull_model
    if _weibull_model is None:
        _weibull_model = WeibullDecayModel()
    return _weibull_model


# ============================================================
# 独立函数接口
# ============================================================

def register_memory(
    memory_id: str,
    initial_importance: float = 0.5,
    memory_type: str = "fact"
) -> Dict:
    """注册新记忆"""
    model = get_weibull_model()
    return model.register_memory(memory_id, initial_importance, memory_type)


def access_memory(memory_id: str) -> Optional[Dict]:
    """访问记忆，触发重要性提升"""
    model = get_weibull_model()
    return model.access_memory(memory_id)


def get_current_importance(memory_id: str) -> Optional[float]:
    """获取记忆当前重要性"""
    model = get_weibull_model()
    return model.get_current_importance(memory_id)


def check_for_cold_storage() -> List[Dict]:
    """检查需要进入冷存储的记忆"""
    model = get_weibull_model()
    return model.check_for_cold_storage()


def get_decay_stats() -> Dict:
    """获取衰减统计"""
    model = get_weibull_model()
    return model.get_stats()


def get_decay_curve(days_range: int = 90) -> List[Dict]:
    """获取衰减曲线"""
    model = get_weibull_model()
    return model.get_decay_curve(days_range)


def apply_decay_to_search_results(results: List[Dict]) -> List[Dict]:
    """
    对搜索结果应用Weibull衰减
    
    在搜索结果返回前，根据当前重要性调整排序：
    - 访问频率高但重要性低的记忆降权
    - 长时间未访问的高重要性记忆保留
    - 新记忆（<7天）获得短期加权
    
    Args:
        results: 搜索结果列表，每项需包含 id 和可选的 importance 字段
        
    Returns:
        添加了 decay_score 后的结果列表
    """
    model = get_weibull_model()
    now = datetime.now()
    
    for result in results:
        memory_id = result.get("id", result.get("memory_id", ""))
        if not memory_id:
            continue
        
        # 获取当前重要性
        current_importance = model.get_current_importance(memory_id)
        if current_importance is None:
            # 未注册的记忆，使用原始重要性
            current_importance = result.get("importance", 0.5)
        
        # 获取衰减状态
        state = model.state["memories"].get(memory_id, {})
        last_access = state.get("last_access")
        
        decay_multiplier = 1.0
        
        if last_access:
            days_elapsed = (now - datetime.fromisoformat(last_access)).total_seconds() / 86400
            
            # 7天内的新记忆获得+20%加权（鼓励新记忆被使用）
            if days_elapsed < 7:
                decay_multiplier *= 1.20
            
            # 30天未访问的记忆降权（除非重要性很高）
            elif days_elapsed > 30 and current_importance < 0.6:
                decay_multiplier *= 0.80
            
            # 90天未访问的记忆大幅降权
            elif days_elapsed > 90:
                decay_multiplier *= 0.50
        
        # 访问次数奖励（访问多的记忆略微加权）
        access_count = state.get("access_count", 0)
        if access_count > 10:
            decay_multiplier *= 1.10
        elif access_count > 5:
            decay_multiplier *= 1.05
        
        # 计算最终衰减分数
        result["decay_score"] = round(current_importance * decay_multiplier, 4)
        result["current_importance"] = round(current_importance, 4)
    
    # 按 decay_score 重新排序
    results.sort(key=lambda x: x.get("decay_score", 0), reverse=True)
    
    return results
