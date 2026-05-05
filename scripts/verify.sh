#!/bin/bash
# 验证脚本 - 检查服务状态和 API 端点

set -e

REMOTE_HOST="39.106.11.65"
REMOTE_USER="djy"
SSH_KEY="~/.ssh/id_aliyun_djy"
REMOTE_DIR="/home/djy/Quant"
COMPOSE_DIR="$REMOTE_DIR/infra/deploy"

SSH_CMD="ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST"

echo "=== 验证服务状态 ==="

# 1. 检查容器状态
echo ""
echo ">>> 容器状态..."
$SSH_CMD "docker compose -f $COMPOSE_DIR/docker-compose.yml ps api web"

# 2. 检查 API 健康端点
echo ""
echo ">>> 检查端口映射..."
$SSH_CMD "docker port quant-api 2>&1 || echo 'No port mapping'"
echo ""
echo ">>> 通过 Docker 网络访问 API..."
$SSH_CMD "docker exec quant-api python -c \"import urllib.request; print(urllib.request.urlopen('http://localhost:9011/health').read().decode())\" 2>&1 || echo 'Failed'"

# 3. 检查前端
echo ""
echo ">>> 前端状态..."
$SSH_CMD "curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://localhost:3000/ || echo 'Frontend not ready'"

# 4. 检查 API 日志
echo ""
echo ">>> API 启动日志..."
$SSH_CMD "docker logs quant-api 2>&1 | head -30"

# 5. 检查进程和网络
echo ""
echo ">>> 检查容器内进程..."
$SSH_CMD "docker exec quant-api ps aux 2>&1 | head -10"

# 6. 检查环境变量
echo ""
echo ">>> 检查 API 环境变量..."
$SSH_CMD "docker exec quant-api env 2>&1 | grep -E 'PORT|HOST' | head -10"

echo ""
echo "=== 验证完成 ==="
