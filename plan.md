# Quant 当前计划

这份文件只保留"当前阶段在哪里"和"下一步看哪份文档"。

## 当前阶段

| 阶段 | 状态 |
|------|------|
| phase1 | ✅ 已完成 - 主链打通 |
| phase2 | ✅ 已完成 - 工作台可配置 |
| phase3 | ✅ 已完成 - 综合验收 |
| phase4 | ✅ 已完成 - 前端信息架构重构 |
| phase-i | ✅ 已完成 - 视觉交互统一 |
| phase-j | ✅ 已完成 - 多因子主线补强 |
| phase-k | ✅ 已完成 - 综合验收 |
| 运维完善 | ✅ 已完成 |
| 性能优化 | ✅ 已完成 |
| 周期历史增强 | ✅ 已完成 |

**当前状态**：ML模型参数优化完成，EnhancedStrategy策略优化完成，系统稳定运行

## 最近完成（2026-05-20）

- ML模型参数优化（验证AUC 0.51→0.64）
- EnhancedStrategy参数优化（RSI入场 50→32）
- 训练超时修复（3处超时配置）
- 自动化周期恢复（8天停滞后重新运行）
- 时间框架切换（4h+1h→4h单一时间框架）

## 下一步待办

1. **EnhancedStrategy 亏损观察** - 新参数下观察1-2周表现
2. **数据分析报表** - 每日/每周交易统计
3. **自动化周期稳定性** - 监控不再出现超时失败

## 文档导航

| 文档 | 内容 |
|------|------|
| [AGENTS.md](AGENTS.md) | 开发规则和部署规范 |
| [CONTEXT.md](CONTEXT.md) | 当前系统状态 |
| [README.md](README.md) | 项目概览 |
| [docs/HANDOFF_SESSION.md](docs/HANDOFF_SESSION.md) | 会话接力文档 |
| [docs/roadmap.md](docs/roadmap.md) | 整体规划 |
| [docs/archive/README.md](docs/archive/README.md) | 历史阶段文档 |
