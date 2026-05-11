# 双策略架构详解

> 最后更新：2026-05-11

---

## 概述

Quant 系统运行两个独立的交易策略，同时监控市场，相互补充：

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

---

## 一、Freqtrade 独立策略 (EnhancedStrategy)

### 1.1 基本信息

| 项目 | 值 |
|------|------|
| 类型 | 实时交易策略 |
| 运行位置 | quant-freqtrade 容器 |
| 监控频率 | 每小时检查 |
| 交易对 | 16个（固定白名单） |
| 配置文件 | `infra/freqtrade/user_data/config.live.base.json` |
| 策略文件 | `infra/freqtrade/user_data/strategies/EnhancedStrategy.py` |

### 1.2 交易参数

| 参数 | 值 | 说明 |
|------|------|------|
| stake_amount | 7 USDT | 单笔投入金额（基础值） |
| max_open_trades | 3 | 最大并行持仓数 |
| stoploss | -8% | 固定止损 |
| RSI入场阈值 | 50 | RSI < 50 触发买入 |
| RSI出场阈值 | 80 | RSI > 80 触发卖出 |
| tradable_balance_ratio | 100% | 使用全部可用余额 |
| 时间框架 | 1H（主）+ 4H（趋势确认） |

### 1.3 入场条件

必须同时满足以下条件：

```
入场信号 = (
    1H RSI < 50                    # 1小时RSI超卖/中性偏弱
    AND 4H价格 > SMA200            # 4小时趋势向上
    AND 4H RSI < 70                # 4小时RSI不极端超买
    AND 成交量 > 20日平均 × 0.8    # 成交量确认
)
```

**条件解释**：

1. **RSI < 50**：相对强弱指数低于50，表示市场中性偏弱，有反弹潜力
2. **4H趋势向上**：价格在200日均线上方，避免逆势交易
3. **4H RSI < 70**：4小时周期不超买，确保不是追高
4. **成交量确认**：有足够的市场活跃度

### 1.4 出场条件

满足任一条件即触发卖出：

```
出场信号 = (
    ROI止盈                         # 持仓时间 + 利润目标
    OR RSI > 80                    # RSI超买
    OR 价格跌破 SMA50 × 0.98        # 短期趋势反转
    OR 亏损 ≥ 8%                   # 止损
    OR 追踪止盈触发                 # 利润回撤
)
```

**ROI止盈表**：

| 持仓时间 | 利润目标 |
|----------|----------|
| 0分钟 | 8% |
| 30分钟 | 5% |
| 60分钟 | 4% |
| 120分钟 | 3% |

**追踪止盈**：

- 利润达到 5% 后激活
- 从最高点回撤 3% 时卖出

### 1.5 风控机制

```python
# 日内风控
max_day_loss_pct = 4.5%           # 日亏损上限
max_consecutive_losses = 5         # 连续亏损5次暂停

# 仓位控制
tradable_balance_ratio = 1.0      # 使用全部可用余额
```

### 1.6 信号评分与动态仓位调整

EnhancedStrategy 根据信号质量动态调整仓位大小，实现更精细的风险控制。

#### 信号评分机制

信号强度评分由两个因子组成：

| 因子 | 权重 | 计算方式 |
|------|------|----------|
| RSI偏离度 | 60% | RSI越低于阈值，评分越高 |
| 成交量比值 | 40% | 放量程度越高，评分越高 |

**评分公式**：
```
signal_score = rsi_deviation × 0.6 + volume_score × 0.4
```

#### 仓位调整规则

| 信号评分 | 仓位倍数 | 说明 |
|----------|----------|------|
| > 80% | ×1.5 | 强信号，加仓买入 |
| 50% - 80% | ×1.0 | 正常信号，标准仓位 |
| < 50% | ×0.5 | 弱信号，减仓买入 |

#### 实际案例

**BNB/USDT 交易示例**：

| 项目 | 值 |
|------|------|
| 信号评分 | 44.2%（弱信号） |
| RSI | 46.5 |
| 成交量比值 | 1.21 |
| 仓位调整 | ×0.5 |
| 计算仓位 | 7 × 0.5 = 3.5 USDT |
| **实际成交** | 5.22 USDT |

**注意**：币安最小下单金额限制为 5 USDT。当计算仓位低于最小金额时，Freqtrade 会自动调整到交易所允许的最小金额。

