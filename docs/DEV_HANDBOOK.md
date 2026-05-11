# Quant 开发手册

> **开发快速参考** - 代码结构、API、开发流程
>
> 最后更新：2026-05-11

---

## ⚠️ 重要：开发环境架构

### 混合部署架构（2026-05-05 更新）

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          部署架构                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   本地 WSL (开发机)                阿里云服务器 39.106.11.65              │
│   ┌──────────────────┐            ┌────────────────────────────────┐   │
│   │ 代码编辑         │            │                                │   │
│   │ Git提交/推送     │  ───────>  │  直接运行（快速迭代）:          │   │
│   │ 文档更新         │   SSH      │  ├─ quant-api  (FastAPI:9011)  │   │
│   │                  │   git pull │  └─ quant-web  (Next.js:9012)  │   │
│   │ ❌ 不运行服务    │            │                                │   │
│   └──────────────────┘            │  Docker容器（稳定服务）:        │   │
│                                   │  ├─ quant-freqtrade (:9013)    │   │
│                                   │  ├─ quant-mihomo    (:7890)    │   │
│                                   │  ├─ quant-openclaw             │   │
│                                   │  ├─ quant-grafana   (:3000)    │   │
│                                   │  └─ quant-prometheus(:9091)    │   │
│                                   └────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 为什么使用混合部署？

| 服务 | 部署方式 | 原因 |
|------|----------|------|
| **API** | 直接运行 | 修改代码后重启即可，无需 Docker build（节省 2-3 分钟） |
| **Web** | 开发模式 | 热重载，修改前端即时生效 |
| **Freqtrade** | Docker | 第三方服务，环境隔离更重要 |
| **mihomo** | Docker | 代理服务，配置固定 |

### 服务管理命令

```bash
# 查看所有服务状态
tmux ls                    # API 和 Web 运行在 tmux 中
docker ps --filter name=quant  # Docker 容器状态

# API 服务
tmux attach -t quant-api   # 查看 API 日志
tmux send-keys -t quant-api C-c  # 停止 API

# Web 服务
tmux attach -t quant-web   # 查看 Web 日志
tmux send-keys -t quant-web C-c  # 停止 Web

# Docker 容器
docker restart quant-freqtrade quant-mihomo
docker logs quant-freqtrade --tail 50
```

---

## 1. 快速部署流程

### 修改 API 代码后部署

```bash
# 1. 本地修改并推送
git add . && git commit -m "fix: xxx" && git push

# 2. 服务器拉取并重启（一条命令）
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && tmux send-keys -t quant-api C-c; sleep 2; tmux send-keys -t quant-api 'cd ~/Quant/services/api && source ~/Quant/infra/deploy/api.env && export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 PYTHONPATH=/home/djy/Quant && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9011' Enter"
```

### 修改 Web 代码后部署

```bash
# 1. 本地修改并推送
git add . && git commit -m "feat: xxx" && git push

# 2. 服务器拉取（Web 开发模式会自动热重载）
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull"
```

### 修改 Freqtrade/mihomo 配置后部署

```bash
# 这些服务仍使用 Docker，需要重建
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && cd infra/deploy && docker compose build freqtrade && docker compose up -d freqtrade"
```

---

## 2. 服务启动/重启脚本

### 启动 API 服务

```bash
# 在服务器上执行
cd ~/Quant/services/api
source ~/Quant/infra/deploy/api.env
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export PYTHONPATH=/home/djy/Quant
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9011
```

### 启动 Web 服务

```bash
# 在服务器上执行
source ~/.nvm/nvm.sh
cd ~/Quant/apps/web
export QUANT_API_BASE_URL=http://127.0.0.1:9011/api/v1
pnpm dev --hostname 0.0.0.0 --port 9012
```

### 使用启动脚本

```bash
~/Quant/scripts/start-api.sh   # 启动 API
~/Quant/scripts/start-web.sh   # 启动 Web
```

---

## 3. 端口分配

