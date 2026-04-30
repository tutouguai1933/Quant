# Quant 项目状态文档

> 最后更新：2026-04-30

---

## 当前进度

**状态**：P5 开发完成，系统可用

**最近完成（2026-04-30）**：
- **P5 开发**：
  - WebSocket实时推送：替换HTTP轮询，支持多通道订阅
  - 前端图表可视化：4个图表组件（盈亏曲线、策略对比、时间线、归因饼图）
  - 实盘代理方案：CCXT async代理配置文档和测试脚本
  - 安全修复：WebSocket认证保护、通道白名单验证、线程锁保护
- **P4 开发（2026-04-30）**：
  - 测试修复：7个预存测试问题全部解决（464 passed）
  - 多币种扩展：Freqtrade 配置 BTC/ETH/SOL/DOGE 四币种
  - 依赖修复：安装缺失的 httpx 模块
- **P3 开发（2026-04-29）**：
  - 配置迁移：SampleStrategy/analytics_service 使用 get_config() 统一接口
  - 文件锁保护：config_center_service 并发写入安全（4个测试通过）
  - 研究评分集成：入场决策读取 API 评分（本地*0.6 + 研究*0.4）
  - 创建 config_helper.py：Freqtrade 容器独立配置接口
- 测试通过率：464 passed (100%)

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ 运行中 |
| 服务器Web | http://39.106.11.65:9012 | ✅ 运行中 |
| Freqtrade | http://39.106.11.65:9013 | ✅ Dry-run |
| mihomo代理 | 127.0.0.1:7890 | ✅ 日本节点 |
| 本地API | http://127.0.0.1:9011 | ✅ |

### VPN状态
| 项目 | 值 |
|------|------|
| 当前节点 | ★ 日本¹ |
| 出口IP | 154.31.113.7（白名单内） |
| 白名单IP | 39.106.11.65, 202.85.76.66, 154.31.113.7, 154.3.37.169 |

### Freqtrade状态
| 项目 | 值 |
|------|------|
| 模式 | **live** (真实交易) |
| 交易对 | BTC/USDT, ETH/USDT, SOL/USDT, DOGE/USDT |
| stake_amount | 6 USDT |
| max_open_trades | 4 |
| stoploss | -0.1 |
| API端口 | 9013 |
| 状态 | RUNNING |
| 代理 | mihomo 127.0.0.1:7890 |

---

## 已完成功能清单

### Phase 3 - 策略引擎增强
| 功能 | 文件 | 说明 |
|------|------|------|
| 入场评分 | strategy_engine_service.py | MIN_ENTRY_SCORE=0.60 |
| 趋势指标 | indicator_service.py | RSI/MACD/成交量计算 |
| 仓位计算 | strategy_engine_service.py | 动态仓位比例 |
| 止损追踪 | strategy_engine_service.py | 移动止损 |

### Phase 4 - 模型辅助
| 功能 | 文件 | 说明 |
|------|------|------|
| 边界场景检测 | model_suggestion_service.py | score接近阈值时触发 |
| 模型API调用 | model_suggestion_service.py | anthropic/openai支持 |

### Phase 5 - 运维扩展
| 功能 | 文件 | 说明 |
|------|------|------|
| 性能监控 | performance_monitor_service.py | P50/P95/P99延迟 |
| 回测验证 | backtest_validation_service.py | 历史数据回测 |
| 定时巡检 | openclaw_patrol_service.py | OpenClaw安全动作 |

### 基础设施（2026-04-27）
| 功能 | 文件 | 状态 |
|------|------|------|
| VPN自动切换 | vpn_switch_service.py | ✅ |
| 研究到执行自动化 | auto_dispatch_service.py | ✅ |
| 告警推送 | alert_push_service.py | ✅ |
| 风控熔断 | risk_guard_service.py | ✅ |
| 配置中心 | config_center_service.py | ✅ |

