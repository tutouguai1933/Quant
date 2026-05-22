# 双策略架构详解

> 最后更新：2026-05-23

---

## 概述

Quant 系统运行两个独立的交易策略：

```
┌──────────────────────────────────────────────────────────────┐
│                     量化交易系统架构                           │
├──────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐     ┌─────────────────────────────┐   │
│  │ EnhancedStrategy   │     │  自动化周期策略              │   │
│  │ (RSI 技术指标)     │     │  (ML 模型选币)               │   │
│  │                   │     │                             │   │
│  │ • 1H 实时监控      │     │ • 每15分钟运行一次           │   │
│  │ • RSI < 32 入场    │     │ • LightGBM 评分排序          │   │
│  │ • 15个交易对        │     │ • 只选 TOP1 候选            │   │
│  └────────┬──────────┘     └──────────────┬──────────────┘   │
│           └───────────────┬───────────────┘                   │
│                           ▼                                   │
│                  ┌─────────────────┐                          │
│                  │   Binance 交易所 │                          │
│                  └─────────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 一、EnhancedStrategy（RSI策略）

### 1.1 基本信息

| 项目 | 值 |
|------|------|
| 运行位置 | quant-freqtrade 容器 |
| 时间框架 | 1H（主）+ 4H（趋势确认） |
| 策略文件 | `infra/freqtrade/user_data/strategies/EnhancedStrategy.py` |
| 参数文件 | `infra/freqtrade/user_data/strategies/EnhancedStrategy.json` |

### 1.2 入场条件（4个同时满足）

```python
入场 = (
    1H RSI < 32                              # 超卖区域
    AND 4H价格 > SMA200(4H)                   # 长期趋势向上
    AND 4H RSI < 70                           # 不超买
    AND 成交量 > 过去7天同一时段均量 × 0.6      # 同时段量能确认
)
```

| 条件 | 阈值 | 作用 |
|------|------|------|
| RSI < 32 | 1H RSI 低于 32 | 真超卖，避免弱信号 |
| 价格 > 4H SMA200 | 4H收盘在200均线上方 | 只在上升趋势中做多 |
| 4H RSI < 70 | 不极端超买 | 不追高 |
| 成交量 ≥ 同时段60% | 过去7天同一小时均量 | 作息规律自适应，过滤异常缩量 |

### 1.3 出场条件

```
出场 = ROI止盈 | RSI > 72 | 价格 < SMA50×0.98 | 止损-8% | 追踪止盈
```

ROI：0min=8%, 30min=5%, 60min=3%, 120min=2%

追踪止盈：利润达5%激活，回撤3%触发

### 1.4 参数总览

| 参数 | 值 |
|------|------|
| rsi_entry_threshold | 32 |
| rsi_exit_threshold | 72 |
| atr_multiplier | 2.0 |
| max_day_loss_pct | 5% |
| max_consecutive_losses | 4 |
| stoploss | -8% |
| stake_amount | 7 USDT |
| max_open_trades | 3 |

### 1.5 信号评分与仓位调整

| 信号评分 | 仓位倍数 |
|----------|----------|
| > 80% | ×1.5 |
| 50-80% | ×1.0 |
| < 50% | ×0.5 |

---

## 二、自动化周期策略（ML策略）

### 2.1 基本信息

| 项目 | 值 |
|------|------|
| 运行位置 | quant-api + quant-openclaw |
| 运行频率 | 每15分钟 |
| 模型 | LightGBM |
| 特征 | 10个因子 |

### 2.2 执行流程

```
每15分钟:
  1. 训练: 60天4H数据 → LightGBM → 模型文件
  2. 推理: 15币种各打一个概率分(0~1) → 按分排序
  3. 门控: 6道Gate逐币检查 → 确定能否推进
  4. 执行: TOP1通过全部Gate → 执行
```

### 2.3 门控体系

| Gate | 检查 | 阈值 |
|------|------|------|
| Score Gate | ML得分 | ≥ 0.45 |
| Rule Gate | EMA/ATR/成交量 | ema20_gap>0, ema55_gap>0 |
| Backtest Gate | 回测（仅ML买入样本） | return>0, sharpe≥0.25 |
| Consistency Gate | 回测内部一致性 | 胜率vs Sharpe, 收益vs回撤 |
| Validation Gate | per-symbol 验证 | sample≥12 |
| Live Gate | 实盘准入 | score≥0.50, win_rate≥55% |

### 2.4 当前 ML 配置

```python
DEFAULT_LIGHTGBM_PARAMS = {
    "num_leaves": 31,
    "learning_rate": 0.02,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "min_child_samples": 20,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "n_estimators": 200,
    "early_stopping_rounds": 15,
}
```

DEFAULT_LOOKBACK_DAYS = 60

---

## 三、两策略对比

| 对比项 | EnhancedStrategy | 自动化周期 |
|--------|-----------------|-----------|
| 决策方式 | RSI 技术指标 | ML 模型预测 |
| 频率 | 1H 实时 | 15分钟周期 |
| 选币 | 15个固定白名单 | AI 动态评分 TOP1 |
| 入场条件 | RSI<32 + 趋势向上 | 通过全部 Gate |
| 风控 | ATR止损+ROI+追踪 | Gate验证门槛 |

---

## 四、配置文件位置

| 配置项 | 文件路径 |
|--------|----------|
| ML 模型参数 | `services/worker/qlib_config.py` |
| Gate 阈值 | `services/worker/qlib_ranking.py` |
| 门控环境变量 | `infra/deploy/api.env` |
| EnhancedStrategy 代码 | `infra/freqtrade/user_data/strategies/EnhancedStrategy.py` |
| EnhancedStrategy 参数 | `infra/freqtrade/user_data/strategies/EnhancedStrategy.json` |
| 自动化状态 | `infra/data/runtime/automation_state.json` |
