# Quant 前端终端化复刻重构规划

> 目标：把当前 Quant 前端重构成参考图那种深色量化研究终端结构。  
> 输出对象：给 GLM5 或其他开发 Agent 执行。  
> 本文只规划前端重构，不要求修改后端核心交易逻辑，不新增依赖。

---

## 1. 项目背景

当前项目是个人加密量化研究与执行工作台，主链已经打通：

`数据 -> 因子 -> 研究训练 -> 回测 -> 评估 -> dry-run -> 小额 live -> 复盘`

现有前端已经做过“摘要优先、细节下沉”的重构，但视觉结构仍然偏普通控制台，缺少参考图里那种“量化研究终端”的清晰结构。参考图的优势不是单纯暗色，而是页面结构非常固定：

- 左侧窄导航固定。
- 顶部只放面包屑、页面标题和一句说明。
- 每页都有明确参数区。
- 参数区旁边或下方是指标卡。
- 页面主视觉由大图表承载。
- 文案短、密度高、解释少。
- 表单、按钮、标签、图表、卡片都用同一套视觉语言。

本次规划要求：尽量按参考图接近 1:1 复刻页面结构，再把股票语义本地化成当前项目的加密量化语义。

---

## 2. 参考图片来源

参考图目录：

`/mnt/c/Users/19332/Desktop/前端优化方向`

图片清单：

| 图片 | 尺寸 | 页面 |
|---|---:|---|
| `恳请量化前辈指导_1_Strive_来自小红书网页版.jpg` | 1795x1080 | 回测训练 |
| `恳请量化前辈指导_2_Strive_来自小红书网页版.jpg` | 1900x1080 | 选股回测 |
| `恳请量化前辈指导_3_Strive_来自小红书网页版.jpg` | 1775x1080 | 因子研究 |
| `恳请量化前辈指导_4_Strive_来自小红书网页版.jpg` | 1788x1080 | 因子知识库 |
| `恳请量化前辈指导_5_Strive_来自小红书网页版.jpg` | 1791x1080 | 模型训练 |

参考图浏览器地址显示为 `localhost:5174`，但本项目继续使用 Next.js 当前路由与端口，不需要迁移到 Vite。

---

## 3. 当前前端和后端入口

### 3.1 当前前端技术

- 前端目录：`apps/web`
- 框架：Next.js 15、React 19、TypeScript
- 样式：Tailwind CSS 4、`apps/web/app/globals.css`
- 图表：Recharts 已存在，不需要新增图表依赖
- 页面壳：`apps/web/components/app-shell.tsx`
- API 封装：`apps/web/lib/api.ts`

### 3.2 当前主要页面

| 当前路由 | 当前作用 | 重构后参考图映射 |
|---|---|---|
| `/` | 驾驶舱 | 工作台，保持总览，但视觉改成终端首页 |
| `/research` | 研究工作台 | 模型训练页，对应参考图 5 |
| `/backtest` | 回测工作台 | 回测训练页，对应参考图 1 |
| `/evaluation` | 评估中心 | 选币回测页，对应参考图 2 |
| `/features` | 因子工作台 | 因子研究页，对应参考图 3 |
| `/features?tab=knowledge` 或新增 `/factor-knowledge` | 当前无独立页 | 因子知识库页，对应参考图 4 |
| `/strategies` | 执行中心 | 实盘管理 |
| `/tasks` | 运维任务 | 参数优化 / 运行管理 |
| `/market`、`/balances`、`/positions`、`/orders`、`/risk` | 明细工具页 | 保留为低优先级工具入口 |

### 3.3 当前可用 API

| 前端函数 | 后端路由 | 适用页面 |
|---|---|---|
| `getResearchWorkspace()` | `/api/v1/research/workspace` | 模型训练 |
| `getResearchRuntimeStatus()` | `/api/v1/signals/research/runtime` | 模型训练、信号状态 |
| `getResearchReport()` | `/api/v1/signals/research/report` | 选币回测、模型结果 |
| `getBacktestWorkspace()` | `/api/v1/backtest/workspace` | 回测训练 |
| `getEvaluationWorkspace()` | `/api/v1/evaluation/workspace` | 选币回测 |
| `getFeatureWorkspace()` | `/api/v1/features/workspace` | 因子研究、因子知识库 |
| `getStrategyWorkspace()` | `/api/v1/strategies/workspace` | 实盘管理 |
| `getAutomationStatus()` | `/api/v1/tasks/automation` | 工作台、任务、执行 |
| `listSignals()` | `/api/v1/signals` | 候选信号 |
| `listOrders()` | `/api/v1/orders` | 订单明细 |
| `listPositions()` | `/api/v1/positions` | 持仓明细 |
| `listBalances()` | `/api/v1/balances` | 余额明细 |
| `listRiskEvents()` | `/api/v1/risk-events` | 风险事件 |

---

## 4. 全局视觉规范

### 4.1 整体方向

视觉定位：专业、紧凑、低干扰的量化研究终端。

不要做成现在常见的“大卡片 SaaS 面板”。参考图更像交易研究软件，页面密度高但层级清楚。

### 4.2 颜色

用接近参考图的深色体系，建议在 `apps/web/app/globals.css` 里定义统一变量。

| 用途 | 建议颜色 | 说明 |
|---|---|---|
| 页面底色 | `#070b12` | 接近纯黑但略带蓝 |
| 侧边栏底色 | `#0a0f18` | 比主背景略亮 |
| 卡片底色 | `#141a25` | 主卡片 |
| 卡片深层底色 | `#0b1018` | 输入框、表格、图表底 |
| 卡片描边 | `#202838` | 细线，不要发光过强 |
| 分割线 | `#1b2433` | 顶栏、侧栏、图表网格 |
| 主强调色 | `#43c7e8` | 青蓝，用于按钮、选中态、主曲线 |
| 主强调暗底 | `rgba(67,199,232,0.16)` | 选中 chip 背景 |
| 成功绿 | `#6bd889` | 正收益、正常 |
| 风险红 | `#ee6b78` | 回撤、负收益、失败 |
| 黄色 | `#e5c46b` | 第三条曲线、提示 |
| 紫色 | `#8b6be8` | ML 标签、辅助曲线 |
| 正文 | `#e8edf4` | 主文字 |
| 次级文字 | `#8b96a8` | 描述、坐标轴 |
| 弱文字 | `#5e6a7b` | 面包屑、辅助说明 |

### 4.3 字体和字号

参考图字号普遍很小，重点靠颜色、加粗和位置表达。

| 位置 | 字号 | 字重 | 说明 |
|---|---:|---:|---|
| 页面标题 | 20-22px | 700 | 如“模型训练” |
| 卡片标题 | 14-15px | 700 | 如“训练配置” |
| 指标数值 | 24-28px | 700 | 如 `+10.65%` |
| 表单标签 | 12px | 500 | 如“股票池” |
| 输入文字 | 13-14px | 600 | 表单内部 |
| 正文说明 | 12-13px | 400 | 卡片解释 |
| 面包屑 | 11-12px | 400 | 如“研究 / 模型训练” |
| chip | 11-12px | 600 | 标签、快速筛选 |

