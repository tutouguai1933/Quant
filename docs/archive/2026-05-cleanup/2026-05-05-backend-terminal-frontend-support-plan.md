# Quant 后端配套前端终端化重构规划

> 目标：为 `docs/2026-05-05-frontend-terminal-reference-rebuild-plan.md` 里的终端化前端复刻提供后端配套方案。  
> 输出对象：给 GLM5 或其他开发 Agent 执行。  
> 本文只规划后端接口、聚合服务、worker 输出和测试，不要求修改交易执行策略，不新增依赖。

---

## 1. 背景和目标

本次前端要接近 1:1 复刻参考图的量化研究终端结构。前端页面的核心不是视觉暗色，而是每个页面都有固定的信息模型：

- 左侧导航状态。
- 顶部面包屑和页面标题。
- 参数区。
- 指标卡。
- 大图表。
- 表格或知识库明细。
- 任务运行状态。

当前后端已经有较完整的 `workspace` 聚合接口，适合继续沿用。后端不需要推翻重做，重点是把现有数据整理成更稳定、更适合终端页面直接消费的结构，并补齐图表序列和空状态说明。

本规划的核心结论：

- 继续保留现有 `/api/v1/*/workspace` 路由。
- 不建议另建一套完全独立的终端接口。
- 在现有聚合服务里新增 `terminal` 字段，承载终端化页面模型。
- 图表数据必须来自真实训练、回测、因子和候选结果；没有真实数据时返回空数组和明确 `meta`，不要生成演示曲线。
- worker 层补充保存前端需要的序列数据，API 层只负责读取、校验、裁剪和聚合。

---

## 2. 当前后端结构

### 2.1 后端入口

| 文件 | 当前职责 | 本次关系 |
|---|---|---|
| `services/api/app/main.py` | FastAPI 入口，注册所有路由 | 只在新增路由时修改；优先不新增路由 |
| `services/api/app/routes/research_workspace.py` | `/api/v1/research/workspace` | 模型训练页主入口 |
| `services/api/app/routes/backtest_workspace.py` | `/api/v1/backtest/workspace` | 回测训练页主入口 |
| `services/api/app/routes/evaluation_workspace.py` | `/api/v1/evaluation/workspace` | 选币回测页主入口 |
| `services/api/app/routes/feature_workspace.py` | `/api/v1/features/workspace` | 因子研究和因子知识库主入口 |
| `services/api/app/routes/strategies.py` | `/api/v1/strategies/workspace` | 实盘管理页主入口 |
| `services/api/app/routes/tasks.py` | `/api/v1/tasks/automation` | 参数优化、任务运行、侧边栏运行状态 |
| `services/api/app/routes/signals.py` | 研究报告、候选、训练和推理动作 | 模型训练按钮和候选列表 |
| `services/api/app/routes/backtest_charts.py` | 回测图表接口 | 需要重点整改 |
| `services/api/app/routes/factor_analysis.py` | 因子贡献和相关性分析 | 可作为因子研究页补充来源 |

### 2.2 聚合服务

| 文件 | 当前能力 | 本次处理 |
|---|---|---|
| `services/api/app/services/research_workspace_service.py` | 聚合研究报告、训练配置、标签、模型参数 | 新增模型训练终端视图字段 |
| `services/api/app/services/backtest_workspace_service.py` | 聚合回测指标、成本假设、过滤条件、排行榜 | 新增回测训练终端视图字段 |
| `services/api/app/services/evaluation_workspace_service.py` | 聚合候选排行、闸门矩阵、实验对比、复盘结果 | 新增选币回测终端视图字段 |
| `services/api/app/services/feature_workspace_service.py` | 聚合因子协议、因子分类、预处理和权重 | 新增因子研究和因子知识库终端视图字段 |
| `services/api/app/services/strategy_workspace_service.py` | 聚合策略、运行、账户、执行状态 | 用于侧边栏和实盘管理页 |
| `services/api/app/services/automation_service.py` | 记录自动化周期、告警和运行摘要 | 用于任务状态、运行中状态点 |
| `services/api/app/services/workbench_config_service.py` | 统一工作台配置、preset 和选项目录 | 继续作为参数区唯一来源 |

### 2.3 worker 和研究输出

| 文件 | 当前能力 | 本次处理 |
|---|---|---|
| `services/worker/qlib_runner.py` | 研究训练、推理、候选生成、训练上下文和回测摘要 | 补充训练曲线、特征重要性、候选回测序列引用 |
| `services/worker/qlib_backtest.py` | 回测指标和成本模型 | 补充真实净值、基准、回撤、交易分布序列 |
| `services/worker/qlib_experiment_report.py` | 统一实验报告 | 把新增序列字段纳入 report |
| `services/worker/qlib_dataset.py` | 数据集拆分、样本窗口、快照 | 补充训练/验证/测试样本统计给前端指标卡 |
| `services/worker/qlib_features.py` | 因子协议和因子行构造 | 补充因子统计、IC、分组收益的原始依据 |
| `services/worker/qlib_ranking.py` | 候选排序和门控 | 给选币回测页补候选明细和淘汰原因 |

---

## 3. 总体后端方案

### 3.1 推荐接口策略

推荐在现有 workspace 响应中新增统一字段：

```json
{
  "data": {
    "item": {
      "status": "ready",
      "backend": "qlib",
      "terminal": {
        "page": {},
        "parameters": {},
        "metrics": [],
        "charts": {},
        "tables": {},
        "states": {}
      }
    }
  },
  "error": null,
  "meta": {
    "source": "research-workspace",
    "terminal_schema_version": "2026-05-05"
  }
}
```

这样做的原因：

- 前端现有 `apps/web/lib/api.ts` 已经接入 workspace，不需要大规模换接口。
- 旧页面字段继续保留，避免一次性打断现有页面。
- 新前端可以优先读取 `item.terminal`，缺失时再用旧字段兼容。
- 后端服务边界保持清楚，每个页面仍由对应 workspace 服务负责。

不推荐的方案：

