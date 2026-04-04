# 自动化运维与自动买卖设计

## 1. Summary

为 `Quant` 增加一条可控的自动化主线：先自动化运维，再自动化 `dry-run`，最后在硬风控下放开小额 `live`。

这样做的目的是把当前已经能手动跑通的 `Qlib -> Freqtrade` 链路，变成一套可定时、可告警、可复盘、可人工接管的稳定工作流。

## 2. Goals / Non-goals

### Goals

- 建立统一的自动化工作流：训练、推理、筛选、`dry-run`、小额 `live`。
- 明确自动化运维和自动买卖的边界，不让任何任务绕过控制平面直接下单。
- 引入统一调度、告警、停机和人工接管机制。
- 把自动化动作沉淀成可追踪的任务、审计和复盘记录。
- 先支持 `Binance + Freqtrade + Qlib` 主链，保持与当前系统一致。

### Non-goals

- 不在这一阶段接入 `Lean / vn.py`。
- 不在这一阶段实现多币轮动和多市场自动交易。
- 不在这一阶段追求完全无人值守的高频系统。
- 不在这一阶段引入新的研究框架替代 `Qlib`。

## 3. Current State & Constraints

### Current State

- 当前系统已经能手动完成 `Qlib -> 筛选 -> dry-run -> 小额 live -> 复盘`。
- `Freqtrade` 已完成真实 `Spot`、`dry-run` 和小额 `live` 验证。
- `Qlib` 已完成最小训练、推理、候选排行、研究报告和复盘摘要。
- 控制平面已经具备任务、风险、执行状态和人工操作页面。

关键文件：

- [CONTEXT.md](/home/djy/Quant/CONTEXT.md)
- [plan.md](/home/djy/Quant/plan.md)
- [docs/architecture.md](/home/djy/Quant/docs/architecture.md)
- [docs/ops-qlib.md](/home/djy/Quant/docs/ops-qlib.md)
- [docs/ops-freqtrade.md](/home/djy/Quant/docs/ops-freqtrade.md)

### Constraints

- 当前主链仍然只做 `crypto + Binance + Freqtrade + Qlib`。
- 本地开发以 `WSL` 为主，真实验证和最终部署以阿里云为主。
- 端口继续统一遵循 `/home/djy/.port-registry.yaml`。
- 自动化动作必须保留人工暂停和人工接管能力。
- 真实交易仍要保留现有硬安全门：
  - 白名单
  - 单笔金额上限
  - 最大持仓数
  - `live` 显式开关

## 4. Requirements

### P0

- 提供统一的自动化任务编排入口。
- 支持定时训练、定时推理、定时同步、定时复盘。
- 支持“研究通过后自动进入 `dry-run`”。
- 支持“`dry-run` 通过后，在硬风控下自动进入小额 `live`”。
- 提供全局停机开关、自动化开关和人工接管入口。
- 所有自动化动作都要留下任务记录、执行结果和复盘记录。

### P1

- 提供统一告警出口，至少覆盖训练失败、推理失败、执行失败、同步失败、风控停机。
- 提供自动化健康摘要，回答“今天有没有训练、有没有推理、有没有停机、有没有失败”。
- 提供按阶段的自动化策略：
  - 仅自动化运维
  - 自动 `dry-run`
  - 自动小额 `live`

### P2

- 提供自动化日报和阶段性归档。
- 提供策略级别和币种级别的自动化开关。

### Non-functional

- 自动化默认宁可不做，也不能误做。
- 任何真实下单动作都必须在审计里能追溯到：
  - 哪次训练
  - 哪次推理
  - 哪个候选
  - 哪次风控判断
- 自动化失败必须有明确错误提示，不能静默失败。

## 5. Design

### Overall approach

按三层自动化来做：

1. 自动化运维层  
   负责训练、推理、同步、复盘、告警、归档。
2. 自动化验证层  
   负责研究候选自动进入 `dry-run`，并收集验证结果。
3. 自动化交易层  
   负责在硬风控下自动执行小额 `live`。

控制平面仍然是统一入口：

`Qlib -> 研究候选 -> 控制平面筛选与风控 -> Freqtrade -> 同步与复盘 -> 告警/人工接管`

### Key decisions

- 先自动化运维，再自动化交易，不直接走全自动无人值守。
- `OpenClaw` 后续定位为运维代理层，但第一版自动化先在当前控制平面内落地。
- 自动化执行永远不能绕过当前的 `live` 安全门。
- 自动化的默认模式应是：
  - 训练和推理自动
  - `dry-run` 自动
  - `live` 小额且可随时停机

### Alternatives

方案 A：先只做自动化运维，不自动下单。

- 优点：风险最低。
- 缺点：无法形成真正的自动验证闭环。

方案 B：直接做全自动交易。

- 优点：最省人工。
- 缺点：当前项目阶段风险过高，且难以定位问题。

最终选择：

- 采用分阶段方案，先做运维自动化，再做自动 `dry-run`，最后做小额自动 `live`。

### Impact scope

- `services/api/app/tasks/`
- `services/api/app/services/`
- `services/api/app/routes/`
- `services/worker/`
- `apps/web/`
- `docs/ops-qlib.md`
- `docs/ops-freqtrade.md`

## 6. Acceptance Criteria

- 能在系统中看到自动化模式：手动、自动 `dry-run`、自动小额 `live`。
- 能定时执行训练、推理、同步和复盘，并在任务页看到结果。
- 研究候选通过筛选后，系统能自动进入 `dry-run`。
- `dry-run` 通过后，系统能在不突破现有安全门的前提下自动进入小额 `live`。
- 任意阶段失败后，系统会生成清晰的任务记录和错误原因。
- 用户可以在页面上一键暂停自动化、切回手动。
- 真实交易记录可以追溯到研究和风控来源。

## 7. Validation Strategy

- 文档校验：确认 spec、plan、`CONTEXT.md`、`plan.md` 一致。
- API 测试：校验自动化任务、状态、复盘和停机逻辑。
- Worker 测试：校验训练、推理、筛选与自动化门控。
- 页面验证：确认自动化状态、下一步动作、停机入口和任务结果可见。
- 手工验证：
  - 自动训练
  - 自动推理
  - 自动 `dry-run`
  - 小额 `live`
  - 自动复盘

## 8. Risks & Rollback

### Risks

- 自动化误触发真实交易。
- 自动化任务串行关系不清，导致重复执行。
- 研究结果不稳定时，自动化把低质量候选推入 `dry-run / live`。
- 自动化失败没有及时暴露，影响长期运行。

### Rollback

- 保留手动模式作为默认回退。
- 保留全局自动化停机开关。
- 保留 `live` 显式允许开关。
- 任意阶段发现异常时，可退回到“只自动训练和推理”的最低自动化模式。

## 9. Open Questions

- 第一版自动化告警先接哪个出口，当前未定。
- `OpenClaw` 何时正式接入自动化入口，当前未定。

## 10. References

- [2026-04-03-qlib-screening-and-validation-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-03-qlib-screening-and-validation-implementation.md)
- [2026-04-04-qlib-data-replay-hardening-implementation.md](/home/djy/Quant/docs/superpowers/plans/2026-04-04-qlib-data-replay-hardening-implementation.md)
- [README.md](/home/djy/Quant/README.md)
- [CONTEXT.md](/home/djy/Quant/CONTEXT.md)