字体继续用中文友好的 `Noto Sans SC`、`PingFang SC`、`Microsoft YaHei`，不用额外引入字体依赖。

### 4.4 间距和尺寸

以桌面 1790x1080 左右作为主设计尺寸。

| 区域 | 建议尺寸 |
|---|---:|
| 左侧导航宽度 | 144-160px |
| 顶部页面头高度 | 78-92px |
| 主内容左右边距 | 16-18px |
| 卡片圆角 | 7-10px |
| 卡片内边距 | 14-18px |
| 卡片间距 | 12-14px |
| 输入框高度 | 32-36px |
| 主按钮高度 | 34-38px |
| 指标卡高度 | 90-112px |
| 主图表高度 | 430-520px |
| 侧边参数栏宽度 | 320-350px |

### 4.5 组件外观

所有页面统一以下风格：

- 卡片不要大阴影，改成 `1px` 深色描边 + 很弱的内阴影。
- 输入框是黑底，边框细，选中时青蓝描边。
- 按钮是青蓝实心，文字黑色或深色，像参考图里的“运行分析”“训练模型”。
- chip 默认黑底灰字，选中青蓝边框和青蓝文字。
- ML 标签用紫色，RULE 标签用青蓝灰色。
- 图表网格线很弱，坐标轴文字灰蓝。
- 页面不要大面积营销文案，每个说明压到一行。

---

## 5. 全局布局复刻

### 5.1 左侧导航

替换现有 `AppShell` 的大侧栏。参考图左侧导航很窄，不放长说明。

结构：

```text
Quant  v0.1

研究
  □ 工作台
  ◎ 模型训练
  ▣ 回测训练
  ⊞ 选股回测
  ◆ 因子研究
  ⌘ 参数优化

数据与知识
  ■ 数据管理
  ≡ 因子知识库     16
  △ 因子挖掘监控   ●

运营
  ◉ 实盘管理       ●

底部系统状态
  数据更新      正常
  控程引擎      3 运行中
  实盘连接      已连接
  GPU 使用      74%
```

本项目本地化后的导航建议：

| 显示文案 | 路由 |
|---|---|
| 工作台 | `/` |
| 模型训练 | `/research` |
| 回测训练 | `/backtest` |
| 选币回测 | `/evaluation` |
| 因子研究 | `/features` |
| 参数优化 | `/tasks` |
| 数据管理 | `/data` |
| 因子知识库 | `/features?tab=knowledge` 或 `/factor-knowledge` |
| 因子挖掘监控 | `/signals` |
| 实盘管理 | `/strategies` |

底部状态来源：

| 文案 | 数据来源 |
|---|---|
| 数据更新 | `getAutomationStatus().health` 或默认“正常” |
| 控程引擎 | `getAutomationStatus().schedulerPlan`、`controlActions` 数量 |
| 实盘连接 | `getStrategyWorkspace().executor_runtime.connection_status` |
| GPU 使用 | 当前后端没有真实 GPU 字段，先显示 `--` 或保留演示值，不要硬编码 74% 为真实状态 |

### 5.2 顶部页面头

每页顶部只保留：

```text
研究 / 模型训练
模型训练
LightGBM 因子模型训练与产物管理
```

不要再使用现有大块 `PageHero`。页面头应该贴近参考图，左对齐，高度约 80px，下边 1px 分割线。

### 5.3 主内容布局

标准页面分三类。

第一类：左参数栏 + 右指标和图表。适用于模型训练、回测训练。

```text
┌──────────────┬────────────────────────────────────┐
│ 参数栏        │ 指标卡横排                          │
│ 320-350px    ├────────────────────────────────────┤
│              │ 主图表 / 信息面板                    │
│              │                                    │
└──────────────┴────────────────────────────────────┘
```

第二类：顶部参数条 + 指标卡 + 大图表。适用于选币回测、因子研究。

```text
┌───────────────────────────────────────────────────┐
│ 参数条 / 查询条件                                  │
├───────────────────────────────────────────────────┤
│ 指标卡横排                                         │
├───────────────────────────────────────────────────┤
│ 大图表                                             │
└───────────────────────────────────────────────────┘
```

第三类：解释区 + 筛选区 + 知识卡网格。适用于因子知识库。

```text
┌───────────────────────────────────────────────────┐
│ 术语速查 2-3 列网格                                │
├───────────────────────────────────────────────────┤
│ 分类 chip + 搜索框 + 数量                           │
├───────────────────────┬───────────────────────────┤
│ 因子卡                 │ 因子卡                     │
└───────────────────────┴───────────────────────────┘
```

---

## 6. 参考图逐页信息提取

### 6.1 参考图 1：回测训练

页面标题：

- 面包屑：`研究 / 回测训练`
- 标题：`回测训练`
- 副标题：`单标的策略回测，跑出可部署的策略版本`

左侧参数栏第一块：`策略配置`

字段：

| 标签 | 值 |
|---|---|
| 标的代码 | `AAPL` |
| 标的名称 | `Apple`，在输入框右侧显示 |
| 资产类型 | `美股` |
| 频率 | `日线` |
| 策略（可多选） | `model_infer`、`ma_cross`、`lgbm_rolling`、`rsi_reversion` |
| 策略标签 | `model_infer` 和 `lgbm_rolling` 标 `ML`；`ma_cross` 和 `rsi_reversion` 标 `RULE` |
| model_infer 参数 | 选择器：`lstm_smoke · lstm · rank · IC=0.08!` |
| 做多分位 | `0.7` |
| 滚动窗口 | `60` |
| 初始资金（CNY） | `1000` |

左侧参数栏第二块：`风控参数`

字段：

| 标签 | 值 |
|---|---|
| 最大持仓天数 | `10 天` |
| 个股仓位 | `100%` |
| 个股止损 | `8%` |
| 开关 | `过滤ST`、`过滤北交所` 开启，`MA60过滤` 未开启 |

左侧参数栏第三块：`回测区间`

字段：

- 快速选择：`近1月`、`近3月`、`近1年`、`近3年`、`近5年`
- 当前选中：`近5年`

右侧顶部指标卡：

| 指标 | 值 | 辅助说明 |
|---|---|---|
| 年化收益 | `+10.65%` | `累计 22.33%` |
| 夏普比率 | `0.73` | `Calmar 0.55 · Sortino 0.86` |
| 最大回撤 | `-19.20%` | `波动率 15.62%` |
| 胜率 / 盈亏比 | `58.1% / 0.98` | `交易 31 次 · 持仓 8.6天` |

