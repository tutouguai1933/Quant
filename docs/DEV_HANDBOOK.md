# Quant 开发手册

> **开发快速参考** - 代码结构、API、开发流程
>
> 最后更新：2026-05-05

---

## ⚠️ 重要：开发环境架构

### 开发与部署分离原则

```
┌─────────────────────────────────────────────────────────────────┐
│                        开发流程                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   本地 WSL (开发机)              阿里云服务器 (生产环境)          │
│   ┌─────────────────┐           ┌─────────────────┐            │
│   │ 代码编辑        │           │ Docker容器运行   │            │
│   │ Git提交/推送    │  ──────>  │ quant-api       │            │
│   │ 文档更新        │   SSH     │ quant-web       │            │
│   │                 │   部署    │ quant-freqtrade │            │
│   │ ❌ 不运行服务   │           │ quant-mihomo    │            │
│   └─────────────────┘           └─────────────────┘            │
│                                                                 │
│   IP: 动态(WSL2)                 IP: 39.106.11.65               │
│   私网: 172.21.x.x               私网: 172.22.73.168            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 核心规则

| 环境 | 作用 | 禁止操作 |
|------|------|----------|
| 本地WSL | 代码编辑、Git推送、文档维护 | ❌ 运行Docker容器、启动服务 |
| 阿里云服务器 | 运行所有服务、生产环境 | ❌ 直接编辑代码（应通过Git部署） |

### SSH连接到阿里云服务器

```bash
# 本地WSL中执行
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65

# 或使用域名（如已配置）
ssh -i ~/.ssh/id_aliyun_djy djy@quant-server
```

---

## 1. 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 14 + React + TailwindCSS |
| 后端 | FastAPI + Python 3.11 |
| 交易引擎 | Freqtrade + EnhancedStrategy |
| 数据库 | SQLite（Freqtrade） + PostgreSQL（可选） |
| 监控 | Prometheus + Grafana |
| 代理 | mihomo（Clash Meta） |

---

## 2. 服务代码结构

### API服务 (services/api/)
```
services/api/
├── app/
│   ├── main.py              # FastAPI入口
│   ├── routes/              # API路由
│   │   ├── feishu.py        # 飞书推送
│   │   ├── health.py        # 健康检查
│   │   ├── signals.py       # 信号处理
│   │   ├── strategies.py    # 策略管理
│   │   └── openclaw.py      # 自动化控制
│   ├── services/            # 业务逻辑
│   │   ├── feishu_push_service.py
│   │   ├── alert_push_service.py
│   │   ├── health_monitor_service.py
│   │   └── performance_monitor_service.py
│   ├── adapters/            # 外部适配
│   │   └── freqtrade/rest_client.py
│   └── core/                # 配置和日志
├── tests/
└── Dockerfile
```

### OpenClaw服务 (services/openclaw/)
```
services/openclaw/
├── openclaw_scheduler.py    # 巡检调度
├── openclaw_action_policy_service.py  # 动作策略
└── Dockerfile
```

### Web前端 (apps/web/)
```
apps/web/
├── app/                     # Next.js页面
│   ├── analytics/           # 数据分析页
│   ├── dashboard/           # 控制面板
│   └── workbench/           # 工作台
├── components/              # React组件
│   ├── charts/              # 图表组件
│   └── ui/                  # UI组件
├── lib/                     # 工具库
│   ├── websocket-context.tsx  # WebSocket
│   └── api-client.ts        # API调用
└── package.json
```

---

## 3. API端点速查

### 核心端点
| 路径 | 作用 |
|------|------|
| `/healthz` | 健康检查 |
| `/api/v1/feishu/test` | 测试飞书推送 |
| `/api/v1/feishu/alert` | 发送告警 |
| `/api/v1/health` | 容器健康状态 |
| `/api/v1/performance` | 性能指标 |
| `/api/v1/signals` | 信号列表 |
| `/api/v1/strategies` | 策略管理 |

### Freqtrade端点（端口9013）
| 路径 | 作用 |
|------|------|
| `/api/v1/ping` | 心跳 |
| `/api/v1/status` | 持仓状态 |
| `/api/v1/balance` | 余额 |
| `/api/v1/show_config` | 配置 |
| `/api/v1/forceentry` | 强制买入 |
| `/api/v1/forceexit` | 强制卖出 |

---

## 4. 环境变量（api.env）

### 必须配置
```bash
QUANT_RUNTIME_MODE=dry-run
QUANT_FREQTRADE_API_URL=http://127.0.0.1:9013
QUANT_FREQTRADE_API_USERNAME=Freqtrader
QUANT_FREQTRADE_API_PASSWORD=jianyu0.0.

