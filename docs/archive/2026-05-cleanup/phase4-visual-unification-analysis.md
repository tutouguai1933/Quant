# 前端视觉和交互统一需求分析报告

## 1. 当前各组件样式差异清单

### 1.1 卡片组件样式差异

| 组件 | 文件路径 | 阴影 | 边框 | 背景 | 问题 |
|------|---------|------|------|------|------|
| Card (基础) | `/apps/web/components/ui/card.tsx` | `shadow-[0_24px_60px_rgba(0,0,0,0.28)]` | `border-border/70` | `bg-card/95` | 作为基础组件，样式较重 |
| SummaryCard | `/apps/web/components/summary-card.tsx` | `shadow-[0_18px_40px_rgba(2,6,23,0.18)]` | `border-border/70` | `bg-card/92` | 阴影更浅，与基础不一致 |
| DetailDrawer | `/apps/web/components/detail-drawer.tsx` | `shadow-[-24px_0_60px_rgba(2,6,23,0.45)]` | `border-border/70` | `bg-card/98` | 阴影方向不同，背景更重 |
| DetailDialog | `/apps/web/components/detail-dialog.tsx` | `shadow-[0_24px_80px_rgba(2,6,23,0.45)]` | `border-border/70` | `bg-card/95` | 阴影强度不同 |
| PageHero | `/apps/web/components/page-hero.tsx` | 继承 Card | 继承 Card | `bg-card/90` | 自定义背景透明度 |

**问题总结**：
- 阴影值使用了不同的 rgba 颜色基准
- 背景透明度散落在 `/90`, `/92`, `/95`, `/98` 四档
- 部分组件在调用基础 Card 时又重新定义了 `className`

### 1.2 状态徽章组件重复定义问题

**问题**：`status-bar.tsx` 内部定义了独立的 `StatusBadge` 组件，但项目中已有独立的 `status-badge.tsx` 组件。

### 1.3 反馈组件样式不统一

| 组件 | 使用的容器 | 问题 |
|------|------------|------|
| FeedbackBanner | Card + 自定义边框 | 使用 Card 组件 |
| LoadingBanner | 原生 div + Tailwind | **未使用 Card 组件**，样式不一致 |
| ApiErrorFallback | Card + 自定义边框 | 样式与 FeedbackBanner 不同 |

### 1.4 边框透明度不一致

- `border-border/60`：用于 InfoBlock、DetailSection 内部边框
- `border-border/70`：用于 Card、Drawer、Dialog 主要边框
- `border-border/80`：用于 Badge outline 变体

### 1.5 触发按钮变体不一致

- DetailDrawer 默认：`triggerVariant = "outline"`
- DetailDialog 默认：`triggerVariant = "secondary"`

---

## 2. 统一设计规范

### 2.1 卡片层级规范

| 层级 | 用途 | 阴影 | 背景 | 场景 |
|------|------|------|------|------|
| Level 1 | 页面主卡片 | `shadow-card-sm` | `bg-card/90` | 摘要卡、Hero |
| Level 2 | 区块容器 | `shadow-card-md` | `bg-card/95` | 抽屉、弹窗 |
| Level 3 | 内部摘要块 | 无阴影 | `bg-muted/15` | DigestBlock、InfoBlock |

**CSS 变量定义**：
```css
--shadow-card-sm: 0 18px 40px rgba(2, 6, 23, 0.18);
--shadow-card-md: 0 24px 60px rgba(2, 6, 23, 0.28);
--shadow-overlay: 0 24px 80px rgba(2, 6, 23, 0.45);
```

### 2.2 状态徽章统一规范

统一使用 `/apps/web/components/status-badge.tsx`，废弃 `status-bar.tsx` 内部的重复定义。

### 2.3 反馈条组件统一规范

| 类型 | 边框颜色 | 背景色 | 使用场景 |
|------|---------|--------|---------|
| success | `border-emerald-500/30` | `bg-emerald-500/10` | 操作成功 |
| warning | `border-amber-500/40` | `bg-amber-500/10` | 警告提示 |
| error | `border-rose-500/40` | `bg-rose-500/10` | 错误提示 |
| loading | `border-blue-500/30` | `bg-blue-500/10` | 加载状态 |

### 2.4 按钮触发规范

| 用途 | 默认变体 | 说明 |
|------|---------|------|
| 抽屉触发 | `outline` | 次要动作 |
| 弹窗触发 | `outline` | 与抽屉保持一致 |
| 主要动作 | `terminal` | 绿色边框 |
| 危险动作 | `danger` | 红色边框 |

---

## 3. 具体实施清单

### 高优先级（立即实施）

| 序号 | 任务 | 文件路径 | 修改点 |
|------|------|---------|--------|
| 1 | 统一 StatusBadge 组件 | `components/status-bar.tsx` | 删除内部 StatusBadge，导入统一组件 |
| 2 | 统一 LoadingBanner 样式 | `components/loading-banner.tsx` | 改用 Card 组件 |
| 3 | 统一触发按钮变体 | `components/detail-dialog.tsx` | 默认值改为 `outline` |
| 4 | 统一卡片阴影变量 | `app/globals.css` | 新增阴影 CSS 变量 |
| 5 | 统一内部摘要块背景 | `features-focus-grid.tsx`, `research-focus-grid.tsx` | 改为 `bg-muted/15` |

### 中优先级（下一批）

| 序号 | 任务 | 文件路径 | 修改点 |
|------|------|---------|--------|
| 6 | 统一卡片背景透明度 | `card.tsx`, `summary-card.tsx` 等 | 统一为 `bg-card/90` |
| 7 | 抽取 InfoBlock 为公共组件 | 新建 `components/info-block.tsx` | 复用同一组件 |
| 8 | 抽取 DetailSection 为公共组件 | 新建 `components/detail-section.tsx` | 复用同一组件 |
| 9 | 统一边框透明度命名 | `app/globals.css` | 新增工具类 |
| 10 | 统一 Button 变体颜色 | `components/ui/button.tsx` | 与 Badge 颜色一致 |

### 低优先级（后续优化）

| 序号 | 任务 | 说明 |
|------|------|------|
| 11 | 清理 globals.css 过时类 | 检查 `.panel`、`.button-link` 是否仍使用 |
| 12 | 增加组件样式文档 | 新建 `docs/component-styles.md` |
| 13 | 添加 Storybook 组件展示 | 提升组件可发现性 |

---

## 4. 实施建议

### 分批策略

**第一批（本周）**：高优先级 1-5 项
- 改动影响范围小，风险低
- 能立即消除最明显的视觉不一致

**第二批（下周）**：中优先级 6-10 项
- 需要创建新组件文件
- 需要修改多个页面的引用

**第三批（后续迭代）**：低优先级 11-13 项
- 属于代码质量和文档改进

### 验收标准

完成高优先级后：
1. 所有反馈条使用统一容器样式
2. StatusBadge 不再有重复定义
3. 抽屉和弹窗触发按钮使用相同默认变体
4. 内部摘要块背景色统一