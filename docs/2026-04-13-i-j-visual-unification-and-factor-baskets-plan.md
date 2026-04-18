# I + J 视觉统一与多因子主线补强实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一前端摘要卡、抽屉、反馈口径，并把 `/features -> /evaluation -> /strategies` 串成“因子挖掘 -> 因子验证 -> 去冗余 -> 候选篮子 -> 执行篮子”的清晰主线。

**Architecture:** 先在共享展示层统一卡片、抽屉和状态文案，再以 `/features` 为主入口显化主线，最后把 `/evaluation` 与 `/strategies` 的旧术语统一映射成“候选篮子 / 执行篮子”，并在首页补最短承接入口。后端接口字段保持不动，所有改动先限制在前端展示层和页面测试。

**Tech Stack:** Next.js App Router、React Server Components、现有 `SummaryCard` / `DetailDrawer` 组件体系、Playwright 定向 UI 回归。

---

## 文件结构与责任

- `apps/web/components/summary-card.tsx`
  统一摘要卡视觉层级、按钮区与页脚信息密度。
- `apps/web/components/detail-drawer.tsx`
  统一抽屉标题、关闭按钮、底部说明和主体留白。
- `apps/web/components/features-primary-action-section.tsx`
  因子页主动作区，补主线表达和跨页承接入口。
- `apps/web/components/features-focus-grid.tsx`
  因子页摘要卡，挂到“多因子主线”上。
- `apps/web/app/features/page.tsx`
  组装因子主线带、因子摘要与跨页术语。
- `apps/web/app/evaluation/page.tsx`
  把“候选池 / live 子集”统一映射为“候选篮子 / 执行篮子”。
- `apps/web/components/evaluation-decision-center.tsx`
  统一评估页顶部视觉层级，并显化“候选篮子”承接。
- `apps/web/components/evaluation-focus-grid.tsx`
  统一评估摘要卡表达。
- `apps/web/app/strategies/page.tsx`
  把执行页首屏和抽屉改成“候选篮子 / 执行篮子”表达。
- `apps/web/components/strategies-focus-grid.tsx`
  统一执行摘要卡结构和抽屉命名。
- `apps/web/app/page.tsx`
  首页只补最短主线入口与篮子状态提示。
- `apps/web/tests/ui-features-workbench.spec.cjs`
  因子页主线带与抽屉承接回归。
- `apps/web/tests/ui-evaluation-decision-center.spec.cjs`
  评估页候选篮子表达回归。
- `apps/web/tests/ui-strategies-workbench.spec.cjs`
  执行页执行篮子表达回归。
- `apps/web/tests/ui-home-workbench.spec.cjs`
  首页最短入口和主线提示回归。
- `CONTEXT.md`
  记录 I/J 的阶段进展和验证结果。

## Task 1: 先写红灯测试，锁定 I/J 的用户可见结果

**Files:**
- Modify: `apps/web/tests/ui-features-workbench.spec.cjs`
- Modify: `apps/web/tests/ui-evaluation-decision-center.spec.cjs`
- Modify: `apps/web/tests/ui-strategies-workbench.spec.cjs`
- Modify: `apps/web/tests/ui-home-workbench.spec.cjs`

- [ ] **Step 1: 在因子页测试里增加“五步主线”断言**

预期新增断言：

```javascript
await expect(page.getByText("因子挖掘")).toBeVisible();
await expect(page.getByText("因子验证")).toBeVisible();
await expect(page.getByText("去冗余")).toBeVisible();
await expect(page.getByText("候选篮子")).toBeVisible();
await expect(page.getByText("执行篮子")).toBeVisible();
```

- [ ] **Step 2: 运行因子页测试，确认因主线文案缺失而失败**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-features-workbench.spec.cjs
```

Expected:

- 至少 1 条失败
- 失败点明确指向主线文案不存在，而不是服务未启动

- [ ] **Step 3: 在评估页测试里增加“候选篮子 / 执行篮子”断言**

预期新增断言：

```javascript
await expect(page.locator("body")).toContainText("候选篮子");
await expect(page.locator("body")).toContainText("执行篮子");
```

- [ ] **Step 4: 运行评估页测试，确认旧术语导致失败**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-evaluation-decision-center.spec.cjs
```

Expected:

- 至少 1 条失败
- 失败点明确指向旧文案仍是“候选池 / live 子集”

- [ ] **Step 5: 在执行页和首页测试里补最短入口断言**

预期新增断言：

```javascript
await expect(page.locator("body")).toContainText("执行篮子");
await expect(page.locator("body")).toContainText("候选篮子");
await expect(page.locator("body")).toContainText("当前主线");
```

- [ ] **Step 6: 运行执行页与首页测试，确认旧文案和入口表达失败**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-strategies-workbench.spec.cjs tests/ui-home-workbench.spec.cjs
```

Expected:

- 至少 1 条失败
- 失败点明确指向术语或入口文案缺失

## Task 2: 统一共享视觉层，收紧摘要卡和抽屉节奏

**Files:**
- Modify: `apps/web/components/summary-card.tsx`
- Modify: `apps/web/components/detail-drawer.tsx`

- [ ] **Step 1: 调整摘要卡结构，让标题、摘要、动作和页脚层级更清楚**

改动目标：

- 标题区与状态区对齐
- `summary` 与 `detail` 的留白更稳定
- `actions` 与 `footer` 不再挤在一起

- [ ] **Step 2: 运行相关页面测试，确认没有破坏已有抽屉交互**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-home-primary-actions.spec.cjs tests/ui-tool-detail-pages.spec.cjs
```

