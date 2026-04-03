# Decision-First Terminal UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把首页、信号页、单币页、策略页统一重构成决策优先的专业交易终端界面。

**Architecture:** 保留现有数据和接口，主要重构页面骨架、组件层级和样式规则。页面统一成“顶部摘要 + 双栏主区 + 下方次要信息”的结构，左侧负责决策与动作，右侧负责图表和上下文。

**Tech Stack:** Next.js App Router、现有 React 组件、现有控制平面 API

---

### Task 1: 统一顶层壳层和摘要条

**Files:**
- Modify: `apps/web/components/app-shell.tsx`
- Modify: `apps/web/app/globals.css`
- Test: `tests/test_frontend_refactor.py`

- [ ] 把 `AppShell` 调整成更适合终端布局的顶层结构。
- [ ] 增加统一摘要条、页面动作区和终端主区样式。
- [ ] 跑前端结构测试。

### Task 2: 重构首页为决策入口页

**Files:**
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/components/metric-grid.tsx`
- Test: `tests/test_frontend_refactor.py`

- [ ] 把首页从总览页改成决策入口页。
- [ ] 把推荐候选、执行状态、下一步动作收成一屏主结构。
- [ ] 跑相关页面测试。

### Task 3: 重构信号页为研究终端

**Files:**
- Modify: `apps/web/app/signals/page.tsx`
- Modify: `apps/web/components/research-candidate-board.tsx`
- Test: `tests/test_frontend_refactor.py`

- [ ] 把信号页改成左侧候选、右侧统一研究报告。
- [ ] 收紧回测摘要和失败原因的展示层级。
- [ ] 跑相关页面测试。

### Task 4: 重构单币页为左决策右主图

**Files:**
- Modify: `apps/web/app/market/[symbol]/page.tsx`
- Modify: `apps/web/components/market-symbol-workspace.tsx`
- Test: `tests/test_market_workspace.py`

- [ ] 把单币页改成左侧判断与动作、右侧图表主区。
- [ ] 保留 EMA、最近图表点和下一步动作，但改成更清晰的终端布局。
- [ ] 跑单币页相关测试。

### Task 5: 重构策略页为执行控制台

**Files:**
- Modify: `apps/web/app/strategies/page.tsx`
- Test: `tests/test_frontend_refactor.py`

- [ ] 把策略页改成左侧推荐执行、右侧执行器状态和操作。
- [ ] 减少解释性堆叠文案，让执行动作更直观。
- [ ] 跑策略页相关测试。

### Task 6: 做真实页面验证与收口

**Files:**
- Modify: `CONTEXT.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`

- [ ] 启动 `9011` 和 `9012`。
- [ ] 验证 `/`、`/signals`、`/market/BTCUSDT`、`/strategies`。
- [ ] 更新进度文档和设计说明。
- [ ] 提交 git。