FEISHU_WEBHOOK_URL=https://open.feishu.cn/...
QUANT_ALERT_WEBHOOK_URL=https://open.feishu.cn/...
```

### 监控配置
```bash
QUANT_MIHOMO_API_URL=http://127.0.0.1:9090
QUANT_API_LATENCY_THRESHOLD_MS=60000
QUANT_TRADE_LATENCY_THRESHOLD_MS=5000
```

---

## 5. 开发流程

### 正确的开发部署流程

```bash
# 步骤1: 在本地WSL编辑代码
vim services/api/app/routes/market.py

# 步骤2: 本地提交并推送到GitHub
git add services/api/app/routes/market.py
git commit -m "fix: market endpoint优化"
git push origin master

# 步骤3: SSH连接到阿里云服务器
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65

# 步骤4: 在服务器上拉取最新代码并重建
cd ~/Quant && git pull origin master
cd ~/Quant/infra/deploy && docker compose build api
docker compose up -d api

# 步骤5: 验证部署
curl -s http://127.0.0.1:9011/api/v1/health | jq '.'
```

### 本地开发（仅用于代码调试，不用于生产）

```bash
# 安装依赖（本地测试用）
cd services/api && pip install -r requirements.txt

# 本地单元测试
pytest tests/ -v

# ⚠️ 注意：本地不要启动完整服务，只做代码验证
```

### 远程部署（生产环境）

```bash
# SSH到阿里云服务器后执行
cd ~/Quant/infra/deploy

# 构建所有服务
docker compose build

# 启动服务
docker compose up -d

# 查看状态
docker ps --filter "name=quant"
```

---

## 6. 策略开发

### EnhancedStrategy位置
```
infra/freqtrade/user_data/strategies/
├── EnhancedStrategy.py      # 策略代码
└── EnhancedStrategy.json    # 超参数
```

### 关键参数
| 参数 | 当前值 | 说明 |
|------|--------|------|
| rsi_entry_threshold | **45** | RSI超卖入场（从40提高到45增加机会） |
| rsi_exit_threshold | 74 | RSI超买出场 |
| stoploss | -8% | 止损 |
| minimal_roi (120min) | **3%** | 最低ROI（已考虑手续费） |
| order_time_in_force | **IOC** | 防止重复挂单 |

### RSI阈值选择依据（基于30天历史数据分析）
```
RSI阈值    入场机会    胜率      平均收益
RSI<30     极少        70-85%    0.9-2.0%
RSI<35     较少        44-71%    0.3-2.3%
RSI<40     中等        51-63%    0.6-2.1%
RSI<45     较多        57-74%    1.0-2.4%  ← 当前选择
RSI<50     很多        62-75%    0.8-2.2%
```

选择RSI=45的权衡：
- 交易频率适中（30天约50-64次信号）
- 胜率较好（57-74%）
- 扣除0.2%手续费后仍有合理利润

### ROI配置（已考虑0.2%手续费）
```
时间    ROI阈值    净收益（扣手续费）
0分钟   8%         7.80%
30分钟  5%         4.80%
60分钟  4%         3.80%
120分钟 3%         2.80%  ← 最低阈值
```

**重要**：设置ROI时必须考虑双边手续费（买入0.1% + 卖出0.1% = 0.2%），确保净收益合理。

### 修改策略后部署
```bash
# 重启Freqtrade加载新策略
docker restart quant-freqtrade
docker logs quant-freqtrade --tail 50 | grep -i rsi
```

---

## 7. WebSocket使用

### 前端连接
```typescript
// apps/web/lib/websocket-context.tsx
const ws = new WebSocket('ws://127.0.0.1:9011/api/v1/ws');

// 可用通道
channels: ['research_runtime', 'automation_status']
```

### 后端处理
```python
# services/api/app/routes/websocket.py
@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
```

---

## 8. 测试

### API测试
```bash
cd services/api
pytest tests/ -v

# 快速测试
curl -s http://127.0.0.1:9011/healthz | jq '.'
```

### 集成测试
```bash
python infra/deploy/api_endpoint_test.py
```

---

## 9. 常用命令

### 查看日志
```bash
docker logs quant-api --since 10m -f
docker logs quant-freqtrade --tail 100 | grep -iE 'buy|sell|profit'
```

### 进入容器
```bash
docker exec -it quant-api bash
docker exec -it quant-freqtrade freqtrade backtesting --config ...
```

### 复制文件到容器
```bash
docker cp services/api/app/main.py quant-api:/app/app/main.py
docker restart quant-api
```

---

## 10. 调试技巧

### 查看环境变量
```bash
docker exec quant-api env | grep QUANT
```

### 测试API响应
```bash
time curl -s http://127.0.0.1:9011/api/v1/health | jq '.'
```

### 检查Freqtrade连接
```bash
curl -v -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/ping
```