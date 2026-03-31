"""
Claw Memory 自动备份调度
定时自动备份，确保数据安全
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable
from pathlib import Path


class AutoBackupScheduler:
    """
    自动备份调度器
    
    支持：
    - 定时备份（每小时/每天/每周）
    - 增量备份
    - 备份数量限制（保留最新N个）
    """
    
    def __init__(
        self,
        interval_hours: float = 24,
        max_backups: int = 7,
        incremental: bool = True
    ):
        """
        Args:
            interval_hours: 备份间隔（小时）
            max_backups: 最多保留备份数
            incremental: 是否使用增量备份
        """
        self.interval_hours = interval_hours
        self.max_backups = max_backups
        self.incremental = incremental
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_backup: Optional[datetime] = None
    
    def start(self, callback: Optional[Callable] = None):
        """
        启动自动备份调度
        
        Args:
            callback: 备份完成后的回调函数
        """
        if self._running:
            print("[AutoBackup] 调度器已在运行")
            return
        
        self._running = True
        self._callback = callback
        
        def run():
            while self._running:
                self._perform_backup()
                # 等待下一个备份时间
                interval_seconds = self.interval_hours * 3600
                for _ in range(int(interval_seconds)):
                    if not self._running:
                        break
                    time.sleep(1)
        
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        print(f"[AutoBackup] 调度器已启动，间隔 {self.interval_hours} 小时")
    
    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[AutoBackup] 调度器已停止")
    
    def _perform_backup(self):
        """执行备份"""
        from memory_backup import memory_backup, incremental_backup, auto_backup_schedule
        
        try:
            print(f"[AutoBackup] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 开始备份...")
            
            if self.incremental:
                result = incremental_backup()
            else:
                result = auto_backup_schedule(
                    interval_hours=self.interval_hours,
                    max_backups=self.max_backups
                )
            
            if result.get("success"):
                self._last_backup = datetime.now()
                count = result.get("changed_count", result.get("count", 0))
                print(f"[AutoBackup] ✅ 备份成功 ({count} 条记忆)")
                
                if self._callback:
                    self._callback(result)
            else:
                print(f"[AutoBackup] ❌ 备份失败: {result.get('error')}")
                
        except Exception as e:
            print(f"[AutoBackup] ❌ 备份异常: {e}")
    
    def backup_now(self) -> dict:
        """立即执行一次备份"""
        self._perform_backup()
        return {"success": True, "time": datetime.now().isoformat()}
    
    @property
    def is_running(self) -> bool:
        """调度器是否在运行"""
        return self._running
    
    @property
    def last_backup_time(self) -> Optional[datetime]:
        """上次备份时间"""
        return self._last_backup


# 全局调度器实例
_scheduler: Optional[AutoBackupScheduler] = None


def get_scheduler() -> AutoBackupScheduler:
    """获取调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AutoBackupScheduler()
    return _scheduler


def start_auto_backup(
    interval_hours: float = 24,
    max_backups: int = 7
) -> AutoBackupScheduler:
    """启动自动备份（便捷函数）"""
    scheduler = get_scheduler()
    scheduler.interval_hours = interval_hours
    scheduler.max_backups = max_backups
    scheduler.start()
    return scheduler


def stop_auto_backup():
    """停止自动备份"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()


if __name__ == "__main__":
    # 测试
    print("=== 自动备份调度测试 ===")
    scheduler = AutoBackupScheduler(interval_hours=0.1, max_backups=3)  # 6分钟一次
    scheduler.start()
    
    # 运行一小段时间后停止
    time.sleep(2)
    scheduler.stop()
    
    print("测试完成")
