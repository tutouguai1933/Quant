# Quant 项目状态文档

> 最后更新：2026-05-08

---

## 当前进度

**状态**：系统稳定运行，功能持续优化中

**本次更新（2026-05-08）**：
- **自动化周期历史增强**：
  - 新增 RSI 快照记录（从缓存获取相关币种 RSI 值）
  - 新增候选币种列表展示（TOP 5）
  - 新增任务执行状态显示（train/infer/signal/review）
  - 拦截原因显示中文翻译
  - RSI 显示颜色指示（红色超买/绿色超卖）
- **配置管理界面修复**：
  - 修复 Docker 环境下配置不显示的问题
  - `_read_env_file` 方法支持从系统环境变量读取
- **规则门控参数调整**：
  - 成交量阈值从 1.0 调整为 0.8

**上次更新（2026-05-06）**：
- API 性能优化（TTLCache、并行获取、响应时间降至 20ms）
- RSI 缓存文件机制
- Patrol 认证修复
- 自动化恢复运行

**运维能力达成**：100%，所有核心容器 healthy

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ Healthy |
| 服务器Web | http://39.106.11.65:9012 | ✅ Healthy |
| Freqtrade | http://39.106.11.65:9013 | ✅ Live模式 |
| mihomo代理 | 127.0.0.1:7890 | ✅ Healthy |
| Prometheus | http://127.0.0.1:9090 | ✅ Healthy |
| Grafana | http://127.0.0.1:3000 | ✅ Healthy |
| 飞书推送 | Webhook已配置 | ✅ 正常 |
| OpenClaw | 巡检服务 | ✅ Healthy |
| 定时巡检 | 15分钟间隔 | ✅ 运行中 |

### 服务架构

```
服务器 (39.106.11.65)
├── quant-api (FastAPI) - 端口 9011
│   ├── RSI缓存: /app/.runtime/rsi_cache.json
│   ├── 自动化状态: /app/.runtime/automation_state.json
│   ├── 周期历史: /app/.runtime/automation_cycle_history.json
│   └── 并行获取账户数据，响应时间 ~20ms
├── quant-web (Next.js) - 端口 9012
├── quant-freqtrade - API端口 9013 (内部)
├── quant-mihomo - 代理端口 7890, 控制端口 9090
├── quant-prometheus - 端口 9090
├── quant-grafana - 端口 3000
└── quant-openclaw - 巡检服务
```

### 状态文件位置

| 文件 | 说明 |
|------|------|
| `.runtime/automation_state.json` | 自动化状态 |
| `.runtime/automation_cycle_history.json` | 周期历史（含RSI快照） |
| `.runtime/workbench_config.json` | 工作台配置 |
| `.runtime/rsi_cache.json` | RSI 缓存数据 |
| `.runtime/openclaw_patrol_records.json` | 巡检记录 |

---

## 核心功能模块

### 自动化工作流

| 文件 | 说明 |
|------|------|
| `services/api/app/services/automation_workflow_service.py` | 自动化工作流主服务 |
| `services/api/app/services/automation_service.py` | 自动化状态管理 |
| `services/api/app/services/automation_cycle_history_service.py` | 历史记录服务 |
| `services/api/app/services/scheduled_patrol_service.py` | 定时巡检服务 |
| `services/api/app/services/openclaw_patrol_service.py` | 巡检执行服务 |

### 规则门控

| 文件 | 说明 |
|------|------|
| `services/worker/qlib_rule_gate.py` | 规则门控（趋势/波动/量能过滤） |
| `services/worker/qlib_ranking.py` | 候选评分与验证 |
| `services/worker/qlib_config.py` | Qlib 配置加载 |

### 前端组件

| 文件 | 说明 |
|------|------|
| `apps/web/components/automation-cycle-history-card.tsx` | 自动化周期历史卡片 |
| `apps/web/app/config/page.tsx` | 配置管理页面 |

---

## 规则门控参数

### 当前配置（infra/deploy/api.env）

| 参数 | 值 | 说明 |
|------|------|------|
| `QUANT_QLIB_RULE_MIN_VOLUME_RATIO` | 0.8 | 成交量比率阈值 |
| `QUANT_QLIB_RULE_MAX_ATR_PCT` | 5 | ATR波动率上限 |
| `QUANT_QLIB_DRY_RUN_MIN_SHARPE` | 0.25 | 最小夏普比率 |
| `QUANT_QLIB_DRY_RUN_MIN_WIN_RATE` | 0.30 | 最小胜率 |
| `QUANT_QLIB_DRY_RUN_MIN_SCORE` | 0.45 | 最小综合评分 |

### 拦截原因对照表

| 英文代码 | 中文含义 | 说明 |
|---------|---------|------|
| `volume_not_confirmed` | 成交量不足 | 当前成交量低于历史平均的 80% |
| `volatility_too_high` | 波动率过高 | ATR 波动率超过 5% |
| `validation_future_return_not_positive` | 预测收益为负 | 回测预测收益不满足要求 |
| `trend_broken` | 趋势破位 | EMA 趋势线破位 |
| `score_too_low` | 评分过低 | 综合评分低于 0.45 |