图表区：

- 顶部 tabs：`净值曲线`、`K线`、`交易记录`、`策略配置`
- 右侧策略筛选 chip：`ma_cross` 选中，后面有 `model_infer`、`rsi_reversion`、日期 `2021-04-26 · 2026-04-26`
- 主图：净值曲线，多条策略线
- 图例：`ma_cross`、`model_infer`、`rsi_reversion`、`基准`、`回撤`
- 下方第二图：回撤区域，红色填充

资金对比区：

| 区块 | 值 |
|---|---|
| 初始资金 | `￥1,000` |
| 中间箭头 | `+22.33%`，净赚 `￥223` |
| 最终资金 | `￥1,223` |
| 同期 Buy & Hold | `￥2,016` |
| 策略 vs B&H 超额收益 | `-79.32%` |
| 多赚 / 少赚 | `￥-793` |

本项目本地化：

- `AAPL / Apple` 改成 `BTCUSDT / Bitcoin` 或默认当前推荐币。
- `资产类型：美股` 改成 `资产类型：加密货币`。
- `频率：日线` 改成 `1h / 4h / 1d`。
- `初始资金（CNY）` 改成 `初始资金（USDT）`。
- `过滤ST / 过滤北交所 / MA60过滤` 改成 `流动性过滤 / live 白名单 / 趋势过滤`。
- 页面对应当前 `/backtest`，数据优先来自 `getBacktestWorkspace()` 和 `getResearchReport()`。

### 6.2 参考图 2：选股回测

页面标题：

- 面包屑：`研究 / 选股回测`
- 标题：`选股回测`
- 副标题：`多标的 Top-K 组合回测`

顶部参数大卡：

第一行：

- 模式 tabs：`因子打分`、`模型打分`
- 当前选中：`模型打分`
- 说明：`用已训练的 LightGBM 模型预测收益并排序`

第二行表单：

| 标签 | 值 |
|---|---|
| 股票池 | `hs300_top30 — 沪深 300 权重前 30 (30)` |
| 已训练模型 | `lstm_smoke · rank · IC=-0.085` |
| Top K | `3` |
| 调仓天数 | `5` |
| 开始日期 | `2021/04/26` |
| 结束日期 | `2026/04/26` |
| 按钮 | `运行选股回测` |

快速区间：

- `近1月`、`近3月`、`近1年`、`近3年`、`近5年`、`YTD`
- 当前选中：`近5年`

参数摘要：

| 标签 | 值 |
|---|---|
| 模型类型 | `lstm · rank` |
| 训练区间 | `20220101 - 20241231` |
| 预测期（天） | `5` |
| 样本量（训练/测试） | `5339 / 1233` |
| 因子 | `mom_5, mom_20, vol_20, rsi_14` |
| 训练集 R² / IC | `-7.321 / 0.084` |
| 测试集 R² / IC | `-7.300 / 0.085` |

股票池成员 chip：

`600519 贵州茅台`、`300750 宁德时代`、`601318 中国平安`、`600036 招商银行`、`000858 五粮液`、`601166 兴业银行`、`600900 长江电力`、`601888 中国中免`、`002594 比亚迪`、`600276 恒瑞医药`、`600030 中信证券`、`601012 隆基绿能`、`000333 美的集团`、`600887 伊利股份`、`000568 泸州老窖`、`601899 紫金矿业`、`002415 海康威视`、`600000 浦发银行`、`601668 中国建筑`、`600050 中国联通`、`601628 中国人寿`、`601988 中国银行`、`600031 三一重工`、`601857 中国石油`、`600809 山西汾酒`、`601919 中远海控`、`601601 中国太保`、`601328 交通银行`、`000002 万科A`、`600048 保利发展`

指标卡：

| 指标 | 值 |
|---|---|
| 总收益 | `121.02%` |
| 年化 | `21.15%` |
| Sharpe | `1.25` |
| 最大回撤 | `-19.58%` |
| 超额收益 | `103.32%` |
| 平均换手 | `13.4%` |

图表区：

- 标题：`组合净值 vs 等权基准`
- 副标题：`打分方式：模型 lstm_smoke`
- 图例：`Top-K 组合`、`等权基准`
- 主线：青蓝色 Top-K 曲线，带半透明面积填充
- 基准线：灰色虚线

本项目本地化：

- `选股回测` 改成 `选币回测`。
- `股票池` 改成 `候选池`，默认显示当前研究候选池，例如 `research_candidates_top30` 或 `live_allowed_symbols`。
- `沪深300` 改成 `主流币候选池`。
- 股票 chip 改成 `BTCUSDT`、`ETHUSDT`、`SOLUSDT`、`BNBUSDT` 等。
- 页面对应 `/evaluation`，数据来自 `getEvaluationWorkspace()`、`getResearchReport()`、`getBacktestWorkspace()`。

### 6.3 参考图 3：因子研究

页面标题：

- 面包屑：`研究 / 因子研究`
- 标题：`因子研究`
- 副标题：`IC / IR / 分位组合`

顶部参数条：

| 标签 | 值 |
|---|---|
| 因子 | `mom_20 — 20日动量` |
| 股票池 | `hs300_top30 (30)` |
| 开始日期 | `2021/04/26` |
| 结束日期 | `2026/04/26` |
| Forward（天） | `5` |
| 按钮 | `运行分析` |

快速区间：

- `近1月`、`近3月`、`近1年`、`近3年`、`近5年`、`YTD`
- 当前选中：`近5年`

指标卡：

| 指标 | 值 |
|---|---|
| IC 均值 | `0.0095` |
| IC 标准差 | `0.2994` |
| IR | `0.032` |
| IC 胜率 | `48.9%` |
| 股票池 | `30` |

图表：

- 左图标题：`分位组合净值（Q5=因子值最高）`
- 左图图例：`Q1 低`、`Q2`、`Q3`、`Q4`、`Q5 高`
- 左图为多条折线，Q5 在后段明显拉升。
- 右图标题：`IC 时间序列`
- 右图是正负柱状图，绿色为正 IC，红色为负 IC。

本项目本地化：

- `股票池` 改成 `币种池`。
- `mom_20 — 20日动量` 可改成 `mom_20 — 20根K线动量`。
- 页面对应 `/features` 默认 tab。
- 数据来自 `getFeatureWorkspace()`，现有后端没有完整 IC 序列时，先用 `effectiveness_summary`、`category_catalog`、`selection_matrix` 和研究报告生成摘要；图表需要优先接真实研究产物，缺失时显示空状态，不要假装真实历史。

### 6.4 参考图 4：因子知识库

页面标题：

- 面包屑：`数据 / 因子知识库`
- 标题：`因子知识库`
- 副标题：`已注册因子`

顶部解释区：`量化术语速查`

解释卡 7 个：