| 服务 | 端口 | 部署方式 |
|------|------|----------|
| API | 9011 | 直接运行 |
| Web | 9012 | 直接运行 |
| Freqtrade | 9013 | Docker |
| mihomo HTTP代理 | 7890 | Docker |
| mihomo 控制台 | 9090 | Docker |
| Grafana | 3000 | Docker |
| Prometheus | 9091 | Docker |

---

## 4. 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 15 + React 19 + TailwindCSS |
| 后端 | FastAPI + Python 3.12 |
| 交易引擎 | Freqtrade + EnhancedStrategy |
| 数据库 | SQLite（Freqtrade） |
| 监控 | Prometheus + Grafana |
| 代理 | mihomo（Clash Meta） |

---

## 5. 服务代码结构

### API服务 (services/api/)
```
services/api/
├── app/
│   ├── main.py              # FastAPI入口
│   ├── routes/              # API路由
│   │   ├── market.py        # 市场数据
│   │   ├── feishu.py        # 飞书推送
│   │   └── health.py        # 健康检查
│   ├── services/            # 业务逻辑
│   │   ├── market_service.py
│   │   └── alert_push_service.py
│   └── adapters/            # 外部适配
└── requirements.txt
```

### Web前端 (apps/web/)
```
apps/web/
├── app/                     # Next.js页面
├── components/              # React组件
├── lib/                     # 工具库
└── package.json
```

---

## 6. API端点速查

### 核心端点
| 路径 | 作用 |
|------|------|
| `/healthz` | 健康检查 |
| `/api/v1/market` | 市场快照（16币种白名单） |
| `/api/v1/market/{symbol}/chart` | 单币K线图 |
| `/api/v1/market/{symbol}/rsi-history` | RSI历史 |
| `/api/v1/trade-log/history` | 交易历史 |

### Freqtrade端点（端口9013）
| 路径 | 作用 |
|------|------|
| `/api/v1/ping` | 心跳 |
| `/api/v1/status` | 持仓状态 |
| `/api/v1/balance` | 余额 |

---

## 7. 环境变量

API 环境变量位于 `infra/deploy/api.env`：

```bash
QUANT_RUNTIME_MODE=dry-run
QUANT_FREQTRADE_API_URL=http://127.0.0.1:9013
QUANT_FREQTRADE_API_USERNAME=Freqtrader
QUANT_FREQTRADE_API_PASSWORD=jianyu0.0.

HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

---

## 8. 策略开发

### EnhancedStrategy位置
```
infra/freqtrade/user_data/strategies/
├── EnhancedStrategy.py      # 策略代码
└── EnhancedStrategy.json    # 超参数
```

### 关键参数
| 参数 | 当前值 | 说明 |
|------|--------|------|
| rsi_entry_threshold | 45 | RSI超卖入场 |
| rsi_exit_threshold | 74 | RSI超买出场 |
| stoploss | -8% | 止损 |
| minimal_roi (120min) | 3% | 最低ROI |

### 修改策略后部署
```bash
# Freqtrade 是 Docker 容器，需要重启
docker restart quant-freqtrade
```

---

## 9. 常用命令

### 查看 API 日志
```bash
tmux attach -t quant-api
# 按 Ctrl+B 然后 D 退出（不停止服务）
```

### 查看 Web 日志
```bash
tmux attach -t quant-web
```

### 查看 Docker 容器日志
```bash
docker logs quant-freqtrade --tail 50
docker logs quant-mihomo --since 10m
```

### 测试 API 响应
```bash
curl -s 'http://127.0.0.1:9011/api/v1/market' | jq '.data.items | length'
# 应返回 16
```

---

## 10. 故障排查

### API 无法启动
```bash
# 检查端口占用
lsof -i :9011

# 检查依赖
pip list | grep fastapi
```

### Web 无法启动
```bash
# 检查 Node.js
source ~/.nvm/nvm.sh && node --version

# 检查依赖
cd ~/Quant/apps/web && pnpm install
```

### 代理不工作
```bash
# 检查 mihomo 容器
docker ps --filter name=mihomo
curl -x http://127.0.0.1:7890 https://api.ipify.org
```
