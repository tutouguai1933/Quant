#!/bin/bash
# 部署脚本 - 从远程仓库拉取代码并重启服务

set -e

REMOTE_HOST="39.106.11.65"
REMOTE_USER="djy"
SSH_KEY="~/.ssh/id_aliyun_djy"
REMOTE_DIR="/home/djy/Quant"
COMPOSE_DIR="$REMOTE_DIR/infra/deploy"

# SSH 命令前缀（包含 cd）
SSH_CMD="ssh -i $SSH_KEY $REMOTE_USER@$REMOTE_HOST"

echo "=== 开始部署 ==="
echo "远程主机: $REMOTE_HOST"
echo "远程目录: $REMOTE_DIR"

# 0. 检查目录结构
echo ""
echo ">>> 检查远程目录..."
$SSH_CMD "cd $COMPOSE_DIR && docker compose config --services"

# 1. 拉取代码
echo ""
echo ">>> 拉取最新代码..."
$SSH_CMD "cd $REMOTE_DIR && git pull"

# 2. 重建 API 容器
echo ""
echo ">>> 重建 API 容器..."
$SSH_CMD "cd $COMPOSE_DIR && docker compose build api"

# 3. 重启服务
echo ""
echo ">>> 停止并删除旧容器..."
$SSH_CMD "docker stop quant-api quant-web 2>/dev/null || true"
$SSH_CMD "docker rm quant-api quant-web 2>/dev/null || true"
echo ""
echo ">>> 启动新服务..."
$SSH_CMD "cd $COMPOSE_DIR && docker compose up -d --no-deps api web"

# 4. 检查服务状态
echo ""
echo ">>> 检查服务状态..."
$SSH_CMD "cd $COMPOSE_DIR && docker compose ps"

# 5. 验证 API 健康端点
echo ""
echo ">>> 验证 API 健康端点..."
$SSH_CMD "curl -s http://localhost:3001/api/v1/health"

# 6. 验证前端
echo ""
echo ">>> 验证前端..."
$SSH_CMD "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/"

echo ""
echo "=== 部署完成 ==="
