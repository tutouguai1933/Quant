# Qlib 强制验证 Live 实现计划

关联规格：
- [2026-04-04-qlib-forced-validation-live-design.md](../specs/2026-04-04-qlib-forced-validation-live-design.md)

## Scope
- 新增本地临时强制验证模式。
- 打通一轮 `Qlib -> 训练 -> 推理 -> 统一研究报告 -> dry-run -> 小额 live -> 复盘`。

## Out of Scope
- 不修改正式研究筛选阈值。
- 不扩展轮动或多币同时执行。

## Steps
1. 先写失败测试，锁住“只强制放行一个最佳候选”的行为。
2. 实现 worker 侧候选强制验证标记。
3. 接通 API 推荐、信号派发和复盘对强制验证的识别。
4. 用本地环境跑一轮完整真实链路。
5. 更新进度文档并提交。

## Validation
- `python3 -m unittest services.worker.tests.test_qlib_ranking -v`
- `python3 -m unittest services.api.tests.test_research_service -v`
- `python3 -m unittest services.api.tests.test_signal_service -v`
- `python3 -m unittest services.api.tests.test_api_skeleton -v`
