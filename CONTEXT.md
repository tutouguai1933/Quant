# Quant 项目状态文档

> 最后更新：2026-04-29

---

## 当前进度

**状态**：P3 开发完成，系统可用

**最近完成（2026-04-29）**：
- **P3 开发**：
  - 配置迁移：SampleStrategy/analytics_service 使用 get_config() 统一接口
  - 文件锁保护：config_center_service 并发写入安全（4个测试通过）
  - 研究评分集成：入场决策读取 API 评分（本地*0.6 + 研究*0.4）
  - 创建 config_helper.py：Freqtrade 容器独立配置接口
- **P2 开发**：
  - 策略实现：SampleStrategy → 真实策略（25个测试通过）
  - 数据分析报表：5个新API端点
  - 配置统一管理：get_config()统一接口
  - 安全修复：配置更新接口认证保护
- **联调验证修复**：
  - MIN_ENTRY_SCORE：0.7 → 0.60
  - Freqtrade dry_run：false → true
  - 服务器代码同步：6 commits 已合并
- 测试通过率：486/493 (98.6%)

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
| 模式 | dry_run=true |
| 交易对 | DOGE/USDT |
| stake_amount | 6 USDT |
| max_open_trades | 1 |
| stoploss | -0.1 |
| API端口 | 9013 |
| 状态 | RUNNING |

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

---

## 测试状态

| 类别 | 结果 |
|------|------|
| 后端测试 | 445 passed (98.4%) |
| 策略测试 | 17 passed (100%) |
| 数据分析测试 | 25 passed (100%) |
| 前端构建 | passed |
| Review评分 | B+ |

**剩余7个失败测试为预存问题**，不影响P2功能。

---

## 待完成任务（P3 - 可选优化）

1. **统一配置接口迁移**：让 SampleStrategy 和 AnalyticsService 使用 get_config()
2. **并发写入文件锁**：config_center_service 写入保护
3. **策略研究评分集成**：从 API 获取研究评分到策略入场决策

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
- Live模式：研究解决ccxt async代理问题