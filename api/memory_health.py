"""
记忆健康度仪表盘 - 记忆系统状态监控
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from core.memory_config import CONFIG


class MemoryHealth:
    """
    记忆健康度监控
    """
    
    def __init__(self):
        self.min_importance = CONFIG.get("min_importance", 0.3)
        self.warm_ttl_days = CONFIG.get("warm_ttl_days", 30)
        self.hot_ttl_hours = CONFIG.get("hot_ttl_hours", 24)
    
    def generate_report(self, stats: dict = None) -> dict:
        """
        生成记忆健康报告
        """
        if stats is None:
            from memory_main import memory_stats
            stats = memory_stats()
        
        warm = stats.get("warm_store", {})
        cold = stats.get("cold_store", {})
        
        # 分析类型分布
        type_dist = warm.get("by_type", {})
        
        # 计算重要性分布
        importance_buckets = {"high": 0, "medium": 0, "low": 0, "critical": 0}
        
        # 获取详细数据进行分析
        from memory_main import get_db
        try:
            db = get_db()
            all_memories = db.table.to_arrow().to_pylist() if db.table else []
            
            for mem in all_memories:
                imp = mem.get("importance", 0.5)
                if imp >= 0.8:
                    importance_buckets["high"] += 1
                elif imp >= 0.5:
                    importance_buckets["medium"] += 1
                elif imp >= self.min_importance:
                    importance_buckets["low"] += 1
                else:
                    importance_buckets["critical"] += 1
            
            # 分析陈旧记忆（30天未访问）
            stale_count = 0
            orphaned_count = 0
            cutoff = (datetime.now() - timedelta(days=self.warm_ttl_days)).isoformat()
            
            for mem in all_memories:
                last_access = mem.get("last_accessed", "")
                created = mem.get("created_at", "")
                
                # 超过TTL未访问
                if last_access and last_access < cutoff:
                    stale_count += 1
                
                # 无来源的记忆（可能是噪音或错误存储）
                if not mem.get("source") and not mem.get("transcript"):
                    orphaned_count += 1
            
            total = len(all_memories)
            
        except Exception:
            total = warm.get("total", 0)
            importance_buckets = {"high": 0, "medium": total, "low": 0, "critical": 0}
            stale_count = 0
            orphaned_count = 0
        
        # 计算健康分数
        health_score = self._calculate_health_score(
            total=total,
            stale_count=stale_count,
            orphaned_count=orphaned_count,
            importance_buckets=importance_buckets,
            type_dist=type_dist
        )
        
        # 【P2增强】遗忘分析
        forgetting_analysis = self._analyze_forgetting(all_memories)
        
        # 生成建议
        suggestions = self._generate_suggestions(
            total=total,
            stale_count=stale_count,
            orphaned_count=orphaned_count,
            importance_buckets=importance_buckets,
            type_dist=type_dist,
            forgetting_analysis=forgetting_analysis
        )
        
        return {
            "generated_at": datetime.now().isoformat(),
            "health_score": health_score,
            "summary": {
                "total_memories": total,
                "warm_count": warm.get("total", 0),
                "cold_count": cold.get("count", 0),
            },
            "distributions": {
                "type": type_dist,
                "importance": importance_buckets,
            },
            "analysis": {
                "stale_memories": stale_count,
                "orphaned_memories": orphaned_count,
                "avg_importance": self._calc_avg_importance(importance_buckets),
                "memories_above_threshold": importance_buckets["high"] + importance_buckets["medium"],
            },
            "forgetting": forgetting_analysis,  # 【P2新增】遗忘分析
            "suggestions": suggestions,
            "status": self._get_status_label(health_score)
        }
    
    def _calculate_health_score(self, total: int, stale_count: int, 
                               orphaned_count: int, importance_buckets: dict,
                               type_dist: dict) -> int:
        """
        计算健康分数 (0-100)
        """
        if total == 0:
            return 100  # 空系统默认健康
        
        score = 100
        
        # 扣分项
        
        # 1. 陈旧记忆 (-5每条，最高-25)
        stale_penalty = min(25, stale_count * 5)
        score -= stale_penalty
        
        # 2. 孤儿记忆 (-3每条，最高-15)
        orphan_penalty = min(15, orphaned_count * 3)
        score -= orphan_penalty
        
        # 3. 低重要性记忆过多 (-10)
        low_ratio = (importance_buckets["low"] + importance_buckets["critical"]) / max(1, total)
        if low_ratio > 0.3:
            score -= 10
        
        # 4. 类型分布不均衡 (-5)
        if type_dist:
            max_type_ratio = max(type_dist.values()) / max(1, sum(type_dist.values()))
            if max_type_ratio > 0.8:
                score -= 5
        
        # 5. fact类型过多但preference过少 (-5)
        fact_count = type_dist.get("fact", 0)
        pref_count = type_dist.get("preference", 0)
        if fact_count > 0 and pref_count == 0:
            score -= 5
        elif fact_count > 20 and pref_count < 3:
            score -= 5
        
        return max(0, min(100, score))
    
    def _calc_avg_importance(self, importance_buckets: dict) -> float:
        """计算平均重要性"""
        total = sum(importance_buckets.values())
        if total == 0:
            return 0.0
        
        weighted_sum = (
            importance_buckets["high"] * 0.9 +
            importance_buckets["medium"] * 0.65 +
            importance_buckets["low"] * 0.4 +
            importance_buckets["critical"] * 0.15
        )
        
        return round(weighted_sum / total, 2)
    
    def _analyze_forgetting(self, memories: list) -> dict:
        """
        【P2新增】分析记忆的遗忘情况
        """
        try:
            from memory.weibull_forgetting import get_weibull_decay
            
            decay = get_weibull_decay()
            
            if not memories:
                return {"total": 0, "should_forget": 0, "avg_current": 1.0}
            
            should_forget = 0
            total_current = 0.0
            
            for mem in memories:
                info = decay.get_importance_with_decay(mem)
                total_current += info["current"]
                if info["should_forget"]:
                    should_forget += 1
            
            return {
                "total": len(memories),
                "should_forget": should_forget,
                "forget_ratio": round(should_forget / len(memories), 3),
                "avg_current_importance": round(total_current / len(memories), 3),
                "weibull_shape": decay.shape,
                "weibull_scale": decay.scale
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _generate_suggestions(self, total: int, stale_count: int,
                            orphaned_count: int, importance_buckets: dict,
                            type_dist: dict, forgetting_analysis: dict = None) -> list:
        """生成优化建议"""
        suggestions = []
        
        if total == 0:
            suggestions.append({
                "type": "info",
                "message": "记忆库为空，开始使用后将自动积累记忆"
            })
            return suggestions
        
        # 陈旧记忆建议
        if stale_count > 0:
            suggestions.append({
                "type": "warning",
                "message": f"{stale_count}条记忆超过{self.warm_ttl_days}天未访问，建议归档或删除"
            })
        
        # 孤儿记忆建议
        if orphaned_count > 0:
            suggestions.append({
                "type": "warning",
                "message": f"{orphaned_count}条记忆缺少来源信息，可能是噪音存储"
            })
        
        # 重要性分布建议
        low_ratio = (importance_buckets["low"] + importance_buckets["critical"]) / max(1, total)
        if low_ratio > 0.3:
            suggestions.append({
                "type": "action",
                "message": f"{(low_ratio*100):.0f}%的记忆重要性较低，建议运行 auto_tier 清理"
            })
        
        # 类型分布建议
        pref_count = type_dist.get("preference", 0)
        if pref_count < 3 and total > 20:
            suggestions.append({
                "type": "tip",
                "message": "preference类型记忆偏少，多存储用户偏好可提升个性化"
            })
        
        fact_count = type_dist.get("fact", 0)
        if fact_count > 50 and pref_count < fact_count / 20:
            suggestions.append({
                "type": "tip",
                "message": "fact类型记忆占主导，考虑存储更多 lessons 和 decisions"
            })
        
        # 【P2新增】遗忘建议
        if forgetting_analysis and not forgetting_analysis.get("error"):
            forget_ratio = forgetting_analysis.get("forget_ratio", 0)
            if forget_ratio > 0.2:
                suggestions.append({
                    "type": "action",
                    "message": f"{(forget_ratio*100):.0f}%的记忆已接近遗忘阈值，建议运行 auto_tier 清理"
                })
            elif forget_ratio > 0.1:
                suggestions.append({
                    "type": "tip",
                    "message": f"{(forget_ratio*100):.0f}%的记忆正在衰减，考虑定期访问重要记忆"
                })
        
        # 健康度良好
        if len(suggestions) == 0:
            suggestions.append({
                "type": "success",
                "message": "记忆系统健康，无需特殊处理"
            })
        
        return suggestions
    
    def _get_status_label(self, score: int) -> str:
        """获取状态标签"""
        if score >= 90:
            return "excellent"
        elif score >= 75:
            return "good"
        elif score >= 50:
            return "fair"
        elif score >= 25:
            return "poor"
        else:
            return "critical"
    
    def get_dashboard(self) -> dict:
        """
        获取仪表盘数据（用于展示）
        """
        report = self.generate_report()
        
        return {
            "score": report["health_score"],
            "status": report["status"],
            "summary": report["summary"],
            "distributions": report["distributions"],
            "suggestions": report["suggestions"],
            "last_checked": report["generated_at"]
        }


# 全局实例
_health_instance = None


def get_health() -> MemoryHealth:
    """懒加载单例"""
    global _health_instance
    if _health_instance is None:
        _health_instance = MemoryHealth()
    return _health_instance
