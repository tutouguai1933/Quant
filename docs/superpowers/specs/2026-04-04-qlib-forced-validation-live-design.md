# Qlib 强制验证 Live 设计

## 1. Summary
为本地验证新增一个临时“强制验证最佳候选”模式，在四个币都没通过研究筛选门时，仍然允许分数最高的一个继续进入 `dry-run -> 小额 live -> 复盘`，先把全流程真实跑通。

## 2. Goals / Non-goals

### Goals
- 在不拆掉原有研究筛选逻辑的前提下，增加一个临时强制验证模式。
- 强制模式下只放行当前最优的一个候选，不同时放行多个币。
- 统一研究报告、推荐结果、信号派发和复盘都要能看出“这是强制验证”。
- 保留现有 `live` 安全门：白名单、单笔上限、最大持仓数、显式允许 live。

### Non-goals
- 不长期关闭研究筛选门。
- 不修改现有正式研究门槛的默认阈值。
- 不扩展到多币轮动。

## 3. Current State & Constraints
- 当前本地 `Qlib -> 训练 -> 推理 -> 统一研究报告 -> 复盘` 能跑通，但会停在 `continue_research`。
- 当前四个币没有候选能通过研究筛选门，所以不会进入 `dry-run` 和 `live`。
- 真实 `live` 风险已经存在，因此不能绕开白名单、单笔金额和仓位限制。

## 4. Requirements

### Functional
- 增加环境开关，显式启用“强制验证最佳候选”模式。
- 当正常 `ready_count=0` 时，强制放行分数最高的一个候选。
- 强制放行后，这个候选要进入研究推荐、信号派发和复盘主链路。
- 报告里要能看见“forced_validation=true”以及原始失败原因。

### Non-functional
- 默认行为保持不变，未开启开关时，系统仍严格按原有研究门工作。
- 改动范围保持最小，优先复用现有候选排行、推荐和验证工作流。

## 5. Design
- 在 `qlib_ranking` 层增加一个显式开关：开启后，如果没有正常通过研究门的候选，则挑排序第一的一个候选做“强制验证通过”。
- 这个候选保留原始 `dry_run_gate` 失败信息，同时新增：
  - `forced_for_validation=true`
  - `forced_reason`
  - `next_action=enter_dry_run`
  - `review_status=forced_validation`
- 研究报告总览和复盘总览透出这个状态。
- 信号派发层允许这种“强制验证候选”进入执行链。

## 6. Acceptance Criteria
- 开启开关且四个币都未通过时，只会有一个候选被标记为可进入 `dry-run`。
- 统一研究报告会显示该候选被强制验证。
- 这条候选能进入派发，并可继续走 `dry-run -> live -> 复盘`。
- 未开启开关时，现有行为不变。

## 7. Validation Strategy
- Worker 测试：验证强制模式只放行一个最佳候选。
- API 测试：验证推荐结果和研究报告能正确标记 `forced_validation`。
- 本地真实验证：跑一轮 `Qlib -> 训练 -> 推理 -> 统一研究报告 -> dry-run -> live -> 复盘`。

## 8. Risks & Rollback
- 风险：把研究失败候选带入真实验证会提高交易风险。
- 约束：只允许在显式开关下启用，并保留现有 live 安全门。
- 回滚：关闭环境开关即可恢复原始行为。

## 9. Open Questions
- None

## 10. References
- [2026-04-03-qlib-screening-and-validation-implementation.md](../plans/2026-04-03-qlib-screening-and-validation-implementation.md)
