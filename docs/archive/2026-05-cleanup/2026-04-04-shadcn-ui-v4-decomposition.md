# shadcn/ui v4 拆解报告

## 这份报告是干什么的

这份报告不是教人“怎么装一个组件库”，而是回答 3 个更重要的问题：

1. 为什么 `shadcn/ui` 官网看起来精致，但 AI 直接套组件时常常很普通。
2. 官方站点里哪些文件最值得直接参考，避免 AI 只会拼基础组件。
3. 以后在 `Quant` 或别的项目里，应该怎样把它当成一套“页面组合规范”来用。

本次拆解基于官方开源仓库本地快照：

- 仓库根目录：`/tmp/shadcn-ui-ui`
- 官网应用目录：`/tmp/shadcn-ui-ui/apps/v4`

## 先说结论

`shadcn/ui` 的核心价值，不是“提供很多按钮、输入框、弹窗”，而是：

- 用一套稳定的主题变量管全站颜色、间距、圆角和层级。
- 用页面壳层、标题区、导航区、图区、表格区这些高层结构，把页面先搭对。
- 用大量完整示例去说明“在什么场景下该用什么变体、什么组合”。

所以 AI 直接只拿基础组件来拼页面，通常会丑，原因不是组件差，而是少了下面这些东西：

- 少了页面壳层
- 少了统一的标题和操作区
- 少了组件组合模式
- 少了真实状态和响应式布局
- 少了图表、表格、筛选、表单这些完整用法

一句话说：`shadcn/ui` 真正应该学的是“组合方式”，不是“组件清单”。

## 官方仓库里最值得参考的资源

### 1. 官网首页和站点壳层

这两处最能说明官方不是“随便堆组件”，而是先搭页面骨架：

- 首页：`/tmp/shadcn-ui-ui/apps/v4/app/(app)/(root)/page.tsx`
- 应用壳层：`/tmp/shadcn-ui-ui/apps/v4/app/(app)/layout.tsx`
- 标题区组件：`/tmp/shadcn-ui-ui/apps/v4/components/page-header.tsx`

能学到的点：

- 首页先用统一标题区，再接页面导航，再接主展示区。
- 壳层统一处理头部、正文、底部，不把每个页面写成独立散装布局。
- 标题、描述、操作按钮是一个固定组合，不是每页临时发挥。

### 2. 全局主题和视觉基础

- 全局样式：`/tmp/shadcn-ui-ui/apps/v4/app/globals.css`

能学到的点：

- 官方不是直接在组件里写死颜色，而是先定义一整套变量。
- 深色模式和浅色模式都用同一套语义变量，例如 `background`、`card`、`muted`、`border`。
- 图表、侧栏、代码块、选择态也都有单独语义层。

这意味着：以后复用时，应该优先继承“语义变量体系”，不要先抄一堆具体颜色值。

### 3. 基础组件目录

- 基础 UI 组件目录：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/ui`
- 本次统计文件数：`57`

这一层解决的是“原子能力”，例如：

- 按钮
- 表格
- 输入框
- 下拉菜单
- 侧栏
- 图表容器

适合做什么：

- 搭组件库底座
- 做可重复使用的小单元

不适合单独做什么：

- 直接拿来拼高质量页面

### 4. 图表目录

- 图表目录：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/charts`
- 本次统计文件数：`71`

这一层最值得学的不是某一张图，而是：

- 图表和主题变量怎么打通
- 图表颜色怎么走语义变量
- 图表容器怎么先统一尺寸和状态，再放具体图形

示例文件：

- `chart-bar-demo.tsx`
  路径：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples/chart-bar-demo.tsx`

值得参考的点：

- 不直接把颜色写死在图表组件里，而是通过 `ChartContainer` 和配置对象统一管理。

### 5. 示例目录

- 示例目录：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples`
- 本次统计文件数：`235`

这是最值得给 AI 直接读的部分。因为这里不只是单个组件，而是“组件在真实场景里的组合方式”。

特别值得参考的类型：

- 表格类：`data-table-demo.tsx`、`table-demo.tsx`
- 图表类：`chart-bar-demo.tsx`、`chart-tooltip-demo.tsx`
- 表单类：`form-rhf-demo.tsx`、`form-rhf-array.tsx`
- 空状态类：`empty-demo.tsx`
- 输入组合类：`input-group-demo.tsx`
- 按钮组合类：`button-group-dropdown.tsx`
- 面包屑和导航类：`breadcrumb-responsive.tsx`

例如：

- 数据表格示例：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples/data-table-demo.tsx`

这个示例不是只展示表格，而是完整展示了：

- 筛选输入
- 列控制
- 排序
- 选择
- 行级动作
- 容器边框和信息层级

这正是 AI 容易漏掉的部分。

### 6. 功能块目录

- 功能块目录：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/blocks`

这层是整份仓库里最值得项目级复用的部分，因为它已经接近完整页面。

本次确认到的高价值块：

- `dashboard-01`
  路径：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/blocks/dashboard-01/page.tsx`
- `login-01`
  路径：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/blocks/login-01/page.tsx`
