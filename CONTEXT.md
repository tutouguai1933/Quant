# Quant 项目状态文档

> 最后更新：2026-05-11

---

## 当前进度

**状态**：系统稳定运行，前端优化完成

**本次更新（2026-05-11）**：
- **前端优化**：
  - 新增 `RsiDataContext` 共享 RSI 数据，避免重复 API 请求
  - `EntryStatusCard` 和 `RsiSummaryCard` 共享 RSI 数据源
  - `AutomationCycleHistoryCard` 添加标签页导航（基础/候选/任务/RSI）
  - `RsiSummaryCard` 添加筛选和排序功能
  - `EntryStatusCard` 增强显示 RSI、趋势、策略指标
  - `CandidateQueueCard` 新增候选队列卡片
  - `BalancesPage` 添加 USD 估值和资产分布可视化
  - `OpsPage` 添加巡检统计（总运行次数、成功率、平均耗时）
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

系统运行两个独立的交易策略，同时监控市场：

```
┌─────────────────────────────────────────────────────────────────┐
│                        量化交易系统架构                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐     ┌─────────────────────────────┐   │
│  │  Freqtrade 独立策略  │     │    自动化周期策略            │   │
│  │  (EnhancedStrategy) │     │  (机器学习模型选币)          │   │
│  │                     │     │                             │   │
│  │  • 实时监控16个交易对 │     │  • 每15分钟运行一次          │   │
│  │  • RSI < 45 入场     │     │  • AI模型评分排序            │   │
│  │  • RSI > 80 出场     │     │  • 只选TOP1候选              │   │
│  └──────────┬──────────┘     └──────────────┬──────────────┘   │
│             └───────────────┬───────────────┘                   │
│                             ▼                                   │
│                    ┌─────────────────┐                          │
│                    │   Binance 交易所 │                          │
│                    └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### 1. Freqtrade 独立策略 (EnhancedStrategy)

| 项目 | 值 |
|------|------|
| 类型 | 实时交易策略 |
| 运行位置 | quant-freqtrade 容器 |
| 配置文件 | `infra/freqtrade/user_data/config.live.base.json` |
| 监控频率 | 每小时检查 |
| 交易对 | 16个（固定白名单） |
| stake_amount | 8 USDT |
| max_open_trades | 3 |
| RSI入场阈值 | 45 |
| RSI出场阈值 | 80 |
| 止损 | -8% |

**入场条件（必须全部满足）**：
1. 1H RSI < 45（超卖）
2. 4H价格 > SMA200（趋势向上）
3. 4H RSI < 70（非超买）
4. 成交量 > 20日平均 × 0.8

**出场条件（满足任一）**：
- ROI止盈：0分钟8% → 30分钟5% → 60分钟4% → 120分钟3%
- RSI > 80（超买）
- 价格跌破 SMA50 × 0.98
- 亏损 ≥ 8%（止损）
- 追踪止盈：利润5%后回撤3%

### 2. 自动化周期策略 (Automation Cycle)

| 项目 | 值 |
|------|------|
| 类型 | AI驱动的周期策略 |
| 运行位置 | quant-api + quant-openclaw |
| 运行频率 | 每15分钟 |
| 模式 | auto_live |
| 候选选择 | 只选TOP1 |

**执行流程**：
```
每15分钟运行:
  1. 训练阶段 - 机器学习模型用过去30天数据训练
  2. 推理阶段 - 对16个币种评分（0-1），排序
  3. Gate验证 - 检查TOP1候选是否满足条件
  4. 执行阶段 - 通过验证则买入，否则等待
```

**Gate 验证门槛**：

| Gate | 参数 | Dry-Run阈值 | Live阈值 |
|------|------|-------------|----------|
| 评分 | score | ≥ 0.45 | ≥ 0.65 |
| 胜率 | win_rate | ≥ 30% | ≥ 55% |
| 净收益率 | net_return | - | ≥ 20% |
| 样本数 | sample_count | ≥ 12 | ≥ 24 |
| 夏普比率 | sharpe | ≥ 0.25 | - |
| 换手率 | turnover | - | ≤ 45% |

### 两个策略的关系

| 对比项 | Freqtrade 独立策略 | 自动化周期策略 |
|--------|-------------------|---------------|
| 选币方式 | 固定白名单（16个币） | AI动态评分选TOP1 |
| 运行频率 | 实时（每小时） | 周期（每15分钟） |
| 决策依据 | RSI技术指标 | 机器学习预测 |
| 风险控制 | 内置止损/止盈 | Gate验证门槛 |
| 当前状态 | ✅ 正常运行 | ⚠️ 候选未通过Gate |

### 为何近期无交易

**历史统计（79轮运行）**：
- waiting: 43次（候选未放行到live）
- blocked: 32次（候选被Gate拦下）
- cooldown: 5次（冷却中）
- succeeded: 0次

**根本原因**：
1. **Freqtrade策略**：RSI入场阈值45太严格，当前市场大多数币RSI在50-70之间
2. **自动化周期策略**：Live Gate门槛高（胜率≥55%、样本数≥24），TOP1候选未通过

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
| stake_amount | **8 USDT** (单笔投入) |
| max_open_trades | **3** (并行仓位) |
| stoploss | -8% |
| 止盈目标 | 8%主目标，120分钟后最低 3% |
| 订单类型 | **IOC** (Immediate Or Cancel) |
| 策略 | EnhancedStrategy |
| RSI入场阈值 | **45** |
| RSI出场阈值 | **80** |
| 时间框架 | 1H（主）+ 4H（趋势确认） |

### 策略参数详解

```python
# 入场条件
rsi_entry_threshold = 45      # RSI < 45 触发买入
rsi_exit_threshold = 80       # RSI > 80 触发卖出

