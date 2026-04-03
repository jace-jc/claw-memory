"""
自适应RRF权重模块 - Adaptive RRF Weights
根据用户反馈自动调整4通道融合权重

通道:
1. vector - 向量相似度
2. bm25 - 关键词匹配
3. importance - 重要性分数
4. kg - 知识图谱关联
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime, timedelta

# 配置文件路径
CONFIG_DIR = Path(__file__).parent
WEIGHTS_FILE = CONFIG_DIR / "adaptive_weights.json"
FEEDBACK_FILE = CONFIG_DIR / "search_feedback.json"

# 默认权重（初始值）
DEFAULT_WEIGHTS = {
    "vector": 0.40,
    "bm25": 0.25,
    "importance": 0.20,
    "kg": 0.15
}

# 最小置信度（低于此值不调整）
MIN_CONFIDENCE = 5  # 至少5次反馈

# 学习率
LEARNING_RATE = 0.1


class AdaptiveRRF:
    """
    自适应RRF权重管理器
    
    工作原理：
    1. 记录每次搜索的4通道原始分数
    2. 用户点击/选择某个结果时，记录该结果在哪些通道表现好
    3. 基于反馈计算各通道的贡献度
    4. 动态调整RRF权重
    """
    
    def __init__(self):
        self.weights = self._load_weights()
        self.feedback = self._load_feedback()
        self._stats = {
            "total_searches": 0,
            "total_feedback": 0,
            "last_update": None
        }
    
    def _load_weights(self) -> Dict[str, float]:
        """加载权重配置"""
        if WEIGHTS_FILE.exists():
            try:
                with open(WEIGHTS_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("weights", DEFAULT_WEIGHTS.copy())
            except:
                pass
        return DEFAULT_WEIGHTS.copy()
    
    def _save_weights(self):
        """保存权重配置"""
        data = {
            "weights": self.weights,
            "updated_at": datetime.now().isoformat()
        }
        with open(WEIGHTS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_feedback(self) -> Dict:
        """加载反馈数据"""
        if FEEDBACK_FILE.exists():
            try:
                with open(FEEDBACK_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"clicks": [], "skips": [], "ratings": []}
    
    def _save_feedback(self):
        """保存反馈数据"""
        with open(FEEDBACK_FILE, 'w') as f:
            json.dump(self.feedback, f, indent=2)
    
    def get_weights(self) -> Dict[str, float]:
        """获取当前权重"""
        return self.weights.copy()
    
    def get_effective_k(self, channel: str) -> float:
        """
        获取某通道的有效k值
        k越小，该通道的排名差异越敏感
        """
        weight = self.weights.get(channel, 0.25)
        # 权重越高，k值越低（更敏感）
        return 60 / (weight * 5 + 0.5)
    
    def record_search(self, query: str, results: List[dict]):
        """
        记录一次搜索（用于分析）
        
        Args:
            query: 查询词
            results: 搜索结果列表，每项包含各通道分数
        """
        self._stats["total_searches"] += 1
        
        # 存储本次搜索的结果分数
        search_id = f"{query}_{int(time.time())}"
        channel_scores = []
        
        for r in results:
            scores = {
                "id": r.get("id", ""),
                "vector": r.get("_vector_score", 0),
                "bm25": r.get("_bm25_score", 0),
                "importance": r.get("_importance_score", 0),
                "kg": r.get("_kg_score", 0),
                "final": r.get("_final_score", 0)
            }
            channel_scores.append(scores)
        
        return search_id, channel_scores
    
    def record_click(self, memory_id: str, query: str, results: List[dict]):
        """
        记录用户点击
        
        Args:
            memory_id: 被点击的记忆ID
            query: 查询词
            results: 当时搜索的全部结果
        """
        self._stats["total_feedback"] += 1
        
        # 找到被点击的结果在各通道的排名
        clicked_idx = None
        for i, r in enumerate(results):
            if r.get("id") == memory_id:
                clicked_idx = i
                break
        
        if clicked_idx is None:
            return
        
        # 记录反馈
        feedback_entry = {
            "memory_id": memory_id,
            "query": query,
            "position": clicked_idx + 1,
            "timestamp": datetime.now().isoformat(),
            "channel_scores": {}
        }
        
        # 记录各通道分数
        if clicked_idx < len(results):
            r = results[clicked_idx]
            feedback_entry["channel_scores"] = {
                "vector": r.get("_vector_score", 0),
                "bm25": r.get("_bm25_score", 0),
                "importance": r.get("_importance_score", 0),
                "kg": r.get("_kg_score", 0)
            }
        
        self.feedback["clicks"].append(feedback_entry)
        self._save_feedback()
        
        # 调整权重
        self._adjust_weights(feedback_entry)
    
    def record_skip(self, query: str, results: List[dict]):
        """
        记录用户跳过结果（看了但没点）
        """
        # 简单处理：最上面的结果没被点击算skip
        if not results:
            return
        
        # 记录位置0的结果被跳过
        feedback_entry = {
            "query": query,
            "position": 1,
            "timestamp": datetime.now().isoformat(),
            "type": "skip"
        }
        
        self.feedback["skips"].append(feedback_entry)
        self._save_feedback()
    
    def _adjust_weights(self, feedback_entry: dict):
        """
        根据反馈调整权重
        
        核心逻辑：
        - 如果某个通道在用户选择的结果中得分高，说明这个通道重要 → 增加权重
        - 如果某个通道在用户选择的结果中得分低，说明这个通道不太重要 → 降低权重
        """
        scores = feedback_entry.get("channel_scores", {})
        if not scores:
            return
        
        total_score = sum(scores.values())
        if total_score == 0:
            return
        
        # 计算各通道的贡献比例
        contributions = {k: v / total_score for k, v in scores.items()}
        
        # 获取当前权重
        old_weights = self.weights.copy()
        
        # 计算调整量
        adjustments = {}
        for channel in ["vector", "bm25", "importance", "kg"]:
            # 贡献超过权重 → 应该增加
            # 贡献低于权重 → 应该减少
            diff = contributions.get(channel, 0) - old_weights[channel]
            adjustments[channel] = diff * LEARNING_RATE
        
        # 应用调整（保持总和为1）
        new_weights = old_weights.copy()
        for channel, adj in adjustments.items():
            new_weights[channel] = max(0.05, min(0.8, new_weights[channel] + adj))
        
        # 归一化
        total = sum(new_weights.values())
        if total > 0:
            new_weights = {k: v / total for k, v in new_weights.items()}
        
        self.weights = new_weights
        self._save_weights()
        
        self._stats["last_update"] = datetime.now().isoformat()
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "weights": self.weights,
            "total_searches": self._stats["total_searches"],
            "total_feedback": self._stats["total_feedback"],
            "total_clicks": len(self.feedback.get("clicks", [])),
            "total_skips": len(self.feedback.get("skips", [])),
            "last_update": self._stats["last_update"],
            "confidence": min(len(self.feedback.get("clicks", [])), MIN_CONFIDENCE) / MIN_CONFIDENCE
        }
    
    def reset_weights(self):
        """重置为默认权重"""
        self.weights = DEFAULT_WEIGHTS.copy()
        self._save_weights()
        self.feedback = {"clicks": [], "skips": [], "ratings": []}
        self._save_feedback()
        self._stats = {
            "total_searches": 0,
            "total_feedback": 0,
            "last_update": None
        }


# 全局实例
_adaptive_rrf = None


def get_adaptive_rrf() -> AdaptiveRRF:
    """获取自适应RRF实例"""
    global _adaptive_rrf
    if _adaptive_rrf is None:
        _adaptive_rrf = AdaptiveRRF()
    return _adaptive_rrf