| 标题 | 内容 |
|---|---|
| IC（信息系数） | 每日横截面上，因子值排名与未来收益排名的 Spearman 相关系数。>0.05 为好因子，>0.10 为强因子。量化选股最核心指标，比 R² 更重要，因为我们只选 Top-K。 |
| IR（信息比率） | IC 的稳定性 = IC 均值 / IC 标准差。IR > 0.3 算可用，>0.5 算好，>1.0 非常稀有。IC 再高，如果 IR 低，实盘一样会大幅回撤。 |
| 方向（direction） | +1 = 因子值越大越好，-1 = 因子值越小越好。例如：vol_20 方向 = -1，意思是买低波动股票。 |
| 股票池（universe） | 允许选股的候选范围。限定池子是为了降噪、保证风格一致，让 Top-K 截面比较有意义。 |
| Top-K 调仓 | 每个调仓日按因子打分排序，买入分数最高的 K 只，等权持有，N 天后再调。K 小风险集中但收益潜力大，K 大更稳但不够锐利。 |
| 因子正交 | 两个因子相关性高时，同时叠加没有意义，相当于重复下注。选因子时要注意来自不同类别的组合效果最好。 |
| rank 标签 vs raw 标签 | 训练模型时，把 N 日收益率改成“当日横截面排名百分位”作为标签。抗极端值、去牛熊漂移，更符合量化选股目标。 |

筛选区：

- 分类 chip：`全部`、`波动`、`技术指标`、`量能`、`动量`、`价格形态`、`反转`
- 搜索框 placeholder：`搜索因子名或关键词...`
- 右侧数量：`共 22 个因子，已展示 22`

因子卡结构：

每张卡两列网格展示，卡片内固定分区：

- 因子名 + 分类标签
- 一句话解释
- `公式`
- `为什么有效`
- `怎么用`
- `陷阱`
- 可选 `推荐搭配`

示例卡：

`atr_z`：

- 标签：`波动`
- 描述：`ATR 相对价格（波动率代理）`
- 公式：`ATR（14日真实波动均值）/ 当前收盘价`
- 为什么有效：`ATR 标准化后的波动率，比 vol_20 更反映日内波动。`
- 怎么用：`方向=-1，与 vol_20 相关性较高，一般选一个即可。`
- 陷阱：`和 vol_20 冗余。`

`boll_pos`：

- 标签：`技术指标`
- 描述：`布林带位置：(close-lower)/(upper-lower)`
- 公式：`(收盘 - 布林下轨) / (上轨 - 下轨)，20日2σ`
- 为什么有效：`布林带里的位置。0=下轨，1=上轨，0.5=中轨。`
- 怎么用：`可反转（靠近下轨买）或趋势（突破上轨买）。A股震荡市反转逻辑更稳。`
- 陷阱：`和 hl_range_20 有相似作用，选一个即可。`

`macd_hist`：

- 标签：`技术指标`
- 描述：`MACD 柱状值（12,26,9）`
- 公式：`MACD柱状值 = DIF - DEA，参数（12, 26, 9）`
- 为什么有效：`MACD 柱反映短中期动量差。柱由负转正 = 金叉信号；柱由正转负 = 死叉信号。`
- 怎么用：`方向=+1（正柱且放大=多头加速）。但直接作为因子 IC 一般，更多作为模型的一维输入。`
- 陷阱：`震荡市里频繁金叉死叉，全是假信号；MACD 滞后性明显，捕捉到趋势时往往已经中段。`

`rsi_14`：

- 标签：`技术指标`
- 描述：`14日 RSI`
- 公式：`相对强弱指数，14日。范围 0-100。`
- 为什么有效：`衡量过去14天涨跌力量对比。>70 过热，<30 超卖，是最老牌的技术指标之一。`
- 怎么用：`既可做反转（低值做多），也可做趋势（高值做多）。A股里 RSI 反转策略更常用，rsi_14 < 30 时做多。`
- 陷阱：`趋势股可以长期保持 RSI > 80，别以为高 RSI 一定回调，需要配合趋势判断。`
- 推荐搭配：`经典 RSI 反转策略：RSI<30 买入，RSI>50 卖出`

本项目本地化：

- `股票池` 改成 `币种池`。
- `A股` 改成 `加密货币市场` 或删除。
- 因子卡内容来自 `getFeatureWorkspace().factors`、`category_catalog`、`selection_matrix`。
- 当前后端已有 `FEATURE_PROTOCOL`，应优先复用，不在前端硬编码完整因子知识。

### 6.5 参考图 5：模型训练

页面标题：

- 面包屑：`研究 / 模型训练`
- 标题：`模型训练`
- 副标题：`LightGBM 因子模型训练与产物管理`

左侧参数栏：`训练配置`

字段：

| 标签 | 值 |
|---|---|
| Model ID | `lgbm_v1`，输入框聚焦状态，蓝色描边 |
| 股票池 | `hs300_top30 — 沪深 300 权重前 30 (30)` |
| 时间区间快捷 | `近1月`、`近3月`、`近1年`、`近3年`、`近5年`、`YTD` |
| 开始日期 | `2022/01/01` |
| 结束日期 | `2024/12/31` |
| 模型后端 | `lgbm`、`mlp`、`lstm`、`transformer`，当前选中 `lgbm` |
| 损失函数 | `mse`、`ic`，当前选中 `mse` |
| 标签类型 | `raw`、`rank`、`alpha`，当前选中 `rank` |
| Forward | `5` |
| Trees | `200` |
| LR | `0.05` |
| Walk-Forward 滚动评估 | checkbox 未选中 |
| 因子（6） | 多个 chip，选中项有青蓝高亮 |
| 按钮 | `训练模型` |

因子 chip 可见项：

`atr_z`、`boll_pos`、`macd_hist`、`rsi_14`、`amount_z`、`money_flow_14`、`pv_corr_20`、`vol_mom_20`、`vol_ratio_5`、`mom_20`、`mom_5`、`turnover_z`、`vol_20`、`hl_range_20`

右侧顶部指标卡：

| 指标 | 值 |
|---|---|
| R² (train) | `0.041` |
| R² (test) | `-0.014` |
| IC (train) | `0.178` |
| IC (test) | `0.054` |
| 训练样本 | `5444` |
| 测试样本 | `1370` |
| 标签类型 | `rank` |

右侧图表和信息：

- 第一块：`特征重要度`，当前看起来为空或等待图表。
- 第二块：`测试集逐日 IC`，正负柱状图，绿色正值、红色负值。
- 第三块：`模型信息`，大块 JSON 代码面板。

JSON 面板可见字段：

```json
{
  "model_id": "lgbm_v1",
  "universe": [
    "600519",
    "000858",
    "601318",
    "600036",
    "000001",
    "600030",
    "601888",
    "600887",
    "000333",
    "601166"
  ],
  "factors": [
    "mom_5",
    "mom_20",
    "vol_20",
    "rsi_14",
    "macd_hist",
    "boll_pos"
  ],
  "beg": "20220101",
  "end": "20241231",
  "label_horizon": 5,
  "label_type": "rank",
  "n_estimators": 200,
  "learning_rate": 0.05
}
```

