# 研究/回测/评估配置入口补全

## 1. Summary
- 补齐 Phase2 研究、回测、评估三个工作台的配置入口：分别加上 holding_window_label 下拉、回测成本模型选择、评估 gate 开关，并把 API 类型补全让前端安全读取新字段，从而满足前端测试和用户预期。

## 2. Goals / Non-goals
- Goals:
  1. P0 在 Research 配置卡里新增“持有窗口标签”下拉，默认读当前配置值。
  2. P0 在 Backtest 配置卡里新增“成本模型”下拉，回显当前假设并继续通过 `update_workbench_config` 提交。
  3. P0 在 Evaluation 准入门槛卡里增加 enable_rule/validation/backtest/consistency/live gate 开关，去掉重复的“实验对比与复盘窗口”卡片，保留唯一的操作窗口表述。
  4. P1 补齐 `/apps/web/lib/api.ts` 中 Research/Backtest/Evaluation 模型的 controls 类型和 normalize 逻辑，确保新增字段有默认值、可读性、并为前端提供 bool/string 数据。
  5. P0 tests/test_frontend_refactor.py 必须在新增字段后继续通过。
- Non-goals:
  1. 不触及后端 Python 代码或工作台服务实现。
  2. 不调整现有后端接口地址或提交动作，继续沿用 `/actions update_workbench_config`。

## 3. Current State & Constraints
- 当前 Research/Backtest/Evaluation 页面在配置区少了上述字段，用户不能在 front-end 直接选 holding_window_label/cost_model，也看不到 gate 开关，tests 中的断言会失效。
- apps/web/lib/api.ts 的 Research/Backtest/Evaluation 类型只声明部分 controls，normalizeXxxModel 仅返回数值字段，gate 开关无法安全读取。
- 工作目录是 `/home/djy/Quant/.worktrees/hardening-phase1`，不能改后端 Python、不能自动执行依赖安装。命令尽量用已有工具（如 pnpm、python 虚拟环境）。

## 4. Requirements
- Functional requirements:
  1. P0 Research 页面新增 `name="holding_window_label"` 的下拉，显示 1-3d、2-4d、3-5d，默认值优先取 workspace.controls；选项改动后提交至 `section=research`。
  2. P0 Backtest 页面新增 `name="cost_model"` 的下拉，选项包括 `round_trip_basis_points`、`single_side_basis_points`、`zero_cost_baseline`，默认回填 workspace.assumptions 或 config 中的值。
  3. P0 Evaluation 页面准入门槛卡保持原有数字输入，新增 enable_rule/validation/backtest/consistency/live gate checkbox，确保每个字段始终提交；移除多余的“实验对比与复盘窗口”卡片，保留单个 operations 配置卡且继续提供 review_limit/comparison_run_limit。
  4. P1 `apps/web/lib/api.ts` 中的 Research/Backtest/Evaluation 模型类型补全新字段，normalizeXxxModel 需读出新字段并提供默认结果，避免前端 `controls` 访问报错。
  5. P0 tests/test_frontend_refactor.py 在前端变更后仍全部通过。
- Non-functional requirements:
  1. 最大复用已有 WorkbenchConfigCard、ConfigSelect/ConfigCheckboxGrid 组件，避免视觉跳动。
  2. 保持字段命名与现有 action 兼容（`name="holding_window_label"`，`name="cost_model"`，`name="enable_*"` 等）。
  3. 前端输入控件应提供明确提示文案，保持终端语气。
- Compatibility/migration requirements: Frontend 变更必须兼容现有 `/actions update_workbench_config` 表单解析逻辑，勿引入新的接口。