Expected:

- 相关用例继续通过

- [ ] **Step 3: 调整抽屉结构，让标题、说明、主体、底部说明统一**

改动目标：

- 关闭按钮和标题区对齐
- 抽屉主体滚动区留白更一致
- 统一底部说明层级

- [ ] **Step 4: 重新运行同组测试，确认共享层改动仍为绿色**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-home-primary-actions.spec.cjs tests/ui-tool-detail-pages.spec.cjs
```

Expected:

- 全部通过

## Task 3: 在 `/features` 显化多因子主线，并补篮子去向说明

**Files:**
- Modify: `apps/web/components/features-primary-action-section.tsx`
- Modify: `apps/web/components/features-focus-grid.tsx`
- Modify: `apps/web/app/features/page.tsx`

- [ ] **Step 1: 在因子页组装“五步主线带”数据**

改动目标：

- 从现有分类、有效性、冗余、总分解释数据里组装五步
- 不新增后端依赖
- 不把因子页重新做成长表页面

- [ ] **Step 2: 在 `features-focus-grid` 或相邻区块里渲染主线带**

主线固定为：

```text
因子挖掘 -> 因子验证 -> 去冗余 -> 候选篮子 -> 执行篮子
```

每一步要有一句当前说明。

- [ ] **Step 3: 在因子主动作区的研究承接抽屉里补“候选篮子 / 执行篮子”去向说明**

改动目标：

- 明确因子页结果如何流向 `/evaluation`
- 明确执行篮子如何流向 `/strategies`

- [ ] **Step 4: 运行因子页测试，确认主线文案与抽屉承接都通过**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-features-workbench.spec.cjs
```

Expected:

- 全部通过

## Task 4: 在 `/evaluation` 统一成“候选篮子”表达

**Files:**
- Modify: `apps/web/app/evaluation/page.tsx`
- Modify: `apps/web/components/evaluation-decision-center.tsx`
- Modify: `apps/web/components/evaluation-focus-grid.tsx`

- [ ] **Step 1: 建立前端术语映射，把旧字段展示成新术语**

改动目标：

- 页面标题、摘要、抽屉说明统一使用“候选篮子 / 执行篮子”
- 不改接口字段名

- [ ] **Step 2: 在评估摘要和抽屉里说清楚四件事**

需要直接可见：

- 当前候选篮子里有哪些标的
- 为什么它们被保留
- 为什么有些标的被淘汰
- 执行篮子如何从候选篮子继续缩出来

- [ ] **Step 3: 运行评估页测试，确认新术语和新承接通过**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-evaluation-decision-center.spec.cjs
```

Expected:

- 全部通过

## Task 5: 在 `/strategies` 统一成“执行篮子”表达

**Files:**
- Modify: `apps/web/app/strategies/page.tsx`
- Modify: `apps/web/components/strategies-focus-grid.tsx`

- [ ] **Step 1: 把“候选池详情”统一改成“候选篮子详情”**

改动目标：

- 首屏摘要、抽屉标题、抽屉说明统一替换
- 保留现有数据结构和按钮路径

- [ ] **Step 2: 把 `live 子集` 统一改成“执行篮子”**

改动目标：

- 首屏能直接看懂“上游候选篮子”和“当前执行篮子”
- 执行器只对执行篮子负责

- [ ] **Step 3: 运行执行页测试，确认执行篮子表达通过**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-strategies-workbench.spec.cjs
```

Expected:

- 全部通过

## Task 6: 首页只补最短主线入口，不扩页

**Files:**
- Modify: `apps/web/app/page.tsx`

- [ ] **Step 1: 在首页推荐/下一步相关卡片里补“当前主线走到哪一步”的一句话**

改动目标：

- 首页只负责提示主线位置
- 不重复因子页与评估页的大段说明

- [ ] **Step 2: 把首页入口稳定落到 `/features`、`/evaluation`、`/strategies`**

改动目标：

- 用户能从首页直接进入主线当前页面
- 文案与“候选篮子 / 执行篮子”保持一致

- [ ] **Step 3: 运行首页测试，确认最短入口通过**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test tests/ui-home-workbench.spec.cjs tests/ui-home-primary-actions.spec.cjs
```

Expected:

- 全部通过

## Task 7: 综合验证与文档同步

**Files:**
- Modify: `CONTEXT.md`
- Optionally modify: `README.md`
- Optionally modify: `docs/roadmap.md`

- [ ] **Step 1: 运行 I/J 相关定向回归**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm exec playwright test \
  tests/ui-features-workbench.spec.cjs \
  tests/ui-evaluation-decision-center.spec.cjs \
  tests/ui-strategies-workbench.spec.cjs \
  tests/ui-home-workbench.spec.cjs \
  tests/ui-home-primary-actions.spec.cjs
```

Expected:

- 全部通过

- [ ] **Step 2: 运行前端构建**

Run:

```bash
cd /home/djy/Quant/apps/web
pnpm build
```

Expected:

- 构建通过

- [ ] **Step 3: 更新 `CONTEXT.md`**

需要同步：

- I/J 当前做到哪一步
- 最近验证结果
- 下一步是否进入 K 综合验收

- [ ] **Step 4: 必要时更新入口文档**

仅在这些信息发生变化时更新：

- `README.md`
- `docs/roadmap.md`

- [ ] **Step 5: 检查工作区，不回退其他人的改动**

Run:

```bash
git -C /home/djy/Quant status --short
```

Expected:

- 只新增本轮需要的改动
- 不误删、不误回退他人内容
