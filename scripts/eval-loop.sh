#!/bin/bash
# Claw Memory 评测循环脚本
# 每30分钟运行一轮，直到早上9点

SKILL_DIR="/Users/claw/.openclaw/skills/claw-memory"
LOG_FILE="/tmp/claw-memory-eval-loop.log"

echo "[$(date)] === 评测循环启动 ===" | tee -a "$LOG_FILE"

# 检查是否到9点了
current_hour=$(date +%H)
if [ "$current_hour" -ge 9 ]; then
    echo "[$(date)] 已到9点，评测循环结束" | tee -a "$LOG_FILE"
    exit 0
fi

# 运行一轮评测（这里只是触发，实际评测由agent完成）
echo "[$(date)] 运行评测..." | tee -a "$LOG_FILE"

# 触发命令会在后台启动评测agent
openclaw exec "cd $SKILL_DIR && python3 -c \"
import warnings; warnings.filterwarnings('ignore')
from memory_main import memory_stats
stats = memory_stats()
print('Current stats:', stats)
\""

echo "[$(date)] 评测触发完成，下次运行在30分钟后" | tee -a "$LOG_FILE"
