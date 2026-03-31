#!/usr/bin/env python3
"""
Claw Memory CLI 工具
命令行快速使用记忆系统
"""

import sys
import argparse
import json


def cmd_store(args):
    """存储记忆"""
    from memory_main import get_db
    
    db = get_db()
    result = db.store({
        "content": args.content,
        "type": args.type or "fact",
        "importance": args.importance or 0.5
    })
    
    if result.get("success", True):
        mem_id = result.get('id') or result.get('memory_id', 'unknown')
        print(f"✅ 记忆已存储: {mem_id}")
    else:
        error_msg = result.get('error') or result.get('message', 'unknown')
        print(f"❌ 存储失败: {error_msg}")


def cmd_search(args):
    """搜索记忆"""
    from memory_main import get_db
    
    db = get_db()
    results = db.search_rrf(args.query, limit=args.limit or 5)
    
    if not results:
        print("未找到相关记忆")
        return
    
    print(f"找到 {len(results)} 条记忆:\n")
    for i, r in enumerate(results, 1):
        content = r.get("content", "")[:60]
        score = r.get("_final_score", r.get("score", 0))
        mtype = r.get("type", "")
        print(f"{i}. [{mtype}] {content}... (分数: {score:.3f})")


def cmd_stats(args):
    """查看统计"""
    from memory_main import get_db
    
    db = get_db()
    stats = db.stats()
    
    print("📊 记忆统计:")
    print(f"   总记忆数: {stats.get('total_memories', 'N/A')}")
    print(f"   类型分布: {stats.get('type_distribution', {})}")


def cmd_health(args):
    """健康检查"""
    from memory_main import get_db
    
    db = get_db()
    health = db.health()
    
    print("🏥 系统状态:")
    for key, value in health.items():
        status = "✅" if value.get("status") == "ok" else "❌"
        print(f"   {status} {key}: {value}")


def cmd_backup(args):
    """备份记忆"""
    from memory_backup import memory_backup
    
    result = memory_backup(action="create")
    if result.get("success"):
        print(f"✅ 备份成功: {result.get('message')}")
    else:
        print(f"❌ 备份失败: {result.get('error')}")


def cmd_list(args):
    """列出最近记忆"""
    from memory_main import get_db
    
    db = get_db()
    results = db.search("", limit=args.limit or 10)
    
    print(f"最近 {len(results)} 条记忆:\n")
    for i, r in enumerate(results, 1):
        content = r.get("content", "")[:50]
        mtype = r.get("type", "")
        created = r.get("created_at", "")[:10] if r.get("created_at") else "N/A"
        print(f"{i}. [{mtype}] {content}... ({created})")


def main():
    parser = argparse.ArgumentParser(
        description="Claw Memory CLI - AI记忆系统命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # store 命令
    store_parser = subparsers.add_parser("store", help="存储记忆")
    store_parser.add_argument("content", help="记忆内容")
    store_parser.add_argument("-t", "--type", choices=["fact", "preference", "decision", "lesson", "entity", "task_state"], help="记忆类型")
    store_parser.add_argument("-i", "--importance", type=float, help="重要性 (0.0-1.0)")
    store_parser.set_defaults(func=cmd_store)
    
    # search 命令
    search_parser = subparsers.add_parser("search", help="搜索记忆")
    search_parser.add_argument("query", help="搜索查询")
    search_parser.add_argument("-l", "--limit", type=int, help="返回数量")
    search_parser.set_defaults(func=cmd_search)
    
    # stats 命令
    stats_parser = subparsers.add_parser("stats", help="查看统计")
    stats_parser.set_defaults(func=cmd_stats)
    
    # health 命令
    health_parser = subparsers.add_parser("health", help="健康检查")
    health_parser.set_defaults(func=cmd_health)
    
    # backup 命令
    backup_parser = subparsers.add_parser("backup", help="备份记忆")
    backup_parser.set_defaults(func=cmd_backup)
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="列出最近记忆")
    list_parser.add_argument("-l", "--limit", type=int, help="返回数量")
    list_parser.set_defaults(func=cmd_list)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
