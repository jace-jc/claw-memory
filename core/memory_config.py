"""
Claw Memory 配置
安全修复版本 - 禁用有问题的E2E加密
"""
import os
from pathlib import Path

# 安全修复：禁用E2E加密（原实现有安全漏洞）
# 如需加密，建议使用操作系统级加密(FileVault/LUKS)或等待修复
ENCRYPTION_ENABLED = True  # 默认禁用

# 数据库路径
DB_PATH = Path.home() / ".openclaw/workspace/memory/lancedb"

# 默认配置
DEFAULT_CONFIG = {
    "hot_ttl_hours": 24,
    "warm_ttl_days": 30,
    "min_importance": 0.3,
    "encryption_enabled": False,  # 安全修复
}

# 兼容层：CONFIG = DEFAULT_CONFIG（多处模块依赖此别名）
CONFIG = DEFAULT_CONFIG
