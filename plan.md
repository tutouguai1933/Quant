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
| ML模型升级 | ✅ 已完成 |
| 门控修复 | ✅ 已完成 |
| EnhancedStrategy优化 | ✅ 已完成 |

**当前状态**：ML模型推理正常（val_auc=0.58），门控逻辑正确，EnhancedStrategy 成交量过滤改进完成，系统稳定运行

## 最近完成（2026-05-23）

- ML模型推理Bug修复（文件路径、类方法缩进）
- 门控逻辑全面审查修复（Backtest/Consistency/Validation Gate）
- 门控阈值调整（与模型实际表现对齐）
- EnhancedStrategy 成交量改为同时段对比
- RSI概览默认周期 1D→1H，缓存TTL过期
- 文档全面更新

## 下一步待办

1. **EnhancedStrategy 交易观察** - 新成交量和ROI参数下观察入场情况
2. **ML模型效果提升** - 当前 val_auc=0.58，观察自动化周期候选能否通过 Gate
3. **BNB 仓位清理** - NOTIONAL filter 导致 0.007 BNB 无法平仓