- 不推荐新增 `/api/v1/terminal/*` 全套接口，因为会造成同一页面数据有两套来源。
- 不推荐让前端拼装复杂图表序列，因为图表序列的真实性和口径应由后端控制。
- 不推荐继续使用后端演示数据填图表，因为前端会被误导成真实回测结果。

### 3.2 统一 terminal 结构

每个 workspace 建议新增同样的顶层结构：

```json
{
  "terminal": {
    "page": {
      "route": "/research",
      "breadcrumb": "研究 / 模型训练",
      "title": "模型训练",
      "subtitle": "LightGBM 因子模型训练与产物管理",
      "updated_at": "2026-05-05T00:00:00+00:00"
    },
    "parameters": {
      "groups": []
    },
    "metrics": [],
    "charts": {},
    "tables": {},
    "actions": [],
    "states": {
      "status": "ready",
      "empty_reason": "",
      "data_quality": "real",
      "warnings": []
    }
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `page` | object | 页面标题、路由和更新时间 |
| `parameters.groups` | array | 参数面板分组，前端按顺序渲染 |
| `metrics` | array | 指标卡数组，前端不需要猜字段 |
| `charts` | object | 页面主图表数据 |
| `tables` | object | 页面表格、排行、知识库列表 |
| `actions` | array | 可执行动作，如训练、推理、刷新 |
| `states.status` | string | `ready`、`empty`、`running`、`degraded`、`error` |
| `states.data_quality` | string | `real`、`partial`、`empty` |
| `states.warnings` | array | 明确告诉前端哪些数据不足 |

---

## 4. 全局后端优化原则

### 4.1 保留现有业务链路

当前链路是：

`数据 -> 因子 -> 研究训练 -> 回测 -> 评估 -> dry-run -> live -> 复盘`

本次后端优化只做展示数据聚合和序列补齐，不改交易执行逻辑，不改 live 策略参数，不改风控规则。

### 4.2 不再伪造图表数据

`services/api/app/services/backtest_chart_service.py` 当前会在缺失数据时生成 demo 曲线，并用总收益反推一条带噪声的收益曲线。这不适合终端化复刻，因为参考图的大图表是核心信息区域，必须反映真实结果。

整改规则：

- 没有真实曲线时返回 `[]`。
- 同时返回 `meta.data_quality = "empty"`。
- `warnings` 写清楚缺失原因，例如 `backtest_series_missing`。
- 指标卡可以显示已有聚合指标，但图表不能伪造。

### 4.3 统一空状态

每个 workspace 都要能表达以下状态：

| 状态 | 含义 | 前端展示 |
|---|---|---|
| `ready` | 数据完整 | 正常渲染 |
| `partial` | 有摘要但缺少部分序列 | 渲染指标，图表显示空状态 |
| `running` | 后台任务运行中 | 显示进度条和禁用重复提交 |
| `empty` | 还没跑过对应任务 | 显示下一步动作 |
| `degraded` | 后端依赖降级或配置未对齐 | 显示提示，不阻断页面 |
| `error` | 服务异常 | 显示错误摘要 |

### 4.4 配置统一从 workbench_config_service 来

参数区不要在多个服务里硬编码。所有默认值、选项、preset 继续从：

`services/api/app/services/workbench_config_service.py`

读取。workspace 服务只负责把配置转换成前端需要的分组结构。

### 4.5 图表数据在服务层构造

新增一个服务文件集中处理序列：

`services/api/app/services/terminal_series_service.py`

职责：

- 从研究报告读取已有序列。
- 对序列字段做类型规范。
- 按前端图表要求裁剪字段。
- 不制造业务结果。
- 给缺失数据返回明确空状态。

---

## 5. 页面级后端规划

## 5.1 `/research` 模型训练页

### 页面需要的数据

参考图对应“模型训练”。本项目本地化为加密量化研究训练。

页面结构：

- 左侧参数栏：模型类型、训练区间、验证区间、测试区间、因子组合、标签规则、样本拆分。
- 右上指标卡：训练样本、验证样本、测试样本、候选数量、模型版本、最近训练状态。
- 主图表：训练/验证/测试损失或评分曲线。
- 下方表格：特征重要性、最近训练记录、样本窗口。
- 动作：训练模型、运行推理、运行完整流水线。

### 复用现有数据

| 现有字段 | 来源 | 用途 |
|---|---|---|
| `controls` | `ResearchWorkspaceService` | 参数区 |
| `labeling` | `ResearchWorkspaceService` | 标签规则 |
| `sample_window` | `ResearchWorkspaceService` | 训练/验证/测试区间 |
| `model` | `ResearchWorkspaceService` | 模型版本和 backend |
| `readiness` | `ResearchWorkspaceService` | 按钮可用性和下一步 |
| `getResearchRuntimeStatus()` | `ResearchRuntimeService` | 运行状态和进度 |

### 需要新增字段

建议在 `research_workspace_service.py` 的 `terminal` 中新增：

```json
{
  "terminal": {
    "page": {
      "route": "/research",
      "breadcrumb": "研究 / 模型训练",
      "title": "模型训练",
      "subtitle": "LightGBM 因子模型训练与产物管理"
    },
    "parameters": {
      "groups": [
        {
          "title": "模型配置",
          "fields": [
            {"key": "model_key", "label": "模型", "value": "lightgbm_ltr", "control": "select"},
            {"key": "research_template", "label": "训练模板", "value": "single_asset_timing", "control": "select"},
            {"key": "research_preset_key", "label": "研究预设", "value": "baseline_balanced", "control": "select"}
          ]
        },
        {
          "title": "标签与窗口",
          "fields": [
            {"key": "holding_window_label", "label": "持仓窗口", "value": "1-3d", "control": "select"},
            {"key": "label_target_pct", "label": "目标收益", "value": "1", "unit": "%"},
            {"key": "label_stop_pct", "label": "止损收益", "value": "-1", "unit": "%"}
          ]
        }
      ]
    },
    "metrics": [
      {"key": "training_rows", "label": "训练样本", "value": 0, "format": "integer"},
      {"key": "validation_rows", "label": "验证样本", "value": 0, "format": "integer"},
      {"key": "testing_rows", "label": "测试样本", "value": 0, "format": "integer"},
      {"key": "candidate_count", "label": "候选数量", "value": 0, "format": "integer"}
    ],
    "charts": {
      "training_curve": [],
      "feature_importance": []
    },
    "tables": {
      "sample_windows": [],
      "recent_training_runs": []
    }
  }
}
```

### worker 需要补的数据

在 `services/worker/qlib_runner.py` 训练输出里补：

| 字段 | 类型 | 说明 |
|---|---|---|
| `training_metrics.training_curve` | array | 训练/验证/测试曲线 |
| `training_metrics.feature_importance` | array | 因子重要性 |
| `training_context.sample_counts` | object | 训练、验证、测试样本数量 |
| `experiments.recent_runs[].metrics_summary` | object | 最近训练记录摘要 |

推荐训练曲线格式：

```json
[
  {
    "step": 1,
    "train_score": 0.6123,
    "validation_score": 0.5881,
    "test_score": null
  }
]
```

推荐特征重要性格式：

```json
[
  {
    "factor": "ema20_gap_pct",
    "category": "trend",
    "importance": 0.1834,
    "rank": 1
  }
]
```

### 服务改造点

| 文件 | 改造内容 |
|---|---|
| `services/api/app/services/research_workspace_service.py` | 新增 `_build_terminal_view()`、`_build_terminal_parameters()`、`_build_terminal_metrics()` |
| `services/api/app/services/terminal_series_service.py` | 新增 `build_training_curve()`、`build_feature_importance()` |
| `services/api/app/services/research_runtime_service.py` | 保持现有状态结构，必要时把 `current_stage` 映射成更短的中文文案 |
| `services/api/tests/test_research_workspace_service.py` | 增加 terminal 字段测试 |

---

## 5.2 `/backtest` 回测训练页

### 页面需要的数据

参考图对应“回测训练”。本项目本地化为候选策略回测训练。

页面结构：

- 左侧参数栏：策略模板、回测预设、手续费、滑点、成本模型、持仓窗口。
- 右上指标卡：累计收益、年化收益、最大回撤、夏普、胜率、换手率。
- 主图表：策略净值、基准净值、回撤曲线。
- 下方表格：交易分布、阶段评估、排行榜。

### 复用现有数据

| 现有字段 | 来源 | 用途 |
|---|---|---|
| `controls` | `BacktestWorkspaceService` | 参数区 |
| `training_backtest.metrics` | `BacktestWorkspaceService` | 指标卡 |
| `stage_assessment` | `BacktestWorkspaceService` | 阶段评估 |
| `selection_story` | `BacktestWorkspaceService` | 口径说明 |
| `leaderboard` | `BacktestWorkspaceService` | 候选排行 |

### 必须整改的问题

`BacktestChartService.generate_profit_curve()` 当前会用 demo 或用总收益生成一条曲线。这个行为要改掉。

整改后的行为：

| 输入 | 旧行为 | 新行为 |
|---|---|---|
| 没有真实回测 | 返回 demo 曲线 | 返回空数组和 `backtest_series_missing` |
| 只有总收益 | 反推曲线 | 返回指标卡，不返回曲线 |
| 有真实序列 | 返回真实序列 | 返回真实序列 |

### 需要新增字段

建议 `backtest_workspace_service.py` 的 `terminal`：

```json
{
  "terminal": {
    "page": {
      "route": "/backtest",
      "breadcrumb": "研究 / 回测训练",
      "title": "回测训练",
      "subtitle": "训练样本回测、成本口径与闸门检查"
    },
    "metrics": [
      {"key": "total_return_pct", "label": "累计收益", "value": "0", "format": "percent", "tone": "profit_loss"},
      {"key": "max_drawdown_pct", "label": "最大回撤", "value": "0", "format": "percent", "tone": "risk"},
      {"key": "sharpe", "label": "夏普比率", "value": "0", "format": "decimal"},
      {"key": "win_rate", "label": "胜率", "value": "0", "format": "percent_ratio"},
      {"key": "turnover", "label": "换手率", "value": "0", "format": "percent_ratio"},
      {"key": "sample_count", "label": "样本数", "value": "0", "format": "integer"}
    ],
    "charts": {
      "performance": {
        "series": [],
        "meta": {
          "data_quality": "empty",
          "warnings": ["backtest_series_missing"]
        }
      }
    },
    "tables": {
      "leaderboard": [],
      "stage_assessment": []
    }
  }
}
```

推荐 performance 序列格式：

```json
[
  {
    "date": "2026-01-01",
    "strategy_nav": 1.0,
    "benchmark_nav": 1.0,
    "drawdown_pct": 0.0,
    "daily_return_pct": 0.0,
    "turnover": 0.0
  }
]
```

### worker 需要补的数据

在 `services/worker/qlib_backtest.py` 或训练回测输出里补：

| 字段 | 类型 | 说明 |
|---|---|---|
| `backtest.series.performance` | array | 净值、基准、回撤 |
| `backtest.series.trade_distribution` | array | 盈亏分布 |
| `backtest.series.monthly_returns` | array | 月度收益 |
| `backtest.metrics.annual_return_pct` | string | 年化收益 |
| `backtest.metrics.calmar` | string | Calmar，可选 |

### 服务改造点

| 文件 | 改造内容 |
|---|---|
| `services/api/app/services/backtest_workspace_service.py` | 新增 terminal 视图，指标卡和图表 meta |
| `services/api/app/services/backtest_chart_service.py` | 移除 demo 曲线和反推曲线行为，保留兼容接口但返回真实数据或空状态 |
| `services/api/app/services/terminal_series_service.py` | 新增 `build_backtest_performance_series()` |
| `services/api/tests/test_backtest_workspace_service.py` | 增加 terminal metrics 和空图表测试 |
| `services/api/tests/test_backtest_chart_service.py` | 增加“不生成 demo 曲线”的测试 |

---

## 5.3 `/evaluation` 选币回测页

### 页面需要的数据

参考图对应“选股回测”。本项目本地化为“选币回测”。

页面结构：

- 顶部参数条：候选范围、top N、阈值预设、闸门开关、排序方式。
- 指标卡：推荐标的、候选数量、通过数量、淘汰数量、最佳收益、最大回撤。
- 主图表：Top N 候选回测净值对比。
- 右侧或下方表格：候选排行、闸门结果、淘汰原因。

### 复用现有数据

| 现有字段 | 来源 | 用途 |
|---|---|---|
| `leaderboard` | `EvaluationWorkspaceService` | 候选排行 |
| `priority_queue` | `CandidatePriorityService` | 优先队列 |
| `gate_matrix` | `EvaluationWorkspaceService` | 闸门检查 |
| `best_experiment` | `EvaluationWorkspaceService` | 最佳候选 |
| `elimination_explanation` | `EvaluationWorkspaceService` | 淘汰原因 |
| `threshold_catalog` | `EvaluationWorkspaceService` | 参数条 |

### 需要新增字段

建议 `evaluation_workspace_service.py` 的 `terminal`：

```json
{
  "terminal": {
    "page": {
      "route": "/evaluation",
      "breadcrumb": "研究 / 选币回测",
      "title": "选币回测",
      "subtitle": "Top N 候选对比、闸门过滤与执行建议"
    },
    "metrics": [
      {"key": "recommended_symbol", "label": "推荐标的", "value": "BTCUSDT", "format": "text"},
      {"key": "candidate_count", "label": "候选数量", "value": 0, "format": "integer"},
      {"key": "passed_count", "label": "通过数量", "value": 0, "format": "integer"},
      {"key": "rejected_count", "label": "淘汰数量", "value": 0, "format": "integer"},
      {"key": "best_net_return_pct", "label": "最佳净收益", "value": "0", "format": "percent", "tone": "profit_loss"},
      {"key": "best_max_drawdown_pct", "label": "最佳回撤", "value": "0", "format": "percent", "tone": "risk"}
    ],
    "charts": {
      "top_candidate_nav": {
        "series": [],
        "meta": {
          "data_quality": "empty",
          "warnings": ["candidate_backtest_series_missing"]
        }
      }
    },
    "tables": {
      "candidate_rows": [],
      "gate_rows": [],
      "elimination_rows": []
    }
  }
}
```

推荐 Top N 净值序列格式：

```json
[
  {
    "date": "2026-01-01",
    "BTCUSDT": 1.0,
    "ETHUSDT": 1.0,
    "SOLUSDT": 1.0,
    "benchmark": 1.0
  }
]
```

推荐候选表格式：

```json
[
  {
    "rank": 1,
    "symbol": "BTCUSDT",
    "strategy_template": "single_asset_timing",
    "score": "0.72",
    "net_return_pct": "3.20",
    "max_drawdown_pct": "-4.10",
    "win_rate": "0.58",
    "gate_status": "passed",
    "next_action": "dry_run"
  }
]
```

### 服务改造点

| 文件 | 改造内容 |
|---|---|
| `services/api/app/services/evaluation_workspace_service.py` | 新增 terminal 指标、Top N 图表、候选表 |
| `services/api/app/services/candidate_priority_service.py` | 确保候选排序字段稳定，补 rank 和 gate_status |
| `services/api/app/services/terminal_series_service.py` | 新增 `build_top_candidate_nav_series()` |
| `services/worker/qlib_ranking.py` | 候选输出里保留每个候选的回测序列引用或精简序列 |
| `services/api/tests/test_evaluation_workspace_service.py` | 增加选币终端视图测试 |

---

## 5.4 `/features` 因子研究页

### 页面需要的数据

参考图对应“因子研究”。本项目本地化为加密因子研究。

页面结构：

- 顶部参数条：因子池、时间周期、行业/标的范围、IC 口径、分组数量。
- 指标卡：因子数量、主因子数量、辅助因子数量、平均 IC、ICIR、有效因子数。
- 主图表：IC 时间序列、IC 累计曲线、分组收益曲线。
- 表格：因子贡献、相关性、冗余提示。

### 复用现有数据

| 现有字段 | 来源 | 用途 |
|---|---|---|
| `factors` | `FeatureWorkspaceService` | 因子列表 |
| `categories` | `FeatureWorkspaceService` | 因子分类 |
| `roles` | `FeatureWorkspaceService` | 主因子/辅助因子 |
| `effectiveness_summary` | `FeatureWorkspaceService` | 有效性摘要 |
| `redundancy_summary` | `FeatureWorkspaceService` | 冗余摘要 |
| `factor_analysis_service` | `FactorAnalysisService` | 因子贡献和相关性 |

### 需要新增字段

建议 `feature_workspace_service.py` 的 `terminal.research`：

```json
{
  "terminal": {
    "page": {
      "route": "/features",
      "breadcrumb": "数据与知识 / 因子研究",
      "title": "因子研究",
      "subtitle": "因子 IC、分组收益与冗余检查"
    },
    "metrics": [
      {"key": "factor_count", "label": "因子数量", "value": 0, "format": "integer"},
      {"key": "primary_count", "label": "主因子", "value": 0, "format": "integer"},
      {"key": "auxiliary_count", "label": "辅助因子", "value": 0, "format": "integer"},
      {"key": "mean_ic", "label": "平均 IC", "value": "0", "format": "decimal"},
      {"key": "icir", "label": "ICIR", "value": "0", "format": "decimal"},
      {"key": "effective_factor_count", "label": "有效因子", "value": 0, "format": "integer"}
    ],
    "charts": {
      "ic_series": [],
      "cumulative_ic": [],
      "quantile_nav": []
    },
    "tables": {
      "factor_rows": [],
      "correlation_rows": [],
      "redundancy_rows": []
    }
  }
}
```

推荐 IC 序列格式：

```json
[
  {
    "date": "2026-01-01",
    "factor": "ema20_gap_pct",
    "ic": 0.034,
    "rank_ic": 0.041,
    "cumulative_ic": 0.034
  }
]
```

推荐分组收益格式：

```json
[
  {
    "date": "2026-01-01",
    "q1": 1.0,
    "q2": 1.0,
    "q3": 1.0,
    "q4": 1.0,
    "q5": 1.0,
    "long_short": 1.0
  }
]
```

### worker 需要补的数据

在 `qlib_features.py`、`qlib_runner.py` 或专门的因子评估流程里补：

| 字段 | 类型 | 说明 |
|---|---|---|
| `factor_evaluation.ic_series` | array | 每个因子的每日 IC |
| `factor_evaluation.rank_ic_series` | array | Rank IC |
| `factor_evaluation.quantile_nav` | array | 分组收益 |
| `factor_evaluation.factor_summary` | array | 平均 IC、ICIR、覆盖率 |
| `factor_evaluation.correlation_matrix` | object | 因子相关性矩阵 |

### 服务改造点

| 文件 | 改造内容 |
|---|---|
| `services/api/app/services/feature_workspace_service.py` | 新增因子研究 terminal 视图 |
| `services/api/app/services/factor_analysis_service.py` | 增加从研究报告读取因子评估数据的聚合方法 |
| `services/api/app/services/terminal_series_service.py` | 新增 `build_factor_ic_series()`、`build_factor_quantile_nav()` |
| `services/api/tests/test_feature_workspace_service.py` | 增加因子研究 terminal 字段测试 |

---

## 5.5 `/factor-knowledge` 或 `/features?tab=knowledge` 因子知识库页

### 页面需要的数据

参考图对应“因子知识库”。本项目当前没有独立知识库路由，但 `FeatureWorkspaceService` 已经有因子协议，可先用同一个 `/api/v1/features/workspace` 支撑。

页面结构：

- 顶部统计：因子总数、分类数量、主因子、辅助因子、当前版本。
- 左侧分类筛选：趋势、动量、量能、震荡、波动。
- 主列表：因子名称、类别、角色、说明、启用状态、权重入口。
- 右侧详情：公式说明、适用场景、风险、相关因子。

### 复用现有数据

| 现有字段 | 来源 | 用途 |
|---|---|---|
| `factors` | `FeatureWorkspaceService` | 知识库列表 |
| `categories` | `FeatureWorkspaceService` | 分类筛选 |
| `selection_matrix` | `FeatureWorkspaceService` | 启用状态 |
| `category_catalog` | `FeatureWorkspaceService` | 分类说明 |
| `score_story` | `FeatureWorkspaceService` | 评分说明 |

### 需要新增字段

建议 `feature_workspace_service.py` 的 `terminal.knowledge`：

```json
{
  "terminal": {
    "knowledge": {
      "metrics": [
        {"key": "factor_count", "label": "因子总数", "value": 0, "format": "integer"},
        {"key": "category_count", "label": "分类数量", "value": 0, "format": "integer"},
        {"key": "enabled_count", "label": "已启用", "value": 0, "format": "integer"},
        {"key": "feature_version", "label": "协议版本", "value": "v1", "format": "text"}
      ],
      "filters": [],
      "factor_cards": [],
      "factor_details": []
    }
  }
}
```

推荐因子卡格式：

```json
[
  {
    "name": "ema20_gap_pct",
    "display_name": "EMA20 偏离",
    "category": "trend",
    "category_label": "趋势类因子",
    "role": "primary",
    "current_role": "主判断",
    "enabled": true,
    "description": "衡量当前价格相对 EMA20 的偏离。",
    "weight_entry": "trend_weight",
    "risk_note": "单边急涨后容易追高，需要和震荡类因子一起看。"
  }
]
```

### 服务改造点

| 文件 | 改造内容 |
|---|---|
| `services/api/app/services/feature_workspace_service.py` | 新增 `terminal.knowledge` |
| `services/worker/qlib_features.py` | 可逐步补充每个因子的公式、解释、风险提示 |
| `services/api/tests/test_feature_workspace_service.py` | 增加知识库列表和分类测试 |

---

## 5.6 `/strategies` 实盘管理页

### 页面需要的数据

本页不在参考图五张核心页面里，但左侧导航有“实盘管理”。本次后端主要支持终端首页和侧边栏状态。

需要的数据：

- Freqtrade 连接状态。
- 当前运行模式：dry-run / live。
- 当前策略名。
- 持仓数量。
- 余额。
- 风险状态。
- 最近订单。

复用：

| 来源 | 用途 |
|---|---|
| `/api/v1/strategies/workspace` | 执行状态、策略、连接 |
| `/api/v1/positions` | 持仓 |
| `/api/v1/orders` | 订单 |
| `/api/v1/balances` | 余额 |
| `/api/v1/risk-events` | 风险事件 |

建议在 `strategy_workspace_service.py` 新增轻量 `terminal`：

```json
{
  "terminal": {
    "metrics": [
      {"key": "connection_status", "label": "实盘连接", "value": "connected", "format": "status"},
      {"key": "runtime_mode", "label": "运行模式", "value": "live", "format": "text"},
      {"key": "open_positions", "label": "持仓数", "value": 0, "format": "integer"},
      {"key": "risk_status", "label": "风险状态", "value": "normal", "format": "status"}
    ]
  }
}
```

---

## 5.7 `/tasks` 参数优化和运行管理页

### 页面需要的数据

参考图左侧导航有“参数优化”，本项目现有 `/tasks` 更接近运行和自动化管理。本次后端需要让前端能展示：

- 当前自动化周期状态。
- 当前研究任务状态。
- 最近任务列表。
- 最近告警。
- 可执行动作。

复用：

| 来源 | 用途 |
|---|---|
| `/api/v1/tasks/automation` | 自动化状态 |
| `/api/v1/signals/research/runtime` | 研究训练/推理/流水线进度 |
| `automation_service` | 周期、告警、最近结果 |
| `research_runtime_service` | 后台研究任务状态 |

建议 `tasks` 响应补终端结构：

```json
{
  "terminal": {
    "runtime_cards": [],
    "recent_tasks": [],
    "alerts": [],
    "actions": [
      {"key": "run_pipeline", "label": "运行流水线", "method": "POST", "path": "/api/v1/signals/research/pipeline"}
    ]
  }
}
```

---

## 5.8 `/` 终端首页和侧边栏状态

首页和全局侧边栏需要轻量聚合状态。建议先由前端并行调用现有接口，不新增总览接口：

| 状态文案 | 数据来源 | 缺失时 |
|---|---|---|
| 数据更新 | `/api/v1/tasks/automation` | 显示 `--` |
| 控程引擎 | `/api/v1/tasks/automation` | 显示 `--` |
| 实盘连接 | `/api/v1/strategies/workspace` | 显示 `--` |
| GPU 使用 | 当前无真实字段 | 显示 `--` |

后端不要硬编码 GPU 使用率。只有接入真实监控后，才返回具体百分比。

---

## 6. 新增服务设计

### 6.1 `terminal_series_service.py`

建议新增：

`services/api/app/services/terminal_series_service.py`

文件职责：

- 把研究报告里的图表序列转换成前端稳定结构。
- 给每类图表返回 `series` 和 `meta`。
- 对字段做安全类型转换。
- 不生成业务含义上的假数据。

建议方法：

```python
class TerminalSeriesService:
    def build_training_curve(self, report: dict[str, object]) -> dict[str, object]:
        """返回训练曲线。"""

    def build_feature_importance(self, report: dict[str, object]) -> dict[str, object]:
        """返回特征重要性。"""

    def build_backtest_performance_series(
        self,
        report: dict[str, object],
        *,
        backtest_id: str = "latest",
    ) -> dict[str, object]:
        """返回回测净值、基准和回撤序列。"""

    def build_top_candidate_nav_series(
        self,
        report: dict[str, object],
        *,
        limit: int = 5,
    ) -> dict[str, object]:
        """返回 Top N 候选净值对比。"""

    def build_factor_ic_series(self, report: dict[str, object]) -> dict[str, object]:
        """返回因子 IC 序列。"""

    def build_factor_quantile_nav(self, report: dict[str, object]) -> dict[str, object]:
        """返回因子分组收益序列。"""
