#!/bin/bash
# 自动化系统健康检查脚本
# 检查流水线选币、自动交易、RSI计算、交易历史、飞书报警

set -e

REMOTE_HOST="39.106.11.65"
REMOTE_USER="djy"
SSH_KEY="~/.ssh/id_aliyun_djy"
REMOTE_DIR="/home/djy/Quant"
COMPOSE_DIR="$REMOTE_DIR/infra/deploy"

SSH_CMD="ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST"

echo "=============================================="
echo "自动化系统健康检查"
echo "=============================================="

# 计数器
PASS=0
FAIL=0
WARN=0

check_pass() {
    echo "✅ $1"
    PASS=$((PASS + 1))
}

check_fail() {
    echo "❌ $1"
    FAIL=$((FAIL + 1))
}

check_warn() {
    echo "⚠️  $1"
    WARN=$((WARN + 1))
}

echo ""
echo "=== 1. 容器运行状态 ==="
echo ""

# 检查核心容器状态
echo ">>> 检查核心容器状态..."
$SSH_CMD "docker compose -f $COMPOSE_DIR/docker-compose.yml ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null | grep -E 'quant-|NAME'"

echo ""
echo "=== 2. Freqtrade 状态 ==="
echo ""

# 检查 Freqtrade 是否运行
echo ">>> 检查 Freqtrade 容器..."
FREQTRADE_STATUS=$($SSH_CMD "docker inspect quant-freqtrade --format '{{.State.Status}}' 2>/dev/null || echo 'not found'")
if [ "$FREQTRADE_STATUS" == "running" ]; then
    check_pass "Freqtrade 容器运行中"
else
    check_fail "Freqtrade 容器状态: $FREQTRADE_STATUS"
fi

# 检查 Freqtrade API
echo ">>> 检查 Freqtrade API..."
FREQTRADE_API=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:9013/api/v1/ping 2>/dev/null || echo '000'")
if [ "$FREQTRADE_API" == "200" ]; then
    check_pass "Freqtrade API 正常"
else
    check_fail "Freqtrade API 返回: $FREQTRADE_API"
fi

# 检查 Freqtrade 运行模式
echo ">>> 检查 Freqtrade 运行模式..."
DRY_RUN=$($SSH_CMD "curl -s http://localhost:9013/api/v1/show_config 2>/dev/null | grep -o '\"dry_run\": [^,]*' | head -1")
echo "    $DRY_RUN"

echo ""
echo "=== 3. 自动化流水线状态 ==="
echo ""

# 检查自动化状态 API
echo ">>> 检查自动化服务状态..."
AUTO_STATUS=$($SSH_CMD "curl -s http://localhost:9011/api/v1/automation/status 2>/dev/null")
if [ -n "$AUTO_STATUS" ] && [ "$AUTO_STATUS" != "null" ]; then
    echo "    $AUTO_STATUS" | head -c 500
    echo ""
    check_pass "自动化状态 API 响应正常"
else
    check_warn "自动化状态 API 无响应或为空"
fi

# 检查最近自动化周期
echo ""
echo ">>> 检查最近自动化周期..."
$SSH_CMD "curl -s http://localhost:9011/api/v1/automation/cycles?limit=3 2>/dev/null | head -c 1000"
echo ""

echo ""
echo "=== 4. RSI 计算记录 ==="
echo ""

# 检查 RSI 计算端点
echo ">>> 检查 RSI 计算状态..."
RSI_STATUS=$($SSH_CMD "curl -s http://localhost:9011/api/v1/market/BTCUSDT/indicators 2>/dev/null")
if [ -n "$RSI_STATUS" ] && echo "$RSI_STATUS" | grep -q "rsi"; then
    echo "    BTCUSDT RSI 指标:"
    echo "$RSI_STATUS" | head -c 500
    echo ""
    check_pass "RSI 计算 API 正常"
else
    check_warn "RSI 计算无数据或异常"
fi

# 检查 RSI 历史
echo ""
echo ">>> 检查 RSI 历史记录..."
RSI_HISTORY=$($SSH_CMD "curl -s 'http://localhost:9011/api/v1/market/BTCUSDT/rsi-history?limit=5' 2>/dev/null")
if [ -n "$RSI_HISTORY" ] && [ "$RSI_HISTORY" != "[]" ]; then
    echo "    最近 RSI 记录:"
    echo "$RSI_HISTORY" | head -c 500
    echo ""
    check_pass "RSI 历史记录存在"
else
    check_warn "RSI 历史记录为空"
fi

echo ""
echo "=== 5. 交易历史记录 ==="
echo ""

