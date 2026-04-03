"""
Claw Memory 主入口 - 工具注册和调度（修复版）

Phase 3: This file is now a compatibility shim.
All implementation has been moved to api/ submodules.
Import from here for backward compatibility.
"""
import warnings
# 压制 SSL 警告（urllib3 v2 与 LibreSSL 兼容性问题，不影响功能）
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List, Union

# Import everything from api module for backward compatibility
from api import (
    memory_store,
    memory_search,
    memory_search_rrf,
    memory_adaptive,
    memory_recall,
    memory_forget,
    memory_kg,
    memory_kg_extract_and_link,
    memory_disambiguate,
    memory_tier,
    memory_tier_get,
    memory_tier_move,
    memory_tier_stats_v2,
    memory_stats,
    memory_health,
    memory_temporal,
    memory_temporal_extract,
    memory_cache,
    memory_batch,
    memory_transaction_stats,
    memory_extract_session,
    memory_auto_extract,
    auto_capture,
    auto_recall,
    api_response,
)

# Import extract functions directly (not through api to avoid circular)
from memory_extract import extract_from_messages, is_noise, quick_extract, deep_extract
from memory_config import CONFIG

# Lazy loading for db store
_db_store = None


def get_db():
    """Lazy import to avoid circular dependency"""
    global _db_store
    if _db_store is None:
        from lancedb_store import get_db_store
        _db_store = get_db_store()
    return _db_store


# ==================== 工具定义 ====================

TOOLS = {
    "memory_store": {
        "description": "存储新记忆到记忆系统",
        "params": {
            "content": {"type": "string", "required": True, "description": "记忆内容"},
            "type": {"type": "string", "description": "类型: fact|preference|decision|lesson|entity|task_state"},
            "importance": {"type": "number", "description": "重要性 0.0-1.0"},
            "tags": {"type": "array", "description": "标签列表"},
            "source_id": {"type": "string", "description": "来源消息ID"},
            "scope": {"type": "string", "description": "范围: global|user|project|agent|session|channel"},
        }
    },
    "memory_search": {
        "description": "搜索记忆（支持Cross-Encoder重排和多范围隔离）",
        "params": {
            "query": {"type": "string", "required": True, "description": "搜索查询"},
            "limit": {"type": "number", "description": "返回数量限制"},
            "types": {"type": "array", "description": "过滤类型"},
            "min_score": {"type": "number", "description": "最低重要性分数"},
            "scope": {"type": "string", "description": "范围过滤: global|user|project|agent|session|channel"},
            "use_rerank": {"type": "boolean", "description": "是否使用Cross-Encoder重排"},
        }
    },
    "memory_search_rrf": {
        "description": "【P0新增】RRF融合搜索 - 4通道融合（Vector+BM25+Importance+KG）",
        "params": {
            "query": {"type": "string", "required": True, "description": "搜索查询"},
            "limit": {"type": "number", "description": "返回数量限制（默认5）"},
            "k": {"type": "number", "description": "RRF参数k（默认60，越小越激进）"},
        }
    },
    "memory_recall": {
        "description": "召回相关记忆（自动注入上下文）",
        "params": {
            "query": {"type": "string", "required": True, "description": "召回查询"},
            "auto_inject": {"type": "boolean", "description": "是否自动注入上下文"},
        }
    },
    "memory_forget": {
        "description": "删除记忆",
        "params": {
            "memory_id": {"type": "string", "description": "记忆ID"},
            "query": {"type": "string", "description": "按内容查询删除"},
        }
    },
    "memory_tier": {
        "description": "查看或管理记忆层级（4-Tier: HOT/WARM/COLD/ARCHIVED）",
        "params": {
            "action": {"type": "string", "description": "操作: view|stats|auto_tier|rebalance"},
            "tier": {"type": "string", "description": "层级: HOT|WARM|COLD|ARCHIVED|ALL"},
        }
    },
    "memory_tier_get": {
        "description": "【P2新增】获取记忆所在层级",
        "params": {
            "memory_id": {"type": "string", "required": True, "description": "记忆ID"},
        }
    },
    "memory_tier_move": {
        "description": "【P2新增】移动记忆到指定层级",
        "params": {
            "memory_id": {"type": "string", "required": True, "description": "记忆ID"},
            "tier": {"type": "string", "required": True, "description": "目标层级: HOT|WARM|COLD|ARCHIVED"},
            "force": {"type": "boolean", "description": "强制移动（忽略重要性检查）"},
        }
    },
    "memory_tier_stats_v2": {
        "description": "【P2新增】获取各层级统计（新版4-Tier统计）",
        "params": {}
    },
    "memory_stats": {
        "description": "获取记忆统计",
        "params": {}
    },
    "memory_kg": {
        "description": "知识图谱查询（新增）",
        "params": {
            "action": {"type": "string", "description": "操作: search|network|stats|suggest"},
            "entity": {"type": "string", "description": "实体名称"},
            "depth": {"type": "number", "description": "探索深度（默认2）"},
        }
    },
    "memory_disambiguate": {
        "description": "【P1新增】实体消歧 - 判断实体是否已存在并合并",
        "params": {
            "entity_name": {"type": "string", "required": True, "description": "实体名称"},
            "entity_type": {"type": "string", "description": "实体类型: person|company|project|tool|concept|location"},
            "context": {"type": "string", "description": "上下文信息"},
        }
    },
    "memory_health": {
        "description": "记忆健康度仪表盘（新增）",
        "params": {
            "action": {"type": "string", "description": "操作: report|dashboard|score"},
        }
    },
    "memory_temporal": {
        "description": "【P2新增】时序追踪 - 记忆版本管理和历史",
        "params": {
            "action": {"type": "string", "description": "操作: history|as_of|changes|prune"},
            "memory_id": {"type": "string", "description": "记忆ID（history时必填）"},
            "days": {"type": "number", "description": "天数（changes时使用，默认30）"},
        }
    },
    "memory_cache": {
        "description": "【P3新增】搜索缓存管理",
        "params": {
            "action": {"type": "string", "description": "操作: stats|clear|invalidate"},
        }
    },
    "memory_forgetting": {
        "description": "【P2新增】Weibull遗忘机制 - 智能记忆衰减",
        "params": {
            "action": {"type": "string", "description": "操作: decay_curve|should_forget|analyze"},
            "memory_id": {"type": "string", "description": "记忆ID（should_forget时必填）"},
            "threshold": {"type": "number", "description": "遗忘阈值（默认0.2）"},
        }
    },
    "memory_temporal_extract": {
        "description": "【P2新增】时序信息提取 - 从文本中提取时间信息（相对/绝对）",
        "params": {
            "text": {"type": "string", "required": True, "description": "要分析的文本"},
            "reference_date": {"type": "string", "description": "参考时间 ISO 格式（默认当前时间）"},
        }
    },
    "memory_extract_session": {
        "description": "从当前会话消息中抽取记忆",
        "params": {
            "messages": {"type": "array", "required": True, "description": "消息列表"},
        }
    },
    "memory_auto_extract": {
        "description": "【新增】自动从对话中提取事实、偏好、决策、目标、教训（模仿Mem0）",
        "params": {
            "text": {"type": "string", "description": "要分析的文本"},
            "messages": {"type": "array", "description": "消息列表（替代text）"},
        }
    },
}