```

统一返回：

```json
{
  "series": [],
  "meta": {
    "data_quality": "empty",
    "source": "factory-report",
    "warnings": ["series_missing"]
  }
}
```

### 6.2 `terminal_view_helpers.py`

可选新增：

`services/api/app/services/terminal_view_helpers.py`

职责：

- 构造指标卡。
- 构造参数分组。
- 构造统一状态。
- 避免每个 workspace 重复写格式化逻辑。

建议方法：

```python
def metric_card(key: str, label: str, value: object, *, format: str, tone: str = "neutral") -> dict[str, object]:
    """构造统一指标卡。"""

def terminal_state(status: str, *, data_quality: str, warnings: list[str]) -> dict[str, object]:
    """构造统一页面状态。"""
```

这个 helper 不承载业务逻辑，只承载展示格式。

---

## 7. 数据契约规划

### 7.1 指标卡统一格式

```json
{
  "key": "net_return_pct",
  "label": "净收益",
  "value": "3.20",
  "format": "percent",
  "tone": "profit_loss",
  "unit": "%",
  "caption": "扣除手续费和滑点"
}
```

字段规则：

| 字段 | 规则 |
|---|---|
| `key` | 稳定英文 key，前端用于 React key |
| `label` | 中文显示名 |
| `value` | 后端原始值，字符串或数字均可 |
| `format` | `integer`、`decimal`、`percent`、`percent_ratio`、`text`、`status` |
| `tone` | `neutral`、`profit_loss`、`risk`、`success`、`warning`、`danger` |
| `caption` | 可选短说明 |

### 7.2 参数字段统一格式

```json
{
  "key": "fee_bps",
  "label": "手续费",
  "value": "10",
  "unit": "bps",
  "control": "number",
  "options": [],
  "readonly": false
}
```

字段规则：

| 字段 | 规则 |
|---|---|
| `control` | `select`、`number`、`text`、`toggle`、`chips` |
| `options` | select/chips 的候选项 |
| `readonly` | 后端暂不支持前端直接修改时置为 true |

### 7.3 图表统一 meta

```json
{
  "series": [],
  "meta": {
    "data_quality": "empty",
    "source": "factory-report",
    "warnings": ["backtest_series_missing"],
    "updated_at": ""
  }
}
```

`warnings` 建议枚举：

| code | 含义 |
|---|---|
| `training_curve_missing` | 缺训练曲线 |
| `feature_importance_missing` | 缺特征重要性 |
| `backtest_series_missing` | 缺真实回测序列 |
| `candidate_backtest_series_missing` | 缺候选对比序列 |
| `factor_ic_missing` | 缺 IC 序列 |
| `factor_quantile_missing` | 缺分组收益 |
| `config_not_aligned` | 当前配置和最新结果不一致 |

---

## 8. 具体实施阶段

### 阶段 1：建立 terminal 视图骨架

目标：前端能开始按 `item.terminal` 渲染页面，即使部分图表为空。

修改文件：

| 文件 | 动作 |
|---|---|
| `services/api/app/services/terminal_view_helpers.py` | 新增指标卡、参数字段、状态 helper |
| `services/api/app/services/terminal_series_service.py` | 新增空状态序列服务 |
| `services/api/app/services/research_workspace_service.py` | 返回 `terminal` |
| `services/api/app/services/backtest_workspace_service.py` | 返回 `terminal` |
| `services/api/app/services/evaluation_workspace_service.py` | 返回 `terminal` |
| `services/api/app/services/feature_workspace_service.py` | 返回 `terminal` |

验收：

- 四个 workspace 都有 `item.terminal.page`。
- 四个 workspace 都有 `item.terminal.metrics`。
- 缺图表时返回空数组和 warnings。
- 旧字段保持不变。

### 阶段 2：整改回测图表真实性

目标：移除 demo 曲线，避免前端显示假回测。

修改文件：

| 文件 | 动作 |
|---|---|
| `services/api/app/services/backtest_chart_service.py` | 移除 `_generate_demo_curve()`、`_get_demo_statistics()`、`_get_demo_distribution()` 的外部使用 |
| `services/api/app/services/terminal_series_service.py` | 从 report 读取真实 `backtest.series.performance` |
| `services/api/tests/test_backtest_chart_service.py` | 增加缺失数据返回空状态测试 |

验收：

- 没有真实序列时，图表为空。
- 有真实序列时，按真实数据返回。
- 不再出现 `2026-01-01` 固定 demo 曲线。

### 阶段 3：worker 输出图表序列

目标：让前端大图表有真实数据。

修改文件：

| 文件 | 动作 |
|---|---|
| `services/worker/qlib_backtest.py` | 输出净值、基准、回撤、交易分布 |
| `services/worker/qlib_runner.py` | 把序列写入训练结果和候选回测 |
| `services/worker/qlib_experiment_report.py` | 把新增序列纳入统一报告 |
| `services/worker/tests/test_qlib_runner.py` | 增加序列字段测试 |
| `services/worker/tests/test_qlib_backtest.py` | 增加净值和回撤序列测试 |

验收：

- 最新训练报告包含 `latest_training.backtest.series.performance`。
- 候选排行包含候选回测序列或序列引用。
- API 层能读到真实序列。

### 阶段 4：因子研究序列

目标：因子研究页能显示 IC、累计 IC、分组收益。

修改文件：

| 文件 | 动作 |
|---|---|
| `services/worker/qlib_features.py` | 输出因子评估基础统计 |
| `services/worker/qlib_runner.py` | 把因子评估结果纳入训练报告 |
| `services/api/app/services/factor_analysis_service.py` | 读取并聚合因子评估 |
| `services/api/app/services/feature_workspace_service.py` | 返回因子研究 terminal 图表 |
| `services/api/tests/test_feature_workspace_service.py` | 增加 IC 和分组收益字段测试 |

验收：

- `/api/v1/features/workspace` 返回 `terminal.charts.ic_series`。
- 没有因子评估时返回 `factor_ic_missing`。
- 知识库列表不依赖 IC 数据，也能正常展示。

### 阶段 5：补齐导航和运行状态

目标：侧边栏和首页状态不再依赖前端硬编码。

修改文件：

| 文件 | 动作 |
|---|---|
| `services/api/app/services/strategy_workspace_service.py` | 增加实盘终端指标 |
| `services/api/app/services/automation_service.py` | 确认任务页所需字段完整 |
| `services/api/app/routes/tasks.py` | 必要时补 terminal 字段 |
| `services/api/tests/test_strategy_workspace_service.py` | 增加侧边栏状态字段测试 |

验收：

- 前端可从真实接口显示实盘连接状态。
- GPU 使用率没有真实来源时返回 `--` 或空值。
- 任务运行状态和研究运行状态能同时展示。

---

## 9. 测试规划

### 9.1 API 服务测试

新增或扩展测试：

| 测试文件 | 覆盖内容 |
|---|---|
| `services/api/tests/test_research_workspace_service.py` | 模型训练 terminal 字段、参数分组、指标卡 |
| `services/api/tests/test_backtest_workspace_service.py` | 回测 terminal 指标、图表 meta |
| `services/api/tests/test_evaluation_workspace_service.py` | 选币 terminal 指标、候选表、Top N 空状态 |
| `services/api/tests/test_feature_workspace_service.py` | 因子研究、因子知识库 terminal 字段 |
| `services/api/tests/test_backtest_chart_service.py` | 不生成 demo 曲线 |

建议重点断言：

- `terminal.page.title` 存在。
- `terminal.metrics` 是数组。
- 图表缺失时 `series == []`。
- 图表缺失时 warnings 包含对应 code。
- 旧字段仍然存在。

### 9.2 worker 测试

新增或扩展测试：

| 测试文件 | 覆盖内容 |
|---|---|
| `services/worker/tests/test_qlib_backtest.py` | 净值序列、基准序列、回撤序列 |
| `services/worker/tests/test_qlib_runner.py` | 训练输出包含序列引用和样本统计 |
| `services/worker/tests/test_qlib_features.py` | 因子评估统计格式 |
| `services/worker/tests/test_qlib_ranking.py` | 候选排行保留图表所需字段 |

### 9.3 推荐验证命令

本项目 Python 命令默认先进入 Conda `quant` 环境：

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m pytest services/api/tests/test_research_workspace_service.py services/api/tests/test_backtest_workspace_service.py services/api/tests/test_evaluation_workspace_service.py services/api/tests/test_feature_workspace_service.py services/api/tests/test_backtest_chart_service.py
python -m pytest services/worker/tests/test_qlib_runner.py services/worker/tests/test_qlib_ranking.py
```

