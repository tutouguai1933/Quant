# Quant Phase3 执行待办

这份文档只做一件事：

- 把 `Phase3` 的开发主线拆成可以连续执行和逐项打勾的待办

## 使用方式

- 当前主线按顺序推进，默认一项做完再做下一项
- 每项完成后必须同步：
  - 勾选当前任务
  - 更新 `CONTEXT.md`
  - 先做 code review，再做测试和真实页面联调
  - 按主题提交 git
- 默认优先使用 subagent 加速：
  - 一路负责后端与数据契约
  - 一路负责前端显化与 Playwright
  - 一路负责 review / 回归测试
  - 如果 reviewer 超时，由主 agent 补 review，不留空档

## A. 多模板研究与统一候选池

- [x] A1. 固定统一候选池与 `live` 子集契约
  - 目标：研究、评估、策略、自动化四处都读同一份候选池和 `live` 子集，不再各自解释
  - 重点后端：`services/api/app/services/workbench_config_service.py`、`services/api/app/services/evaluation_workspace_service.py`、`services/api/app/services/automation_service.py`
  - 重点前端：`apps/web/app/research/page.tsx`、`apps/web/app/evaluation/page.tsx`、`apps/web/app/strategies/page.tsx`
  - review 重点：统一候选池 key、候选列表、`live` 子集和页面说明是否还会漂
  - 测试重点：
    - 后端单测覆盖候选池一致性和空池兜底
    - Playwright 覆盖研究页、评估页、策略页的候选池展示一致
    - 真实页面检查候选池说明和 `live` 子集说明是否同步变化

- [x] A2. 把研究模板扩成真正可切换的多模板
  - 目标：研究页不再只是单一模板，而是能稳定切换 2-3 套研究模板，并记录到训练 / 推理产物
  - 重点后端：`services/api/app/services/research_service.py`、`services/api/app/routes/signals.py`
  - 重点前端：`apps/web/app/research/page.tsx`
  - review 重点：模板切换后，参数、标签、说明、训练产物里的模板字段是否一致
  - 测试重点：
    - 后端单测覆盖模板切换、模板缺省值和模板回退
    - Playwright 覆盖模板切换、刷新后保持、空态模板提示
    - 真实页面检查模板说明、参数区、训练入口是否跟着模板变化

- [x] A3. 给多模板结果补“模板适配解释”
  - 目标：每个候选不只显示分数，还要说明当前更适合哪套模板、为什么
  - 重点后端：`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`、`apps/web/app/signals/page.tsx`
  - review 重点：模板适配解释是否稳定、人话、和真实模板字段对齐
  - 测试重点：
    - 后端单测覆盖不同模板下的推荐解释和淘汰解释
    - Playwright 覆盖评估页模板说明区和信号页来源说明区
    - 真实页面检查模板适配解释是否跟当前候选一致

## B. 研究到执行仲裁层