---

## 部署命令速查

### 重建并部署 API 容器

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && cd infra/deploy && docker compose build api && docker compose up -d --no-deps api"
```

### 重建并部署 Web 容器

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && cd infra/deploy && docker compose build web && docker compose up -d --no-deps web"
```

### 重建并部署 API 和 Web

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && cd infra/deploy && docker compose build api web && docker compose up -d --no-deps api web"
```

### 启动定时巡检服务

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 'docker exec quant-api python3 -c "
import sys
sys.path.insert(0, \"/app/services/api\")
from services.api.app.services.scheduled_patrol_service import scheduled_patrol_service
result = scheduled_patrol_service.start_schedule(interval_minutes=15)
print(result)
"'
```

### 手动触发自动化周期

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 'docker exec quant-api python3 -c "
import sys
sys.path.insert(0, \"/app/services/api\")
from services.api.app.services.automation_workflow_service import automation_workflow_service
result = automation_workflow_service.run_cycle(source=\"manual_trigger\")
print(\"status:\", result.get(\"status\"))
print(\"recommended_symbol:\", result.get(\"recommended_symbol\"))
"'
```

### 查看历史记录

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "docker exec quant-api cat .runtime/automation_cycle_history.json | python3 -m json.tool | head -50"
```

---

## 前端页面清单

| 路由 | 页面名称 | 分组 | 认证 |
|------|----------|------|------|
| `/` | 工作台 | 研究 | - |
| `/research` | 模型训练 | 研究 | ✓ |
| `/backtest` | 回测训练 | 研究 | ✓ |
| `/evaluation` | 选币回测 | 研究 | ✓ |
| `/features` | 因子研究 | 研究 | ✓ |
| `/signals` | 信号 | 研究 | - |
| `/hyperopt` | 参数优化 | 研究 | ✓ |
| `/analytics` | 数据分析 | 研究 | - |
| `/data` | 数据管理 | 数据与知识 | - |
| `/factor-knowledge` | 因子知识库 | 数据与知识 | - |
| `/config` | 配置管理 | 数据与知识 | - |
| `/strategies` | 策略中心 | 运营 | ✓ |
| `/ops` | 运维监控 | 运营 | - |
| `/tasks` | 任务 | 运营 | ✓ |
| `/market` | 市场 | 工具 | - |
| `/balances` | 余额 | 工具 | - |
| `/positions` | 持仓 | 工具 | - |
| `/orders` | 订单 | 工具 | - |
| `/risk` | 风险 | 工具 | ✓ |

---

## Freqtrade 配置

| 项目 | 值 |
|------|------|
| 模式 | **live** (dry_run=false) |
| 交易对 | BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX/LINK/DOT/POL/PEPE/SHIB/WIF/ORDI/BONK (**16个**) |
| stake_amount | **6 USDT** (单笔投入) |
| max_open_trades | **1** (并行仓位) |
| stoploss | -8% |
| 止盈目标 | 8%主目标，120分钟后最低 3% |
| 订单类型 | **IOC** (Immediate Or Cancel) |
| 策略 | EnhancedStrategy |
| RSI入场阈值 | **45** |
| RSI出场阈值 | **74** |
| 时间框架 | 1H |

---

## 常见问题

### Q1: 配置管理页面显示为空

**原因**：Docker 容器中没有 api.env 文件，配置通过 docker-compose 的 env_file 注入为环境变量

**解决**：已修复，`_read_env_file` 方法现在同时读取系统环境变量

### Q2: 自动化周期历史 RSI 为空

**原因**：旧记录在代码修改前创建，没有保存 RSI 数据

**解决**：新记录会自动从 RSI 缓存获取数据

### Q3: 频繁拦截"成交量不足"

**原因**：市场成交量偏低，低于历史平均

**解决**：已将 `QUANT_QLIB_RULE_MIN_VOLUME_RATIO` 从 1.0 调整为 0.8

---

## 参考文档

| 文档 | 内容 | 用途 |
|------|------|------|
| [AGENTS.md](AGENTS.md) | 开发规则和部署规范 | 开发指南 |
| [README.md](README.md) | 项目概览和使用动线 | 快速了解 |
| [docs/HANDOFF_SESSION.md](docs/HANDOFF_SESSION.md) | 会话接力文档 | 任务交接 |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | 部署详细说明 | 运维参考 |

---

## 当前状态

- **Freqtrade**: Live模式运行
- **mihomo**: Healthy，JP1节点
- **系统**: 所有核心容器 healthy
- **自动化**: 运行中，15分钟间隔巡检
- **飞书**: 推送正常
- **前端**: 终端风格，功能完善
- **API**: 性能优化完成
