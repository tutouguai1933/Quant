# UI 统一终端风格实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 shadcn 卡片（`ui/card.tsx`）与终端卡片（`components/terminal/terminal-card.tsx`）混用导致的 UI 割裂，全部统一为终端风格。

**Architecture:** 项目已完成终端化改版（24 个页面骨架均为 TerminalShell/TerminalCard），但 19 个页面的部分子组件仍残留 shadcn 卡片（大圆角 rounded-2xl + 大阴影 + 半透明泛蓝背景）。本计划将 13 个混用组件改为 TerminalCard 外观，保留 shadcn 基础交互件（button/badge/tabs 等）。

**Tech Stack:** Next.js + TypeScript + Tailwind CSS。终端主题变量在 `apps/web/app/terminal-theme.css`（CSS 变量 `--terminal-*`）。验证用 Playwright（`apps/web/tests/`）。

**样式对照（替换时必须遵守）:**

| 样式 | shadcn Card（旧） | TerminalCard（新） |
|------|-------------------|--------------------|
| 圆角 | `rounded-2xl`(16px) | 8px（`.terminal-card` 自带） |
| 阴影/模糊 | `shadow-[0_24px_60px_rgba(0,0,0,0.28)] backdrop-blur` | 无（`.terminal-card` 自带） |
| 背景 | `bg-card/90` 半透明泛蓝 | `--terminal-panel`(#141a25) 实色 |
| 边框 | `border-border/70` | `1px solid var(--terminal-border)` |
| 标题 | `text-lg font-semibold` | `text-[14px] font-bold text-[var(--terminal-text)]` |
| 内容 padding | `p-5` | `p-4`（TerminalCard 自带） |
| 描述文字 | `text-muted-foreground` | `text-[var(--terminal-muted)]` |
| 成功色 | `emerald-500` | `var(--terminal-green)` |
| 警告色 | `amber-500` | `var(--terminal-yellow)` |
| 错误色 | `destructive/red-500` | `var(--terminal-red)` |

**通用替换模式（适用于所有任务）:**
1. 把 `import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./ui/card"` 换成 `import { TerminalCard } from "./terminal/terminal-card"`（路径按实际相对位置调整）
2. `<Card className="...">` → `<TerminalCard className="...">`；`</Card>` → `</TerminalCard>`
3. `<CardHeader>`+`<CardTitle>{x}</CardTitle>` → `title={x}` prop；`<CardDescription>{y}</CardDescription>` 移到内容区顶部，用 `text-xs text-[var(--terminal-muted)]`（可加 `mb-3` 间距）
4. `<CardContent>`/`<CardFooter>` 标签直接删除，内容留在 TerminalCard 内部
5. 状态色 class 映射见上表：如 `border-emerald-500/50 bg-emerald-500/10` → `border border-[var(--terminal-green)]/40 bg-[var(--terminal-green)]/10`（TerminalCard 外层加 className 追加即可，注意 `border` 要与 `.terminal-card` 的 border 共存，用 `!border` 或直接替换背景）
6. 内容区的内部布局 class（grid/flex/gap 等）一律保留不动
7. 保留 `"use client"` 指令和其余 import
8. 删除文件中不再使用的 import（避免 TS 报错：未使用的 import 在 Next 构建时警告不失败，但仍应清理）
9. 禁止改动 `components/ui/card.tsx`、`terminal-theme.css`、页面文件

**每个任务完成后验证（所有任务相同）:**
- 本地（WSL，`apps/web` 目录）: `npx tsc --noEmit` 通过（无类型错误）
- `npm run build` 成功（如构建耗时过长可仅跑 `npx tsc --noEmit` + 抽查相关页面代码，但最终总体验收必须 build）
- `git add -A && git commit -m "style: 统一 xxx 为终端风格"` 并 `git push`（推送各自分支或主分支，视协调方式）

---

### Task 1: 共用横幅组件（feedback-banner + loading-banner）

**Files:**
- Modify: `apps/web/components/feedback-banner.tsx`
- Modify: `apps/web/components/loading-banner.tsx`

影响 14 个页面（feedback）和 11 个页面（loading），两文件独立可并行内部处理。

- [ ] **Step 1: 改写 loading-banner.tsx**

```tsx
"use client";

import { Loader2 } from "lucide-react";

import { TerminalCard } from "./terminal/terminal-card";

export function LoadingBanner() {
  return (
    <TerminalCard className="border border-[var(--terminal-cyan)]/30 bg-[var(--terminal-cyan)]/10">
      <div className="flex items-center gap-2 text-sm text-[var(--terminal-cyan)]">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>正在加载数据...</span>
      </div>
    </TerminalCard>
  );
}
```

- [ ] **Step 2: 改写 feedback-banner.tsx**

```tsx
/* 这个文件负责统一展示操作成功、失败或提示信息。 */

import type { FeedbackState } from "../lib/feedback";

import { TerminalCard } from "./terminal/terminal-card";

type FeedbackBannerProps = {
  feedback: FeedbackState;
  fallbackTitle?: string;
};

/* 渲染反馈条。 */
export function FeedbackBanner({ feedback, fallbackTitle = "动作反馈" }: FeedbackBannerProps) {
  if (!feedback) {
    return null;
  }

  const toneClass =
    feedback.tone === "error"
      ? "border border-[var(--terminal-red)]/40 bg-[var(--terminal-red)]/10"
      : feedback.tone === "warning"
        ? "border border-[var(--terminal-yellow)]/40 bg-[var(--terminal-yellow)]/10"
        : "border border-[var(--terminal-green)]/40 bg-[var(--terminal-green)]/10";

  return (
    <TerminalCard title={fallbackTitle} className={toneClass}>
      <div className="space-y-1">
        <p className="text-sm font-medium text-[var(--terminal-text)]">{feedback.title}</p>
        <p className="text-sm text-[var(--terminal-muted)]">{feedback.message}</p>
      </div>
    </TerminalCard>
  );
}
```

- [ ] **Step 3: 验证**（见总则）：`npx tsc --noEmit` + `npm run build`
- [ ] **Step 4: 提交推送**

---

### Task 2: 首页 + 行情页组件（home-workbench-grid + page-hero + market-symbol-workspace）

**Files:**
- Modify: `apps/web/components/home-workbench-grid.tsx`（首页工作台 4 张摘要卡）
- Modify: `apps/web/components/page-hero.tsx`（行情页页头）
- Modify: `apps/web/components/market-symbol-workspace.tsx`（行情页 6 处内容卡）

- [ ] **Step 1: home-workbench-grid.tsx**——第 192 行附近 `<div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">` 改为 `<div className="terminal-card p-4">`（`.terminal-card` 提供 8px 圆角 + 边框 + 深色背景，注意外部原本的 className 冲突需合并）。其余卡片如有 Card 组件同样替换为 TerminalCard，标题/描述遵循对照表。
- [ ] **Step 2: page-hero.tsx**——`<Card className="overflow-hidden bg-card/90">` → `<TerminalCard title={...}>`；内部 CardHeader/CardContent 结构按对照表展开。
- [ ] **Step 3: market-symbol-workspace.tsx**——6 处 `<Card className="bg-card/80|92">` → `<TerminalCard>`；内容区有标题的用 title prop，无标题的直接展开；保持内部图表/行情布局 class 不动。
- [ ] **Step 4: 验证 + 提交**（同总则）

---

### Task 3: 信号 + 策略 + 任务页组件（research-candidate-board + arbitration-handoff-card + openclaw-action-confirm-dialog）

**Files:**
- Modify: `apps/web/components/research-candidate-board.tsx`（信号页候选排行榜，最大最复杂的组件）
- Modify: `apps/web/components/arbitration-handoff-card.tsx`（策略页 + 任务页人工接管卡）
- Modify: `apps/web/components/openclaw-action-confirm-dialog.tsx`（任务页动作确认弹窗）

- [ ] **Step 1: research-candidate-board.tsx**
  当前结构：`<Card>` 内含 CardHeader（eyebrow + CardTitle + CardDescription + Badge + 统计区 + 筛选 chips 区）+ CardContent（主候选区 + 列表）。
  替换：`<TerminalCard title={title}>`，`<p className="eyebrow">研究候选</p>` 删除（title 已含），`<CardDescription>{description}</CardDescription>` 移到内容区顶部 `text-xs text-[var(--terminal-muted)] mb-3`。内部两处 `rounded-2xl border border-border/70 bg-background/40 p-3` 筛选容器改为 `terminal-card p-3`（或 `border border-[var(--terminal-border)] bg-[var(--terminal-panel-deep)] p-3 rounded`）。Badge 保留（基础交互件）。列表行样式保留。
- [ ] **Step 2: arbitration-handoff-card.tsx**
  当前：`<Card className="border-emerald-500/25 bg-[color:var(--panel-strong)]/90">`。替换为 `<TerminalCard>`，标题用 title prop；内部结构按对照表；成功色 `border-emerald-500/25` → `border-[var(--terminal-green)]/25` 或直接去掉（终端卡片默认边框即可）。
- [ ] **Step 3: openclaw-action-confirm-dialog.tsx**
  当前：`<Card className="border-destructive/50">`。替换为 `<TerminalCard>`；错误色 → `var(--terminal-red)`；dialog 内部布局保留。
- [ ] **Step 4: 验证 + 提交**（同总则）

---

### Task 4: ops + analytics + data 页组件（alert-list + health-status-card + data-table + workbench-config-card + workbench-config-status-card）

**Files:**
- Modify: `apps/web/components/alert-list.tsx`（ops 页告警列表，2 处 Card）
- Modify: `apps/web/components/health-status-card.tsx`（ops 页健康状态，2 处 Card）
- Modify: `apps/web/components/data-table.tsx`（analytics 页表格，2 处 Card）
- Modify: `apps/web/components/workbench-config-card.tsx`（data 页配置卡）
- Modify: `apps/web/components/workbench-config-status-card.tsx`（data 页配置状态卡）

- [ ] **Step 1: alert-list.tsx**——2 处 Card → TerminalCard；告警级别颜色（如有 red/amber）→ `var(--terminal-red)` / `var(--terminal-yellow)`；列表行布局保留。
- [ ] **Step 2: health-status-card.tsx**——2 处 Card → TerminalCard；健康状态色（green/red）→ 终端绿/红；表格布局保留。
- [ ] **Step 3: data-table.tsx**——2 处 Card → TerminalCard；表头/行保留；分页器如为 shadcn 交互件保留。
- [ ] **Step 4: workbench-config-card.tsx + workbench-config-status-card.tsx**——Card → TerminalCard；配置表单/输入框保留。
- [ ] **Step 5: 验证 + 提交**（同总则）

---

### Task 5: 总体验收（所有任务完成后）

- [ ] **Step 1: 汇总构建验证**：`apps/web` 下 `npx tsc --noEmit` + `npm run build` 通过
- [ ] **Step 2: 页面回归**：本地起 dev server 或用构建产物，人工/截图检查 9 个页面（首页、行情页、信号页、策略中心、任务页、ops、analytics、data、含横幅的任一页面），确认无 shadcn 大圆角/大阴影卡片残留、无布局错乱、无报错
- [ ] **Step 3: Playwright 冒烟**：`npm run test:ui`（如现有用例与改动无冲突）
- [ ] **Step 4: 部署**：`git add -A && git commit -m "style: 全部卡片统一终端风格" && git push`；SSH 服务器 `cd ~/Quant && git pull && cd infra/deploy && docker compose build web && docker compose up -d --no-deps web`
- [ ] **Step 5: 线上验证**：访问 http://39.106.11.65:9012 检查上述页面，确认样式统一；`docker logs quant-web --tail 20` 无报错

---

## 注意事项

- 禁止修改 `apps/web/components/ui/card.tsx`（它是 shadcn 基础件，其他未终端化的页面可能仍用；但本计划范围内页面都改完后可评估删除）
- 禁止修改页面文件（`apps/web/app/**/page.tsx`）——本计划只改组件
- `apps/web/app/page-original.tsx` 是历史备份，不用管
- TerminalCard 的 `title` prop 为空字符串 `""` 时不渲染头部，可用来表示无标题卡片
- 每个组件文件的顶部注释（中文）保留，替换后更新说明（如"终端风格卡片"）
- 所有代码注释用中文
