"""
Claw Memory 备份与导出模块
【P1新增】解决数据备份和迁移问题
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# 备份目录
BACKUP_DIR = Path(__file__).parent / "backups"


def memory_backup(action: str = "create", output_path: str = None) -> dict:
    """
    【P1新增】记忆备份与导出 API
    
    Args:
        action: 操作
            - create: 创建备份
            - list: 列出已有备份
            - restore: 恢复备份
            - delete: 删除备份
        output_path: 输出路径（create时指定备份文件路径）
    
    Returns:
        操作结果
    """
    global BACKUP_DIR
    
    if action == "create":
        return _create_backup(output_path)
    elif action == "list":
        return _list_backups()
    elif action == "restore":
        return _restore_backup(output_path)
    elif action == "delete":
        return _delete_backup(output_path)
    elif action == "export_json":
        return _export_json(output_path)
    elif action == "import_json":
        return _import_json(output_path)
    else:
        return {"success": False, "error": f"未知action: {action}"}


def _create_backup(output_path: str = None) -> dict:
    """创建备份"""
    try:
        from lancedb_store import get_db_store
        
        db = get_db_store()
        if db.table is None:
            return {"success": False, "error": "数据库未初始化"}
        
        # 生成备份文件名
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = BACKUP_DIR / f"memory_backup_{timestamp}.json"
        else:
            output_path = Path(output_path)
        
        # 确保备份目录存在
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        # 导出数据
        backup_data = {
            "version": "1.8.0",
            "created_at": datetime.now().isoformat(),
            "memories": []
        }
        
        # 获取所有记忆
        total = db.table.count_rows()
        sample = db.table.head(min(total, 10000)).to_pylist()
        backup_data["memories"] = sample
        backup_data["count"] = len(sample)
        
        # 保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": f"备份已创建: {output_path}",
            "count": len(sample)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def _list_backups() -> dict:
    """列出所有备份"""
    try:
        if not BACKUP_DIR.exists():
            return {"success": True, "backups": [], "count": 0}
        
        backups = []
        for f in BACKUP_DIR.glob("memory_backup_*.json"):
            stat = f.stat()
            backups.append({
                "name": f.name,
                "path": str(f),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
        
        # 按时间排序
        backups.sort(key=lambda x: x["created"], reverse=True)
        
        return {
            "success": True,
            "backups": backups,
            "count": len(backups)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def _restore_backup(backup_path: str) -> dict:
    """恢复备份"""
    try:
        from lancedb_store import get_db_store
        
        backup_path = Path(backup_path)
        if not backup_path.exists():
            return {"success": False, "error": "备份文件不存在"}
        
        # 读取备份
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        memories = backup_data.get("memories", [])
        
        # 创建新数据库实例
        db = get_db_store()
        
        # 导入记忆
        count = 0
        for mem in memories:
            try:
                db.store(
                    memory_type=mem.get("type", "unknown"),
                    content=mem.get("content", ""),
                    summary=mem.get("summary", ""),
                    importance=mem.get("importance", 0.5),
                    source=mem.get("source", "backup"),
                    metadata=mem
                )
                count += 1
            except:
                pass
        
        return {
            "success": True,
            "message": f"已恢复 {count} 条记忆",
            "restored": count
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def _delete_backup(backup_path: str) -> dict:
    """删除备份"""
    try:
        backup_path = Path(backup_path)
        if backup_path.exists():
            backup_path.unlink()
            return {"success": True, "message": f"已删除: {backup_path}"}
        else:
            return {"success": False, "error": "文件不存在"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _export_json(output_path: str = None) -> dict:
    """导出为JSON格式"""
    return _create_backup(output_path)


def _import_json(input_path: str) -> dict:
    """从JSON导入"""
    return _restore_backup(input_path)


# 便捷函数
def quick_backup() -> str:
    """快速备份到默认位置"""
    result = _create_backup()
    if result["success"]:
        return result["message"]
    return f"备份失败: {result['error']}"


def incremental_backup(since: str = None) -> dict:
    """
    【P2新增】增量备份 - 只备份自指定时间以来更改的记忆
    
    Args:
        since: ISO格式时间字符串，如 "2026-03-31T00:00:00"
               如果为None，则使用上次备份时间
    
    Returns:
        增量备份结果
    """
    try:
        from lancedb_store import get_db_store
        
        db = get_db_store()
        if db.table is None:
            return {"success": False, "error": "数据库未初始化"}
        
        # 确定起始时间
        if since is None:
            # 查找最近备份时间
            result = _list_backups()
            if result.get("backups") and len(result["backups"]) > 0:
                since = result["backups"][0]["created"]
            else:
                since = "1970-01-01T00:00:00"
        
        # 查询更改的记忆
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        
        # 获取所有记忆并过滤
        total = db.table.count_rows()
        all_memories = db.table.head(min(total, 100000)).to_pylist()
        
        changed = [
            m for m in all_memories 
            if m.get("updated_at") and 
            datetime.fromisoformat(m["updated_at"].replace("Z", "+00:00")) > since_dt
        ]
        
        # 保存增量备份
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = BACKUP_DIR / f"memory_incr_{timestamp}.json"
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        backup_data = {
            "version": "2.8.0",
            "type": "incremental",
            "since": since,
            "created_at": datetime.now().isoformat(),
            "memories": changed,
            "count": len(changed)
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        return {
            "success": True,
            "message": f"增量备份已创建: {output_path}",
            "since": since,
            "changed_count": len(changed)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def auto_backup_schedule(interval_hours: int = 24, max_backups: int = 7) -> dict:
    """
    【P2新增】自动备份调度 - 清理旧备份，保留最新N个
    
    Args:
        interval_hours: 备份间隔（小时）
        max_backups: 最多保留备份数
    
    Returns:
        调度结果
    """
    try:
        import time
        
        # 创建新备份
        result = _create_backup()
        if not result["success"]:
            return result
        
        # 列出备份并清理旧备份
        result = _list_backups()
        backups = result.get("backups", [])
        
        # 删除多余备份（保留最新max_backups个）
        deleted = 0
        for backup in backups[max_backups:]:
            try:
                Path(backup["path"]).unlink()
                deleted += 1
            except:
                pass
        
        return {
            "success": True,
            "message": f"自动备份完成，保留{min(len(backups), max_backups)}个，删除{deleted}个旧备份",
            "deleted": deleted,
            "kept": min(len(backups) + 1, max_backups)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # 测试
    print("=== 备份测试 ===")
    result = memory_backup(action="list")
    print(f"现有备份: {result}")
