# Quant 项目状态文档

> 最后更新：2026-05-11

---

## 当前进度

**状态**：系统稳定运行，性能优化完成

**本次更新（2026-05-11）**：
- **Patrol接口性能优化**：响应时间从100+秒降至1-3秒
  - FreqtradeRestClient.get_snapshot(): 5秒TTL缓存
  - AutomationWorkflowService.get_status(): 60秒TTL缓存
  - ValidationWorkflowService.build_report(): 60秒TTL缓存
  - OpenClawSnapshotService.get_snapshot(): 60秒TTL缓存 + 线程锁
- **BTC持仓卡住问题解决**：买入补足后一起卖出，dust转BNB
- **自动化状态恢复**：修复paused/manual_takeover状态
- **文档更新**：DEPLOYMENT_GUIDE.md, SERVICE_ARCHITECTURE.md, ops-troubleshooting.md

**上次更新（2026-05-08）**：
- 自动化周期历史增强（RSI快照、候选币种、任务状态）
- 配置管理界面修复
- 规则门控参数调整（成交量阈值0.8）

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
│   ├── 缓存层: 多级TTL缓存（5秒/60秒）
│   ├── RSI缓存: /app/.runtime/rsi_cache.json
│   ├── 自动化状态: /app/.runtime/automation_state.json
│   ├── 周期历史: /app/.runtime/automation_cycle_history.json
│   └── 响应时间: Patrol ~1-3秒（优化前100+秒）
├── quant-web (Next.js) - 端口 9012
├── quant-freqtrade - API端口 8080 (内部), stake_amount=10 USDT
├── quant-mihomo - 代理端口 7890, 控制端口 9090
├── quant-prometheus - 端口 9090
├── quant-grafana - 端口 3000
└── quant-openclaw - 巡检服务 (health_check/state_sync/cycle_check)
```

### 状态文件位置

| 文件 | 说明 |
|------|------|
| `.runtime/automation_state.json` | 自动化状态 |
| `.runtime/automation_cycle_history.json` | 周期历史（含RSI快照） |
| `.runtime/workbench_config.json` | 工作台配置 |
| `.runtime/rsi_cache.json` | RSI 缓存数据 |
| `.runtime/openclaw_patrol_records.json` | 巡检记录 |
| `.runtime/openclaw_audit_records.json` | 审计记录 |

---

## 双策略架构

### 1. Freqtrade EnhancedStrategy

- **类型**: 实时交易策略
- **运行位置**: quant-freqtrade 容器
- **配置**: `infra/freqtrade/user_data/config.live.base.json`
- **stake_amount**: 10 USDT
- **交易对**: 16个

### 2. Automation Cycle

- **类型**: 自动化周期策略
- **运行位置**: quant-api + quant-openclaw
- **模式**: auto_live
- **状态**: waiting（候选币种未通过验证）

### 为何近期无交易

系统运行正常，但候选币种未通过验证检查：
1. **BONKUSDT**: 成交量不足以进入live模式，停留在dry-run
2. **LINKUSDT**: validation_future_return_not_positive（预测收益非正）

---

## 缓存配置

| 服务 | 方法 | TTL | 文件 |
|------|------|-----|------|
| FreqtradeRestClient | get_snapshot() | 5秒 | `services/api/app/adapters/freqtrade/rest_client.py` |
| AutomationWorkflowService | get_status() | 60秒 | `services/api/app/services/automation_workflow_service.py` |
| ValidationWorkflowService | build_report() | 60秒 | `services/api/app/services/validation_workflow_service.py` |
| OpenClawSnapshotService | get_snapshot() | 60秒 | `services/api/app/services/openclaw_snapshot_service.py` |

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
| `candidate_not_live_ready` | 候选未放量 | 成交量不足以进入live模式 |

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

### 查看系统状态

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 'curl -s http://localhost:9011/api/v1/system/status | python3 -m json.tool'
```

### 恢复自动化运行

```python
# 如果自动化被暂停，执行以下代码恢复
import json
path = "/home/djy/Quant/infra/data/runtime/automation_state.json"
with open(path, 'r+') as f:
    state = json.load(f)
    state['paused'] = False
    state['manual_takeover'] = False
    f.seek(0)
    json.dump(state, f, indent=2)
    f.truncate()
```

---

## Freqtrade 配置

| 项目 | 值 |
|------|------|
| 模式 | **live** (dry_run=false) |
| 交易对 | BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX/LINK/DOT/POL/PEPE/SHIB/WIF/ORDI/BONK (**16个**) |
| stake_amount | **10 USDT** (单笔投入) |
| max_open_trades | **1** (并行仓位) |
| stoploss | -8% |
| 止盈目标 | 8%主目标，120分钟后最低 3% |
| 订单类型 | **IOC** (Immediate Or Cancel) |
| 策略 | EnhancedStrategy |
| RSI入场阈值 | **45** |
| RSI出场阈值 | **74** |
| 时间框架 | 1H |

---

## 当前持仓

| 资产 | 数量 | 状态 |
|------|------|------|
| USDT | 14.71700681 | 可交易 |
| BNB | 0.00843852 | 部分dust |
| ETH | 0.0001947 | dust |
| XRP | 0.0958 | dust |
| ADA | 0.0759 | dust |

---

## 参考文档

| 文档 | 内容 | 用途 |
|------|------|------|
| [AGENTS.md](AGENTS.md) | 开发规则和部署规范 | 开发指南 |
| [README.md](README.md) | 项目概览和使用动线 | 快速了解 |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | 部署详细说明 | 运维参考 |
| [docs/SERVICE_ARCHITECTURE.md](docs/SERVICE_ARCHITECTURE.md) | 服务架构和缓存配置 | 架构参考 |
| [docs/ops-troubleshooting.md](docs/ops-troubleshooting.md) | 运维踩坑记录 | 问题排查 |

---

## 当前状态

- **Freqtrade**: Live模式运行，无持仓
- **mihomo**: Healthy，JP1节点
- **系统**: 所有核心容器 healthy
- **自动化**: auto_live模式，waiting状态（候选未通过验证）
- **飞书**: 推送正常
- **前端**: 终端风格，功能完善
- **API**: 性能优化完成，Patrol响应1-3秒
