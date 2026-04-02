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

前端为了让客户端工作区能直接刷新市场和图表，又不受浏览器跨端口限制，新增了同源代理：

- `GET /api/control/market`
- `GET /api/control/market/{symbol}/chart`

说明：

- 这两个是 Web 前端自己的代理入口，不替代后端 `api/v1`
- 前端客户端组件优先走同源代理，后端服务端组件仍直接读 `api/v1`

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

前端策略页当前主要拿它来展示：

- 运行状态
- 当前判断
- 推荐策略
- 执行建议
- 参数摘要
- 最近信号

### `POST /api/v1/strategies/{strategy_id}/dispatch-latest-signal`

当前会先在控制平面本地筛掉已经 `dispatched / synced` 的信号。

如果当前策略没有可继续派发的信号，会返回：

- `error.code = signal_not_ready`

每张策略卡片里还会带：

- 研究倾向
- 模型版本
- 研究解释摘要
- 判断信心
- 研究门控状态

统一研究摘要字段当前包括：

- `research_bias`
- `recommended_strategy`
- `confidence`
- `research_gate`
- `primary_reason`
- `research_explanation`
- `model_version`
- `generated_at`

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
- `active_interval`
- `supported_intervals`
- `multi_timeframe_summary`
- `research_cockpit`
- `strategy_context`
- `freqtrade_readiness`

当前单币页的客户端交易工作区会用这个接口做：

- 首次服务端预取
- 周期切换时的局部刷新
- 前端短缓存复用

其中：

- `overlays` 已包含最小指标摘要
- `markers` 已包含：
  - `signals`
  - `entries`
  - `stops`
- `active_interval` 会说明当前主图实际使用的周期
- `supported_intervals` 会给出页面可切换的完整周期列表
- `multi_timeframe_summary` 会给出市场页和单币页共用的多周期判断摘要
- `research_cockpit` 会说明：
  - 当前研究倾向
  - 当前研究门控状态
  - 当前最重要的原因
  - 当前入场参考和止损参考
  - 当前图表图层摘要 `overlay_summary`
- `strategy_context` 会说明：
  - 当前更适合哪套策略
  - 当前趋势状态
  - 两套策略各自的判断结果和原因
  - 下一步动作
- `freqtrade_readiness` 会说明：
  - 当前后端是 `memory` 还是 `rest`
  - 当前是否已经具备真实 Freqtrade dry-run 条件
  - 当前还缺什么

### `GET /api/v1/market`

市场总览现在每个币种会额外返回：

- `research_brief`

它是统一研究摘要的简版，当前主要给市场页展示：

- 研究倾向
- 当前推荐策略
- 判断信心
- 研究门控状态

当前市场页会先显示骨架，再通过前端工作区补这份快照数据。
- 当前原因
- 模型版本

市场页当前也会结合接口原有字段一起展示：

- 当前价格
- 当前趋势状态
- 多周期状态
- 研究倾向
- 推荐策略
- 判断信心
- 主判断

统一研究摘要当前字段口径是：

- `research_bias`
- `recommended_strategy`
- `confidence`
- `research_gate`
- `primary_reason`
- `research_explanation`
- `model_version`
- `generated_at`

单币图表页使用的完整版还会额外带：

- `signal_count`
- `entry_hint`
- `stop_hint`
- `overlay_summary`

### `GET /api/control/[...path]`

这是 Web 端新增的同源代理入口，当前主要给浏览器里的市场页和单币图表页使用。

当前作用：

- 把前端客户端读取的 `/market` 和 `/market/{symbol}/chart` 请求代理到本地控制面 API
- 避免浏览器直接跨端口请求 `127.0.0.1:8000`
- 让市场页骨架加载和单币页局部切周期都能走同源请求

### `GET /api/v1/orders` 和 `GET /api/v1/positions`

这两个接口现在除了 `items`，还会在 `meta` 里明确给出：

- `source`
- `truth_source`

用来区分当前看到的是：

- `freqtrade-sync`
- `freqtrade-rest-sync`
- 或 `binance-account-sync`

### `POST /api/v1/strategies/{strategy_id}/dispatch-latest-signal`

这个接口在 `live` 模式下现在会额外做本地安全门检查：

- 必须显式打开 `QUANT_ALLOW_LIVE_EXECUTION=true`
- 必须连接真实 `Freqtrade REST`
- 远端必须确认自己处于 `live`
- 当前只允许 `spot`
- 必须命中 `QUANT_LIVE_ALLOWED_SYMBOLS`
- 必须满足 `QUANT_LIVE_MAX_STAKE_USDT`
- 必须满足 `QUANT_LIVE_MAX_OPEN_TRADES`
- 必须满足 Binance 最小下单额

当前仓库默认的最小 live 骨架是：

- `DOGE/USDT`
- 单笔 `1 USDT`
- 最多 `1` 个真实仓位

如果这些条件不满足，接口会直接返回业务错误，不会把真实下单直接放给远端。

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