本项目本地化：

- 页面对应 `/research`。
- `股票池` 改成 `币种池`。
- `lgbm/mlp/lstm/transformer` 可映射到当前 `model_catalog`，如果后端暂未支持真实后端，仍按配置目录显示。
- `Model ID` 显示当前 `workspace.model.model_version` 或 `controls.model_key`。
- 指标卡优先取 `getResearchReport().latest_training`、`latest_inference`、`experiments`，没有字段时显示 `--`。
- JSON 面板展示当前训练配置，字段从 `getResearchWorkspace()` 组装，不硬编码示例股票。

---

## 7. 页面级重构方案

### 7.1 `/research`：模型训练页

目标：完全复刻参考图 5。

页面结构：

```text
研究 / 模型训练
模型训练
LightGBM 因子模型训练与产物管理

┌──────────────┬─────────────────────────────────────┐
│ 训练配置      │ 7 个指标卡横排                       │
│              ├─────────────────────────────────────┤
│              │ 特征重要度                           │
│              ├─────────────────────────────────────┤
│              │ 测试集逐日 IC                         │
│              ├─────────────────────────────────────┤
│              │ 模型信息 JSON                         │
└──────────────┴─────────────────────────────────────┘
```

左侧训练配置字段：

| 页面字段 | 本项目数据来源 |
|---|---|
| Model ID | `workspace.model.model_version || workspace.controls.model_key` |
| 币种池 | `workspace.selectors.symbols` 或 `candidate_scope.candidate_symbols` |
| 时间区间 | `workspace.sample_window` |
| 模型后端 | `workspace.controls.available_models` |
| 损失函数 | 先用固定 UI：`score` / `ic` / `rank`，后端没有字段时只展示不保存 |
| 标签类型 | `workspace.controls.label_mode`、`label_preset_key` |
| Forward | `workspace.controls.min_holding_days` / `max_holding_days` 可压成平均或 horizon |
| 权重参数 | `trend_weight`、`momentum_weight`、`volume_weight` 等 |
| 因子 | `getFeatureWorkspace().controls.primary_factors + auxiliary_factors` |
| 训练按钮 | 复用当前 action：`run_research_training` |

右侧指标卡：

| 指标 | 优先数据 |
|---|---|
| R² (train) | 暂无真实字段时显示 `--` |
| R² (test) | 暂无真实字段时显示 `--` |
| IC (train) | `latest_training.training_metrics.ic` 或 `experiments.training` |
| IC (test) | `latest_inference.metrics.ic` 或 `experiments.inference` |
| 训练样本 | `sample_window.train.sample_count` |
| 测试样本 | `sample_window.test.sample_count` |
| 标签类型 | `workspace.labeling.label_preset_key` 或 `controls.label_mode` |

图表：

- `特征重要度`：优先用研究报告字段；没有时根据因子权重生成“配置权重条形图”，标题注明“配置权重”而不是“模型真实重要度”。
- `测试集逐日 IC`：优先用后端真实 IC 序列；没有时显示空图和提示“当前研究产物没有逐日 IC 序列”。
- `模型信息`：展示当前训练配置 JSON。

应修改文件：

| 文件 | 动作 |
|---|---|
| `apps/web/app/research/page.tsx` | 重构为参考图 5 布局 |
| `apps/web/components/terminal/terminal-shell.tsx` | 新建终端壳 |
| `apps/web/components/terminal/control-panel.tsx` | 新建左侧参数面板 |
| `apps/web/components/terminal/metric-card.tsx` | 新建指标卡 |
| `apps/web/components/terminal/ic-bar-chart.tsx` | 新建 IC 柱状图 |
| `apps/web/components/terminal/model-json-panel.tsx` | 新建 JSON 信息面板 |

### 7.2 `/backtest`：回测训练页

目标：复刻参考图 1。

页面结构：

```text
研究 / 回测训练
回测训练
单标的策略回测，跑出可部署的策略版本

┌──────────────┬─────────────────────────────────────┐
│ 策略配置      │ 年化 / 夏普 / 回撤 / 胜率指标卡       │
│ 风控参数      ├─────────────────────────────────────┤
│ 回测区间      │ 净值曲线 tabs + 多策略对比图           │
│              ├─────────────────────────────────────┤
│              │ 资金对比                             │
└──────────────┴─────────────────────────────────────┘
```

左侧策略配置字段：

| 页面字段 | 本项目数据来源 |
|---|---|
| 标的代码 | `workspace.overview.recommended_symbol` 或 `BTCUSDT` |
| 标的名称 | 由 symbol 映射，未配置时显示 symbol |
| 资产类型 | 固定 `加密货币` |
| 频率 | `workspace.overview.holding_window` 或当前研究周期 |
| 策略 | `workspace.leaderboard[].strategy_template` |
| 模型参数 | `workspace.selection_story`、`controls.backtest_preset_key` |
| 初始资金 | 从余额接口或配置读取，缺失时显示 `-- USDT` |
| 风控参数 | `workspace.controls` 中 dry-run/live 门槛 |
| 回测区间 | `sample_window` 或用户选择 |

右侧指标卡：

| 指标 | 数据来源 |
|---|---|
| 年化收益 | `training_backtest.metrics.annual_return_pct`，缺失时从净收益近似或显示 `--` |
| 夏普比率 | `training_backtest.metrics.sharpe` |
| 最大回撤 | `training_backtest.metrics.max_drawdown_pct` |
| 胜率 / 盈亏比 | `training_backtest.metrics.win_rate`，盈亏比缺失显示 `--` |

图表：

- `净值曲线`：用 Recharts `ComposedChart` 或 `LineChart`。
- `K线`：可复用现有 `pro-kline-chart` 或暂保留空状态。
- `交易记录`：使用当前 `DataTable` 的紧凑版本。
- `策略配置`：展示 `selection_story` 和 `controls`。
- 回撤区：单独一条红色 AreaChart，放在净值曲线下方。

资金对比：

| 区块 | 本项目显示 |
|---|---|
| 初始资金 | `初始资金 USDT` |
| 回测收益 | `净收益 pct` |
| 最终资金 | `初始资金 * (1 + 净收益)` |
| Buy & Hold | 如果没有基准收益，显示 `--` |
| 策略 vs B&H | 如果没有基准收益，显示 `等待基准曲线` |

应修改文件：

| 文件 | 动作 |
|---|---|
| `apps/web/app/backtest/page.tsx` | 重构为参考图 1 布局 |
| `apps/web/components/terminal/equity-curve-chart.tsx` | 新建净值曲线 |
| `apps/web/components/terminal/drawdown-chart.tsx` | 新建回撤图 |
| `apps/web/components/terminal/funds-bridge.tsx` | 新建资金对比 |

