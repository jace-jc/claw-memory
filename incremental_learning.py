"""
Claw Memory 增量学习模块
基于用户反馈的在线权重学习

实现机制：
1. 记录用户点击/选择行为
2. 根据反馈调整RRF通道权重
3. 支持探索-利用平衡（ε-greedy）
4. 按用户/scope隔离学习数据
"""

import json
import random
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path


class IncrementalLearner:
    """
    增量学习器
    
    基于用户反馈持续优化检索策略
    """
    
    def __init__(self, scope: str = "user", epsilon: float = 0.1):
        """
        Args:
            scope: 学习数据隔离范围
            epsilon: 探索率（0-1），0.1表示10%概率随机探索
        """
        self.scope = scope
        self.epsilon = epsilon
        self.feedback_file = Path(f"~/.openclaw/workspace/memory/feedback_{scope}.json").expanduser()
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._load_feedback()
    
    def _load_feedback(self):
        """加载历史反馈"""
        if self.feedback_file.exists():
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                self.feedback = json.load(f)
        else:
            self.feedback = {
                "clicks": [],  # 用户点击记录
                "weights_history": [],  # 权重变化历史
                "current_weights": {
                    "vector": 0.40,
                    "bm25": 0.20,
                    "importance": 0.15,
                    "kg": 0.10,
                    "temporal": 0.15
                }
            }
    
    def _save_feedback(self):
        """保存反馈数据"""
        with open(self.feedback_file, 'w', encoding='utf-8') as f:
            json.dump(self.feedback, f, ensure_ascii=False, indent=2)
    
    def record_click(self, query: str, clicked_result: dict, result_rank: int, 
                     channel_scores: dict = None):
        """
        记录用户点击行为
        
        Args:
            query: 搜索查询
            clicked_result: 被点击的结果
            result_rank: 结果排名（1-based）
            channel_scores: 各通道贡献分数
        """
        click = {
            "query": query,
            "memory_id": clicked_result.get("id"),
            "rank": result_rank,
            "timestamp": datetime.now().isoformat(),
            "channel_scores": channel_scores or {}
        }
        
        self.feedback["clicks"].append(click)
        
        # 限制历史长度
        if len(self.feedback["clicks"]) > 1000:
            self.feedback["clicks"] = self.feedback["clicks"][-1000:]
        
        self._save_feedback()
    
    def get_weights(self, use_exploration: bool = True) -> dict:
        """
        获取当前权重（支持探索-利用）
        
        Args:
            use_exploration: 是否使用探索策略
            
        Returns:
            通道权重字典
        """
        current = self.feedback["current_weights"].copy()
        
        if not use_exploration:
            return current
        
        # ε-greedy: 以epsilon概率随机扰动权重
        if random.random() < self.epsilon:
            # 随机探索：小幅扰动权重
            for key in current:
                noise = random.uniform(-0.05, 0.05)
                current[key] = max(0.05, min(0.5, current[key] + noise))
            
            # 归一化
            total = sum(current.values())
            current = {k: v/total for k, v in current.items()}
        
        return current
    
    def update_weights(self, learning_rate: float = 0.01):
        """
        基于反馈更新权重
        
        策略：
        - 用户点击排名靠前的结果 → 当前权重有效，小幅调整
        - 用户点击排名靠后的结果 → 某些通道权重需调整
        
        Args:
            learning_rate: 学习率
        """
        clicks = self.feedback["clicks"]
        if len(clicks) < 10:  # 至少需要10条反馈
            return
        
        # 分析最近100条点击
        recent_clicks = clicks[-100:]
        
        # 计算平均点击排名
        avg_rank = sum(c["rank"] for c in recent_clicks) / len(recent_clicks)
        
        weights = self.feedback["current_weights"].copy()
        
        if avg_rank <= 2:
            # 排名很好，当前策略有效，保持稳定
            pass
        elif avg_rank <= 5:
            # 中等表现，小幅调整
            # 增加BM25权重（关键词匹配通常更直接）
            weights["bm25"] += learning_rate * 0.5
            weights["vector"] -= learning_rate * 0.3
        else:
            # 排名较差，需要显著调整
            # 增加向量权重（语义理解更重要）
            weights["vector"] += learning_rate
            weights["bm25"] -= learning_rate * 0.5
        
        # 确保所有权重为正
        for key in weights:
            weights[key] = max(0.05, weights[key])
        
        # 归一化
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}
        
        # 保存历史
        self.feedback["weights_history"].append({
            "timestamp": datetime.now().isoformat(),
            "weights": weights.copy(),
            "avg_rank": avg_rank
        })
        
        self.feedback["current_weights"] = weights
        self._save_feedback()
    
    def get_stats(self) -> dict:
        """获取学习统计"""
        clicks = self.feedback["clicks"]
        
        if not clicks:
            return {"total_clicks": 0}
        
        recent = clicks[-100:]
        avg_rank = sum(c["rank"] for c in recent) / len(recent)
        
        # 计算各排名区间的点击数
        rank_distribution = {
            "top1": sum(1 for c in recent if c["rank"] == 1),
            "top3": sum(1 for c in recent if c["rank"] <= 3),
            "top5": sum(1 for c in recent if c["rank"] <= 5),
        }
        
        return {
            "total_clicks": len(clicks),
            "recent_avg_rank": round(avg_rank, 2),
            "current_weights": self.feedback["current_weights"],
            "rank_distribution": rank_distribution,
            "epsilon": self.epsilon
        }


# 全局实例管理
_learners: Dict[str, IncrementalLearner] = {}


def get_learner(scope: str = "user") -> IncrementalLearner:
    """获取学习器实例"""
    if scope not in _learners:
        _learners[scope] = IncrementalLearner(scope=scope)
    return _learners[scope]


def record_search_feedback(query: str, clicked_result: dict, rank: int, scope: str = "user"):
    """快捷记录搜索反馈"""
    learner = get_learner(scope)
    learner.record_click(query, clicked_result, rank)


def get_adaptive_weights(scope: str = "user", use_exploration: bool = True) -> dict:
    """获取自适应权重"""
    learner = get_learner(scope)
    return learner.get_weights(use_exploration)
