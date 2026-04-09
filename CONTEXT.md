# 当前进度

- 当前正在做：`Phase2` 工作台收口，A1 / A2 / A3 / A4 已完成，下一步进入 A5 评估页准入门槛收口。
- 上次停留位置：回测页已经补完“当前回测选择”和“过滤参数目录”，并把浏览器回归用例同步到新页面结构。

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
  - 页面不再本地拼接回测解释，优先展示后端返回的成本模型、过滤摘要和门控目录
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
  - Python 单测通过：`59`
  - 前端生产构建通过：`1`
  - Playwright 回归通过：`40`
  - `/backtest` 真实 HTML 已验证出现“当前回测选择”“过滤参数目录”和最新配置项

# 下一步

- 继续推进 A5：评估页更完整的 dry-run / live 准入门槛
- 然后进入 B 段：把研究结果收成更清楚的决策中心
