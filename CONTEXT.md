# 当前进度

- 当前正在做：`Phase2` 研究工作台收口，A1 / A2 已完成，准备进入 A3 因子细粒度配置。
- 上次停留位置：研究页刚补完“当前研究选择”和“研究模板说明”显化，前后端字段已经统一。

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
- 登录和动作按钮现在显式暴露 `data-hydrated`，浏览器测试会等客户端真正接管事件后再验证 Enter / 点击反馈。
- 自动化状态接口现在补齐 `comparison_run_limit`，任务页和评估页的长期运行配置终于能对齐。
- 当前真实主链仍固定为：`Qlib 研究 -> 候选筛选 -> dry-run -> 小额 live -> 复盘`。
- 这轮 A1 / A2 的验收口径固定为：
  - 后端单测通过：`24`
  - 前端生产构建通过：`1`
  - Playwright 回归通过：`40`
  - 研究页真实保存动作已验证，并已恢复到原配置

# 下一步

- 继续推进 A3：特征页更细的因子配置
- 再推进 A4 / A5：回测参数和准入门槛补全
- 然后进入 B 段：把研究结果收成更清楚的决策中心
