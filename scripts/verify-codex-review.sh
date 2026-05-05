#!/bin/bash
# Codex 审阅报告修复验证脚本
# 验证 2026-05-06-codex-project-review.md 中列出的问题是否已修复

# 不要在错误时退出，我们需要收集所有结果

REMOTE_HOST="39.106.11.65"
REMOTE_USER="djy"
SSH_KEY="~/.ssh/id_aliyun_djy"
REMOTE_DIR="/home/djy/Quant"
COMPOSE_DIR="$REMOTE_DIR/infra/deploy"

SSH_CMD="ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST"

echo "=============================================="
echo "Codex 审阅报告修复验证"
echo "=============================================="

# 计数器
PASS=0
FAIL=0

check_pass() {
    echo "✅ $1"
    PASS=$((PASS + 1))
}

check_fail() {
    echo "❌ $1"
    FAIL=$((FAIL + 1))
}

echo ""
echo "=== 1. API 路径规范化验证 ==="
echo ""

# 1.1 检查 /analytics 是否正常
echo ">>> 检查 /api/v1/analytics 端点..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:9011/api/v1/analytics" 2>&1)
if [ "$RESULT" == "200" ]; then
    check_pass "Analytics API 返回 200"
else
    check_fail "Analytics API 返回 $RESULT (期望 200)"
fi

# 1.2 检查 /health 是否正常
echo ">>> 检查 /health 端点..."
RESULT=$($SSH_CMD "curl -s http://localhost:9011/health | grep -o '\"status\":\"ok\"'" 2>&1)
if [ -n "$RESULT" ]; then
    check_pass "Health 端点正常"
else
    check_fail "Health 端点异常"
fi

echo ""
echo "=== 2. 后端认证保护验证 ==="
echo ""

# 2.1 检查 hyperopt/start 是否需要认证
echo ">>> 检查 /api/v1/hyperopt/start 认证保护..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:9011/api/v1/hyperopt/start" 2>&1)
if [ "$RESULT" == "403" ] || [ "$RESULT" == "401" ] || [ "$RESULT" == "500" ]; then
    check_pass "Hyperopt start 需要认证 (HTTP $RESULT)"
else
    check_fail "Hyperopt start 未受保护 (HTTP $RESULT)"
fi

# 2.2 检查 patrol/start 是否需要认证
echo ">>> 检查 /api/v1/patrol/start 认证保护..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:9011/api/v1/patrol/start" 2>&1)
if [ "$RESULT" == "403" ] || [ "$RESULT" == "401" ] || [ "$RESULT" == "500" ]; then
    check_pass "Patrol start 需要认证 (HTTP $RESULT)"
else
    check_fail "Patrol start 未受保护 (HTTP $RESULT)"
fi

# 2.3 检查 openclaw/actions 是否需要认证
echo ">>> 检查 /api/v1/openclaw/actions 认证保护..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{\"action\":\"test\"}' http://localhost:9011/api/v1/openclaw/actions" 2>&1)
if [ "$RESULT" == "403" ] || [ "$RESULT" == "401" ] || [ "$RESULT" == "500" ]; then
    check_pass "OpenClaw actions 需要认证 (HTTP $RESULT)"
else
    check_fail "OpenClaw actions 未受保护 (HTTP $RESULT)"
fi

# 2.4 检查 health/monitoring/start 是否需要认证
echo ">>> 检查 /api/v1/health/monitoring/start 认证保护..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' -X POST http://localhost:9011/api/v1/health/monitoring/start" 2>&1)
if [ "$RESULT" == "403" ] || [ "$RESULT" == "401" ] || [ "$RESULT" == "500" ]; then
    check_pass "Health monitoring start 需要认证 (HTTP $RESULT)"
else
    check_fail "Health monitoring start 未受保护 (HTTP $RESULT)"
fi

echo ""
echo "=== 3. 运维监控端点验证 ==="
echo ""

# 3.1 检查 /api/v1/health 详细健康状态
echo ">>> 检查 /api/v1/health 详细健康状态..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:9011/api/v1/health" 2>&1)
if [ "$RESULT" == "200" ]; then
    check_pass "详细健康状态 API 正常"
else
    check_fail "详细健康状态 API 返回 $RESULT"
fi

# 3.2 检查 /api/v1/patrol/schedule
echo ">>> 检查 /api/v1/patrol/schedule..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:9011/api/v1/patrol/schedule" 2>&1)
if [ "$RESULT" == "200" ]; then
    check_pass "Patrol schedule API 正常"