### P2 开发（2026-04-29）
| 功能 | 文件 | 状态 |
|------|------|------|
| 真实策略 | SampleStrategy.py | ✅ |
| 数据分析报表 | analytics_service.py | ✅ |
| 配置统一接口 | config_center_service.py | ✅ |
| 安全认证修复 | routes/config.py | ✅ |

---

## 新增API端点

| 端点 | 方法 | 功能 |
|------|------|------|
| /api/v1/performance | GET | 性能统计 |
| /api/v1/model/status | GET | 模型建议状态 |
| /api/v1/config/pairs | GET | 交易对白名单 |
| /api/v1/config/environment | GET | 环境信息 |
| /api/v1/config/value/{key} | GET | 单配置项 |
| /api/v1/config/section/{section}/values | GET | 配置段值 |
| /api/v1/analytics/daily | GET | 每日统计 |
| /api/v1/analytics/weekly | GET | 每周统计 |
| /api/v1/analytics/attribution | GET | 盈亏归因 |
| /api/v1/analytics/performance | GET | 策略表现对比 |
| /api/v1/analytics/history | GET | 交易历史 |
| /api/v1/backtest/run | POST | 执行回测 |
| /api/v1/strategies/{id}/entry-score | POST | 入场评分 |
| /api/v1/patrol | GET | 定时巡检状态 |

### WebSocket端点（P5新增）

| 端点 | 功能 | 认证 |
|------|------|------|
| /ws | 主WebSocket端点，支持多通道订阅 | Token参数 |
| /ws/research_runtime | 研究运行时状态专用通道 | Token参数 |
| /ws/automation | 自动化状态专用通道 | Token参数 |

---

## 测试状态

| 类别 | 结果 |
|------|------|
| 后端测试 | 464 passed (100%) |
| 策略测试 | 17 passed (100%) |
| 数据分析测试 | 25 passed (100%) |
| 前端构建 | passed |
| WebSocket功能 | verified |

所有测试通过，系统稳定可用。

---

## 下一步可选任务

1. **Live模式测试**：使用代理方案进行实盘验证
2. **WebSocket单元测试**：补充WebSocket测试文件
3. **多策略模板**：支持不同策略模板切换
4. **风控增强**：动态风控参数调整

---

## 关键决定记录

1. **Phase 2分层实施**：程序判断90%，模型辅助边界场景10%
2. **巡检节流策略**：同一动作每小时最多3次，连续失败2次停止
3. **OpenClaw安全模式**：只执行白名单低风险动作，不碰交易决策
4. **MIN_ENTRY_SCORE**：从0.70调整到0.60，提高候选通过率
5. **Python环境**：统一使用 `conda activate quant`
6. **前端验收**：使用 `pnpm start`，不与 `next dev` 共用 `.next`

---

## 参考文档

- **配置清单**：[docs/CONFIG_CHECKLIST.md](docs/CONFIG_CHECKLIST.md) - 所有配置项详细记录
- **部署手册**：[docs/deployment-handbook.md](docs/deployment-handbook.md)
- **开发手册**：[docs/developer-handbook.md](docs/developer-handbook.md)
- **OpenClaw设计**：[docs/2026-04-15-openclaw-safe-actions-design.md](docs/2026-04-15-openclaw-safe-actions-design.md)
- **CCXT代理方案**：[docs/ccxt-async-proxy-solution.md](docs/ccxt-async-proxy-solution.md) - P5新增

---

## SSH连接服务器

```bash
sshpass -p "1933" ssh -o StrictHostKeyChecking=no djy@39.106.11.65 "命令"
```

---

## 下一步

系统现已可用，可继续：
- 真实联调：运行研究训练观察候选排序
- 因子调整：修改因子权重观察推荐币变化
- 回测验证：检查训练结果中的回测指标
- **Live模式测试**：使用代理方案进行实盘验证（见 docs/ccxt-async-proxy-solution.md）
- WebSocket推送：已完成，支持实时状态更新