```
弱信号计算: stake_amount × 0.5 = 3.5 USDT
币安最小限制: 5 USDT
实际成交: max(3.5, 5) = 5 USDT（精度调整后 5.22 USDT）
```

### 1.7 交易对白名单

```
BTC/USDT, ETH/USDT, SOL/USDT, XRP/USDT, 
BNB/USDT, DOGE/USDT, ADA/USDT, AVAX/USDT, 
LINK/USDT, DOT/USDT, POL/USDT, PEPE/USDT, 
SHIB/USDT, WIF/USDT, ORDI/USDT, BONK/USDT
```

---

## 二、自动化周期策略 (Automation Cycle)

### 2.1 基本信息

| 项目 | 值 |
|------|------|
| 类型 | AI驱动的周期策略 |
| 运行位置 | quant-api + quant-openclaw |
| 运行频率 | 每15分钟 |
| 模式 | auto_live |
| 候选选择 | 只选TOP1 |

### 2.2 执行流程

```
每15分钟运行:
│
├── 1. 训练阶段
│   └── 使用过去30天的K线数据训练机器学习模型
│
├── 2. 推理阶段
│   └── 对16个币种分别评分（0-1），按评分排序
│
├── 3. Gate验证
│   ├── Dry-Run Gate: 检查是否满足模拟盘条件
│   └── Live Gate: 检查是否满足实盘条件
│
└── 4. 执行阶段
    ├── 通过验证 → 执行买入
    └── 未通过验证 → 继续dry-run或等待
```

### 2.3 评分机制

机器学习模型根据以下因子计算评分：

| 因子类别 | 权重 | 包含指标 |
|----------|------|----------|
| 趋势 | 1.3 | EMA距离、趋势强度 |
| 动量 | 1.0 | ROC、动量指标 |
| 成交量 | 1.1 | 成交量比率、成交量趋势 |
| 震荡 | 0.7 | RSI、CCI、Stoch |
| 波动率 | 0.9 | ATR、波动率指标 |

**评分公式**：
```
Score = Σ(因子值 × 因子权重) / Σ(因子权重)
```

### 2.4 Gate 验证门槛

#### Dry-Run Gate（模拟盘门槛）

通过后可进入dry-run验证：

| 参数 | 阈值 | 说明 |
|------|------|------|
| score | ≥ 0.45 | 综合评分 |
| win_rate | ≥ 30% | 回测胜率 |
| sharpe | ≥ 0.25 | 夏普比率 |
| sample_count | ≥ 12 | 样本数量 |

#### Live Gate（实盘门槛）

通过后可直接进入live交易：

| 参数 | 阈值 | 说明 |
|------|------|------|
| score | ≥ 0.65 | 综合评分 |
| win_rate | ≥ 55% | 回测胜率 |
| net_return_pct | ≥ 20% | 净收益率 |
| sample_count | ≥ 24 | 样本数量 |
| turnover | ≤ 45% | 换手率上限 |

### 2.5 只选TOP1的原因

```
为什么只选TOP1？
├── 风险控制：避免同时买入多个不确定的候选
├── 资金效率：集中资金在最有把握的机会
├── 验证机制：先验证TOP1，失败再考虑TOP2
└── 简化决策：减少过度交易的风险
```

---

## 三、两个策略的关系

### 3.1 对比表

| 对比项 | Freqtrade 独立策略 | 自动化周期策略 |
|--------|-------------------|---------------|
| **运行频率** | 实时（每小时） | 周期（每15分钟） |
| **选币方式** | 固定白名单（16个币） | AI动态评分选TOP1 |
| **决策依据** | RSI技术指标 | 机器学习预测 |
| **买入条件** | RSI < 50 + 趋势向上 | TOP1 + 通过Gate |
| **卖出条件** | RSI > 80 / 止损 / ROI | 复用Freqtrade卖出 |
| **风险控制** | 内置止损/止盈 + 动态仓位 | Gate验证门槛 |
| **当前状态** | ✅ 正常运行 | ⚠️ 候选未通过Gate |

### 3.2 协作关系

```
Freqtrade 独立策略
    │
    ├── 监控固定白名单
    │
    ├── 发现机会 → 自己执行交易
    │
    └── 卖出逻辑独立控制

自动化周期策略
    │
    ├── AI选出TOP1候选
    │
    ├── 通过Gate → 调用Freqtrade执行买入
    │
    └── 卖出依赖Freqtrade策略

两者可以同时持仓（最多3个）
但买入逻辑相互独立
```

### 3.3 资金分配

