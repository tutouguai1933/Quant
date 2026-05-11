# Quant Schema Draft

## 设计原则

- 第一阶段只覆盖 `crypto + Binance + Freqtrade`
- 核心目标是支撑 `signal -> risk -> execution -> monitoring`
- 先使用少量核心表完成主链路，避免提前抽象为通用多市场模型
- 状态字段优先使用受控枚举语义，减少联调返工

## 核心实体

### `accounts`

用途：
保存控制平面关注的交易账户元信息，第一阶段默认指向 `Binance`。

关键字段：

- `account_key`: 账户稳定标识
- `venue`: 固定为 `binance`
- `account_type`: 账户类型，先保留为 `spot`
- `base_currency`: 账户基准币种，默认 `USDT`
- `status`: `active | disabled | archived`

索引：

- `(venue, status)`
- `account_key` 唯一索引

### `balances`

用途：
保存账户最新资产快照。

关键字段：

- `account_id`
- `asset`
- `total`
- `available`
- `locked`
- `snapshot_time`

索引：

- `(account_id, asset)` 唯一索引

### `positions`

用途：
保存账户当前持仓快照，供策略执行反馈与 WebUI 展示。

关键字段：

- `account_id`
- `strategy_id`
- `symbol`
- `side`
- `quantity`
- `entry_price`
- `mark_price`
- `unrealized_pnl`

索引：

- `(account_id, symbol)`
- `(account_id, symbol, side)` 唯一约束

### `orders`

用途：
保存执行器回传的订单状态，系统内部不维护第二套订单真相源。

关键字段：

- `account_id`
- `strategy_id`
- `source_signal_id`
- `venue_order_id`
- `symbol`
- `side`
- `order_type`
- `status`
- `quantity`
- `executed_qty`
- `avg_price`

索引：

- `(account_id, status, updated_at DESC)`
- `venue_order_id` 可在后续任务视需要补唯一约束

### `strategies`

用途：
保存策略定义与当前运行状态。

关键字段：

- `strategy_key`
- `name`
- `producer_type`
- `execution_engine`
- `symbols_scope`
- `status`
- `risk_enabled`

索引：

- `strategy_key` 唯一索引
- `(status)`

状态流转：

- `draft -> stopped`
- `stopped -> running`
- `running -> paused`
- `paused -> running`
- `running -> stopped`
- `paused -> stopped`
- 任一状态可在同步异常时进入 `error`

### `signals`

用途：
保存研究层输出的标准化信号及其处理状态。

关键字段：

- `strategy_id`
- `source`: `mock | qlib | rule-based`
- `symbol`
- `side`
- `score`
- `confidence`
- `target_weight`
- `status`
- `generated_at`
- `received_at`
- `payload`

索引：

- `(strategy_id, generated_at DESC)`
- `(status, generated_at DESC)`

建议状态流转：

- `received -> accepted`
- `received -> rejected`
- `accepted -> dispatched`
- `dispatched -> synced`
- `received -> expired`
- `accepted -> expired`

### `tasks`

用途：
统一记录训练、同步、对账、归档、风控检查等后台任务。

关键字段：

- `task_type`
- `source`: `system | openclaw | user | scheduler`
- `status`
- `target_type`
- `target_id`
- `requested_at`
- `started_at`
- `finished_at`
- `error_message`

索引：

- `(status, requested_at DESC)`

状态流转：

- `queued -> running`
- `running -> succeeded`
- `running -> failed`
- `failed -> retrying`
- `retrying -> running`
- `queued -> cancelled`
- `running -> cancelled`

### `risk_events`

用途：
记录风控拒绝、告警与风险相关异常。

关键字段：

- `signal_id`
- `strategy_id`
- `rule_name`
- `level`
- `decision`
- `reason`
- `event_time`
- `resolved_at`

索引：

- `(level, event_time DESC)`

建议语义：

- `level`: `low | medium | high | critical`
- `decision`: `allow | warn | block`

## 实体关系

- `accounts` 1:N `balances`
- `accounts` 1:N `positions`
- `accounts` 1:N `orders`
- `strategies` 1:N `signals`
- `strategies` 1:N `orders`
- `strategies` 1:N `positions`
- `signals` 1:N `risk_events`
- `signals` 1:N `orders`（通过 `source_signal_id` 关联）

## 第一阶段刻意不做的 schema 复杂化

- 不做多市场统一账户模型
- 不做通用执行器抽象表簇
- 不做策略参数版本化表
- 不做复杂订单事件流水
- 不做多用户、角色、权限表

这些扩展在第一阶段都会抬高建模成本，并偏离当前最小闭环目标。
