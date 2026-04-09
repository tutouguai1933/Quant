# 当前进度

- 当前正在做：`Phase2` 决策中心收口，A1 / A2 / A3 / A4 / A5 / B1 已完成，下一步进入 B2 推荐原因稳定化。
- 上次停留位置：评估页已经把实验历史里的 `研究预设 / 标签预设 / 标签触发口径` 接到真实研究产物，最近两轮对比不再只剩 `n/a`。

# 关键决定

- 当前主真相源固定为：
  - `README.md`
  - `CONTEXT.md`
  - `plan.md`
  - `docs/roadmap.md`
  - `docs/system-flow-guide.md`
  - `docs/architecture.md`
- 合并回主线前，主文档统一使用 `/home/djy/Quant` 和正式端口 `9011-9020`；临时联调端口只作为说明，不再写死在主入口。
- 浏览器验证统一改成生产形态：
  - 前端先 `pnpm build`
  - 再 `pnpm start`
  - `Playwright` 默认单 worker，避免流式工作台页面被并发压垮
- 研究工作台这次新增的真相源是：
  - `selection_story`
  - `research_template_catalog`
  - 标签结构字段：`label_preset_key`、`label_trigger_basis`、`holding_window_label`、`label_target_pct`、`label_stop_pct`
- 特征工作台这次新增的真相源是：
  - `selection_story`
  - `category_catalog`
  - 当研究报告没有 `factor_protocol` 时，自动回退到默认 `FEATURE_PROTOCOL`，继续展示主判断、辅助确认和类别目录
- 回测工作台这次新增的真相源是：
  - `selection_story`
  - `cost_filter_catalog`
  - 页面不再本地拼接回测解释，优先展示后端返回的成本模型、过滤摘要、结果口径和门控目录
- 评估工作台这次新增的真相源是：
  - `selection_story`
  - `threshold_catalog`
  - `gate_matrix.live_gate`
  - 页面现在直接展示当前准入组合、四层门槛摘要和 `live` 门卡点，不再只靠本地占位文案
- 研究运行链这次新增的真相源是：
  - `training_context.parameters.research_preset_key`
  - `training_context.parameters.label_preset_key`
  - `inference_context.input_summary.research_preset_key`
  - `inference_context.input_summary.label_preset_key`
  - 评估页最近训练 / 推理实验、配置差异和自选实验对比，终于能看懂研究预设与标签预设变化
- 登录与动作按钮的浏览器测试不再依赖 `data-hydrated`，统一改成等待真实按钮文案和可见状态，避免测试继续绑定旧 DOM 细节。
- 自动化状态接口现在补齐 `comparison_run_limit`，任务页和评估页的长期运行配置终于能对齐。
- 当前真实主链仍固定为：`Qlib 研究 -> 候选筛选 -> dry-run -> 小额 live -> 复盘`。
- 这轮 A1 / A2 的验收口径固定为：
  - 后端单测通过：`24`
  - 前端生产构建通过：`1`
  - Playwright 回归通过：`40`
  - 研究页真实保存动作已验证，并已恢复到原配置
- 这轮 A3 的验收口径固定为：
  - 后端单测通过：`27`
  - 前端生产构建通过：`1`
  - Playwright 回归通过：`40`
  - 特征页真实页面和配置切换已验证，并已恢复到原配置
- 这轮 A4 的验收口径固定为：
  - Python 单测通过：`60`
  - 前端生产构建通过：`1`
  - Playwright 回归通过：`40`
  - `/backtest` 真实 HTML 已验证出现“当前回测选择”“结果口径”“过滤参数目录”和最新配置项
- 这轮 A5 的验收口径固定为：
  - Python 单测通过：`11`
  - 前端生产构建通过：`1`
  - Playwright 回归通过：`41`
  - `/evaluation` 真实 HTML 已验证出现“当前准入选择”“准入门槛目录”“live 门槛”“门控分解”和 `live 门`
  - `/api/v1/evaluation/workspace` 已验证返回 `selection_story`、`threshold_catalog` 和 `live_gate`
- 这轮 B1 的验收口径固定为：
  - Python 单测通过：`80`
  - Playwright 定向回归通过：`3`
  - 本地真实训练 + 推理已连续重跑 `2` 轮
  - `/api/v1/evaluation/workspace` 已验证最近训练 / 推理实验返回 `research_preset_key`、`label_preset_key`、`label_trigger_basis`
  - `/evaluation` 真实 HTML 已验证最近两轮自选实验对比出现 `baseline_balanced`、`balanced_window` 和 `close`

# 下一步

- 继续推进 B2：把推荐原因压成稳定结论
- 然后进入 B3：把淘汰原因压成稳定结论