预期结果：

- API workspace 测试通过。
- worker 训练和候选排序测试通过。
- 如果新增 `qlib_backtest` 或 `qlib_features` 测试，也需要一起通过。

---

## 10. 风险和处理

| 风险 | 影响 | 处理 |
|---|---|---|
| 旧前端依赖旧 workspace 字段 | 页面可能异常 | 新增 `terminal`，不删除旧字段 |
| 图表序列暂时缺失 | 新前端大图表为空 | 返回空状态和 warnings，不伪造数据 |
| worker 输出过大 | API 响应变慢 | 序列只保留前端需要字段，必要时限制点数 |
| 因子 IC 计算复杂 | 开发周期拉长 | 先返回知识库和因子表，IC 作为第二阶段补齐 |
| 配置和结果不对齐 | 前端指标误读 | 使用现有 `config_alignment` 并映射到 `terminal.states.warnings` |
| live 状态敏感 | 错误展示可能误导操作 | 策略和任务页只展示真实接口状态，不硬编码正常 |

---

## 11. 文件级开发清单

### 必改文件

| 文件 | 具体任务 |
|---|---|
| `services/api/app/services/research_workspace_service.py` | 新增模型训练 `terminal` |
| `services/api/app/services/backtest_workspace_service.py` | 新增回测训练 `terminal` |
| `services/api/app/services/evaluation_workspace_service.py` | 新增选币回测 `terminal` |
| `services/api/app/services/feature_workspace_service.py` | 新增因子研究和知识库 `terminal` |
| `services/api/app/services/backtest_chart_service.py` | 停止返回 demo 图表 |
| `services/api/app/services/terminal_series_service.py` | 新增图表序列服务 |
| `services/api/app/services/terminal_view_helpers.py` | 新增终端视图 helper |