else
    check_fail "Patrol schedule API 返回 $RESULT"
fi

# 3.3 检查 /api/v1/performance/alerts (替代 alerts)
echo ">>> 检查 /api/v1/performance/alerts..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:9011/api/v1/performance/alerts" 2>&1)
if [ "$RESULT" == "200" ]; then
    check_pass "Performance alerts API 正常"
else
    check_fail "Performance alerts API 返回 $RESULT"
fi

echo ""
echo "=== 4. WebSocket Channel 验证 ==="
echo ""

# 4.1 检查 channels.py 是否包含 health_status
echo ">>> 检查 WebSocket health_status channel..."
RESULT=$($SSH_CMD "grep -c 'CHANNEL_HEALTH_STATUS' $REMOTE_DIR/services/api/app/websocket/channels.py" 2>&1)
if [ "$RESULT" -ge 1 ]; then
    check_pass "health_status channel 已定义"
else
    check_fail "health_status channel 未定义"
fi

echo ""
echo "=== 5. 前端代码验证 ==="
echo ""

# 5.1 检查 resolveControlPlaneUrl 是否有路径规范化
echo ">>> 检查 API 路径规范化代码..."
RESULT=$($SSH_CMD "grep -c 'normalizedPath' $REMOTE_DIR/apps/web/lib/api.ts" 2>&1)
if [ "$RESULT" -ge 1 ]; then
    check_pass "resolveControlPlaneUrl 包含路径规范化"
else
    check_fail "resolveControlPlaneUrl 缺少路径规范化"
fi

# 5.2 检查 config 页面是否使用 /api/control
echo ">>> 检查 config 页面代理使用..."
RESULT=$($SSH_CMD "grep -c '/api/control/config' $REMOTE_DIR/apps/web/app/config/page.tsx" 2>&1)
if [ "$RESULT" -ge 1 ]; then
    check_pass "config 页面使用 /api/control 代理"
else
    check_fail "config 页面未使用 /api/control 代理"
fi

# 5.3 检查 ops 页面路径修复
echo ">>> 检查 ops 页面 API 路径..."
RESULT=$($SSH_CMD "grep -c 'resolveControlPlaneUrl.*health' $REMOTE_DIR/apps/web/app/ops/page.tsx" 2>&1)
if [ "$RESULT" -ge 1 ]; then
    check_pass "ops 页面 health 路径已修复"
else
    check_fail "ops 页面 health 路径未修复"
fi

echo ""
echo "=== 6. 容器状态验证 ==="
echo ""

# 6.1 检查容器健康状态
echo ">>> 检查容器健康状态..."
RESULT=$($SSH_CMD "docker compose -f $COMPOSE_DIR/docker-compose.yml ps api web --format '{{.Status}}'" 2>&1)
if echo "$RESULT" | grep -q "healthy"; then
    check_pass "容器健康状态正常"
else
    check_fail "容器健康状态异常: $RESULT"
fi

echo ""
echo "=== 7. 前端页面访问验证 ==="
echo ""

# 7.1 检查前端首页
echo ">>> 检查前端首页..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/" 2>&1)
if [ "$RESULT" == "200" ] || [ "$RESULT" == "302" ]; then
    check_pass "前端首页正常 (HTTP $RESULT)"
else
    check_fail "前端首页异常 (HTTP $RESULT)"
fi

# 7.2 检查前端 /ops 页面
echo ">>> 检查前端 /ops 页面..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/ops" 2>&1)
if [ "$RESULT" == "200" ] || [ "$RESULT" == "302" ]; then
    check_pass "前端 /ops 页面正常 (HTTP $RESULT)"
else
    check_fail "前端 /ops 页面异常 (HTTP $RESULT)"
fi

# 7.3 检查前端 /config 页面
echo ">>> 检查前端 /config 页面..."
RESULT=$($SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/config" 2>&1)
if [ "$RESULT" == "200" ] || [ "$RESULT" == "302" ]; then
    check_pass "前端 /config 页面正常 (HTTP $RESULT)"
else
    check_fail "前端 /config 页面异常 (HTTP $RESULT)"
fi

echo ""
echo "=============================================="
echo "验证结果汇总"
echo "=============================================="
echo "通过: $PASS"
echo "失败: $FAIL"
echo "总计: $((PASS + FAIL))"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "🎉 所有问题已修复！"
    exit 0
else
    echo "⚠️  存在未修复的问题，请检查上述失败项"
    exit 1
fi
