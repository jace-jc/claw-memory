"""
Claw Memory 性能监控模块
追踪系统性能指标，帮助优化
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class PerformanceMetric:
    """性能指标"""
    operation: str
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error: Optional[str] = None


class PerformanceMonitor:
    """
    性能监控器
    
    追踪各操作的耗时，帮助发现性能瓶颈
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Args:
            max_history: 最多保留的历史记录数
        """
        self.max_history = max_history
        self._metrics: List[PerformanceMetric] = []
        self._operation_stats: Dict[str, Dict] = {}
    
    def record(self, operation: str, duration_ms: float, success: bool = True, error: str = None):
        """
        记录一次操作
        
        Args:
            operation: 操作名称
            duration_ms: 耗时（毫秒）
            success: 是否成功
            error: 错误信息
        """
        metric = PerformanceMetric(
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            error=error
        )
        
        self._metrics.append(metric)
        
        # 维护操作统计
        if operation not in self._operation_stats:
            self._operation_stats[operation] = {
                "count": 0,
                "total_ms": 0,
                "success_count": 0,
                "error_count": 0,
                "min_ms": float("inf"),
                "max_ms": 0
            }
        
        stats = self._operation_stats[operation]
        stats["count"] += 1
        stats["total_ms"] += duration_ms
        stats["success_count"] += 1 if success else 0
        stats["error_count"] += 1 if not success else 0
        stats["min_ms"] = min(stats["min_ms"], duration_ms)
        stats["max_ms"] = max(stats["max_ms"], duration_ms)
        
        # 清理超长历史
        if len(self._metrics) > self.max_history:
            self._metrics = self._metrics[-self.max_history:]
    
    def get_stats(self, operation: str = None) -> Dict:
        """
        获取统计数据
        
        Args:
            operation: 操作名称，None表示所有操作
            
        Returns:
            统计数据
        """
        if operation:
            if operation not in self._operation_stats:
                return {}
            
            stats = self._operation_stats[operation].copy()
            if stats["count"] > 0:
                stats["avg_ms"] = stats["total_ms"] / stats["count"]
                stats["success_rate"] = stats["success_count"] / stats["count"]
            return stats
        
        # 所有操作统计
        result = {}
        for op, stats in self._operation_stats.items():
            stats_copy = stats.copy()
            if stats_copy["count"] > 0:
                stats_copy["avg_ms"] = stats_copy["total_ms"] / stats_copy["count"]
                stats_copy["success_rate"] = stats_copy["success_count"] / stats_copy["count"]
            result[op] = stats_copy
        
        return result
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        """
        获取最近的操作记录
        
        Args:
            limit: 返回数量
            
        Returns:
            最近的操作列表
        """
        recent = self._metrics[-limit:]
        return [
            {
                "operation": m.operation,
                "duration_ms": m.duration_ms,
                "success": m.success,
                "error": m.error,
                "timestamp": m.timestamp.isoformat()
            }
            for m in reversed(recent)
        ]
    
    def get_slow_operations(self, threshold_ms: float = 1000) -> List[Dict]:
        """
        获取慢操作
        
        Args:
            threshold_ms: 慢操作阈值（毫秒）
            
        Returns:
            慢操作列表
        """
        slow = [m for m in self._metrics if m.duration_ms > threshold_ms]
        return [
            {
                "operation": m.operation,
                "duration_ms": m.duration_ms,
                "timestamp": m.timestamp.isoformat()
            }
            for m in reversed(slow[-10:])
        ]
    
    def reset(self):
        """重置监控数据"""
        self._metrics.clear()
        self._operation_stats.clear()


# 装饰器：自动监控函数性能
def monitor(monitor_instance: PerformanceMonitor, operation_name: str = None):
    """
    函数性能监控装饰器
    
    用法:
        monitor_instance = PerformanceMonitor()
        
        @monitor(monitor_instance, "my_operation")
        def my_function():
            ...
    """
    def decorator(func):
        name = operation_name or func.__name__
        
        def wrapper(*args, **kwargs):
            start = time.time()
            success = True
            error = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                duration_ms = (time.time() - start) * 1000
                monitor_instance.record(name, duration_ms, success, error)
        
        return wrapper
    return decorator


# 全局实例
_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """获取性能监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


def record_performance(operation: str, duration_ms: float, success: bool = True, error: str = None):
    """快捷记录函数"""
    get_monitor().record(operation, duration_ms, success, error)
