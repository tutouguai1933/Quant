# Quant 项目接力开发提示词

> **给下一个Claude Session的启动提示词**
>
> 最后更新：2026-05-05

---

## ⚠️ 混合部署架构（必读）

### 部署方式

| 服务 | 部署方式 | 原因 |
|------|----------|------|
| **API** | 直接运行 | 修改代码后重启即可，无需 Docker build |
| **Web** | 开发模式 | 热重载，修改前端即时生效 |
| **Freqtrade** | Docker | 第三方服务，环境隔离 |
| **mihomo** | Docker | 代理服务，配置固定 |

### 服务管理

```bash
# 查看所有服务
tmux ls                                    # API 和 Web
docker ps --filter name=quant              # Docker 容器

# API 服务
tmux attach -t quant-api                   # 查看日志
tmux send-keys -t quant-api C-c            # 停止

# Web 服务
tmux attach -t quant-web                   # 查看日志
tmux send-keys -t quant-web C-c            # 停止
```

### SSH连接方式

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
```

---

## 启动提示词（复制粘贴给Claude）

```
我正在继续Quant量化交易系统的开发和运维工作。

## ⚠️ 混合部署架构
- API/Web：直接运行（tmux管理），修改代码后 git pull + 重启即可
- Freqtrade/mihomo：Docker容器，修改后需要 docker compose build
- SSH密钥：~/.ssh/id_aliyun_djy

## 服务状态检查
tmux ls && docker ps --format 'table {{.Names}}\t{{.Status}}' --filter "name=quant"

## 项目概况
- Quant = Freqtrade交易引擎 + FastAPI控制平面 + Next.js前端 + 自动化运维
- Live实盘模式，运行于阿里云服务器 39.106.11.65
- 当前余额约21 USDT，16个交易对白名单

## 核心服务
- quant-api (9011): FastAPI控制平面，市场数据、告警推送
- quant-web (9012): Next.js前端，开发模式
- quant-freqtrade (9013): Freqtrade交易引擎
- quant-mihomo (7890/9090): 代理服务，出口IP 154.31.113.7

## 关键认证
- Freqtrade API: `Freqtrader:jianyu0.0.`
- API Admin: `admin:1933`

## 文档位置
- 开发手册: docs/DEV_HANDBOOK.md（含混合部署说明）
- 运维手册: docs/OPS_HANDBOOK.md
- 项目概览: docs/PROJECT_OVERVIEW.md

请先阅读 docs/DEV_HANDBOOK.md 了解部署架构，然后检查系统状态。
```

---

## 服务启动命令

### API 服务
```bash
cd ~/Quant/services/api && source ~/Quant/infra/deploy/api.env && export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 PYTHONPATH=/home/djy/Quant && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9011
```

### Web 服务
```bash
source ~/.nvm/nvm.sh && cd ~/Quant/apps/web && export QUANT_API_BASE_URL=http://127.0.0.1:9011/api/v1 && pnpm dev --hostname 0.0.0.0 --port 9012
```

### Docker 容器
```bash
cd ~/Quant/infra/deploy && docker compose up -d
```

---

## 快速部署流程

### 修改 API/Web 代码后部署
```bash
# 1. 本地推送
git add . && git commit -m "fix: xxx" && git push

# 2. 服务器拉取
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull"

# 3. 重启服务（API需要重启，Web会自动热重载）
# API: tmux send-keys -t quant-api C-c 然后重新启动
```

### 修改 Docker 服务后部署
```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && cd infra/deploy && docker compose build && docker compose up -d"
```

---

## 最近完成的工作（2026-05-05）

| 完成项 | 内容 |
|--------|------|
| 混合部署架构 | API/Web 直接运行，Freqtrade/mihomo 保持 Docker |
| Market API优化 | 响应时间从 25s 降至 0.5s |
| RSI历史功能 | 添加 `/api/v1/market/{symbol}/rsi-history` 端点 |
| 交易历史功能 | 添加 `/api/v1/trade-log/history` 端点 |

---

## 当前系统状态（2026-05-05）

| 服务 | 状态 | 部署方式 |
|------|------|----------|
| quant-api | ✅ Running | 直接运行 |
| quant-web | ✅ Running | 直接运行 |
| quant-freqtrade | ✅ Running | Docker |
| quant-mihomo | ✅ Running | Docker |

### Market白名单（16个币种）

```
BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT,
ADAUSDT, LINKUSDT, AVAXUSDT, DOTUSDT, MATICUSDT,
PEPEUSDT, SHIBUSDT, WIFUSDT, ORDIUSDT, BONKUSDT
```

---

## 待办事项

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 配置 systemd 服务 | 开机自启动 API/Web |
| P2 | Grafana告警规则优化 | 添加更多交易指标监控 |
| P3 | RSI历史Tab完善 | 单币页面RSI历史展示 |

---

## 关键配置文件路径

```
infra/deploy/api.env           # API环境变量
infra/freqtrade/user_data/config.live.base.json  # Freqtrade主配置
infra/freqtrade/user_data/strategies/EnhancedStrategy.py  # 策略代码
infra/grafana/dashboards/quant-overview.json  # Grafana仪表盘
scripts/start-api.sh           # API启动脚本
scripts/start-web.sh           # Web启动脚本
```

---

## 常见问题快速修复

### API 无法访问
```bash
tmux ls                      # 检查 session 是否存在
lsof -i :9011               # 检查端口占用
tmux attach -t quant-api    # 查看日志
```

### Web 无法访问
```bash
tmux ls                      # 检查 session 是否存在
lsof -i :9012               # 检查端口占用
source ~/.nvm/nvm.sh && node --version  # 检查 Node.js
```

### Market API返回空数据
```bash
# 检查代理配置
curl -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping
```

### Docker容器unhealthy
```bash
docker logs quant-freqtrade --tail 20
docker restart quant-freqtrade
```
