# 当前进度

- 当前正在做：`hardening-phase1-data` 已合回 `master`，主仓库文档归档、控制平面验收和工作台配置链路已经统一到主线。
- 上次停留位置：合并前主仓库有一批未提交文档改动，已先备份到 `premerge-master-local-docs-2026-04-09`，再完成主线合并和验证。

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
- 登录和动作按钮现在显式暴露 `data-hydrated`，浏览器测试会等客户端真正接管事件后再验证 Enter / 点击反馈。
- 自动化状态接口现在补齐 `comparison_run_limit`，任务页和评估页的长期运行配置终于能对齐。
- 当前真实主链仍固定为：`Qlib 研究 -> 候选筛选 -> dry-run -> 小额 live -> 复盘`。

# 下一步

- 继续推进研究工作台“更完整可配置”的后续阶段
- 继续强化研究结果、执行结果和自动化状态的对齐说明
- 决定是否把当前 `master` 推送到远端