### 第二阶段文件

| 文件 | 具体任务 |
|---|---|
| `services/worker/qlib_backtest.py` | 输出真实回测序列 |
| `services/worker/qlib_runner.py` | 写入训练曲线、特征重要性、候选序列 |
| `services/worker/qlib_experiment_report.py` | 把新增序列纳入统一报告 |
| `services/worker/qlib_features.py` | 输出因子评估序列 |
| `services/worker/qlib_ranking.py` | 保留候选展示字段 |

### 可选文件

| 文件 | 具体任务 |
|---|---|
| `services/api/app/services/strategy_workspace_service.py` | 给实盘管理页补 terminal 指标 |
| `services/api/app/routes/tasks.py` | 给任务页补 terminal 结构 |
| `docs/api.md` | 后端实现完成后补充 `terminal` 字段说明 |
| `docs/architecture.md` | 后端实现完成后补充终端视图数据流 |

---

## 12. 与前端规划的字段对应

| 前端页面 | 前端主要区域 | 后端字段 |
|---|---|---|
| `/research` | 参数栏 | `research.workspace.item.terminal.parameters.groups` |
| `/research` | 指标卡 | `research.workspace.item.terminal.metrics` |
| `/research` | 训练曲线 | `research.workspace.item.terminal.charts.training_curve` |
| `/research` | 特征重要性 | `research.workspace.item.terminal.charts.feature_importance` |
| `/backtest` | 参数栏 | `backtest.workspace.item.terminal.parameters.groups` |
| `/backtest` | 收益指标 | `backtest.workspace.item.terminal.metrics` |
| `/backtest` | 净值曲线 | `backtest.workspace.item.terminal.charts.performance` |
| `/evaluation` | 顶部参数条 | `evaluation.workspace.item.terminal.parameters.groups` |
| `/evaluation` | Top N 曲线 | `evaluation.workspace.item.terminal.charts.top_candidate_nav` |
| `/evaluation` | 候选表 | `evaluation.workspace.item.terminal.tables.candidate_rows` |
| `/features` | 因子指标 | `features.workspace.item.terminal.metrics` |
| `/features` | IC 曲线 | `features.workspace.item.terminal.charts.ic_series` |
| `/features` | 分组收益 | `features.workspace.item.terminal.charts.quantile_nav` |
| `/factor-knowledge` | 因子卡片 | `features.workspace.item.terminal.knowledge.factor_cards` |
| `/strategies` | 实盘状态 | `strategies.workspace.item.terminal.metrics` |
| `/tasks` | 运行状态 | `tasks.automation.item.terminal.runtime_cards` |

