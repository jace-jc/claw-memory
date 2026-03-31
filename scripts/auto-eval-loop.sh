#!/bin/bash
# Claw Memory 自动评测循环脚本
# 持续发送"继续"指令，直到早上9点
# 
# 使用方法:
#   ./auto-eval-loop.sh <chat_id> [间隔秒数]
#
# 示例（在后台运行）:
#   nohup ./auto-eval-loop.sh oc_425dcdd6e20ce01d2c7b21ce12d43969 60 > /tmp/auto-eval.log 2>&1 &
#

set -e

CHAT_ID="${1:-oc_425dcdd6e20ce01d2c7b21ce12d43969}"
INTERVAL="${2:-60}"  # 默认60秒发送一次
LOG_FILE="/tmp/claw-memory-auto-eval-loop.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE" 2>/dev/null || echo "[$(date)] $1"
}

send_continue() {
    local msg="$1"
    # 发送消息到飞书群
    # 使用 openclaw 工具发送
    openclaw exec "openclaw message send --chat $CHAT_ID --content '$msg'" 2>/dev/null || \
    log "⚠️ 发送消息失败，将重试"
}

check_time() {
    local hour=$(date +%H)
    local min=$(date +%M)
    local time_val=$((hour * 60 + min))
    local stop_time=$((9 * 60))  # 9:00 = 540分钟
    
    if [ "$time_val" -ge "$stop_time" ]; then
        return 1
    fi
    return 0
}

main() {
    local count=0
    
    log "=========================================="
    log "🚀 Claw Memory 自动评测循环启动"
    log "📍 目标群: $CHAT_ID"
    log "⏰ 停止时间: 早上9:00"
    log "📝 发送间隔: ${INTERVAL}秒"
    log "=========================================="
    
    while check_time; do
        count=$((count + 1))
        log "📤 发送第${count}次继续指令..."
        
        # 发送"继续"指令
        send_continue "继续评测循环"
        
        log "✅ 已发送，等待${INTERVAL}秒后继续..."
        sleep "$INTERVAL"
    done
    
    log "🎉 已到9:00，自动评测循环正常结束"
    log "📊 总计发送 ${count} 次指令"
}

# 直接运行时执行主循环
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi