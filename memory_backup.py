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


if __name__ == "__main__":
    # 测试
    print("=== 备份测试 ===")
    result = memory_backup(action="list")
    print(f"现有备份: {result}")
