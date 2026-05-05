# 后端问题清单

> 此文档记录前后端联调测试中发现的后端问题，供后端 session 修复参考。
> 测试日期：2026-05-05
> 更新日期：2026-05-05

---

## 已完成项

### ✅ terminal 字段已实现

所有 workspace 服务已实现 `terminal` 字段：
- `research_workspace_service.py` - `_build_terminal_view` 方法在第528行
- `backtest_workspace_service.py` - `_build_terminal_view` 方法在第177行
- `feature_workspace_service.py` - `_build_terminal_view` 方法在第614行
- `evaluation_workspace_service.py` - `_build_terminal_view` 方法在第2461行

### ✅ health.status 字段已实现

`automation_service.py` 第493-499行已实现 `_compute_health_status` 方法，返回 `status` 字段。

### ✅ terminal_series_service.py 已实现

图表序列服务已实现：
- `build_training_curve()` - 训练曲线
- `build_feature_importance()` - 特征重要性
- `build_backtest_performance_series()` - 回测净值序列
- `build_top_candidate_nav_series()` - Top N 候选净值
- `build_factor_ic_series()` - 因子 IC 序列
- `build_factor_quantile_nav()` - 分组收益序列

### ✅ terminal_view_helpers.py 已实现

帮助函数已实现：
- `metric_card()` - 构造指标卡
- `terminal_state()` - 构造状态
- `build_parameter_group()` - 构造参数分组
- `build_parameter_field()` - 构造参数字段
- `build_chart_meta()` - 构造图表元数据
- `build_terminal_page()` - 构造页面信息

---

## 待优化项

### 1. 图表序列数据来源

**问题描述**:
terminal_series_service 的数据来源于研究报告，但 worker 层可能未保存完整的图表序列数据。

**影响**:
- 当 worker 未保存序列数据时，图表显示空状态
- 需要运行实际训练/回测才能生成数据

**建议修复**:
检查 worker 层是否保存了以下数据：
- `qlib_runner.py` - 保存 `training_metrics.training_curve` 和 `feature_importance`
- `qlib_backtest.py` - 保存 `backtest.series.performance`
- `qlib_features.py` - 保存 `factor_evaluation.ic_series` 和 `quantile_nav`

### 2. 字段名转换（前端已处理）

**问题描述**:
后端返回的字段名与前端期望不完全一致：
- 分位净值：后端 `q1-q5`，前端期望 `Q1-Q5`
- 净值曲线：后端 `strategy_nav`，前端期望 `value`

**当前状态**: 前端已实现字段映射转换

**可选优化**: 在后端统一字段名

### 3. 因子详情字段

**问题描述**:
`FeatureWorkspaceModel.factors` 只包含基础字段，缺少因子知识库需要的详细信息。

**缺失字段**:
- `formula` - 公式说明
- `whyEffective` - 为什么有效
- `howToUse` - 怎么用
- `pitfalls` - 陷阱
- `recommendedWith` - 推荐搭配

**影响页面**: 因子知识库页 (`/factor-knowledge`)

**建议修复**: 扩展 `factors` 返回字段或添加单独查询接口

---

## 相关文档

- 前端终端化重构规划：`docs/2026-05-05-frontend-terminal-reference-rebuild-plan.md`
- 后端配套支持规划：`docs/2026-05-05-backend-terminal-frontend-support-plan.md`