# 止损止盈
stoploss = -0.08              # 8% 固定止损
trailing_stop = True          # 启用追踪止盈
trailing_stop_positive = 0.03 # 利润3%后开始追踪
trailing_stop_positive_offset = 0.05  # 利润5%时激活

# 风控
max_day_loss_pct = 0.045      # 日亏损上限 4.5%
max_consecutive_losses = 5    # 连续亏损5次暂停
```

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

## 前端组件架构

### 共享数据上下文

| Context | 说明 | 刷新间隔 |
|---------|------|---------|
| `WebSocketContext` | 实时状态推送 | WebSocket |
| `RsiDataContext` | RSI 数据共享 | 5分钟 |

### 工作台卡片组件

| 组件 | 说明 | 数据源 |
|------|------|--------|
| `DualStrategyCard` | 双策略运行状态和收益 | Freqtrade API + System Status |
| `EntryStatusCard` | 入场条件指标（RSI、趋势、策略） | RsiDataContext + Market Snapshots |
| `RsiSummaryCard` | RSI 概览（支持筛选/排序） | RsiDataContext |
| `CandidateQueueCard` | 候选币种队列 | Candidate API |
| `TradeHistorySummaryCard` | 交易历史摘要 | Trade History API |
| `AutomationCycleHistoryCard` | 自动化周期历史（标签页导航） | Cycle History API |

### 组件使用示例

```tsx
// RsiDataContext 已集成在 layout.tsx 中
// EntryStatusCard 和 RsiSummaryCard 自动共享 RSI 数据

import { RsiDataProvider } from "../lib/rsi-data-context";
import { EntryStatusCard } from "../components/entry-status-card";
import { RsiSummaryCard } from "../components/rsi-summary-card";

// 在页面中使用
<RsiDataProvider>
  <EntryStatusCard />
  <RsiSummaryCard />
</RsiDataProvider>
```

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

- **Freqtrade**: Live模式运行，无持仓，4笔交易（3胜1负，胜率75%，总收益+13.94%）
- **mihomo**: Healthy，JP1节点
- **系统**: 所有核心容器 healthy
- **自动化**: auto_live模式，waiting状态（候选未通过验证）
- **飞书**: 推送正常
- **前端**: 终端风格，功能完善
- **API**: 性能优化完成，Patrol响应1-3秒

---

## 优化建议

### 问题诊断

**Freqtrade 独立策略无交易原因**：
- RSI入场阈值45过于严格
- 当前市场RSI大多在50-70之间（无超卖信号）
- 需要等待市场回调才能触发入场

**自动化周期策略无交易原因**：
- Live Gate门槛过高（胜率≥55%、样本数≥24）
- TOP1候选（BONK评分0.77）通过了评分门槛
- 但可能未通过胜率/样本数/净收益率门槛

### 优化方案对比

| 方案 | 操作 | 效果 | 风险 |
|------|------|------|------|
| A. 放宽RSI阈值 | 45 → 50 | 更多入场信号 | 可能买在较高位置 |
| B. 降低Live Gate | 胜率55%→45%，样本24→18 | 自动化策略可执行 | 选币质量下降 |
| C. 禁用Live Gate | 临时跳过验证 | 立即开始交易 | 无保护机制 |
| D. 保持现状 | 等待市场回调 | 风险最低 | 可能长期无交易 |

### 推荐方案

**第一阶段**：放宽Freqtrade RSI阈值（方案A）
- 这是独立策略，不依赖AI模型
- RSI 50仍然是合理的入场点（中性偏弱）
- 让系统先跑起来，积累交易经验

**第二阶段**：根据交易情况调整自动化策略
- 观察Freqtrade交易效果
- 如果效果好，考虑放宽Live Gate（方案B）
- 如果效果一般，保持较高门槛

### 参数调整命令

```bash
# 方案A：修改Freqtrade RSI阈值（需要修改策略文件）
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
cd /home/djy/Quant/infra/freqtrade/user_data/strategies
# 修改 EnhancedStrategy.py 中的 rsi_entry_threshold 默认值

# 方案B：降低Live Gate阈值（添加环境变量）
cd /home/djy/Quant/infra/deploy
echo 'QUANT_QLIB_LIVE_MIN_WIN_RATE=0.45' >> api.env
echo 'QUANT_QLIB_LIVE_MIN_SAMPLE_COUNT=18' >> api.env
docker compose up -d --no-deps api
```
