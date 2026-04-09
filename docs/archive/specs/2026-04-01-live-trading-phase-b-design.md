# Quant Live Trading Phase B Design

## 1. Summary

`Phase B` 要把 `Phase A` 已经跑通的真实行情、真实余额和 dry-run 执行链路，推进成第一版真正可用的波段交易工作台。

这一步的重点不再是“把页面和接口做出来”，而是把“第一批策略、币种白名单、参数模型、策略中心、图表标记和验收口径”固定下来，让系统开始具备真实交易决策能力。

## 2. Goals / Non-goals

### Goals

- 固定第一批只做 2 套波段策略，并写清楚各自的适用场景、输入数据和信号条件
- 建立白名单币种和策略参数模型，避免继续硬编码
- 增加“策略中心”页面，让用户能看清每套策略在做什么、对哪些币种生效、最近给了什么判断
- 增强图表页，让图表能展示趋势指标、信号点、买卖点和止损线
- 保持 `Binance Spot + dry-run` 的安全边界，继续避免提前进入真实下单
- 让 `Phase B` 做完后，用户可以用真实行情和策略规则跑一轮“看盘 -> 产出信号 -> 派发 dry-run -> 看结果”的完整流程

### Non-goals

- 不进入真实 `live` 下单
- 不进入合约、杠杆、做空、多交易所
- 不做复杂回测平台和参数搜索平台
- 不接入 `Qlib` 的完整研究平台能力
- 不同时做短线和中长线，只服务第一批波段策略

## 3. Current State & Constraints

### Current State

- `Phase A` 已完成，当前已经有真实 Binance 行情、真实 Binance 余额、市场页、单币图表页、订单页、持仓页和 `dry-run` 执行链路
- 当前页面入口在 `apps/web/app/market`、`apps/web/app/orders`、`apps/web/app/positions`、`apps/web/app/strategies`
- 当前 API 入口在 `services/api/app/routes/market.py`、`services/api/app/routes/signals.py`、`services/api/app/routes/strategies.py`
- 当前市场和账户数据来源分别在 `services/api/app/adapters/binance/market_client.py` 和 `services/api/app/adapters/binance/account_client.py`
- 当前执行仍然通过 `services/api/app/adapters/freqtrade/client.py` 的 `dry-run` 边界来验证主链路

### Constraints

- 第一阶段只做 `crypto + Binance + Freqtrade`
- `Phase B` 仍然只做 `Spot USDT`
- 当前真实执行仍然锁在 `dry-run`，不能把 `Phase B` 写成实盘下单计划
- WebUI 仍然是单管理员工作台，不进入多用户权限
- 继续沿用当前最小架构，不引入新的重量级服务和依赖

## 4. Requirements

### P0

- 系统中必须固定两套首批波段策略：
  - `trend_breakout`
  - `trend_pullback`
- 每套策略必须写清楚：
  - 用什么时间周期
  - 用哪些指标
  - 什么条件触发买入信号
  - 什么条件触发退出或失效
- 必须增加白名单配置，首批只允许固定少量币种进入策略评估
- 必须增加策略参数模型，让每套策略不再依赖散落在代码里的硬编码数值
- 必须提供策略中心页面，至少展示：
  - 策略名称
  - 说明
  - 当前状态
  - 适用币种
  - 参数摘要
  - 最近信号
  - 最近一次执行结果
- 图表页必须能展示：
  - K 线
  - 成交量
  - 趋势指标
  - 信号点
  - 买卖点
  - 止损线

### P1

- 市场页增加“是否在白名单”“适合哪套策略”“当前趋势状态”的摘要信息
- 策略页支持对策略做启停和币种绑定调整
- 信号页能区分信号来源是 `trend_breakout` 还是 `trend_pullback`

### P2

- 增加最小复盘摘要，为后续 `Phase C` 的复盘页做铺垫
- 增加更清晰的“为什么当前不给信号”的说明

### Non-functional Requirements

- 每套策略必须可解释，避免“黑盒信号”
- 所有策略都要先用真实行情计算，但执行仍只落在 `dry-run`
- 页面展示要统一，用户能看懂“先看市场、再看图表、再看策略、再看结果”的动线
- 参数、币种、策略状态都要有统一的配置来源，不能继续散落在多个页面和函数里

## 5. Design

### 5.1 Recommended Scope

`Phase B` 推荐拆成 4 个连续模块：

1. 策略配置基础
2. 图表增强
3. 两套策略落地
4. 策略中心与验收闭环

这样做的原因是：

- 先把白名单和参数收敛好，后面的图表和策略才能共用
- 先把图表指标和标记位置做对，用户才能看懂策略信号
- 先做两套策略，再做策略中心，页面才不会继续只是壳子

### 5.2 Alternatives

#### 方案 A：先做页面，再补策略

优点：

- 视觉完成度上升更快

缺点：

- 很容易再次变成“看起来完整，其实策略逻辑仍然空”的壳子

#### 方案 B：先做策略引擎，再补页面

优点：

- 数据和信号先扎实

缺点：

- 用户短期内看不到明显体验提升，调试成本也更高

#### 方案 C：配置、图表、策略、页面按链路推进

优点：

- 每一步都能被用户看见
- 也能保证策略逻辑和页面展示同步变实

缺点：

- 文档和任务拆分更细

推荐采用 `方案 C`。

### 5.3 First Two Strategies

#### 策略一：趋势突破 `trend_breakout`

目标：

- 捕捉白名单币种在波段上行过程中的突破段

主要数据：