- 多套 `sidebar-*`
  路径示例：`/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/blocks/sidebar-04/page.tsx`

从 `dashboard-01` 可以直接看到官方的做法：

- 先有 `SidebarProvider`
- 再有统一 `AppSidebar`
- 再有 `SiteHeader`
- 再有摘要卡片、主图、表格

这说明官方“精致感”的来源，是完整页面骨架，而不是某一个按钮更好看。

## 为什么 AI 直接用 shadcn/ui 容易写丑

结合这次拆解，可以把原因总结成 5 条：

### 1. 只拿原子组件，不看完整页面

只会用按钮、卡片、输入框，页面自然容易散。

### 2. 忽略变体和状态

官网里同一个组件会在不同位置使用不同尺寸、不同变体、不同组合。  
AI 如果只用默认样式，就会显得呆板。

### 3. 忽略页面壳层

官网的精致感来自：

- 头部
- 标题区
- 页面导航
- 主区
- 功能块

如果没有这层结构，再好的组件也会显得挤。

### 4. 忽略响应式布局

官网首页和块级页面都不是简单单栏到底，而是会根据场景切换展示方式。  
AI 如果只做竖向堆叠，就会很容易出现拥挤和重叠。

### 5. 忽略真实数据状态

官方示例大量展示了：

- 空状态
- 错误状态
- 表单状态
- 表格动作
- 图表容器

如果页面只有“静态信息”，就会显得廉价。

## 以后让 AI 写 UI 时，最值得直接参考的路径

为了避免以后再靠搜索半天，这里把值得直接喂给 AI 的路径列成固定清单。

### 页面骨架

- `/tmp/shadcn-ui-ui/apps/v4/app/(app)/layout.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/components/page-header.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/app/(app)/(root)/page.tsx`

### 功能块

- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/blocks/dashboard-01/page.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/blocks/login-01/page.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/blocks/sidebar-04/page.tsx`

### 图表与数据

- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples/chart-bar-demo.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples/data-table-demo.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/ui/chart`
- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/ui/table`

### 交互与表单

- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples/form-rhf-demo.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples/input-group-demo.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples/button-group-dropdown.tsx`
- `/tmp/shadcn-ui-ui/apps/v4/registry/new-york-v4/examples/empty-demo.tsx`

## 适合沉淀成“跨项目复用规则”的东西

这部分最值得抽成长期复用规范。

### 1. 先定义语义层，不先定具体颜色

优先定义：

- 页面背景
- 面板背景
- 主文本
- 次级文本
- 边框
- 强调色
- 风险色
- 成功色

### 2. 先定义页面结构，再选组件

顺序应该是：

1. 这个页面的主问题是什么
2. 页面是单栏、双栏还是终端式布局
3. 哪个区域是主图，哪个区域是解释，哪个区域是动作
4. 最后才决定用哪些按钮、表格、卡片

### 3. 优先复用“块”和“示例”，不要只复用“原子组件”

对复杂页面而言：

- 功能块比基础组件更有参考价值
- 示例比 API 文档更有参考价值

### 4. 让 AI 总结“组合套路”

真正高价值的不是组件名，而是组合模式，例如：

- 标题区 = 标题 + 描述 + 主动作 + 次动作
- 数据页 = 筛选条 + 摘要卡 + 主表格 + 行动作
- 终端页 = 左决策 + 右主图 + 顶部状态条
- 登录页 = 中央窄容器 + 表单主体 + 辅助说明

## 对 Quant 项目的直接启发

这次拆解对 `Quant` 的启发很明确：

### 1. 不能再只靠自定义卡片堆页面

要优先建立：

- 终端壳层
- 双栏主区
- 状态条
- 面板系统

### 2. 要用“功能块思维”重构，而不是逐个页面打补丁

`Quant` 后续更适合抽这几类块：

- 决策面板块
- 候选列表块
- 回测摘要块
- 执行状态块
- 账户状态块
- 主图块

### 3. 图表、表格、筛选、动作要一起设计

不能把：

- 图表
- 指标
- 候选
- 下一步动作
- 执行按钮

拆成互不相干的区域。

### 4. 后续如果要引入 shadcn/ui，正确姿势不是“把组件全换掉”

更合理的做法是：

1. 先学官方页面结构和组合模式
2. 再在 `Quant` 里定义自己的终端语义层
3. 再逐步替换高频 UI 片段

## 建议的落地方式

如果后续要继续优化 `Quant` 前端，建议按下面顺序：

1. 先用这份报告统一设计语言
2. 再按功能块拆页面
3. 再决定是否引入 `shadcn/ui` 的具体组件实现
4. 最后用真实页面验证工具检查布局、状态和响应式表现

## 一句话总结

`shadcn/ui` 真正值得复用的，不是“57 个基础组件”，而是“页面壳层 + 功能块 + 示例组合 + 语义主题”这整套方法。以后让 AI 写 UI 时，应该优先喂完整页面和功能块源码，而不是只给组件文档。
