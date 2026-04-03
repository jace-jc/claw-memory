"""
API: Health check - broken out of memory_main.py to fix circular dependency

This module provides the memory_health tool function without importing from memory_main.
Instead, it accepts data as parameters or uses lazy imports inside functions.
"""
from datetime import datetime, timedelta
from collections import defaultdict

# Lazy imports for stats and db - called inside functions, not at module load time


class MemoryHealthAPI:
    """
    记忆健康度监控 - API层
    不直接依赖 memory_main，使用传入的数据进行分析
    """
    
    def __init__(self):
        from core.memory_config import CONFIG
        self.min_importance = CONFIG.get("min_importance", 0.3)
        self.warm_ttl_days = CONFIG.get("warm_ttl_days", 30)
        self.hot_ttl_hours = CONFIG.get("hot_ttl_hours", 24)
    
    def generate_report(self, stats: dict, all_memories: list) -> dict:
        """
        生成记忆健康报告
        
        Args:
            stats: memory_stats() 返回的统计信息
            all_memories: 数据库中的所有记忆列表
        """
        warm = stats.get("warm_store", {})
        cold = stats.get("cold_store", {})
        
        # 分析类型分布
        type_dist = warm.get("by_type", {})
        
        # 计算重要性分布
        importance_buckets = {"high": 0, "medium": 0, "low": 0, "critical": 0}
        
        try:
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
        health_score = self._calc_health_score(
            total, stale_count, orphaned_count, importance_buckets
        )
        
        return {
            "health_score": health_score,
            "total_memories": total,
            "stale_memories": stale_count,
            "orphaned_memories": orphaned_count,
            "type_distribution": type_dist,
            "importance": importance_buckets,
            "avg_importance": self._calc_avg_importance(importance_buckets),
            "memories_above_threshold": importance_buckets["high"] + importance_buckets["medium"],
            "recommendations": self._generate_recommendations(
                total, stale_count, orphaned_count, importance_buckets
            ),
        }
    
    def _calc_health_score(self, total: int, stale_count: int,
                           orphaned_count: int, importance_buckets: dict) -> float:
        """计算健康分数 (0-100)"""
        if total == 0:
            return 100.0
        
        # 基础分
        score = 100.0
        
        # 陈旧记忆扣分
        stale_ratio = stale_count / max(1, total)
        score -= stale_ratio * 30
        
        # 孤立记忆扣分
        orphaned_ratio = orphaned_count / max(1, total)
        score -= orphaned_ratio * 20
        
        # 低重要性记忆过多扣分
        low_ratio = (importance_buckets["low"] + importance_buckets["critical"]) / max(1, total)
        score -= low_ratio * 25
        
        return max(0.0, min(100.0, score))
    
    def _calc_avg_importance(self, importance_buckets: dict) -> float:
        """计算平均重要性分数"""
        total = sum(importance_buckets.values())
        if total == 0:
            return 0.5
        
        return (
            importance_buckets["high"] * 0.9 +
            importance_buckets["medium"] * 0.65 +
            importance_buckets["low"] * 0.4 +
            importance_buckets["critical"] * 0.15
        ) / total
    
    def _generate_recommendations(self, total: int, stale_count: int,
                                   orphaned_count: int, importance_buckets: dict) -> list:
        """生成改善建议"""
        recommendations = []
        
        if total == 0:
            recommendations.append("系统还没有记忆，开始积累吧！")
            return recommendations
        
        if stale_count > total * 0.3:
            recommendations.append(f"有 {stale_count} 条记忆超过30天未访问，考虑清理或强化重要记忆")
        
        if orphaned_count > total * 0.1:
            recommendations.append(f"有 {orphaned_count} 条孤立记忆（无来源），建议审查是否为噪音")
        
        if importance_buckets["critical"] > total * 0.2:
            recommendations.append(f"有 {importance_buckets['critical']} 条极低重要性记忆，建议清理")
        
        if not recommendations:
            recommendations.append("记忆系统状态良好！")
        
        return recommendations


# Lazy import helper for weibull decay
def _get_weibull_decay():
    """Lazy import weibull_forgetting"""
    try:
        from weibull_forgetting import get_weibull_decay
        return get_weibull_decay()
    except ImportError:
        return None


# Main tool function
def memory_health(action: str = "report") -> dict:
    """
    记忆健康度检查工具
    
    Args:
        action: "report" (默认) 返回健康报告
               "stats" 返回简要统计
               "decay" 返回衰减曲线信息
    """
    try:
        # Lazy imports to avoid circular dependency
        from memory_main import get_db, memory_stats
        
        db = get_db()
        stats = memory_stats()
        
        # 获取所有记忆用于详细分析
        all_memories = []
        try:
            if db.table:
                all_memories = db.table.to_arrow().to_pylist()
        except Exception:
            pass
        
        health_api = MemoryHealthAPI()
        
        if action == "stats":
            return {
                "total": stats.get("total_memories", 0),
                "warm": stats.get("warm_store", {}).get("total", 0),
                "cold": stats.get("cold_store", {}).get("total", 0),
            }
        
        elif action == "decay":
            weibull = _get_weibull_decay()
            if weibull:
                return {
                    "decay_enabled": True,
                    "curve": weibull.get_decay_curve(days=30),
                }
            return {"decay_enabled": False}
        
        # Default: full report
        return health_api.generate_report(stats, all_memories)
        
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc() if hasattr(traceback, 'format_exc') else "",
        }


def get_health():
    """获取健康检查实例"""
    return MemoryHealthAPI()
