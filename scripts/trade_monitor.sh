#!/bin/bash
# Freqtrade实盘监控脚本
# 功能：检查交易状态、余额、异常告警

set -euo pipefail

# 配置
LOG_FILE="/var/log/trade_monitor.log"
HEARTBEAT_FILE="/var/run/trade_monitor_heartbeat"
API_URL="http://127.0.0.1:8080/api/v1"
AUTH="Freqtrader:jianyu0.0."

# 飞书Webhook配置（需要配置）
FEISHU_WEBHOOK="${FEISHU_WEBHOOK_URL:-}"

# 告警阈值
BALANCE_THRESHOLD=18          # 余额告警阈值 USDT
LOSS_THRESHOLD=5              # 单笔亏损阈值 %
HEARTBEAT_TIMEOUT=30          # 心跳超时阈值 分钟

# 告警冷却时间（避免重复告警）
ALERT_COOLDOWN=300            # 5分钟
ALERT_STATE_DIR="/var/run/trade_monitor_alerts"

# 初始化
mkdir -p "$ALERT_STATE_DIR" 2>/dev/null || true
touch "$HEARTBEAT_FILE" 2>/dev/null || true

# 日志函数
log() {
    local level="$1"
    local message="$2"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $message" >> "$LOG_FILE"
}

log "INFO" "=== 监控检查开始 ==="

# 检查API是否可用
check_api() {
    local response
    response=$(curl -s -u "$AUTH" "$API_URL/ping" 2>/dev/null) || {
        log "ERROR" "Freqtrade API不可达"
        send_alert "critical" "API不可达" "Freqtrade API无法连接，请检查容器状态"
        return 1
    }
    if [[ "$response" != *"pong"* ]]; then
        log "ERROR" "API响应异常: $response"
        return 1
    fi
    log "INFO" "API连接正常"
    return 0
}

# 获取账户余额
check_balance() {
    local balance_json
    local total_usdt

    balance_json=$(curl -s -u "$AUTH" "$API_URL/balance" 2>/dev/null) || {
        log "ERROR" "获取余额失败"
        return 1
    }

    # 解析总余额
    total_usdt=$(echo "$balance_json" | jq -r '.total // 0' 2>/dev/null || echo "0")

    if [[ -z "$total_usdt" || "$total_usdt" == "null" ]]; then
        total_usdt="0"
    fi

    log "INFO" "账户余额: $total_usdt USDT"

    # 余额告警检查
    if (( $(echo "$total_usdt < $BALANCE_THRESHOLD" | bc -l) )); then
        check_and_send_alert "balance_low" "warning" "余额告警" \
            "账户余额 ${total_usdt} USDT 已低于阈值 ${BALANCE_THRESHOLD} USDT"
    fi

    return 0
}

# 获取当前持仓状态
check_trades() {
    local status_json
    local trade_count

    status_json=$(curl -s -u "$AUTH" "$API_URL/status" 2>/dev/null) || {
        log "ERROR" "获取持仓状态失败"
        return 1
    }

    # 持仓数量
    trade_count=$(echo "$status_json" | jq 'length' 2>/dev/null || echo "0")
    log "INFO" "当前持仓数量: $trade_count"

    # 检查每个持仓的盈亏
    if [[ "$trade_count" -gt 0 ]]; then
        echo "$status_json" | jq -c '.[]' 2>/dev/null | while read -r trade; do
            local pair profit_pct current_profit amount open_rate

            pair=$(echo "$trade" | jq -r '.pair // "unknown"')
            profit_pct=$(echo "$trade" | jq -r '.profit_pct // 0')
            current_profit=$(echo "$trade" | jq -r '.current_profit // 0')
            amount=$(echo "$trade" | jq -r '.amount // 0')
            open_rate=$(echo "$trade" | jq -r '.open_rate // 0')

            # 记录持仓信息
            log "INFO" "持仓: $pair, 盈亏: ${profit_pct}%, 数量: $amount, 入场价: $open_rate"

            # 单笔亏损超过阈值告警
            if (( $(echo "$profit_pct < -$LOSS_THRESHOLD" | bc -l) )); then
                local loss_pct=$(echo "$profit_pct" | sed 's/-//')
                check_and_send_alert "loss_${pair}" "error" "大额亏损告警" \
                    "持仓 $pair 当前亏损 ${loss_pct}%，超过阈值 ${LOSS_THRESHOLD}%\n入场价: $open_rate, 当前盈亏: $current_profit USDT"
            fi
        done
    fi

    return 0
}