### 7.3 `/evaluation`：选币回测页

目标：复刻参考图 2。

页面结构：

```text
研究 / 选币回测
选币回测
多标的 Top-K 组合回测

┌──────────────────────────────────────────────────┐
│ 模式 tabs + 参数条 + 候选池 chip                   │
├──────────────────────────────────────────────────┤
│ 总收益 / 年化 / Sharpe / 最大回撤 / 超额收益 / 换手 │
├──────────────────────────────────────────────────┤
│ 组合净值 vs 等权基准                              │
└──────────────────────────────────────────────────┘
```

顶部参数：

| 页面字段 | 本项目数据来源 |
|---|---|
| 模式 | `因子打分` / `模型打分`，默认模型打分 |
| 候选池 | `candidate_scope.headline`、`candidate_symbols` |
| 已训练模型 | `researchReport.latest_inference.model_version` |
| Top K | `priority_queue_summary.top_k` 或默认 `3` |
| 调仓天数 | `holding_window` 或 `max_holding_days` |
| 日期区间 | `sample_window` 或用户选择 |
| 运行按钮 | 当前没有单独 Top-K 回测 action 时先跳到研究/回测动作；不要调用不存在接口 |

指标卡：

| 指标 | 数据来源 |
|---|---|
| 总收益 | `best_experiment.metrics.net_return_pct` 或 backtest metrics |
| 年化 | 同上，缺失显示 `--` |
| Sharpe | `best_experiment.metrics.sharpe` |
| 最大回撤 | `best_experiment.metrics.max_drawdown_pct` |
| 超额收益 | `best_experiment.metrics.excess_return_pct`，缺失显示 `--` |
| 平均换手 | `metrics.turnover` 或 `controls.dry_run_max_turnover` |

候选 chip：

- 优先展示 `priority_queue` 前 30 个。
- 其次展示 `candidate_scope.candidate_symbols`。
- 再次展示 `researchReport.candidates`。

图表：

- 标题：`组合净值 vs 等权基准`
- 主线：Top-K 组合，青蓝。
- 基准线：等权基准，灰色虚线。
- 当前没有真实组合曲线时，显示空图和明确提示，不用随机数据。

应修改文件：

| 文件 | 动作 |
|---|---|
| `apps/web/app/evaluation/evaluation-client.tsx` | 重构为参考图 2 布局 |
| `apps/web/components/terminal/topk-backtest-panel.tsx` | 新建参数条 |
| `apps/web/components/terminal/topk-equity-chart.tsx` | 新建组合净值图 |
| `apps/web/components/terminal/chip-list.tsx` | 新建高密度 chip 列表 |

### 7.4 `/features`：因子研究页

目标：复刻参考图 3。

页面结构：

```text
研究 / 因子研究
因子研究
IC / IR / 分位组合

┌──────────────────────────────────────────────────┐
│ 因子选择 + 币种池 + 日期 + Forward + 运行分析      │
├──────────────────────────────────────────────────┤
│ IC均值 / IC标准差 / IR / IC胜率 / 币种池数量       │
├───────────────────────┬──────────────────────────┤
│ 分位组合净值           │ IC 时间序列               │
└───────────────────────┴──────────────────────────┘
```

顶部参数：

| 页面字段 | 本项目数据来源 |
|---|---|
| 因子 | `workspace.factors` |
| 币种池 | `workspace.selectors.symbols` 或配置候选池 |
| 开始日期/结束日期 | `researchWorkspace.sample_window` |
| Forward | `researchWorkspace.controls.max_holding_days` |
| 运行分析 | 没有独立接口时先做禁用态或跳转研究训练 |

指标卡：

| 指标 | 数据来源 |
|---|---|
| IC 均值 | `effectiveness_summary` 或研究报告 IC |
| IC 标准差 | 后端缺失显示 `--` |
| IR | 后端缺失显示 `--` |
| IC 胜率 | 后端缺失显示 `--` |
| 币种池 | `candidate_symbols.length` |

图表：

- `分位组合净值`：需要真实研究产物；后端没有时显示空状态。
- `IC 时间序列`：需要真实 IC 序列；后端没有时显示空状态。
- 空状态必须保持参考图布局，即仍然留出图表框架。

应修改文件：

| 文件 | 动作 |
|---|---|
| `apps/web/app/features/page.tsx` | 默认 tab 改为因子研究 |
| `apps/web/components/terminal/factor-analysis-toolbar.tsx` | 新建参数条 |
| `apps/web/components/terminal/quantile-net-chart.tsx` | 新建分位净值图 |
| `apps/web/components/terminal/ic-timeseries-chart.tsx` | 新建 IC 时间序列 |

### 7.5 因子知识库页

目标：复刻参考图 4。

推荐实现方式：

- 方案 A：在 `/features` 内用 query `?tab=knowledge` 显示知识库。
- 方案 B：新增 `/factor-knowledge` 路由。

为了尽量贴合参考图左侧导航，“因子研究”和“因子知识库”应是两个独立导航项。推荐方案 B，新增 `/factor-knowledge`。

页面结构：

```text
数据 / 因子知识库
因子知识库
已注册因子

┌──────────────────────────────────────────────────┐
│ 量化术语速查 2-3 列                              │
├──────────────────────────────────────────────────┤
│ 分类 chip + 搜索框 + 数量                         │
├───────────────────────┬──────────────────────────┤
│ 因子知识卡             │ 因子知识卡                │
└───────────────────────┴──────────────────────────┘
```

术语速查内容：

- 固定采用参考图中的 7 个术语。
- 文案可把“股票池”替换为“币种池”。
- `Top-K 调仓` 保留，因为本项目同样有候选篮子和执行篮子。

因子卡数据：

| 页面字段 | 数据来源 |
|---|---|
| 因子名 | `workspace.factors[].name` |
| 分类 | `workspace.factors[].category` |
| 描述 | `workspace.factors[].description` |
| 当前角色 | `selection_matrix.current_role` |
| 公式 | 后端当前没有公式字段时用前端映射表补充，映射表只放展示文案 |
| 为什么有效 | 优先用 `category_catalog.detail/effect` |
| 怎么用 | 根据 `role/current_role/direction` 生成 |
| 陷阱 | 根据冗余组 `redundancy_summary` 生成 |

应修改文件：

| 文件 | 动作 |
|---|---|
| `apps/web/app/factor-knowledge/page.tsx` | 新建页面 |
| `apps/web/components/terminal/factor-term-grid.tsx` | 新建术语速查 |
| `apps/web/components/terminal/factor-card.tsx` | 新建因子知识卡 |
| `apps/web/components/terminal/filter-bar.tsx` | 新建分类和搜索 |

### 7.6 `/`：工作台首页

