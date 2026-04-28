# Quant 项目状态文档

> 最后更新：2026-04-29

---

## 当前进度

**状态**：Phase 3/4/5 开发完成，系统可用

**最近完成（2026-04-29）**：
- Agent Team 7个并行Agent开发完成
- Phase 3: 阈值调整(MIN_ENTRY_SCORE 0.70→0.60) + 趋势指标增强(RSI/MACD/成交量)
- Phase 4: 模型建议服务 + 边界场景检测
- Phase 5: 性能监控 + 回测验证 + 多币种支持 + OpenClaw扩展
- Freqtrade 代理配置修复，Dry-run模式正常运行
- Review报告: 395测试通过，代码质量评分A

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

---

## 新增API端点

| 端点 | 方法 | 功能 |
|------|------|------|
| /api/v1/performance | GET | 性能统计 |
| /api/v1/model/status | GET | 模型建议状态 |
| /api/v1/config/pairs | GET | 交易对白名单 |
| /api/v1/backtest/run | POST | 执行回测 |
| /api/v1/strategies/{id}/entry-score | POST | 入场评分 |
| /api/v1/patrol | GET | 定时巡检状态 |
| /api/v1/patrol-history | GET | 巡检历史 |

---

## 测试状态

| 类别 | 结果 |
|------|------|
| 后端测试 | 395 passed (97%) |
| 前端构建 | passed |
| Playwright | 63 passed |
| Review评分 | A |

---

## 待完成任务（P2）

1. **策略实现**：SampleStrategy → 基于研究结论的真实策略
2. **数据分析报表**：每日/每周交易统计、盈亏归因
3. **配置统一管理**：合并api.env、JSON、docker-compose配置
4. **Freqtrade Live模式**：解决ccxt async代理问题

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