```
总资金: ~15 USDT

Freqtrade 独立策略:
├── stake_amount: 7 USDT/笔（基础值）
├── 动态仓位调整: 根据信号评分 ×0.5/×1.0/×1.5
├── tradable_balance_ratio: 100%
└── max_open_trades: 3

自动化周期策略:
├── 复用Freqtrade的stake_amount
└── 买入后计入max_open_trades

结论: 两个策略共享资金池和持仓上限
```

---

## 四、卖出流程详解

### 4.1 Freqtrade 控制的卖出

无论是哪个策略买入的仓位，卖出都由 Freqtrade 控制：

```
卖出条件（满足任一）:

1. ROI止盈
   ├── 持仓0分钟: 利润 ≥ 8%
   ├── 持仓30分钟: 利润 ≥ 5%
   ├── 持仓60分钟: 利润 ≥ 4%
   └── 持仓120分钟: 利润 ≥ 3%

2. RSI超买
   └── RSI > 80

3. 趋势反转
   └── 价格跌破 SMA50 × 0.98

4. 止损
   └── 亏损 ≥ 8%

5. 追踪止盈
   ├── 利润达到5%后激活
   └── 从最高点回撤3%
```

### 4.2 卖出执行

```
卖出执行流程:
│
├── 1. 检查卖出条件
│
├── 2. 计算卖出数量
│   └── 全部卖出（无部分平仓）
│
├── 3. 发送限价单
│   └── IOC订单（立即成交或取消）
│
└── 4. 记录交易结果
    └── 更新盈亏统计
```

---

## 五、优化历史

### 5.1 已完成优化（2026-05-11）

**问题诊断**：
- RSI入场阈值45过于严格，市场RSI大多在50-70之间
- stake_amount 8 USDT 高于可用余额
- tradable_balance_ratio 50% 限制了资金使用

**已执行优化**：

| 优化项 | 修改前 | 修改后 | 效果 |
|--------|--------|--------|------|
| RSI入场阈值 | 45 | 50 | 更多入场信号 |
| stake_amount | 8 USDT | 7 USDT | 适应当前余额 |
| tradable_balance_ratio | 50% | 100% | 充分利用资金 |
| 策略 | SampleStrategy | EnhancedStrategy | 使用增强策略 |

**优化结果**：系统已开始正常交易，成功买入 BNB/USDT

### 5.2 后续优化方向

**自动化周期策略**：
- Live Gate门槛较高（胜率≥55%、样本数≥24）
- 可根据 Freqtrade 策略表现决定是否放宽

---

## 六、配置文件位置

| 配置项 | 文件路径 |
|--------|----------|
| Freqtrade 主配置 | `infra/freqtrade/user_data/config.live.base.json` |
| Freqtrade 策略 | `infra/freqtrade/user_data/strategies/EnhancedStrategy.py` |
| Gate阈值配置 | `infra/deploy/api.env` |
| 自动化状态 | `infra/data/runtime/automation_state.json` |
| 周期历史 | `infra/data/runtime/automation_cycle_history.json` |

---

## 七、常用运维命令

```bash
# 查看Freqtrade状态
curl -u 'Freqtrader:jianyu0.0.' http://localhost:9013/api/v1/status

# 查看当前持仓
curl -u 'Freqtrader:jianyu0.0.' http://localhost:9013/api/v1/status | jq '.open_trades'

# 查看自动化状态
cat /home/djy/Quant/infra/data/runtime/automation_state.json | jq '.mode, .paused, .last_cycle.status'

# 修改策略参数
# 1. 修改 EnhancedStrategy.py 中的默认值
# 2. 或修改 EnhancedStrategy.json 中的参数值
ssh djy@39.106.11.65
cd /home/djy/Quant/infra/freqtrade/user_data/strategies
# 编辑 EnhancedStrategy.json
docker restart quant-freqtrade

# 查看策略参数日志
docker logs quant-freqtrade 2>&1 | grep "Strategy Parameter"
```

---

## 八、参考文档

- [CONTEXT.md](/home/djy/Quant/CONTEXT.md) - 项目状态总览
- [architecture.md](/home/djy/Quant/docs/architecture.md) - 系统分层架构
- [SERVICE_ARCHITECTURE.md](/home/djy/Quant/docs/SERVICE_ARCHITECTURE.md) - 服务架构
- [DEPLOYMENT_GUIDE.md](/home/djy/Quant/docs/DEPLOYMENT_GUIDE.md) - 部署指南