# ==================== CLI 入口 ====================

if __name__ == "__main__":
    import sys
    
    # 压制 SSL 警告
    warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("""Claw Memory CLI - 本地优先的AI记忆系统

用法: python memory_main.py <command> [args]

命令:
  store <内容>          存储新记忆
  search <查询>         语义搜索记忆
  recall <查询>         召回相关记忆（用于AI上下文）
  forget <关键词>       删除相关记忆
  tier [action] [层]   层级管理 (view/promote/archive)
  stats                显示统计信息
  auto_tier            自动执行层级整理

示例:
  python memory_main.py store "用户喜欢喝咖啡"
  python memory_main.py recall "咖啡"
  python memory_main.py stats
""")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "store":
        content = " ".join(sys.argv[2:])
        result = memory_store(content)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "search":
        query = " ".join(sys.argv[2:])
        result = memory_search(query)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "recall":
        query = " ".join(sys.argv[2:])
        result = memory_recall(query)
        print(result["recall_text"] if result["count"] > 0 else "无相关记忆")

    elif cmd == "forget":
        query = " ".join(sys.argv[2:])
        result = memory_forget(query=query)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "tier":
        action = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else "view"
        tier = sys.argv[3] if len(sys.argv) > 3 else "ALL"
        result = memory_tier(action=action, tier=tier)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "stats":
        result = memory_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "auto_tier":
        from memory_tier import tier_manager
        result = tier_manager.auto_tier()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print(f"Unknown command: {cmd}")
        print("Available commands: store, search, recall, forget, tier, stats, auto_tier")
        sys.exit(1)