参考图没有首页截图，但左侧导航第一项是 `工作台`。本项目首页应该成为终端风格总览，不继续沿用大 Hero。

建议布局：

```text
研究 / 工作台
工作台
研究、回测、执行和风险的当前状态

┌──────────────────────────────────────────────────┐
│ 当前推荐 / 研究状态 / 执行状态 / 风险 / 自动化     │
├───────────────────────┬──────────────────────────┤
│ 最近候选队列           │ 最近执行结果              │
├───────────────────────┬──────────────────────────┤
│ 自动化状态             │ 系统状态                  │
└───────────────────────┴──────────────────────────┘
```

视觉保持与其他页面一致，信息密度提高，弱化解释文案。

---

## 8. 组件拆分规划

新建目录：

`apps/web/components/terminal/`

建议组件：

| 组件 | 职责 |
|---|---|
| `terminal-shell.tsx` | 替代当前大 `AppShell`，提供窄侧栏、顶部标题、主体区域 |
| `terminal-sidebar.tsx` | 左侧导航、分组、底部系统状态 |
| `terminal-page-header.tsx` | 面包屑、标题、副标题 |
| `terminal-card.tsx` | 所有深色卡片基础外观 |
| `metric-card.tsx` | 指标卡，支持正负颜色 |
| `metric-strip.tsx` | 横向指标卡组 |
| `control-panel.tsx` | 左侧参数面板容器 |
| `field-row.tsx` | 表单标签、输入框、select |
| `segmented-control.tsx` | tabs/chip 式开关 |
| `chip-list.tsx` | 高密度标签列表 |
| `chart-panel.tsx` | 图表容器，统一标题和空状态 |
| `equity-curve-chart.tsx` | 净值曲线 |
| `drawdown-chart.tsx` | 回撤图 |
| `ic-bar-chart.tsx` | 正负 IC 柱状图 |
| `quantile-net-chart.tsx` | Q1-Q5 分位组合净值 |
| `model-json-panel.tsx` | 模型信息 JSON |
| `factor-term-grid.tsx` | 术语速查 |
| `factor-card.tsx` | 因子知识卡 |

注意：不要把全部逻辑塞进单个页面文件。当前项目已有多个页面文件很大，重构时每个页面只负责取数和组装，展示逻辑下沉到组件。

---

## 9. 数据本地化规则

### 9.1 股票语义替换

| 参考图 | 本项目 |
|---|---|
| 股票 | 币种 |
| 股票池 | 币种池 / 候选池 |
| 选股 | 选币 |
| AAPL | BTCUSDT |
| Apple | Bitcoin |
| 美股 | 加密货币 |
| CNY | USDT |
| 沪深300 | 主流币候选池 |
| 个股仓位 | 单币仓位 |
| 个股止损 | 单币止损 |
| 过滤ST | 流动性过滤 |
| 过滤北交所 | live 白名单 |
| MA60过滤 | 趋势过滤 |

### 9.2 状态文案

统一状态：

| 状态 | 文案 | 颜色 |
|---|---|---|
| `ready` / `connected` | 正常 / 已连接 | 绿色 |
| `running` | 运行中 | 青蓝 |
| `waiting` / `idle` | 等待中 | 灰蓝 |
| `blocked` / `attention_required` | 需处理 | 黄色 |
| `error` / `unavailable` | 不可用 | 红色 |

### 9.3 缺失真实数据时的规则

复刻结构可以接近 1:1，但不能把演示数值伪装成真实结果。

如果后端没有某字段：

- 指标卡显示 `--`。
- 图表保留图表容器，显示“当前研究产物没有返回该序列”。
- 不生成随机曲线。
- 不把参考图股票代码写入本项目真实页面。

---

## 10. 样式实现要点

### 10.1 `globals.css`

需要新增或替换终端变量：

```css
:root {
  --terminal-bg: #070b12;
  --terminal-sidebar: #0a0f18;
  --terminal-panel: #141a25;
  --terminal-panel-strong: #171e2b;
  --terminal-panel-deep: #0b1018;
  --terminal-border: #202838;
  --terminal-grid: #1b2433;
  --terminal-text: #e8edf4;
  --terminal-muted: #8b96a8;
  --terminal-dim: #5e6a7b;
  --terminal-cyan: #43c7e8;
  --terminal-green: #6bd889;
  --terminal-red: #ee6b78;
  --terminal-yellow: #e5c46b;
  --terminal-purple: #8b6be8;
}
```

页面背景：

```css
body {
  background:
    radial-gradient(circle at 20% 0%, rgba(67, 199, 232, 0.06), transparent 28%),
    linear-gradient(180deg, #070b12 0%, #080d15 100%);
}
```

### 10.2 Tailwind 类风格

优先使用：

- `bg-[var(--terminal-panel)]`
- `border-[var(--terminal-border)]`
- `text-[var(--terminal-muted)]`
- `rounded-[8px]`
- `shadow-none`

避免：

- 大圆角 `rounded-2xl` 到处使用。
- 大阴影。
- 大段说明文字。
- 紫蓝渐变标题。
- 玻璃拟态和模糊背景。

---

## 11. 实施顺序

### Phase 1：终端基础组件

目标：先把外壳和基础组件做出来，不动业务逻辑。

步骤：

1. 新建 `apps/web/components/terminal/terminal-shell.tsx`。
2. 新建 `terminal-sidebar.tsx`，复刻参考图左侧导航。
3. 新建 `terminal-page-header.tsx`。
4. 新建 `terminal-card.tsx`、`metric-card.tsx`、`metric-strip.tsx`。
5. 新建 `field-row.tsx`、`segmented-control.tsx`、`chip-list.tsx`。
6. 在 `globals.css` 加终端颜色变量。
7. 先让 `/research` 使用新 shell 验证整体视觉。

验收标准：

- 左侧栏宽度接近参考图。
- 页面头高度接近参考图。
- 卡片、输入框、按钮和 chip 风格统一。
- 不影响登录、会话和 WebSocket。

### Phase 2：模型训练页 `/research`

目标：优先完成参考图 5，因为它最能定义整套系统视觉。

步骤：

1. 重构 `/research` 页面顶部标题。
2. 左侧改为训练配置参数栏。
3. 右侧第一行改为 7 个紧凑指标卡。
4. 新增特征重要度区域。
5. 新增测试集逐日 IC 图表区域。
6. 新增模型信息 JSON 面板。
7. 保留现有研究训练、研究推理 action，不改后端。

验收标准：

- 页面结构与参考图 5 接近。
- 训练配置字段完整。
- 指标卡即使无数据也保持布局。
- JSON 面板展示当前配置，不展示股票示例。

### Phase 3：回测训练页 `/backtest`

目标：复刻参考图 1。

步骤：

