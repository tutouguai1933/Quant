# Quant 运维手册

> **运维快速参考** - 部署、监控、故障排查
>
> 最后更新：2026-05-05

---

## ⚠️ 混合部署架构

### 服务部署方式

| 服务 | 部署方式 | 端口 | 说明 |
|------|----------|------|------|
| quant-api | 直接运行 | 9011 | FastAPI，修改代码后重启即可 |
| quant-web | 直接运行 | 9012 | Next.js 开发模式，热重载 |
| quant-freqtrade | Docker | 9013 | 交易引擎 |
| quant-mihomo | Docker | 7890/9090 | 代理服务 |
| quant-openclaw | Docker | - | 自动化巡检 |
| quant-grafana | Docker | 3000 | 监控面板 |
| quant-prometheus | Docker | 9091 | 指标存储 |

---

## 1. SSH连接

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
```

---

## 2. 服务管理

### 查看所有服务状态

```bash
# API 和 Web（运行在 tmux 中）
tmux ls

# Docker 容器
docker ps --format 'table {{.Names}}\t{{.Status}}' --filter "name=quant"
```

### API 服务管理

```bash
# 查看 API 日志
tmux attach -t quant-api
# 按 Ctrl+B 然后 D 退出（不停止服务）

# 重启 API
tmux send-keys -t quant-api C-c
# 然后重新启动：
cd ~/Quant/services/api && source ~/Quant/infra/deploy/api.env && export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 PYTHONPATH=/home/djy/Quant && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9011
```

### Web 服务管理

```bash
# 查看 Web 日志
tmux attach -t quant-web

# 重启 Web
tmux send-keys -t quant-web C-c
# 然后重新启动：
source ~/.nvm/nvm.sh && cd ~/Quant/apps/web && pnpm dev --hostname 0.0.0.0 --port 9012
```

### Docker 容器管理

```bash
# 重启容器
docker restart quant-freqtrade quant-mihomo

# 查看日志
docker logs quant-freqtrade --tail 50
docker logs quant-mihomo --since 10m
```

---

## 3. 快速健康检查

```bash
# 一键检查所有服务
tmux ls && echo "---" && docker ps --format 'table {{.Names}}\t{{.Status}}' --filter "name=quant" && echo "--- API ---" && curl -s http://127.0.0.1:9011/healthz | jq '.data.status' && echo "--- Web ---" && curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9012/
```

---

## 4. Freqtrade操作

### 状态检查
```bash
# 查看持仓
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/status | jq '.[] | {pair, profit_pct}'

# 查看余额
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/balance | jq '.total'

# 查看配置
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/show_config | jq '.stake_amount, .max_open_trades'
```

### 手动操作
```bash
# 强制买入
curl -X POST -u 'Freqtrader:jianyu0.0.' "http://127.0.0.1:9013/api/v1/forceentry?pair=BTC/USDT"

# 强制卖出
curl -X POST -u 'Freqtrader:jianyu0.0.' "http://127.0.0.1:9013/api/v1/forceexit?tradeid=1"
```

---

## 5. 代理管理

### 检查状态
```bash
# 当前节点
curl -s 'http://127.0.0.1:9090/proxies/PROXY' | jq '.now'

# 出口IP
curl -s -x http://127.0.0.1:7890 https://api.ipify.org

# 测试Binance连接
curl -s -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping
```

### 白名单IP（Binance）
| 节点 | 出口IP |
|------|--------|
| JP1 | 154.31.113.7 ✅ |
| JP2 | 45.95.212.82 ✅ |
| HK2 | 202.85.76.66 ✅ |

---

## 6. 告警系统

### 飞书测试
```bash
curl -X POST http://127.0.0.1:9011/api/v1/feishu/test | jq '.'
```

---

## 7. 常见故障排查

### API 无法访问

```bash
# 1. 检查 tmux session
tmux ls

# 2. 检查端口
lsof -i :9011

# 3. 查看日志
tmux attach -t quant-api
```

### Web 无法访问

```bash
# 1. 检查 tmux session
tmux ls

# 2. 检查端口
lsof -i :9012

# 3. 查看 Node.js
source ~/.nvm/nvm.sh && node --version
```

### Docker 容器 unhealthy

```bash
docker logs quant-freqtrade --tail 50
docker restart quant-freqtrade
```

### 代理不工作

```bash
curl -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping
# 如果失败，重启 mihomo
docker restart quant-mihomo
```

---

## 8. 关键端口

| 服务 | 端口 | 部署方式 |
|------|------|----------|
| API | 9011 | 直接运行 |
| Web | 9012 | 直接运行 |
| Freqtrade | 9013 | Docker |
| mihomo代理 | 7890 | Docker |
| mihomo控制 | 9090 | Docker |
| Grafana | 3000 | Docker |
| Prometheus | 9091 | Docker |

---

## 9. 紧急操作

### 停止所有交易
```bash
docker stop quant-freqtrade
```

### 重启全部服务
```bash
# API 和 Web
tmux send-keys -t quant-api C-c
tmux send-keys -t quant-web C-c
# 然后手动重启

# Docker 容器
docker restart quant-freqtrade quant-mihomo quant-openclaw
```

### 快速恢复服务
```bash
# 使用启动脚本
~/Quant/scripts/start-api.sh &
~/Quant/scripts/start-web.sh &
```

---

## 10. 服务启动命令速查

### API
```bash
cd ~/Quant/services/api && source ~/Quant/infra/deploy/api.env && export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 PYTHONPATH=/home/djy/Quant && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9011
```

### Web
```bash
source ~/.nvm/nvm.sh && cd ~/Quant/apps/web && export QUANT_API_BASE_URL=http://127.0.0.1:9011/api/v1 && pnpm dev --hostname 0.0.0.0 --port 9012
```

### Docker 容器
```bash
cd ~/Quant/infra/deploy && docker compose up -d
```
