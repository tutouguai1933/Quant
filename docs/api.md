# Quant API

## 当前接口状态

当前 API 已经不是草案状态，而是有一批真实可用接口。

主要能力分成 6 类：

- 登录与会话
- 市场与图表
- 研究层
- 账户与执行结果
- 策略与信号
- 风险与任务

## 统一返回格式

成功：

```json
{
  "data": {},
  "error": null,
  "meta": {}
}
```

失败：

```json
{
  "data": null,
  "error": {
    "code": "string",
    "message": "string"
  },
  "meta": {}
}
```

## 已可用接口

### 健康检查

- `GET /health`
- `GET /healthz`

### 登录与会话

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/session`
- `GET /api/v1/auth/model`

### 市场与图表

- `GET /api/v1/market`
- `GET /api/v1/market/{symbol}/chart`

### 研究层

- `GET /api/v1/signals/research/latest`
- `POST /api/v1/signals/research/train`
- `POST /api/v1/signals/research/infer`

### 账户与执行结果

- `GET /api/v1/accounts`
- `GET /api/v1/balances`
- `GET /api/v1/positions`
- `GET /api/v1/orders`

### 策略与信号

- `GET /api/v1/strategies`
- `GET /api/v1/strategies/catalog`
- `GET /api/v1/strategies/workspace`
- `GET /api/v1/strategies/{strategy_id}`
- `POST /api/v1/strategies/{strategy_id}/start`
- `POST /api/v1/strategies/{strategy_id}/pause`
- `POST /api/v1/strategies/{strategy_id}/stop`
- `POST /api/v1/strategies/{strategy_id}/dispatch-latest-signal`
- `GET /api/v1/signals`
- `GET /api/v1/signals/{signal_id}`
- `POST /api/v1/signals/ingest`
- `POST /api/v1/signals/pipeline/run`
- `POST /api/v1/signals/strategy/run`

### 风险与任务

- `GET /api/v1/risk-events`
- `GET /api/v1/risk-events/{risk_event_id}`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/train`
- `POST /api/v1/tasks/sync`
- `POST /api/v1/tasks/reconcile`
- `POST /api/v1/tasks/archive`
- `POST /api/v1/tasks/health-check`
- `POST /api/v1/tasks/{task_id}/retry`

## 当前最重要的几个接口

### `GET /api/v1/strategies/workspace`

这是现在策略中心页面的后端入口。  
会返回：

- 顶部总览
- 执行器运行摘要
- 研究层总览
- 白名单
- 两套策略卡片
- 最近信号
- 最近执行结果

每张策略卡片里还会带：

- 研究分数
- 模型版本
- 研究解释摘要
- 判断信心
- 研究门控状态

### `GET /api/v1/signals/research/latest`

这是当前研究层页面展示的统一读取入口。  
会返回：

- 当前研究状态
- 当前研究后端
- 最近一次训练结果
- 最近一次推理结果
- 各个币种最近一次研究摘要

### `POST /api/v1/signals/research/train`

这是当前最小训练入口。  
当前会：

- 读取白名单市场样本
- 生成最小特征和标签
- 输出模型版本和训练记录
- 现在需要管理员令牌

### `POST /api/v1/signals/research/infer`

这是当前最小推理入口。  
当前会：

- 读取最近一次训练结果
- 输出标准化研究信号
- 返回分数、解释和模型版本
- 现在需要管理员令牌

### `POST /api/v1/signals/strategy/run`

这是当前最小策略判断入口。  
现阶段支持：

- `trend_breakout`
- `trend_pullback`

输出的判断状态包括：

- `signal`
- `watch`
- `block`
- `evaluation_unavailable`

当前还会额外返回：

- `confidence`
- `research_gate`

说明：

- `research_gate` 现在采用“软门控”
- 研究结果只负责确认或压低策略信号，不单独制造新信号

### `GET /api/v1/market/{symbol}/chart`

当前返回：

- `items`
- `overlays`
- `markers`

其中：

- `overlays` 已包含最小指标摘要
- `markers` 目前还是最小结构，后续会继续补

图表页现在还会另外读取研究结果接口，用于显示：

- 研究状态
- 研究分数
- 模型版本
- 研究解释

### `GET /api/v1/orders` 和 `GET /api/v1/positions`

这两个接口现在除了 `items`，还会在 `meta` 里明确给出：

- `source`
- `truth_source`

用来区分当前看到的是：

- `freqtrade-sync`
- `freqtrade-rest-sync`
- 或 `binance-account-sync`

### `POST /api/v1/strategies/{strategy_id}/start|pause|stop`

这三个接口当前有一个明确边界：

- 只允许 `strategy_id=1`
- 表示控制整台 `Freqtrade` 执行器
- 当前不会把它伪装成“控制策略卡片 2”

返回里会额外带：

- `scope=executor`
- `controlled_strategy_id`

## 需要登录的接口

这些接口当前受保护：

- `GET /api/v1/strategies`
- `GET /api/v1/strategies/catalog`
- `GET /api/v1/strategies/workspace`
- `GET /api/v1/strategies/{strategy_id}`
- `POST /api/v1/strategies/{strategy_id}/start`
- `POST /api/v1/strategies/{strategy_id}/pause`
- `POST /api/v1/strategies/{strategy_id}/stop`
- `POST /api/v1/strategies/{strategy_id}/dispatch-latest-signal`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`
- `POST /api/v1/tasks/train`
- `POST /api/v1/tasks/sync`
- `POST /api/v1/tasks/reconcile`
- `POST /api/v1/tasks/archive`
- `POST /api/v1/tasks/health-check`
- `POST /api/v1/tasks/{task_id}/retry`
- `GET /api/v1/risk-events`
- `GET /api/v1/risk-events/{risk_event_id}`

## 当前边界

- 不开放真实下单接口
- 不开放在线参数编辑接口
- 不开放多用户权限接口
- 不开放 Lean / vn.py 相关接口
- 不提供完整实验平台接口
- 当前研究训练和推理仍以最小闭环为目标
