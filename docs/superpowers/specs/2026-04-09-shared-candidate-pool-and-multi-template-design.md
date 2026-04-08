# 共享候选池与少量策略模板设计

## 1. Summary

把当前只围绕 `BTC / ETH / SOL / DOGE` 的单币研究与执行链，升级成“共享候选池 + 少量策略模板 + 单独 live 子集”的结构。

这样做的原因很直接：现在只有 4 个币时，`Qlib` 很容易一轮全淘汰；但如果把研究池和执行池完全分开，推荐币又会断在执行前。新的结构要同时解决“候选太少”和“推荐无法继续执行”这两个问题。

## 2. Goals / Non-goals

### Goals

- 让研究池扩大到一组高流动性 `USDT` 币，增加可筛选候选数量。
- 让研究池与 `dry-run` 候选池保持一致，避免研究推荐断在执行前。
- 让 `live` 保持更小的白名单子集，继续控制风险。
- 让前端显性展示：
  - 当前候选池
  - 当前 `live` 子集
  - 当前策略模板
  - 当前每轮只会推进的少数候选
- 让后端默认配置、工作台配置、评估页、策略页和任务页保持同一口径。

### Non-goals

- 这一轮不直接扩成“很多策略 × 很多币”的大矩阵。
- 这一轮不引入新的研究框架。
- 这一轮不放宽 `live` 风控。
- 这一轮不做新的交易所或新市场。

## 3. Current State & Constraints

### Current State

- 当前默认研究池和默认 `live` 允许币种都还是 `BTCUSDT / ETHUSDT / SOLUSDT / DOGEUSDT`。
- 当前工作台已经支持配置一部分研究参数，但“研究候选池”和“live 子集”还没有被明确拆开说明。
- 当前系统已经具备：
  - `Qlib` 训练、推理、筛选、评估、复盘
  - `Freqtrade` 的 `dry-run / live`
  - 自动化调度、告警、人工接管
  - 数据 / 特征 / 研究 / 回测 / 评估 / 执行与自动化工作台

### Constraints

- 仍然只做 `crypto + Binance + Freqtrade + Qlib`。
- 当前主线仍然是个人开发者、中低频、波段择时。
- `live` 必须继续保留严格白名单、单笔金额和最大持仓限制。
- 研究推荐出来的币，原则上至少要能继续走到 `dry-run`。
- 前端改动必须做真实页面验证和关键交互验证。

## 4. Requirements

### P0

- 定义一组默认“统一候选池”，同时用于研究和 `dry-run`。
- 定义一组默认“live 子集”，作为统一候选池的严格子集。
- 后端配置归一化时，必须保证 `live_allowed_symbols ⊆ selected_symbols`。
- 前端必须明确显示：
  - 研究 / `dry-run` 候选池
  - `live` 子集
  - 当前为什么只放行 `live` 子集
- 策略页、任务页、数据页、回退数据必须统一新口径。

### P1

- 让任务页和策略页明确解释：
  - 推荐币为什么可以继续 `dry-run`
  - 为什么某些币暂时不能继续 `live`
- 让自动化状态同时给出：
  - 研究候选池
  - `live` 子集
  - 当前执行安全门

### P2

- 后续在这组共享候选池上叠加 `2-3` 套策略模板，并在评估页比较不同模板在同一候选池上的表现。

## 5. Design

### Overall approach

采用“三层同心圆”的结构：

1. **统一候选池**
   - 用于训练、推理、排行和 `dry-run`
   - 默认扩大到 `8-12` 个高流动性 `USDT` 币

2. **live 子集**
   - 是统一候选池的严格子集
   - 只有通过更严格门控的币，才允许继续进入小额 `live`

3. **当前执行集合**
   - 每一轮只从候选里推进 `1-3` 个最优币
   - 真正 `live` 同时只保留更少的仓位

### Default pool choice

默认统一候选池：

- `BTCUSDT`
- `ETHUSDT`
- `BNBUSDT`
- `SOLUSDT`
- `XRPUSDT`
- `DOGEUSDT`
- `ADAUSDT`
- `LINKUSDT`
- `AVAXUSDT`
- `DOTUSDT`

默认 `live` 子集：

- `BTCUSDT`
- `ETHUSDT`
- `SOLUSDT`
- `XRPUSDT`
- `DOGEUSDT`

这样做的原因：

- 候选池足够大，减少“全淘汰”概率
- `live` 子集仍然集中在更熟、更稳、更容易成交的币

### Frontend exposure

前端需要显性回答三件事：

1. 当前研究到底从哪些币里挑
2. 当前哪些币允许进 `dry-run`
3. 当前哪些币允许进 `live`

其中：

- 数据工作台负责展示“研究候选池”
- 策略页负责展示“当前推荐候选”和“当前 `live` 子集”
- 任务页负责展示“执行安全门”和“当前自动化放行口径”
- 评估页负责解释“为什么推荐这个币、为什么它只到 `dry-run` 或可以继续 `live`”

### Alternatives

#### 方案 A：研究池和执行池完全相同

优点：
- 最简单
- 口径最统一

缺点：
- `live` 风险会跟着研究池一起放大

#### 方案 B：研究池和执行池完全分离

优点：
- 风险隔离最强

缺点：
- 推荐币可能断在执行前
- 当前项目阶段不适合

#### 方案 C：统一候选池 + 单独 live 子集

优点：
- 研究推荐不会断链
- `live` 风险还能继续收紧
- 最适合当前项目阶段

结论：
- 采用方案 C

## 6. Acceptance Criteria

- 默认研究候选池扩大到高流动性 `USDT` 币集合。
- 默认 `live` 子集是研究候选池的严格子集。
- `workbench_config` 在保存后会自动收敛到：
  - `selected_symbols` 为研究候选池
  - `live_allowed_symbols` 为其子集
- 前端数据页、策略页、任务页能直接看见：
  - 研究候选池
  - `live` 子集
  - 相关解释文案
- 研究推荐出来的币至少能继续进入 `dry-run` 候选链。
- 浏览器测试和真实页面验证通过，不出现样式丢失或交互断链。

## 7. Validation Strategy

- 后端配置归一化测试
- 自动化状态测试
- 策略工作台测试
- 前端源码测试
- 前端构建
- 浏览器测试
- 真实页面检查：
  - `/data`
  - `/strategies`
  - `/tasks`

## 8. Risks & Rollback

### Risks

- 扩大候选池后，研究结果可能变多，但质量不一定同步变好。
- 如果前端和 fallback 口径没一起改，会再次出现“页面说一套，后端配一套”。
- 如果 `live` 子集约束不严，真实交易风险会被放大。

### Rollback

- 可以回退到旧的 4 币默认集合。
- 也可以只保留新候选池文案，不放开默认配置。

## 9. Open Questions

- None

## 10. References

- [2026-04-06-research-to-execution-workbench-design.md](/home/djy/Quant/.worktrees/hardening-phase1/docs/superpowers/specs/2026-04-06-research-to-execution-workbench-design.md)
- [2026-04-06-research-to-execution-workbench-implementation.md](/home/djy/Quant/.worktrees/hardening-phase1/docs/superpowers/plans/2026-04-06-research-to-execution-workbench-implementation.md)
