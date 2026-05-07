# Quant 项目开发任务清单

> 最后更新：2026-05-08
> 状态：核心功能完成，持续优化中

---

## 一、已完成任务

### 2026-05-08
| 任务 | 文件 | 状态 |
|------|------|------|
| 自动化周期历史增强 | automation_cycle_history_service.py | ✅ |
| RSI 快照记录 | automation_cycle_history_service.py | ✅ |
| 候选币种列表展示 | automation-cycle-history-card.tsx | ✅ |
| 任务状态显示 | automation-cycle-history-card.tsx | ✅ |
| 拦截原因中文翻译 | automation-cycle-history-card.tsx | ✅ |
| 配置管理界面修复 | config_center_service.py | ✅ |
| 成交量阈值调整 | api.env (0.8) | ✅ |

### 2026-05-06
| 任务 | 文件 | 状态 |
|------|------|------|
| API 性能优化 | ttl_cache_service.py | ✅ |
| RSI 缓存机制 | rsi_cache_service.py | ✅ |
| Patrol 认证修复 | openclaw_patrol_service.py | ✅ |
| 自动化恢复 | automation_state.json | ✅ |

### 2026-05-05
| 任务 | 文件 | 状态 |
|------|------|------|
| 前端 UI 优化 | 多个页面 | ✅ |
| 参数优化页面 | /hyperopt | ✅ |
| 终端风格重构 | TerminalShell | ✅ |

### 更早完成
| 任务 | 状态 |
|------|------|
| 服务器代码同步 | ✅ |
| VPN节点自动切换 | ✅ |
| 研究到执行自动化 | ✅ |
| 风控熔断机制 | ✅ |
| 交易告警推送 | ✅ |
| 门控阈值调整 | ✅ |
| 策略引擎增强 | ✅ |
| 模型辅助边界场景 | ✅ |
| 运维扩展 | ✅ |

---

## 二、待开始任务（P2）

### 1. 策略实现优化
- **问题**：SampleStrategy 无实际逻辑
- **状态**：待开始
- **预估工时**：8小时
- **验收标准**：
  - 基于研究结论的入场策略
  - 动态止损追踪
  - 盈亏比触发退出

### 2. 数据分析报表
- **问题**：无历史数据分析
- **状态**：待开始
- **预估工时**：4小时
- **验收标准**：
  - 每日/每周交易统计报表
  - 盈亏归因分析
  - 策略表现对比

### 3. 前端配置修改
- **问题**：配置管理只能查看，不能修改
- **状态**：待开始
- **预估工时**：4小时
- **验收标准**：
  - 支持修改规则门控参数
  - 支持修改自动化参数
  - 配置变更历史追踪

---

## 三、验收检查清单

每次开发完成后需验证：

- [ ] `pnpm build` 构建通过
- [ ] 后端测试通过
- [ ] Freqtrade 运行正常
- [ ] VPN 节点连接稳定
- [ ] Binance API 可访问
- [ ] WebSocket 推送正常
- [ ] OpenClaw 巡检正常
- [ ] 前端页面交互验证

---

## 四、关键配置参考

### 环境变量（api.env）

```bash
# 规则门控
QUANT_QLIB_RULE_MIN_VOLUME_RATIO=0.8
QUANT_QLIB_RULE_MAX_ATR_PCT=5
QUANT_QLIB_DRY_RUN_MIN_SHARPE=0.25
QUANT_QLIB_DRY_RUN_MIN_WIN_RATE=0.30
QUANT_QLIB_DRY_RUN_MIN_SCORE=0.45

# 自动化
QUANT_PATROL_AUTO_START=true
QUANT_PATROL_INTERVAL_MINUTES=15

# 交易
QUANT_RUNTIME_MODE=live
QUANT_ALLOW_LIVE_EXECUTION=true
QUANT_LIVE_MAX_STAKE_USDT=6
QUANT_LIVE_MAX_OPEN_TRADES=1
```

### 服务端口

| 服务 | 端口 | 状态 |
|------|------|------|
| API | 9011 | ✅ |
| Web | 9012 | ✅ |
| Freqtrade | 9013 | ✅ |
| mihomo | 7890 | ✅ |

---

## 五、服务器状态

```bash
# SSH 连接
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65

# 查看容器状态
docker ps --format 'table {{.Names}}\t{{.Status}}'

# 查看日志
docker logs quant-api --tail 50
docker logs quant-web --tail 50
```
