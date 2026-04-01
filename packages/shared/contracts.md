# Quant Shared Contracts

## 目标

本文件定义第一阶段控制平面在模块间共享的最小契约，只覆盖：

- `signal`
- `execution_action`
- `risk_decision`
- 与这些契约直接相关的枚举值

范围严格限定为：

- `crypto`
- `Binance`
- `Freqtrade`

## 枚举

### `strategy_status`

- `draft`
- `stopped`
- `running`
- `paused`
- `error`

### `task_status`

- `queued`
- `running`
- `succeeded`
- `failed`
- `retrying`
- `cancelled`

### `risk_level`

- `low`
- `medium`
- `high`
- `critical`

### `signal_source`

- `mock`
- `qlib`
- `rule-based`

### `signal_side`

- `long`
- `short`
- `flat`

### `signal_status`

- `received`
- `accepted`
- `rejected`
- `dispatched`
- `expired`
- `synced`

### `execution_action_type`

- `open_position`
- `close_position`
- `rebalance_position`

说明：

- `execution_action` 用于控制平面内部从 `signal` 到执行器动作的标准表示
- `Freqtrade start / stop / pause` 属于策略控制接口，不归入该契约

### `risk_decision_status`

- `allow`
- `warn`
- `block`

## `signal` 契约

用途：
研究层向控制平面提交的标准信号。

必填字段：

- `symbol`
- `side`
- `score`
- `confidence`
- `target_weight`
- `generated_at`
- `source`

可选字段：

- `strategy_id`
- `signal_id`
- `status`
- `received_at`

字段约束：

- `side` 取值为 `long | short | flat`
- `confidence` 取值范围为 `0..1`
- `target_weight` 取值范围建议为 `-1..1`
- `status` 默认 `received`

示例：

```json
{
  "symbol": "BTC/USDT",
  "side": "long",
  "score": "0.870000",
  "confidence": "0.920000",
  "target_weight": "0.250000",
  "generated_at": "2026-04-01T06:00:00+00:00",
  "source": "qlib",
  "strategy_id": 1,
  "status": "received"
}
```

## `execution_action` 契约

用途：
风控通过后的信号被转换为标准执行动作，再交给 `Freqtrade` adapter。

必填字段：

- `action_type`
- `symbol`
- `side`
- `quantity`
- `source_signal_id`

可选字段：

- `strategy_id`
- `account_id`
- `execution_engine`
- `venue`
- `created_at`

字段约束：

- `action_type` 取值为 `open_position | close_position | rebalance_position`
- `side` 取值复用 `signal_side`
- `quantity` 必须大于 `0`
- `execution_engine` 第一阶段固定为 `freqtrade`
- `venue` 第一阶段固定为 `binance`

示例：

```json
{
  "action_type": "open_position",
  "symbol": "BTC/USDT",
  "side": "long",
  "quantity": "0.0100000000",
  "source_signal_id": 1001,
  "strategy_id": 1,
  "account_id": 1,
  "execution_engine": "freqtrade",
  "venue": "binance"
}
```

## `risk_decision` 契约

用途：
风控层对单条信号给出的标准判断结果。

必填字段：

- `status`
- `reason`
- `rule_name`
- `evaluated_at`

可选字段：

- `level`
- `source_signal_id`
- `strategy_id`

字段约束：

- `status` 取值为 `allow | warn | block`
- `level` 取值为 `low | medium | high | critical`
- 任一 `block` 决定都应能映射为 `risk_events` 记录

示例：

```json
{
  "status": "block",
  "reason": "strategy is paused",
  "rule_name": "strategy_status_guard",
  "evaluated_at": "2026-04-01T06:01:00+00:00",
  "level": "high",
  "source_signal_id": 1001,
  "strategy_id": 1
}
```

## 契约与数据库的对齐要求

- `signals.source` 必须与 `signal_source` 一致
- `signals.side` 必须与 `signal_side` 一致
- `signals.status` 必须与 `signal_status` 一致
- `strategies.status` 必须与 `strategy_status` 一致
- `tasks.status` 必须与 `task_status` 一致
- `risk_events.level` 必须与 `risk_level` 一致
- `risk_events.decision` 必须与 `risk_decision_status` 一致

