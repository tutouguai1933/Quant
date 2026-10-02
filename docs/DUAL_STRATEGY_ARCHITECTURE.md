# 双策略架构详解

> 最后更新：2026-10-02

## 本次修复后的策略边界

| 策略 | 决策位置 | 本次修复 |
|---|---|---|
| RSI 主策略 | Freqtrade 的 EnhancedStrategy | 入场检查扣费及步长后的止损退出金额；按当日已平仓净收益和权益重建风控；同日重启不清零、UTC跨日恢复 |
| 自动化周期训练策略 | API / worker / OpenClaw | 训练与实时特征分离；只用最新收盘行情，过期币种剔除；新价格回放和隔离评估；只选择通过校验的生产模型 |

RSI 的 RSI/SMA/ATR/ROI 参数本次没有修改，也不依赖 ML 评分。下文的数值是原文档版本的配置示例，线上数值以运行时有效配置为准，不能据本地参数文件推断线上参数。

自动化实验模型可继续训练和研究，但未通过生产准入不能下单。旧的未来标签回测不再满足新准入；新评估版本为 `ml_price_replay_v2`，按真实 OHLC、模型预测与下一根开盘价格回放。训练、验证、最终测试按所有资产共享时间及标签结束时间隔离，测试不参与早停。

特征版本为 `causal_features_v2`；标准化与 BTC 相关性只读取截至该时点的行情。固定/滚动历史窗口在训练与实时预测之间一致。

生产模型记录特征版本、历史窗口、标签目标、输入周期、因子列顺序、预处理与指标配置；输入协议变化后必须重新训练验证，不能默默把新特征喂给旧模型。生产模型的文件不会被实验产物清理误删。

自动化新仓标记 `quant-ml:`，方向空仓标记 `quant-direction-short:`。自动退出按实际交易编号、币种、方向与归属核对，不能按币种平掉自然 RSI 仓位。执行实例的账户资金与已成交风险预算仍共享。

当前二分类模型预测“未来收益超过阈值”，不等于预测下跌；低分不会打开方向空仓。方向模块保留明确归属的已有空仓管理，排序模型的原始分数也不能冒充上涨概率执行。

自动化准入配置统一在 `qlib_live_policy.py`：

| 环境变量 | 默认值 | 作用 |
|---|---:|---|
| QUANT_QLIB_MODEL_MIN_AUC | 0.55 | 验证质量的绝对下限，并要求正类 F1 有效 |
| QUANT_QLIB_PROMOTION_MIN_IMPROVEMENT | 0.01 | 新模型与合格生产模型比较的提升要求 |
| QUANT_QLIB_FEATURE_MAX_AGE_BARS | 2 | 实际行情特征的最大年龄 |
| QUANT_QLIB_PREDICTION_MAX_AGE_SECONDS | 3600 | 推理信号的最大有效时间 |

不足交易所最低卖出金额的历史余额不会被自动补买；入场修复防止新产生此类持仓，历史余额处置需单独确认。

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