1. 左侧做 `策略配置 / 风控参数 / 回测区间` 三块。
2. 右侧顶部做 4 张指标卡。
3. 主图做 tabs：`净值曲线 / K线 / 交易记录 / 策略配置`。
4. 净值曲线下方加入回撤图。
5. 图表下方加入资金对比。

验收标准：

- 左侧参数栏高度和参考图接近。
- 指标卡横排。
- 净值图和回撤图上下组合。
- 资金对比在图表下方。

### Phase 4：选币回测页 `/evaluation`

目标：复刻参考图 2。

步骤：

1. 页面改名显示为 `选币回测`。
2. 顶部做全宽参数大卡。
3. 加 `因子打分 / 模型打分` 模式切换。
4. 显示候选池、模型、Top K、调仓天数、日期区间。
5. 显示候选 chip 列表。
6. 指标卡横排 6 个。
7. 主图做 `组合净值 vs 等权基准`。

验收标准：

- 顶部参数区与参考图 2 接近。
- 候选 chip 一行多列密集展示。
- 主图占页面大部分空间。

### Phase 5：因子研究和因子知识库

目标：复刻参考图 3 和 4。

步骤：

1. `/features` 默认改为因子研究。
2. 顶部做因子分析参数条。
3. 指标卡显示 IC、IR、胜率、池子数量。
4. 主区左右两张图：分位组合净值、IC 时间序列。
5. 新增 `/factor-knowledge` 页面。
6. 复刻术语速查 7 张解释卡。
7. 复刻分类 chip、搜索框、两列因子卡网格。

验收标准：

- 因子研究页与参考图 3 接近。
- 因子知识库与参考图 4 接近。
- 搜索和分类能在前端过滤因子卡。

### Phase 6：工作台、执行、任务页视觉统一

目标：把剩余主线页面统一到终端壳，不强行照某张图。

步骤：

1. `/` 改成终端工作台。
2. `/strategies` 改成 `实盘管理` 视觉。
3. `/tasks` 改成 `参数优化 / 运行管理` 视觉。
4. 工具页保留原功能，但套用终端壳和紧凑卡片。

验收标准：

- 全站侧栏一致。
- 主页面都使用同一套颜色、卡片、按钮、chip。
- 旧的大 Hero、大说明卡不再出现在主线页面。

---

## 12. 需要保留的现有能力

重构不能破坏：

- 登录和退出。
- 需要登录的执行、任务、风险入口。
- `/api/control/session` 会话读取。
- `/actions` 表单动作。
- WebSocket 实时状态。
- API 不可用时的 fallback。
- Playwright 现有冒烟测试。

尤其注意：

- 当前 `AppShell` 里处理了登录状态、退出按钮、WebSocket 横幅。新 `TerminalShell` 必须保留这些能力，只是视觉变窄。
- 不要把当前有认证保护的 `/strategies`、`/tasks`、`/risk` 改成无保护页面。

---

## 13. 验证方式

执行前先确认工具存在。

PowerShell 预检查：

```powershell
Get-Command git
Get-Command pnpm
```

预期结果：两个命令都能返回可执行文件路径。

前端构建：

```powershell
wsl -d Ubuntu -- bash -lc "export LANG=C.UTF-8; cd /home/djy/Quant/apps/web && pnpm build"
```

预期结果：构建通过，失败数为 0。

页面冒烟测试：

```powershell
wsl -d Ubuntu -- bash -lc "export LANG=C.UTF-8; cd /home/djy/Quant/apps/web && QUANT_WEB_BASE_URL=http://127.0.0.1:9012 QUANT_API_BASE_URL=http://127.0.0.1:9011 pnpm exec playwright test tests/ui-all-pages.spec.cjs --reporter=line"
```

预期结果：测试通过，失败数为 0。

前端交互验证要求：

```powershell
wsl -d Ubuntu -- bash -lc "export LANG=C.UTF-8; cd /home/djy/Quant/apps/web && QUANT_WEB_BASE_URL=http://127.0.0.1:9012 QUANT_API_BASE_URL=http://127.0.0.1:9011 pnpm exec playwright test tests/ui-navigation.spec.cjs tests/ui-console.spec.cjs tests/ui-network.spec.cjs --reporter=line"
```

预期结果：导航、控制台错误、网络错误检查通过，失败数为 0。

真实页面检查：

```powershell
wsl -d Ubuntu -- bash -lc "curl -s http://127.0.0.1:9012/research | head"
```

预期结果：返回 HTML，且页面已包含 `模型训练`。

如果本地端口已有旧服务，必须先确认端口进程，不要假设当前页面是最新代码。

---

## 14. 开发注意事项

- 不修改 `package.json`、`pnpm-lock.yaml`，除非另行确认。
- 不新增 UI 依赖，图表继续使用 Recharts。
- 不做后端交易逻辑改动。
- 不把参考图里的股票代码作为真实数据写死。
- 不生成随机收益曲线冒充真实回测。
- 每个新文件顶部写中文注释说明职责。
- 每个函数写一行中文注释。
- 页面文件超过 500 行时要拆组件。
- 图表组件只负责展示，不负责请求数据。
- 页面负责取数和组装 view model。

---

## 15. 最终验收标准

视觉验收：

- `/research` 与参考图 5 的结构接近 1:1。
- `/backtest` 与参考图 1 的结构接近 1:1。
- `/evaluation` 与参考图 2 的结构接近 1:1。
- `/features` 与参考图 3 的结构接近 1:1。
- `/factor-knowledge` 与参考图 4 的结构接近 1:1。
- 左侧导航全站统一，宽度、分组、底部状态接近参考图。

功能验收：

- 原有页面都能打开。
- 登录态和未登录态都正常。
- 原有 action 不丢失。
- API fallback 仍然可用。
- 图表无真实数据时显示空状态。
- 构建通过，失败数为 0。
- Playwright 冒烟测试通过，失败数为 0。

交互验收：

- 侧栏点击能跳转。
- tabs/chip 选中态清楚。
- 搜索因子能过滤卡片。
- 页面不会出现明显横向溢出。
- 1366px 宽度下仍可使用。
- 移动端可以降级为顶部导航或可展开侧栏，但桌面优先。

---

## 16. 推荐给 GLM5 的执行提示词

可以直接把下面这段交给 GLM5：

```text
请按 docs/2026-05-05-frontend-terminal-reference-rebuild-plan.md 执行前端重构。

要求：
1. 只改前端结构和样式，不改后端交易逻辑。
2. 不修改 package.json、pnpm-lock.yaml。
3. 新建 apps/web/components/terminal/ 组件体系。
4. 优先完成 Phase 1 和 Phase 2，让 /research 先复刻参考图 5。
5. 每完成一个 Phase，运行文档里的构建和页面验证命令。
6. 如果发现后端缺少真实图表序列，不要造随机数据，保留空图状态。
7. 代码注释使用中文，文件超过 500 行时拆组件。
```

