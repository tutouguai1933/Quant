# Quant 项目开发任务清单

> 最后更新：2026-04-29
> 状态：所有核心任务已完成，系统可用

---

## 一、高优先级任务（P0 - 已完成）

### 1. 服务器代码同步 ✅
- **完成时间**：2026-04-28
- **方式**：GitHub push/pull
- **最新Commit**：8b66438

### 2. VPN节点自动切换机制 ✅
- **完成时间**：2026-04-27
- **文件**：services/api/app/services/vpn_switch_service.py
- **配置**：QUANT_VPN_WHITELIST_IPS, QUANT_VPN_HEALTH_CHECK_INTERVAL

### 3. 研究到执行自动化 ✅
- **完成时间**：2026-04-27
- **文件**：services/api/app/services/auto_dispatch_service.py
- **配置**：QUANT_AUTO_DISPATCH_ENABLED, QUANT_AUTO_DISPATCH_MIN_SCORE

### 4. 风控熔断机制 ✅
- **完成时间**：2026-04-27
- **文件**：services/api/app/services/risk_guard_service.py
- **配置**：QUANT_RISK_DAILY_MAX_LOSS_PCT

### 5. 交易告警推送 ✅
- **完成时间**：2026-04-27
- **文件**：services/api/app/services/alert_push_service.py
- **支持**：Telegram + Webhook推送

### 6. 门控阈值调整 ✅
- **完成时间**：2026-04-29
- **结果**：MIN_ENTRY_SCORE 0.70→0.60

---

## 二、Phase 3/4/5 开发（已完成）

### Phase 3 - 策略引擎增强 ✅
| 功能 | 文件 | 状态 |
|------|------|------|
| 入场评分计算 | strategy_engine_service.py | ✅ |
| RSI/MACD/成交量趋势 | indicator_service.py | ✅ |
| 仓位动态计算 | strategy_engine_service.py | ✅ |
| 止损追踪机制 | strategy_engine_service.py | ✅ |

### Phase 4 - 模型辅助边界场景 ✅
| 功能 | 文件 | 状态 |
|------|------|------|
| 边界场景检测 | model_suggestion_service.py | ✅ |
| 模型API调用 | model_suggestion_service.py | ✅ |

### Phase 5 - 运维扩展 ✅
| 功能 | 文件 | 状态 |
|------|------|------|
| 性能监控 | performance_monitor_service.py | ✅ |
| 回测验证 | backtest_validation_service.py | ✅ |
| 多币种支持 | config_center_service.py | ✅ |
| OpenClaw巡检 | openclaw_patrol_service.py | ✅ |

---

## 三、低优先级任务（P2 - 待开始）

### 7. 策略实现
- **问题**：SampleStrategy无实际逻辑，交易决策随机
- **状态**：待开始
- **预估工时**：8小时
- **验收标准**：
  - 实现基于研究结论的入场策略
  - 实现动态止损追踪
  - 实现盈亏比触发退出
  - 回测验证策略有效性

### 8. 数据分析报表
- **问题**：无历史数据分析，无法复盘优化
- **状态**：待开始
- **预估工时**：4小时
- **验收标准**：
  - 每日/每周交易统计报表
  - 盈亏归因分析
  - 策略表现对比

### 9. 配置统一管理
- **问题**：配置分散在api.env、多个JSON、docker-compose
- **状态**：待开始
- **预估工时**：2小时
- **验收标准**：
  - 创建统一配置文件
  - 环境变量注入机制
  - 配置变更历史追踪

### 10. Freqtrade Live模式
- **问题**：ccxt async无法通过代理访问Binance私有API
- **状态**：待研究
- **预估工时**：4小时
- **可能的解决方案**：
  - 安装aiohttp-socks使用SOCKS5代理
  - 使用其他代理方案
  - 直接使用公网IP（需Binance白名单）

---

## 四、验收检查清单

### 每次开发完成后需验证：
1. `pnpm build` 构建通过
2. 后端测试通过 (`pytest services/api/tests/`)
3. Freqtrade Dry-run模式运行正常
4. VPN节点连接稳定（出口IP在白名单内）
5. Binance API可正常访问（通过代理）
6. WebSocket实时推送正常
7. OpenClaw巡检正常

---

## 五、关键配置参考

> 详细配置请参考：[docs/CONFIG_CHECKLIST.md](docs/CONFIG_CHECKLIST.md)

### 5.1 环境变量（api.env）
```bash
QUANT_RUNTIME_MODE=dry-run
QUANT_ALLOW_LIVE_EXECUTION=false
QUANT_LIVE_ALLOWED_SYMBOLS=DOGEUSDT
QUANT_LIVE_MAX_STAKE_USDT=6
QUANT_STRATEGY_MIN_ENTRY_SCORE=0.60
QUANT_VPN_WHITELIST_IPS=154.31.113.7,154.3.37.169,202.85.76.66
```

### 5.2 Freqtrade配置文件
| 文件 | 位置 |
|------|------|
| config.base.json | ~/Quant/infra/freqtrade/user_data/ |
| config.deploy.json | ~/Quant/infra/freqtrade/user_data/ |
| config.private.json | ~/Quant/infra/freqtrade/user_data/ |
| config.proxy.json | ~/Quant/infra/freqtrade/user_data/ |

---

## 六、服务器状态

### 服务端口
| 服务 | 端口 | 状态 |
|------|------|------|
| API | 9011 | ✅ |
| Web | 9012 | ✅ |
| Freqtrade | 9013 | ✅ Dry-run |
| mihomo | 7890 | ✅ |

### SSH连接
```bash
sshpass -p "1933" ssh -o StrictHostKeyChecking=no djy@39.106.11.65 "命令"
```