---

## 13. GLM5 后端执行提示词

可以把下面内容直接交给 GLM5：

```text
请阅读 Quant 项目代码，并按照 docs/2026-05-05-backend-terminal-frontend-support-plan.md 执行后端配套改造。

目标：
1. 为前端终端化复刻补齐后端 terminal 视图模型。
2. 保留现有 /api/v1/*/workspace 接口和旧字段，不破坏现有前端。
3. 在 research/backtest/evaluation/features workspace 的 item 下新增 terminal 字段。
4. 新增 services/api/app/services/terminal_series_service.py，统一处理训练曲线、回测净值、候选净值、因子 IC 和分组收益。
5. 新增 services/api/app/services/terminal_view_helpers.py，统一构造指标卡、参数字段和状态。
6. 修改 backtest_chart_service.py，停止生成 demo 曲线或用总收益反推曲线；没有真实序列时返回空数组和明确 warnings。
7. worker 层逐步补真实序列输出：qlib_backtest.py、qlib_runner.py、qlib_experiment_report.py、qlib_features.py、qlib_ranking.py。
8. 增加或扩展 services/api/tests 和 services/worker/tests，确保 terminal 字段、空状态、真实序列读取、不生成假图表都被覆盖。

约束：
- 不新增依赖。
- 不修改依赖文件和 lockfile。
- 不改 live 交易策略、风控规则和部署配置。
- 代码注释使用中文。
- 所有文件读写使用 UTF-8。
- Python 命令使用 Conda 环境 quant。
- 如果图表没有真实数据，返回 empty/partial 状态，不要制造演示数据。

优先执行顺序：
1. 先做 API terminal 视图骨架和测试。
2. 再改 backtest_chart_service.py 的假数据问题。
3. 再补 worker 真实序列输出。
4. 最后补因子 IC、知识库详情和策略/任务页轻量终端状态。
```

---

## 14. 完成标准

后端改造完成后，应满足：

- `/api/v1/research/workspace` 返回模型训练页可直接渲染的 `terminal`。
- `/api/v1/backtest/workspace` 返回回测训练页可直接渲染的 `terminal`。
- `/api/v1/evaluation/workspace` 返回选币回测页可直接渲染的 `terminal`。
- `/api/v1/features/workspace` 返回因子研究和因子知识库可直接渲染的 `terminal`。
- 图表没有真实数据时，返回空数组和 warnings，不返回演示曲线。
- 旧前端依赖字段仍然存在。
- API 服务测试通过。
- worker 相关测试通过。
- 前端可以优先读取 `item.terminal`，减少页面内的数据二次拼装。
