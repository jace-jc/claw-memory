"""
记忆系统CLI工具

提供 stats / list / search / delete 等命令

参考 memory-lancedb-pro 的 CLI 设计
"""
import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


# CLI颜色输出
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def color(text: str, color_code: str) -> str:
    """给文本添加颜色"""
    return f"{color_code}{text}{Colors.ENDC}"


def green(text: str) -> str:
    return color(text, Colors.OKGREEN)


def red(text: str) -> str:
    return color(text, Colors.FAIL)


def blue(text: str) -> str:
    return color(text, Colors.OKBLUE)


def yellow(text: str) -> str:
    return color(text, Colors.WARNING)


def bold(text: str) -> str:
    return color(text, Colors.BOLD)


class MemoryCLI:
    """
    记忆系统CLI工具
    
    命令：
    - stats: 查看记忆统计
    - list: 列出记忆
    - search: 搜索记忆
    - delete: 删除记忆
    - export: 导出记忆
    - import: 导入记忆
    """
    
    def __init__(self, memory_path: str = None):
        """
        Args:
            memory_path: 记忆文件路径，默认 ~/.openclaw/workspace/memory
        """
        self.memory_path = Path(memory_path or 
            os.path.expanduser("~/.openclaw/workspace/memory"))
        self.stats_file = self.memory_path / "stats.json"
        self.recall_guard_file = self.memory_path / "recall_guard.json"
        self.unification_file = self.memory_path / "unification_report.json"
    
    def cmd_stats(self, args) -> int:
        """查看记忆统计（使用LanceDBStore）"""
        print(bold("\n🧠 记忆系统统计\n"))

        try:
            from lancedb_store import LanceDBStore
            db = LanceDBStore()

            if db.table is None:
                print(red("数据库未初始化"))
                return 1

            # 1. 基础统计
            total_count = db.table.count_rows()
            print(f"📁 总记忆数: {green(str(total_count))}")

            # 2. 按类型统计
            try:
                sample = db.table.head(min(1000, total_count))
                if hasattr(sample, 'to_pylist'):
                    memories = sample.to_pylist()
                    types = {}
                    total_importance = 0.0
                    for mem in memories:
                        mem_type = mem.get("type", "unknown")
                        types[mem_type] = types.get(mem_type, 0) + 1
                        total_importance += mem.get("importance", 0.5)

                    print(f"\n📂 按类型分布:")
                    for mem_type, count in sorted(types.items(), key=lambda x: -x[1]):
                        print(f"   {mem_type}: {green(str(count))}")

                    if memories:
                        avg_importance = total_importance / len(memories)
                        print(f"\n📈 平均重要性: {green(f'{avg_importance:.2f}')}")
            except Exception as e:
                print(f"   {yellow(f'统计失败: {e}')}")

            # 3. 存储分层（基于importance）
            print(f"\n📊 重要性分层:")
            try:
                sample = db.table.head(min(500, total_count))
                if hasattr(sample, 'to_pylist'):
                    memories = sample.to_pylist()
                    tiers = {"HIGH (>=0.8)": 0, "MEDIUM (0.5-0.8)": 0, "LOW (<0.5)": 0}
                    for mem in memories:
                        imp = mem.get("importance", 0.5)
                        if imp >= 0.8:
                            tiers["HIGH (>=0.8)"] += 1
                        elif imp >= 0.5:
                            tiers["MEDIUM (0.5-0.8)"] += 1
                        else:
                            tiers["LOW (<0.5)"] += 1

                    for tier, count in tiers.items():
                        print(f"   {tier}: {green(str(count))}")
            except Exception as e:
                print(f"   {yellow(f'分层统计失败: {e}')}")

        except Exception as e:
            print(red(f"数据库连接失败: {e}"))
            return 1

        print()
        return 0
    
    def cmd_list(self, args) -> int:
        """列出记忆（使用LanceDBStore）"""
        print(bold(f"\n📋 记忆列表 (top {args.limit})\n"))

        try:
            from lancedb_store import LanceDBStore
            db = LanceDBStore()

            if db.table is None:
                print(yellow("数据库未初始化"))
                return 0

            # 获取记忆列表
            total = db.table.count_rows()
            if total == 0:
                print(yellow("暂无记忆"))
                return 0

            # 获取最近更新的记忆
            try:
                # 使用head获取数据，然后按updated_at排序
                sample = db.table.head(min(args.limit * 2, total))
                if hasattr(sample, 'to_pylist'):
                    memories = sample.to_pylist()

                    # 按updated_at降序排序
                    memories.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

                    for mem in memories[:args.limit]:
                        mem_id = mem.get("id", "unknown")[:16]
                        mem_type = mem.get("type", "unknown")
                        content = mem.get("content", "")
                        importance = mem.get("importance", 0.5)

                        # 预览内容
                        preview = content.replace("\n", " ")[:60]

                        # 更新时间
                        updated_at = mem.get("updated_at", "")
                        if updated_at:
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(updated_at)
                                time_str = dt.strftime('%Y-%m-%d %H:%M')
                            except:
                                time_str = updated_at[:16]
                        else:
                            time_str = "unknown"

                        print(f"{blue(mem_id)} [{mem_type}] (重要性: {importance:.2f})")
                        print(f"   {preview}...")
                        print(f"   {green(str(len(content)))} bytes | {time_str}")
                        print()

                    if len(memories) > args.limit:
                        print(yellow(f"... 还有 {len(memories) - args.limit} 个记忆"))
                else:
                    print(yellow("无法读取记忆数据"))
            except Exception as e:
                print(red(f"列出记忆失败: {e}"))

        except Exception as e:
            print(red(f"数据库连接失败: {e}"))
            return 1

        print()
        return 0
    
    def cmd_search(self, args) -> int:
        """搜索记忆（使用LanceDBStore语义搜索）"""
        if not args.query:
            print(red("错误: 请提供搜索关键词"))
            return 1

        print(bold(f"\n🔍 语义搜索: {args.query}\n"))

        try:
            from lancedb_store import LanceDBStore
            db = LanceDBStore()

            if db.table is None:
                print(yellow("数据库未初始化"))
                return 0

            # 执行语义搜索
            use_rerank = not args.no_rerank
            results = db.search(args.query, limit=10, use_rerank=use_rerank)

            if not results:
                print(yellow("未找到匹配结果"))
                return 0

            print(f"找到 {green(str(len(results)))} 个匹配:\n")

            for i, r in enumerate(results):
                mem_id = r.get("id", "unknown")[:16]
                mem_type = r.get("type", "unknown")
                content = r.get("content", "")
                importance = r.get("importance", 0.5)
                similarity = r.get("_similarity", 0.0)
                final_score = r.get("_final_score", similarity)

                # 显示搜索结果
                print(f"{i+1}. {blue(mem_id)} [{mem_type}] (重要性: {importance:.2f}, 相似度: {final_score:.3f})")

                # 显示内容预览（高亮关键词）
                preview = content.replace("\n", " ")[:150]
                query_lower = args.query.lower()
                if query_lower in preview.lower():
                    # 简单高亮
                    idx = preview.lower().find(query_lower)
                    if idx >= 0:
                        highlighted = preview[:idx] + yellow(preview[idx:idx+len(args.query)]) + preview[idx+len(args.query):]
                        print(f"   {highlighted}...")
                    else:
                        print(f"   {preview}...")
                else:
                    print(f"   {preview}...")

                # 显示更新时间
                updated_at = r.get("updated_at", "")
                if updated_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(updated_at)
                        print(f"   {green(str(len(content)))} bytes | {dt.strftime('%Y-%m-%d %H:%M')}")
                    except:
                        print(f"   {green(str(len(content)))} bytes")
                else:
                    print(f"   {green(str(len(content)))} bytes")

                print()

        except Exception as e:
            print(red(f"搜索失败: {e}"))
            import traceback
            traceback.print_exc()
            return 1

        return 0
    
    def cmd_delete(self, args) -> int:
        """删除记忆"""
        if not args.name:
            print(red("错误: 请提供要删除的记忆文件名"))
            return 1
        
        file_path = self.memory_path / args.name
        if not file_path.exists():
            print(red(f"文件不存在: {args.name}"))
            return 1
        
        if not args.force:
            confirm = input(f"确认删除 {red(args.name)}? (y/N): ")
            if confirm.lower() != "y":
                print("取消删除")
                return 0
        
        try:
            file_path.unlink()
            print(green(f"已删除: {args.name}"))
        except Exception as e:
            print(red(f"删除失败: {e}"))
            return 1
        
        return 0
    
    def cmd_export(self, args) -> int:
        """导出记忆"""
        output_file = args.output or f"memory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        print(bold(f"\n💾 导出记忆到: {output_file}\n"))
        
        md_files = list(self.memory_path.glob("*.md"))
        md_files = [f for f in md_files if f.name not in ["MEMORY.md", "README.md"]]
        
        export_data = {
            "exported_at": datetime.now().isoformat(),
            "count": len(md_files),
            "memories": []
        }
        
        for f in md_files:
            try:
                content = f.read_text()
                export_data["memories"].append({
                    "name": f.name,
                    "content": content,
                    "size": len(content),
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                })
            except:
                pass
        
        try:
            with open(output_file, "w") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(green(f"导出成功: {len(md_files)} 个记忆"))
            print(f"保存至: {output_file}")
        except Exception as e:
            print(red(f"导出失败: {e}"))
            return 1
        
        return 0
    
    def cmd_import(self, args) -> int:
        """导入记忆"""
        if not args.file:
            print(red("错误: 请提供导入文件"))
            return 1
        
        input_file = Path(args.file)
        if not input_file.exists():
            print(red(f"文件不存在: {args.file}"))
            return 1
        
        print(bold(f"\n📥 导入记忆从: {args.file}\n"))
        
        try:
            with open(input_file) as f:
                data = json.load(f)
            
            memories = data.get("memories", [])
            imported = 0
            
            for mem in memories:
                name = mem.get("name", "imported.md")
                content = mem.get("content", "")
                
                if not content:
                    continue
                
                # 避免覆盖现有文件
                target = self.memory_path / name
                if target.exists() and not args.force:
                    name = f"imported_{name}"
                    target = self.memory_path / name
                
                target.write_text(content)
                imported += 1
            
            print(green(f"导入成功: {imported} 个记忆"))
            
        except Exception as e:
            print(red(f"导入失败: {e}"))
            return 1
        
        return 0
    
    def cmd_dedup(self, args) -> int:
        """执行去重"""
        print(bold("\n🔗 执行记忆去重\n"))
        
        try:
            from memory.data_unification import MemoryUnifier
            unifier = MemoryUnifier()
            report = unifier.unify()
            
            print(f"总发现: {green(str(report.get('total_found', 0)))}")
            print(f"唯一记忆: {green(str(report.get('unique_memories', 0)))}")
            print(f"消除重复: {red(str(report.get('duplicates_eliminated', 0)))}")
            print(f"去重率: {yellow(report.get('deduplication_rate', 'N/A'))}")
            
        except Exception as e:
            print(red(f"去重失败: {e}"))
            return 1
        
        return 0


