# 共享候选池与少量策略模板实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把研究池扩成统一候选池，同时把 `live` 收成更小的子集，并在页面上把这套关系讲清楚。

**Architecture:** 后端统一从工作台配置中心给出“研究 / dry-run 候选池”和“live 子集”，前端数据页、策略页、任务页、评估页都复用这一套口径，不再各写一份默认币种。研究推荐出来的币至少能继续走到 `dry-run`，`live` 仍由更严门控控制。

**Tech Stack:** Python API、Next.js 前端、Qlib 研究链、Freqtrade 执行链、Playwright 浏览器验证

---

### Todo

- [x] Task 1：默认币池改成“统一候选池 + live 子集”
- [x] Task 2：配置归一化保证 `live_allowed_symbols ⊆ selected_symbols`
- [x] Task 3：自动化状态和策略工作台显性展示候选池 / live 子集
- [x] Task 4：前端 fallback 与页面说明统一新口径
- [x] Task 5：评估页补“研究候选池 / live 子集 / 当前推荐”解释
- [x] Task 6：完整验证、更新进度文档并提交推送

### Task 1：默认币池改成“统一候选池 + live 子集”

**Files:**
- Modify: `services/api/app/core/settings.py`
- Modify: `services/api/app/services/strategy_catalog.py`
- Test: `services/api/tests/test_settings.py`
- Test: `services/api/tests/test_strategy_workspace_service.py`

- [x] 写测试，锁住新的默认候选池和默认 `live` 子集
- [x] 修改后端默认常量：
  - 统一候选池：`BTC / ETH / BNB / SOL / XRP / DOGE / ADA / LINK / AVAX / DOT`
  - `live` 子集：`BTC / ETH / SOL / XRP / DOGE`
- [x] 保证策略目录默认白名单同步更新
- [x] 跑定向测试并确认通过
- [x] 提交

### Task 2：配置归一化保证 `live_allowed_symbols ⊆ selected_symbols`

**Files:**
- Modify: `services/api/app/services/workbench_config_service.py`
- Test: `services/api/tests/test_workbench_config_service.py`

- [x] 写失败测试：
  - 当 `selected_symbols` 缩小后，`live_allowed_symbols` 会自动收敛成其子集
  - 当 `live_allowed_symbols` 为空或非法时，回退到默认 `live` 子集与候选池交集
- [x] 修改配置归一化逻辑
- [x] 跑定向测试并确认通过
- [x] 提交

### Task 3：自动化状态和策略工作台显性展示候选池 / live 子集

**Files:**
- Modify: `services/api/app/services/automation_service.py`
- Modify: `services/api/app/services/strategy_workspace_service.py`
- Test: `services/api/tests/test_automation_service.py`
- Test: `services/api/tests/test_api_skeleton.py`

- [x] 写失败测试，锁住自动化状态和策略摘要里同时包含候选池与 `live` 子集
- [x] 修改后端输出：
  - `candidate_symbols`
  - `live_allowed_symbols`
  - `candidate_pool_summary`
- [x] 跑定向测试并确认通过
- [x] 提交

### Task 4：前端 fallback 与页面说明统一新口径

**Files:**
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/data/page.tsx`
- Modify: `apps/web/app/strategies/page.tsx`
- Modify: `apps/web/app/tasks/page.tsx`
- Test: `tests/test_data_workspace.py`
- Test: `tests/test_tasks_workspace.py`
- Test: `tests/test_frontend_refactor.py`

- [x] 写失败测试，锁住页面和 fallback 文案中的“候选池 / live 子集”说明
- [x] 修改前端 fallback 默认币池
- [x] 修改数据页、策略页、任务页说明与选项来源
- [x] 跑源码测试并确认通过
- [x] 提交

### Task 5：评估页补“研究候选池 / live 子集 / 当前推荐”解释

**Files:**
- Modify: `apps/web/app/evaluation/page.tsx`
- Test: `tests/test_evaluation_workspace.py`
- Test: `apps/web/tests/ui-automation-panels.spec.cjs`

- [x] 写失败测试，锁住评估页对候选池、`live` 子集和当前推荐关系的说明
- [x] 修改评估页展示：
  - 当前研究候选池
  - 当前 `live` 子集
  - 当前推荐候选
  - 推荐到 `dry-run` / `live` 的原因
- [x] 跑前端测试并确认通过
- [x] 提交

### Task 6：完整验证、更新进度文档并提交推送

**Files:**
- Modify: `CONTEXT.md`
- Modify: `docs/superpowers/plans/2026-04-06-research-to-execution-workbench-implementation.md`
- Optional: `README.md`

- [x] 跑后端测试
- [x] 跑前端源码测试
- [x] 跑前端构建
- [x] 跑 Playwright 浏览器测试
- [x] 重启本地 `9021/9022`
- [x] 真实检查：
  - `/data`
  - `/strategies`
  - `/evaluation`
  - `/tasks`
- [x] 更新 `CONTEXT.md`
- [x] 在旧实施计划里补勾选进度
- [ ] 提交并推送