## 5. Design
- Overall approach: 在现有 WorkbenchConfigCard 里增设对应字段，Research 用 `ConfigSelect` 提供 holding_window 标签、Backtest 用 `ConfigSelect` 提供成本模型、Evaluation thresholds 卡片底部插入 `ConfigCheckboxGrid` 来体现 gate 开关、operations 卡片合并一次说明并保留两个数字字段。API 层在 `apps/web/lib/api.ts` 补齐类型并在 normalize 函数中返回新增字段，前端可直接从 `workspace.controls` 读取值。
- Key decisions:
  1. Gate 开关放在准入门槛卡片内，保持一张卡即可而不是额外卡片，减少页面高度；checkbox 方案比 select 更适合双状态。
  2. cost_model/holding_window 字段使用固定选项列表（同服务器常量）以便 UI 可稳定显示选项。
  3. `apps/web/lib/api.ts` normalize 函数在读取 `controls` 时提供布尔默认值（true/false），避免 undefined。
- Alternatives:
  1. 把 gate 开关拆出新卡片单独强调，代价是操作区域扩展，用户需要多滑动才能看到全部门槛。
 2. 用 select（启用/禁用）代替 checkbox，虽然和数值字段一致，但阅读体验不如 toggle/checkbox。
 3. 不在前端维护 const options，而是从 API 增加 `available_holding_windows`/`available_cost_models`，需要后端变更，而目前不可修改。
- Impact scope: `/home/djy/Quant/.worktrees/hardening-phase1/apps/web/app/research/page.tsx`, `/.../apps/web/app/backtest/page.tsx`, `/.../apps/web/app/evaluation/page.tsx`, `/.../apps/web/lib/api.ts`, `/.../tests/test_frontend_refactor.py`。

## 6. Acceptance Criteria
1. Research 页面展示 `ConfigSelect` 选择 holding_window_label，HTML 包含 `name="holding_window_label"` 且选项有 1-3d/2-4d/3-5d，默认值来源于 workspace。
2. Backtest 页面展现 `name="cost_model"` 的 select，options 包含三种成本模型，并默认填 workspace.assumptions 或 controls。
3. Evaluation 页面只有一个“实验对比与复盘窗口”表单卡片，thresholds 卡补 gate checkbox，HTML 包含 `name="enable_rule_gate"`、`enable_validation_gate`、`enable_backtest_gate`、`enable_consistency_gate`、`enable_live_gate`。
4. `apps/web/lib/api.ts` 相关类型定义和 normalize 函数覆盖新字段，不再有 TypeScript 错误。
5. `tests/test_frontend_refactor.py` 包含相关断言并全部通过。

## 7. Validation Strategy
- 候选命令：
  1. `.venv/bin/python -m pytest tests/test_frontend_refactor.py`（在 `.worktrees/hardening-phase1` 目录下运行，验证前端字符串断言）。
  2. `pnpm test` 不是必须，但可选择在本地现有环境中跑 `pnpm test` 以防其他 front-end 测试受影响。

## 8. Risks & Rollback
- 风险：gate checkbox 位置/文案和后端期望不一致，可能导致用户保存后以为生效但后端忽略。回退策略：恢复 evaluation 页面 gate 区域和 API 字段修改，验证 tests。
- 风险：API 类型补全忘记处理某个字段导致 front-end runtime 报错。回退策略：撤销 `apps/web/lib/api.ts` 的相关增加并恢复到之前的 normalize 行为。

## 9. Open Questions
- gate 开关是否应与门槛数值放在同一张卡片，还是单独分组？（已问，待确认）。

## 10. References
- 研究页面：`/home/djy/Quant/.worktrees/hardening-phase1/apps/web/app/research/page.tsx`
- 回测页面：`/home/djy/Quant/.worktrees/hardening-phase1/apps/web/app/backtest/page.tsx`
- 评估页面：`/home/djy/Quant/.worktrees/hardening-phase1/apps/web/app/evaluation/page.tsx`
- 类型/normalize：`/home/djy/Quant/.worktrees/hardening-phase1/apps/web/lib/api.ts`
- 前端测试：`/home/djy/Quant/.worktrees/hardening-phase1/tests/test_frontend_refactor.py`
