# 当前进度

- 当前正在做：把 `hardening-phase1-data` 合回 `master`，并在主仓库重新跑一轮完整验证。
- 上次停留位置：`hardening-phase1-data` 已完成提交和工作树验证，但主仓库因为本地未提交文档改动无法直接合并。

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

- 解决当前主线合并冲突并完成合并提交
- 在 `master` 上重跑后端测试和前端生产形态验证
- 确认备份分支是否还有未吸收的独立内容