- [x] B1. 新增研究到执行仲裁服务
  - 目标：把研究推荐、门控结果、执行状态、人工接管、长期运行窗口合成一份单一仲裁结论
  - 重点后端：`services/api/app/services/automation_workflow_service.py`、`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：无，先固定后端契约
  - review 重点：仲裁状态是否清楚区分“继续研究 / 进入 dry-run / 进入 live / 人工处理”
  - 测试重点：
    - 后端单测覆盖研究通过但执行未对齐、执行已对齐但研究过期、人工接管阻断、冷却窗口阻断
    - 契约测试覆盖仲裁结果字段和回退字段

- [x] B2. 把评估页升级成真正的仲裁决策中心
  - 目标：评估页直接回答“现在先推进哪一层、为什么、还差什么、下一步去哪”
  - 重点后端：`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`
  - review 重点：当前仲裁结论和历史记录是否分开，页面不会把旧结论当成当前结论
  - 测试重点：
    - Playwright 覆盖通过态、拒绝态、等待态、人工处理态
    - 真实页面检查“当前结论”和“历史记录”是否分区清楚

- [x] B3. 策略页和任务页统一承接仲裁动作
  - 目标：策略页、任务页不再各自猜下一步动作，而是统一承接仲裁层给出的动作建议
  - 重点后端：`services/api/app/services/automation_service.py`、`services/api/app/routes/tasks.py`
  - 重点前端：`apps/web/app/strategies/page.tsx`、`apps/web/app/tasks/page.tsx`
  - review 重点：页面动作按钮、禁用态、说明文案和仲裁结论是否一致
  - 测试重点：
    - Playwright 覆盖策略页、任务页在不同仲裁状态下的按钮变化
    - 真实页面检查“能不能点”“点了去哪里”“为什么不能点”

- [ ] B4. 把执行结果回填到研究与评估账本
  - 目标：执行订单、持仓、同步结果回填到研究 / 评估，让“研究推荐”和“执行落地”形成闭环
  - 重点后端：`services/api/app/services/sync_service.py`、`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`、`apps/web/app/strategies/page.tsx`
  - review 重点：回填后的状态能否区分“无结果 / 旧结果 / 当前轮结果”
  - 测试重点：
    - 后端单测覆盖执行成功、执行失败、同步失败、无执行动作
    - Playwright 覆盖评估页和策略页的研究 / 执行差异区
    - 真实页面检查最近订单、最近持仓和差异说明是否同步

## C. 自动化优先级、恢复与长期运行

- [ ] C1. 把多候选推进收成“优先级队列”
  - 目标：不再只看单一 top1，而是允许从统一候选池里挑出少数优先候选，按优先级推进
  - 重点后端：`services/api/app/services/automation_workflow_service.py`、`services/api/app/services/automation_service.py`
  - 重点前端：`apps/web/app/tasks/page.tsx`、`apps/web/app/strategies/page.tsx`
  - review 重点：优先级规则是否稳定，页面不会把候选顺序和执行顺序说反
  - 测试重点：
    - 后端单测覆盖多候选排序、跳过不可执行候选、候选耗尽
    - Playwright 覆盖任务页优先级摘要和策略页当前推进对象

- [ ] C2. 收紧恢复流程与人工接管入口
  - 目标：恢复动作不只看暂停与否，还要看当前仲裁状态、候选优先级和执行闭环是否收口
  - 重点后端：`services/api/app/services/automation_service.py`、`services/api/app/services/automation_workflow_service.py`
  - 重点前端：`apps/web/app/tasks/page.tsx`
  - review 重点：恢复动作、保持手动、切回 dry-run only、Kill Switch 四类动作是否边界清楚
  - 测试重点：
    - 后端单测覆盖恢复被拦住、允许恢复、仅允许 dry-run 恢复、保持手动
    - Playwright 覆盖任务页恢复入口在不同状态下的显隐和动作反馈
    - 真实页面检查告警、恢复建议、人工接管说明是否统一

- [ ] C3. 补一轮 Phase3 综合验收
  - 目标：在 `Phase3` 收口前做一次和这轮 `Phase1 / Phase2` 一样严格的总验收
  - 重点后端：`services/api/tests`
  - 重点前端：`apps/web/tests`
  - review 重点：子代理 review + 主 agent 复核，确认没有“测试通过但页面没过”的情况
  - 测试重点：
    - Python 全量单测
    - 前端生产构建
    - Playwright 全量回归
    - 真实页面联调至少覆盖：`/signals`、`/research`、`/evaluation`、`/strategies`、`/tasks`
    - 至少补一条“接口不可用”的异常链路验收

## 当前执行顺序

1. A1 固定统一候选池与 `live` 子集契约
2. A2 多模板研究入口
3. A3 模板适配解释
4. B1 仲裁服务
5. B2 决策中心
6. B3 页面动作统一承接
7. B4 执行结果回填
8. C1 多候选优先级
9. C2 恢复与人工接管
10. C3 综合验收

## 当前备注

- `Phase2` 已完成，所以 `Phase3` 不再重做原有 6 个工作台
- `Phase3` 的核心不是再堆页面，而是让“多模板研究 -> 仲裁 -> 执行 -> 恢复”真正闭环
- 当前默认推荐做法是：
  - 每个任务优先拆成后端、前端、review / test 三路 subagent
  - 每项完成后立刻做定向回归，不累计到最后一起爆
  - reviewer 超时就由主 agent 补 review，避免任务卡住
