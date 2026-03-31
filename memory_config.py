"""
Claw Memory 配置
"""
import os
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "hot_ttl_hours": 24,         # HOT层保留时间
    "warm_ttl_days": 30,         # WARM层保留时间
    "min_importance": 0.3,       # 低于此重要性的记忆自动删除
    "auto_recall": True,          # 自动召回
    "auto_capture": True,         # 自动捕获
    "ollama_url": "http://localhost:11434",
    "embed_model": "bge-m3:latest",
    "llm_model": "qwen3.5:27b",
    "workspace_dir": "/Users/claw/.openclaw/workspace",
    "memory_dir": "/Users/claw/.openclaw/workspace/memory",
    "hot_file": "SESSION-STATE.md",
    "cold_dir": "memory",
    "db_path": "/Users/claw/.openclaw/workspace/memory/lancedb",
}

def load_config():
    """加载配置，优先读取openclaw.json，其次使用默认"""
    config = DEFAULT_CONFIG.copy()
    
    # 尝试从openclaw.json读取
    openclaw_json = Path.home() / ".openclaw" / "openclaw.json"
    if openclaw_json.exists():
        try:
            with open(openclaw_json) as f:
                data = json.load(f)
                plugins = data.get("plugins", {})
                entries = plugins.get("entries", {})
                memory_config = entries.get("claw-memory", {}).get("config", {})
                config.update(memory_config)
        except Exception:
            pass
    
    return config

# 全局配置实例
CONFIG = load_config()
