# Quant Current Plan

## 当前状态

这个仓库已经不再是“只有文档的 greenfield”。  
当前实际进度是：

- `Phase A` 已完成
- `Phase B` 已完成前 `5` 个任务，并补完了市场页和图表页的核心体验
- 平台总架构回归设计已完成
- 系统已经可以真实启动 API 和 WebUI
- 已能读取 Binance 真实行情和真实余额
- 已能完成一条真实 `dry-run` 主链路

## 已完成清单

### 基础阶段

- [x] 仓库骨架与基础文档
- [x] 统一契约与数据库模型
- [x] Control Plane API 骨架
- [x] WebUI 基础页面骨架
- [x] 最小信号流水线
- [x] Freqtrade 执行适配器与同步链路
- [x] 基础风控与任务系统
- [x] 单管理员鉴权
- [x] 最小演示与验收流程

### 真实 dry-run 阶段

- [x] Binance 市场数据接入
- [x] Binance 余额接入
- [x] 市场页与单币图表页
- [x] `dry-run / demo / live` 运行边界
- [x] Freqtrade `flat` 改成按当前币种或当前交易收敛，不再全平
- [x] 本地防重复派发
- [x] 执行成功回执优先返回真实 Freqtrade 字段
- [x] Freqtrade Docker 改成“host 网络 + REST 仅监听 127.0.0.1”
- [x] live 本地安全门
- [x] live Docker 配置骨架
- [x] 首笔真实 live Spot 买单验收
  结果：已完成 `DOGE/USDT + 1 USDT` 首笔真实买单

### Phase B

- [x] Task 1：统一白名单和策略目录
- [x] Task 2：图表指标基础
- [x] Task 3：`trend_breakout`
- [x] Task 4：`trend_pullback`
- [x] Task 5：策略中心

## 当前系统真实能力

### 已可使用

- 登录控制台
- 查看市场页
- 查看单币图表页
- 查看余额页
- 查看订单页
- 查看持仓页
- 查看风险页
- 查看任务页
- 在策略中心查看：
  - 两套策略卡片
  - 当前判断
  - 默认参数
  - 白名单摘要
  - 最近信号
  - 最近执行结果
- 走通 `signal -> risk -> execution -> sync -> display`

### 仍未开放

- 真实下单最终验收
- 在线参数编辑
- 多用户权限
- 多市场
- 完整研究平台

## 下一步执行顺序

后续继续按 `Phase B` 收口，但不再回到大而全路线。

### Next 1：市场页补策略视角

- [x] 显示白名单币种当前更适合哪套策略
- [x] 显示趋势状态：`uptrend / pullback / neutral`
- [x] 让市场页成为策略观察入口，而不是纯价格列表

### Next 2：图表页补策略解释

- [ ] 页面内直接展示 `EMA20 / EMA55`
- [x] 显示突破参考位或回踩参考位
- [ ] 把最近信号点做成更直观的图层
- [x] 显示止损参考
- [x] 增加“为什么当前判断是 signal / watch / block”的解释卡片

### Next 3：Phase B 验收闭环

- [ ] 从市场页进入图表页
- [ ] 从图表页进入策略中心
- [ ] 从策略中心进入 dry-run 派发
- [ ] 在订单、持仓、任务、风险页看见完整反馈

## 当前架构边界

- 只做 `crypto`
- 只做 `Binance`
- 只做 `Freqtrade`
- 当前执行仍以 `dry-run` 为主
- 首批策略固定为：
  - `trend_breakout`
  - `trend_pullback`

## 平台回归 Todo

### 已完成

- [x] 明确总路线为“适配器优先，总控自研”
- [x] 明确 `WebUI + Backend + OpenClaw` 属于控制平面
- [x] 明确 `Qlib` 属于研究层
- [x] 明确 `Freqtrade` 属于加密执行层
- [x] 明确 `Lean / vn.py` 属于扩展执行层
- [x] 输出平台架构回归设计文档

### 下一批重点

- [x] Freqtrade 真实集成计划
- [x] Qlib 最小研究层计划
- [x] Lean / vn.py / OpenClaw 扩展位计划
- [x] Freqtrade 真实 REST 适配器
- [x] Freqtrade bot 状态与订单持仓同步
- [x] Freqtrade Spot dry-run Docker 部署骨架
- [x] 接上一台真实 Freqtrade REST 服务完成最终 dry-run 验收
- [x] live 运行安全门
- [x] live `DOGE/USDT + 1 USDT` 容器骨架
- [x] live 首笔真实 Spot 买单验收
  结果：真实订单已成交
- [x] live 模式下的 `sync_task` 超时修复
  结果：`live` 下改为直接使用 Binance 账户同步，真实 `/tasks/sync` 已验证成功
- [x] live 同步判定改成“必须对上刚派发的订单”
- [x] live 订单同步范围与 live 白名单对齐，并补上 sync 重试成功后的 signal 状态恢复
- [x] GitHub 私有仓库作为唯一代码基线
- [x] 阿里云统一部署骨架（API / WebUI / Freqtrade）
- [x] 阿里云统一部署首轮拉起
  结果：Docker、Compose、端口注册表和 `9011 / 9012 / 9013` 容器都已拉起，外网能打开 WebUI
- [x] 阿里云 Mihomo 代理接入与公开行情恢复
  结果：`9016 / 9017` 已接入，公开行情与 Freqtrade 已能通过代理访问 Binance，市场接口失败时也会优雅降级
- [x] 阿里云 Binance 签名账户链路收口
  结果：服务器上的真实余额、真实订单和真实持仓都已经能读到
- [x] live 最小可卖出金额安全门
  结果：会在买入前拦住“扣费和步长取整后无法满足最小卖出额”的小仓位
- [ ] 真实 `DOGE` 平仓验收
  阻塞：`DOGE` 在 `1 USDT` 额度下会触发最小卖出额限制，需先提高到安全金额再做新闭环
- [x] Qlib 最小训练与推理闭环
- [x] 策略页接入研究分数与解释
- [ ] 补 Lean / vn.py 扩展目录与接口位
- [ ] 补 OpenClaw 非交易任务入口

## 文档计划入口

- [2026-04-02-platform-architecture-restoration-design.md](/home/djy/Quant/docs/superpowers/specs/2026-04-02-platform-architecture-restoration-design.md)
- [2026-04-02-freqtrade-real-integration-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-freqtrade-real-integration-implementation.md)
- [2026-04-02-qlib-minimal-research-layer-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-qlib-minimal-research-layer-implementation.md)
- [2026-04-02-platform-extension-slots-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-02-platform-extension-slots-implementation.md)

## 当前文档入口

- [README.md](/home/djy/Quant/README.md)：项目现状和运行方式
- [docs/architecture.md](/home/djy/Quant/docs/architecture.md)：模块职责和调用关系
- [docs/api.md](/home/djy/Quant/docs/api.md)：当前接口边界
- [docs/ops.md](/home/djy/Quant/docs/ops.md)：实际运行和验收方式
- [CONTEXT.md](/home/djy/Quant/CONTEXT.md)：给下个会话看的最轻量进度记录