# 检查交易记录 API
echo ">>> 检查交易记录..."
TRADES=$($SSH_CMD "curl -s 'http://localhost:9011/api/v1/trades?limit=5' 2>/dev/null")
if [ -n "$TRADES" ]; then
    TRADE_COUNT=$(echo "$TRADES" | grep -o '"trade_id"' | wc -l)
    if [ "$TRADE_COUNT" -gt 0 ]; then
        echo "    最近交易记录数: $TRADE_COUNT"
        echo "$TRADES" | head -c 800
        echo ""
        check_pass "交易记录存在 ($TRADE_COUNT 条)"
    else
        check_warn "暂无交易记录"
    fi
else
    check_warn "交易记录 API 无响应"
fi

# 检查 Freqtrade 交易
echo ""
echo ">>> 检查 Freqtrade 交易状态..."
FREQTRADE_TRADES=$($SSH_CMD "curl -s 'http://localhost:9013/api/v1/trades?limit=3' 2>/dev/null")
if [ -n "$FREQTRADE_TRADES" ]; then
    echo "    Freqtrade 交易:"
    echo "$FREQTRADE_TRADES" | head -c 600
    echo ""
fi

echo ""
echo "=== 6. 选币流水线 ==="
echo ""

# 检查选币结果
echo ">>> 检查选币结果..."
SELECTION=$($SSH_CMD "curl -s 'http://localhost:9011/api/v1/coin-selection?limit=5' 2>/dev/null")
if [ -n "$SELECTION" ] && [ "$SELECTION" != "[]" ] && [ "$SELECTION" != "{}" ]; then
    echo "    选币结果:"
    echo "$SELECTION" | head -c 800
    echo ""
    check_pass "选币结果存在"
else
    check_warn "暂无选币结果"
fi

# 检查白名单
echo ""
echo ">>> 检查当前白名单..."
WHITELIST=$($SSH_CMD "curl -s 'http://localhost:9011/api/v1/whitelist' 2>/dev/null")
if [ -n "$WHITELIST" ]; then
    echo "    白名单:"
    echo "$WHITELIST" | head -c 500
    echo ""
fi

echo ""
echo "=== 7. 飞书报警状态 ==="
echo ""

# 检查飞书配置
echo ">>> 检查飞书报警配置..."
FEISHU_CONFIG=$($SSH_CMD "docker exec quant-api env 2>/dev/null | grep -i FEISHU | head -5")
if [ -n "$FEISHU_CONFIG" ]; then
    echo "    飞书配置:"
    echo "$FEISHU_CONFIG" | sed 's/=.*/=***/'
    check_pass "飞书配置已设置"
else
    check_warn "未找到飞书配置"
fi

# 检查最近告警
echo ""
echo ">>> 检查最近告警记录..."
ALERTS=$($SSH_CMD "curl -s 'http://localhost:9011/api/v1/performance/alerts' 2>/dev/null")
if [ -n "$ALERTS" ]; then
    echo "    性能告警:"
    echo "$ALERTS" | head -c 500
    echo ""
fi

# 检查 OpenClaw 审计记录
echo ""
echo ">>> 检查 OpenClaw 审计记录..."
AUDIT=$($SSH_CMD "curl -s 'http://localhost:9011/api/v1/openclaw/audit?limit=5' 2>/dev/null")
if [ -n "$AUDIT" ] && [ "$AUDIT" != '{"items":[],"total":0}' ]; then
    echo "    审计记录:"
    echo "$AUDIT" | head -c 800
    echo ""
    check_pass "OpenClaw 审计记录存在"
else
    check_warn "暂无 OpenClaw 审计记录"
fi

echo ""
echo "=== 8. API 日志检查 ==="
echo ""

# 检查最近的错误日志
echo ">>> 检查 API 最近日志..."
$SSH_CMD "docker logs quant-api --tail 30 2>&1 | grep -E 'ERROR|WARN|Exception|Failed|失败' | tail -10"

echo ""
echo "=== 9. 数据文件检查 ==="
echo ""

# 检查数据目录
echo ">>> 检查数据目录..."
$SSH_CMD "ls -la $REMOTE_DIR/data/ 2>/dev/null | head -15"

# 检查是否有交易数据
echo ""
echo ">>> 检查交易数据文件..."
$SSH_CMD "find $REMOTE_DIR/data -name '*.json' -type f 2>/dev/null | head -10"

echo ""
echo "=============================================="
echo "检查结果汇总"
echo "=============================================="
echo "通过: $PASS"
echo "失败: $FAIL"
echo "警告: $WARN"
echo "总计: $((PASS + FAIL + WARN))"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "✅ 核心功能正常"
else
    echo "⚠️  存在失败项，请检查"
fi