# 检查RSI信号强度（需要从策略数据获取）
check_rsi_signals() {
    # 这个功能需要Freqtrade策略支持，暂时记录日志
    log "INFO" "RSI信号检查: 需要策略配置支持"
    return 0
}

# 心跳检测
check_heartbeat() {
    local last_heartbeat
    local current_time
    local diff_minutes

    current_time=$(date +%s)

    # 更新当前心跳
    echo "$current_time" > "$HEARTBEAT_FILE"

    # 检查上次心跳（如果存在）
    if [[ -f "$HEARTBEAT_FILE" ]]; then
        last_heartbeat=$(cat "$HEARTBEAT_FILE" 2>/dev/null || echo "$current_time")
        diff_minutes=$(( (current_time - last_heartbeat) / 60 ))

        log "INFO" "心跳时间差: ${diff_minutes}分钟"

        # 心跳超时告警（自身检查不会触发，用于外部监控）
        if [[ "$diff_minutes" -gt "$HEARTBEAT_TIMEOUT" ]]; then
            check_and_send_alert "heartbeat_timeout" "critical" "心跳超时" \
                "监控脚本 ${diff_minutes} 分钟未更新心跳，可能已停止运行"
        fi
    fi

    return 0
}

# 发送飞书告警
send_alert() {
    local level="$1"
    local title="$2"
    local message="$3"

    if [[ -z "$FEISHU_WEBHOOK" ]]; then
        log "WARN" "飞书Webhook未配置，跳过告警发送"
        return 1
    fi

    # 构建飞书卡片消息
    local color="blue"
    local emoji="📊"

    case "$level" in
        "warning") color="orange"; emoji="⚠️" ;;
        "error") color="red"; emoji="❌" ;;
        "critical") color="red"; emoji="🚨" ;;
    esac

    local payload=$(cat <<EOF
{
    "msg_type": "interactive",
    "card": {
        "config": {"wide_screen_mode": true},
        "header": {
            "title": {"tag": "plain_text", "content": "$title"},
            "template": "$color"
        },
        "elements": [
            {
                "tag": "div",
                "text": {"content": "$emoji **$title**", "tag": "lark_md"}
            },
            {
                "tag": "div",
                "text": {"content": "$message", "tag": "lark_md"}
            },
            {
                "tag": "div",
                "fields": [
                    {"is_short": true, "text": {"content": "**级别**: $level", "tag": "lark_md"}},
                    {"is_short": true, "text": {"content": "**时间**: $(date '+%Y-%m-%d %H:%M:%S')", "tag": "lark_md"}}
                ]
            }
        ]
    }
}
EOF
)

    # 发送告警
    local response
    response=$(curl -s -X POST "$FEISHU_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>/dev/null) || {
        log "ERROR" "飞书告警发送失败"
        return 1
    }

    if [[ "$response" == *"StatusCode\":0"* || "$response" == *"code\":0"* ]]; then
        log "INFO" "飞书告警发送成功: $title"
        return 0
    else
        log "ERROR" "飞书告警响应异常: $response"
        return 1
    fi
}

# 检查告警冷却并发送
check_and_send_alert() {
    local alert_key="$1"
    local level="$2"
    local title="$3"
    local message="$4"

    local alert_file="$ALERT_STATE_DIR/$alert_key"
    local current_time=$(date +%s)

    # 检查冷却时间
    if [[ -f "$alert_file" ]]; then
        local last_alert_time=$(cat "$alert_file" 2>/dev/null || echo "0")
        local elapsed=$((current_time - last_alert_time))

        if [[ "$elapsed" -lt "$ALERT_COOLDOWN" ]]; then
            log "DEBUG" "告警冷却中: $alert_key (${elapsed}秒 < ${ALERT_COOLDOWN}秒)"
            return 0
        fi
    fi

    # 发送告警
    if send_alert "$level" "$title" "$message"; then
        # 记录告警时间
        echo "$current_time" > "$alert_file"
    fi
}

# 主流程
main() {
    # 1. 检查API连接
    check_api || log "WARN" "API检查失败，继续其他检查"

    # 2. 检查余额
    check_balance || log "WARN" "余额检查失败"

    # 3. 检查持仓状态
    check_trades || log "WARN" "持仓检查失败"

    # 4. 检查RSI信号
    check_rsi_signals || log "WARN" "RSI信号检查失败"

    # 5. 更新心跳
    check_heartbeat

    log "INFO" "=== 监控检查完成 ==="
}

# 运行主流程
main

exit 0