- Binance `4h` K 线
- Binance `1d` K 线，用来辅助确认大方向
- 24h 成交额和成交量摘要

主要指标：

- `EMA20`
- `EMA55`
- `20 根 K 线最高价`
- `Volume SMA20`
- `ATR14`

买入信号定义：

- `1d` 收盘价在 `EMA55` 之上
- `4h` 的 `EMA20 > EMA55`
- 最新 `4h` 收盘价向上突破最近 `20` 根 `4h` K 线最高价
- 最新 `4h` 成交量大于 `Volume SMA20 * 1.2`
- 当前价格离突破位不超过 `1 * ATR14`

退出或失效定义：

- 收盘价跌回 `EMA20` 下方
- 收盘价跌破入场止损线
- 已经触发信号但价格离突破位过远，视为追高，放弃

适用场景：

- 白名单币种进入明显趋势段
- 市场整体风险不极端

#### 策略二：趋势回踩延续 `trend_pullback`

目标：

- 在已有趋势成立后，捕捉相对温和的回踩再启动机会

主要数据：

- Binance `4h` K 线
- Binance `1d` K 线

主要指标：

- `EMA20`
- `EMA55`
- `ATR14`
- `RSI14`
- `Volume SMA20`

买入信号定义：

- `1d` 收盘价在 `EMA55` 之上
- `4h` 的 `EMA20 > EMA55`
- 最近一段时间已经出现过一次有效上破，说明趋势已经成立
- 最新或最近两根 `4h` K 线最低价回踩到 `EMA20` 附近，允许偏差 `0.5 * ATR14`
- 回踩后重新站回 `EMA20`
- `RSI14` 位于 `48` 到 `68` 之间，避免追过热或接弱反弹
- 回踩结束后的确认 K 线成交量重新回到 `Volume SMA20` 附近或以上

退出或失效定义：

- 收盘价跌破 `EMA55`
- 收盘价跌破本次回踩低点减 `0.5 * ATR14`
- 回踩过深，趋势结构失效

适用场景：

- 趋势已经成立，但不想追突破
- 更强调风险回报比

### 5.4 Whitelist and Parameters

`Phase B` 必须固定第一批白名单币种，不做全市场扫描。

建议初始白名单：

- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`
- `BNBUSDT`

原因：

- 流动性足够
- 波段形态更稳定
- 便于初期观察策略问题

参数模型至少包含：

- `enabled`
- `symbols`
- `timeframe`
- `ema_fast`
- `ema_slow`
- `atr_period`
- `volume_period`
- `breakout_window`
- `volume_multiplier`
- `stop_atr_multiplier`

### 5.5 Page Design

#### 市场页

新增展示：

- 是否在白名单
- 当前更适合哪套策略
- 趋势状态：`uptrend / pullback / neutral`

#### 图表页

新增展示：

- `EMA20` 和 `EMA55`
- 突破参考线
- 最近信号点
- 已派发买点
- 止损线
- 当前策略解释卡片

#### 策略中心

新增页面目标：

- 让用户一眼知道目前两套策略分别在做什么
- 明确每套策略当前是启用还是停用
- 明确每套策略绑定了哪些币种
- 明确最近一次给信号的时间、币种和结果
- 明确当前参数摘要

策略中心最小页面块：

- 顶部总览卡
- 两套策略卡片
- 最近信号表
- 最近执行结果表
- 当前白名单摘要

## 6. Acceptance Criteria

- 仓库中存在 `Phase B` 规格和实现计划文档，且内容能直接指导后续多个会话继续开发
- 系统中固定只有两套首批波段策略：`trend_breakout` 和 `trend_pullback`
- 文档明确写清两套策略的数据来源、指标、买入信号、退出条件和适用场景
- 文档明确写清白名单币种和参数模型字段
- 文档明确写清市场页、图表页、策略中心分别要增加什么内容
- 文档明确写清 `Phase B` 仍然只跑 `dry-run`，不开放真实下单
- 文档明确写清后续实现时的验收路径：市场判断、图表验证、策略产信号、派发 dry-run、查看订单和持仓

## 7. Validation Strategy

- 检查规格文件是否已保存到 `docs/superpowers/specs/`
- 检查实现计划是否已保存到 `docs/superpowers/plans/`
- 检查 `README.md` 是否把“当前推荐下一步执行计划”更新到 `Phase B`
- 检查 `CONTEXT.md` 是否把当前阶段更新到 `Phase B` 计划准备完成

## 8. Risks & Rollback

### Risks

- 如果一开始就把策略做得太多，会再次回到“大而全壳子”
- 如果图表页只展示数字、不展示策略标记，用户仍然很难理解系统判断
- 如果白名单和参数不先统一，后续策略逻辑会继续分散
- 如果提前进入 `live`，会把当前项目带入不必要的实盘风险

### Rollback

- 如果 `Phase B` 实施过程中发现范围过大，就收敛为：
  - 先只做 `trend_breakout`
  - `trend_pullback` 延后
- 如果图表能力超过当前页面承载能力，就先保留指标和信号摘要，不强上完整图层交互
- 如果策略中心页面过重，就先做只读版，不做在线参数编辑

## 9. Open Questions

- `Phase B` 当前默认仍按 `Spot USDT` 执行，无需新增用户确认
- 真实 `live` 下单继续留到后续单独阶段处理

## 10. References

- `README.md`
- `CONTEXT.md`
- `docs/superpowers/specs/2026-04-01-personal-live-trading-workspace-design.md`
- `docs/superpowers/plans/2026-04-01-live-trading-phase-a-implementation.md`