def main():
    """CLI入口"""
    parser = argparse.ArgumentParser(
        description="🧠 Claw Memory CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # stats命令
    stats_parser = subparsers.add_parser("stats", help="查看记忆统计")
    
    # list命令
    list_parser = subparsers.add_parser("list", help="列出记忆")
    list_parser.add_argument("--limit", "-n", type=int, default=10, help="显示数量")
    
    # search命令
    search_parser = subparsers.add_parser("search", help="搜索记忆")
    search_parser.add_argument("query", type=str, help="搜索关键词")
    search_parser.add_argument("--no-rerank", action="store_true", help="禁用Cross-Encoder重排（离线环境用）")
    
    # delete命令
    delete_parser = subparsers.add_parser("delete", help="删除记忆")
    delete_parser.add_argument("name", type=str, help="记忆文件名")
    delete_parser.add_argument("--force", "-f", action="store_true", help="强制删除")
    
    # export命令
    export_parser = subparsers.add_parser("export", help="导出记忆")
    export_parser.add_argument("--output", "-o", type=str, help="输出文件路径")
    
    # import命令
    import_parser = subparsers.add_parser("import", help="导入记忆")
    import_parser.add_argument("file", type=str, help="导入文件路径")
    import_parser.add_argument("--force", "-f", action="store_true", help="强制覆盖")
    
    # dedup命令
    dedup_parser = subparsers.add_parser("dedup", help="执行记忆去重")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    cli = MemoryCLI()
    
    commands = {
        "stats": cli.cmd_stats,
        "list": cli.cmd_list,
        "search": cli.cmd_search,
        "delete": cli.cmd_delete,
        "export": cli.cmd_export,
        "import": cli.cmd_import,
        "dedup": cli.cmd_dedup,
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    exit(main())
