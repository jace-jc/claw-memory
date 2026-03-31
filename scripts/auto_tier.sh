#!/bin/bash
# Claw Memory 定时整理脚本
# 建议添加到 crontab: 每天凌晨2点执行
# crontab -e
# 0 2 * * * /Users/claw/.openclaw/skills/claw-memory/scripts/auto_tier.sh

SKILL_DIR="/Users/claw/.openclaw/skills/claw-memory"
cd "$SKILL_DIR"

echo "[$(date)] Running memory auto_tier..."
python3 -c "
import warnings
warnings.filterwarnings('ignore')
from memory_tier import tier_manager
result = tier_manager.auto_tier()
print(result)
"

echo "[$(date)] Done."
