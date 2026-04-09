# Quant Phase2 执行待办

这份文档只做一件事：

- 把当前 `phase2` 到下一段 `phase3` 入口前的开发任务，拆成可以连续执行和逐项打勾的待办

## 使用方式

- 当前主线按顺序推进
- 默认一项做完再做下一项
- 每项完成后必须同步：
  - 勾选当前任务
  - 更新 `CONTEXT.md`
  - 补测试
  - 做 review
  - 按主题提交 git

## A. Phase2 收口：先把工作台补成真正可配置

- [x] A1. 补完整标签方式与标签参数
  - 目标：研究页不再只有少量标签模式，而是能完整看到标签预设、触发口径、窗口参数和解释
  - 重点页面：`/research`
  - 重点后端：`services/api/app/services/workbench_config_service.py`
  - 重点前端：`apps/web/app/research/page.tsx`

- [x] A2. 补完整模型选择与模型说明
  - 目标：研究页能直接切模型，并看懂每个模型适合什么市场状态
  - 重点页面：`/research`
  - 重点后端：`services/api/app/services/workbench_config_service.py`
  - 重点前端：`apps/web/app/research/page.tsx`

- [x] A3. 补更细的因子配置
  - 目标：特征页不只看预设，还能更细地调主因子、辅助因子、分组和预处理规则
  - 重点页面：`/features`
  - 重点后端：`services/api/app/services/workbench_config_service.py`
  - 重点前端：`apps/web/app/features/page.tsx`

- [ ] A4. 补更完整的回测成本与过滤参数
  - 目标：回测页能完整调手续费、滑点、成本模型、过滤门和关键限制
  - 重点页面：`/backtest`
  - 重点后端：`services/api/app/services/workbench_config_service.py`
  - 重点前端：`apps/web/app/backtest/page.tsx`

- [ ] A5. 补完整 `dry-run / live` 准入门槛
  - 目标：评估页把 `dry-run`、验证、一致性、`live` 的准入门槛补全
  - 重点页面：`/evaluation`
  - 重点后端：`services/api/app/services/workbench_config_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`

## B. 决策中心：再把研究结果做成真正的判断入口

- [ ] B1. 支持更方便的多实验并排比较
  - 目标：评估页能更直接对比两轮或多轮实验，不用手工来回切
  - 重点页面：`/evaluation`
  - 重点后端：`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`

- [ ] B2. 把推荐原因压成稳定结论
  - 目标：评估页和策略页能更稳定地说明“为什么推荐这个币”
  - 重点页面：`/evaluation`、`/strategies`
  - 重点后端：`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`

- [ ] B3. 把淘汰原因压成稳定结论
  - 目标：评估页能明确看到每个候选是卡在规则门、验证门、回测门还是一致性门
  - 重点页面：`/evaluation`
  - 重点后端：`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`

- [ ] B4. 把研究结果和执行结果差异压成统一口径
  - 目标：评估页、任务页、策略页都能用一致术语解释研究 / 回测 / 执行差异
  - 重点页面：`/evaluation`、`/tasks`、`/strategies`
  - 重点后端：`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`

- [ ] B5. 更容易判断哪轮实验值得继续进入 `dry-run / live`
  - 目标：决策入口更清楚，不再只靠单个分数判断下一步
  - 重点页面：`/evaluation`、`/strategies`
  - 重点后端：`services/api/app/services/evaluation_workspace_service.py`
  - 重点前端：`apps/web/app/evaluation/page.tsx`

## C. 长期运行收口：最后把自动化和人工接管继续收紧

- [ ] C1. 告警变得更直白
  - 目标：任务页把告警收成“现在发生了什么 / 你该做什么”
  - 重点页面：`/tasks`
  - 重点后端：`services/api/app/services/automation_service.py`
  - 重点前端：`apps/web/app/tasks/page.tsx`

- [ ] C2. 调度和恢复流程更稳
  - 目标：任务页能更清楚看出当前在等什么、下一步什么时候跑、为什么不能恢复
  - 重点页面：`/tasks`
  - 重点后端：`services/api/app/services/automation_workflow_service.py`
  - 重点前端：`apps/web/app/tasks/page.tsx`

- [ ] C3. 人工接管更顺手
  - 目标：任务页和策略页都能更容易找到恢复、暂停、保持手动的入口
  - 重点页面：`/tasks`、`/strategies`
  - 重点后端：`services/api/app/services/automation_service.py`
  - 重点前端：`apps/web/app/tasks/page.tsx`

- [ ] C4. 长期运行摘要更清楚
  - 目标：任务页能更稳定地看懂周期数、失败趋势、恢复窗口和健康结论
  - 重点页面：`/tasks`
  - 重点后端：`services/api/app/services/automation_service.py`
  - 重点前端：`apps/web/app/tasks/page.tsx`

## 当前执行顺序

1. A4
2. A5
3. B1
4. B2
5. B3
6. B4
7. B5
8. C1
9. C2
10. C3
11. C4

## 当前备注

- 当前主链已经通了，所以这轮不再重做执行链
- 这轮重点是把研究平台补成“更完整可配置 + 更容易判断 + 更稳长期运行”
- A1 / A2 已完成：研究页现在会显式说明当前研究组合、模板目录、模型说明和标签口径，并已做后端单测、生产构建、真实页面验收和 Playwright 回归
- A3 已完成：特征页现在会显式说明当前因子组合、类别目录、预处理与周期摘要；即使研究协议暂时缺失，也会回退到默认因子协议继续把配置讲清楚
