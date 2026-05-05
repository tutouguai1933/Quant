# 后端问题清单

> 此文档记录前后端联调测试中发现的后端问题，供后端 session 修复参考。
> 测试日期：2026-05-05

---

## 1. terminal 字段未实现

### 问题描述
后端规划文档 `docs/2026-05-05-backend-terminal-frontend-support-plan.md` 定义了在 workspace 响应中返回 `terminal` 字段的方案，但当前后端实际返回的数据中没有这个字段。

### 影响页面
- `/research` - 模型训练页
- `/backtest` - 回测训练页
- `/evaluation` - 选币回测页
- `/features` - 因子研究页
- `/factor-knowledge` - 因子知识库页

### 建议修复
在以下服务中实现 `_build_terminal_view()` 方法：
- `services/api/app/services/research_workspace_service.py`
- `services/api/app/services/backtest_workspace_service.py`
- `services/api/app/services/evaluation_workspace_service.py`
- `services/api/app/services/feature_workspace_service.py`

参考文档中的结构：
```json
{
  "terminal": {
    "page": { "route": "...", "title": "...", "subtitle": "..." },
    "metrics": [...],
    "charts": { ... },
    "tables": { ... },
    "states": { ... }
  }
}
```

---

## 2. 图表序列数据缺失

### 问题描述
后端返回的图表序列数据为空或不存在，导致前端图表无法显示数据。

### 具体问题

| 页面 | 图表组件 | 缺失数据 |
|------|---------|---------|
| 模型训练 | FeatureImportanceChart | `terminal.charts.feature_importance` |
| 模型训练 | IcBarChart | `terminal.charts.training_curve` |
| 回测训练 | EquityCurveChart | `terminal.charts.performance.series` |
| 回测训练 | DrawdownChart | `terminal.charts.performance.series` |
| 选币回测 | PortfolioEquityChart | `terminal.charts.top_candidate_nav.series` |
| 因子研究 | QuantileNetChart | `terminal.research.charts.quantile_nav.series` |
| 因子研究 | IcBarChart | `terminal.research.charts.ic_series.series` |

### 建议修复
1. 实现 `services/api/app/services/terminal_series_service.py`
2. 在 worker 层保存图表序列数据：
   - `services/worker/qlib_backtest.py` - 净值、基准、回撤序列
   - `services/worker/qlib_runner.py` - 训练曲线、特征重要性
   - `services/worker/qlib_features.py` - 因子 IC 序列

---

## 3. metrics 字段缺失

### 问题描述
前端指标卡期望的数据在后端返回中缺失。

### 具体问题

| 页面 | 指标 | 缺失字段 |
|------|------|---------|
| 选币回测 | 总收益、年化、夏普等 | `best_experiment.metrics` 不存在 |
| 因子研究 | IC 均值、ICIR | `effectiveness_summary` 中缺少 `ic_mean`, `icir` 等 |
| 模型训练 | R²、IC | `training_metrics` 未在 terminal 中提供 |

### 建议修复
1. `evaluation_workspace_service.py` - 在 `best_experiment` 中添加 `metrics` 字段
2. `feature_workspace_service.py` - 在 `effectiveness_summary` 中添加 IC 相关指标
3. 或者在前端直接使用 `terminal.metrics` 数组

---

## 4. 字段名不一致

### 问题描述
后端返回的字段名与前端期望的不一致。

### 具体问题

| 组件 | 前端期望 | 后端返回 |
|------|---------|---------|
| QuantileNetChart | `Q1`, `Q2`, `Q3`, `Q4`, `Q5` | `q1`, `q2`, `q3`, `q4`, `q5` |
| EquityCurveChart | `value` | `strategy_nav` |
| EquityCurveChart | `benchmark` | `benchmark_nav` |
| DrawdownChart | `drawdown` | `drawdown_pct` |

### 建议修复
选择以下方案之一：
1. 后端调整字段名匹配前端期望
2. 在 API 层添加字段映射转换
3. 前端做数据转换（当前已在前端实现）

---

## 5. health.status 字段缺失

### 问题描述
`AutomationStatusModel.health` 类型定义为 `Record<string, unknown>`，但：
- 前端期望有 `status` 字段判断健康状态
- fallback 数据中只有 `active_blockers` 等字段，没有 `status`

### 影响页面
- 工作台首页 (`/`) - 数据更新状态显示

### 建议修复
在 `health` 对象中添加 `status` 字段：
```json
{
  "health": {
    "status": "ok",
    "active_blockers": [],
    ...
  }
}
```

---

## 6. 因子详情字段缺失

### 问题描述
`FeatureWorkspaceModel.factors` 只包含基础字段，缺少因子知识库需要的详细信息。

### 缺失字段
- `formula` - 公式说明
- `whyEffective` - 为什么有效
- `howToUse` - 怎么用
- `pitfalls` - 陷阱
- `recommendedWith` - 推荐搭配

### 影响页面
- 因子知识库页 (`/factor-knowledge`)

### 建议修复
1. 扩展 `factors` 返回字段
2. 或添加 `/api/v1/features/factors/{name}` 单独查询接口

---

## 7. API 返回结构不一致

### 问题描述
不同 workspace API 返回结构不一致：
- `getAutomationStatus()` 返回 `{ item: T }`
- `getResearchRuntimeStatus()` 返回 `{ item: T }`
- `getStrategyWorkspace()` 直接返回 `T`（无 item 包装）

### 建议修复
统一所有 API 返回结构，都使用或都不使用 `{ item: T }` 包装。

---

## 优先级建议

| 优先级 | 问题 | 原因 |
|--------|------|------|
| P0 | terminal 字段未实现 | 影响所有终端页面的图表显示 |
| P0 | 图表序列数据缺失 | 图表完全无法显示数据 |
| P1 | metrics 字段缺失 | 指标卡显示不正确 |
| P2 | 字段名不一致 | 前端已做转换，后端可后续优化 |
| P2 | health.status 缺失 | 影响工作台状态显示 |
| P3 | 因子详情缺失 | 影响知识库页面详情展示 |
| P3 | API 结构不一致 | 影响代码一致性 |

---

## 相关文档

- 前端终端化重构规划：`docs/2026-05-05-frontend-terminal-reference-rebuild-plan.md`
- 后端配套支持规划：`docs/2026-05-05-backend-terminal-frontend-support-plan.md`
