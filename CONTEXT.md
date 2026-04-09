# 当前进度

- 当前正在做：`Phase2` 工作台收口，A1 / A2 / A3 已完成，下一步进入 A4 回测成本与过滤参数。
- 上次停留位置：特征页已经补完“当前因子选择”和“因子类别目录”，并收了默认因子协议兜底。

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
- 登录和动作按钮现在显式暴露 `data-hydrated`，浏览器测试会等客户端真正接管事件后再验证 Enter / 点击反馈。
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

# 下一步

- 继续推进 A4：回测页更完整的成本模型和过滤参数
- 再推进 A5：评估页更完整的 dry-run / live 准入门槛
- 然后进入 B 段：把研究结果收成更清楚的决策中心
