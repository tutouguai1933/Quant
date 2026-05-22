# Quant 项目开发任务清单

> 最后更新：2026-05-23
> 状态：核心功能完成，持续优化中

---

## 一、已完成任务

### 2026-05-23
| 任务 | 文件 | 状态 |
|------|------|------|
| ML模型推理Bug修复(文件路径) | predictor.py | ✅ |
| 类方法缩进Bug修复 | qlib_runner.py | ✅ |
| Backtest Gate修复(ML预测过滤) | qlib_runner.py | ✅ |
| Consistency Gate修复(内部一致性) | qlib_ranking.py | ✅ |
| Validation Gate修复(per-symbol) | qlib_ranking.py, qlib_runner.py | ✅ |
| 门控阈值调整 | qlib_ranking.py | ✅ |
| 成交量同时段对比+阈值0.6 | EnhancedStrategy.py | ✅ |
| ROI代码与配置同步 | EnhancedStrategy.py | ✅ |
| RSI概览1H+TTL过期 | market.py, rsi_cache_service.py, rsi-data-context.tsx | ✅ |
| 运行时目录持久化 | api.env | ✅ |
| 文档全面更新 | 5个md文件 | ✅ |

### 2026-05-20
| 任务 | 文件 | 状态 |
|------|------|------|
| EnhancedStrategy 参数优化 | EnhancedStrategy.json | ✅ |
| ML 模型参数优化 | qlib_config.py | ✅ |
| 训练超时修复 | 3个文件 | ✅ |
| 自动化周期恢复 | automation_state.json | ✅ |
| 时间框架切换（4h+1h→4h） | workbench_config | ✅ |

### 2026-05-08
| 任务 | 文件 | 状态 |
|------|------|------|
| 自动化周期历史增强 | automation_cycle_history_service.py | ✅ |
| 配置管理界面修复 | config_center_service.py | ✅ |

---

## 二、待开始任务（P2）

### 1. 数据分析报表
- **问题**：无历史数据分析
- **预估工时**：4小时

### 2. BNB 仓位清理
- **问题**：NOTIONAL filter 导致 0.007 BNB 无法平仓
- **临时方案**：手动在 Binance 上卖出

### 3. 前端配置修改
- **问题**：配置管理只能查看，不能修改
- **预估工时**：4小时
