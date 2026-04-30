# Quant 项目状态文档

> 最后更新：2026-05-01

---

## 当前进度

**状态**：P8数据分析 + P9飞书联动监控告警 + WebSocket实时推送完成

**最近完成（2026-05-01）**：
- **WebSocket实时推送**：
  - 后端WebSocket基础设施：ConnectionManager、通道订阅、广播推送
  - 状态变更推送桥接：push_bridge同步到异步桥接
  - 前端WebSocket Context：自动重连、降级轮询
  - 实时状态Hooks：useResearchRuntimeStatus、useAutomationStatus
- **测试修复**：
  - mock scoring gate修复策略引擎测试
  - 全部580测试通过
- **P8 数据分析（Agent Team并行开发）**：
  - 回测可视化：收益曲线、统计指标、交易分布图表
  - 因子分析：因子贡献度、相关性矩阵、有效性评分
  - 交易报告：日报/周报自动生成（Markdown格式）
  - 新增API：9个端点
- **P9 飞书联动监控告警**：
  - 飞书推送：FeishuPushService消息卡片格式
  - OpenClaw联动：巡检结果、VPN状态自动推送飞书
  - 告警升级：INFO→WARNING→ERROR→CRITICAL自动升级
  - 自动恢复：Docker容器异常自动重启、告警静默机制
- **P7 策略增强**：
  - 多策略模板：StrategyBase、TrendStrategy、GridStrategy
  - 动态止损：ATR/标准差波动率计算
  - 入场评分：多因子加权评分模型
- **P6 运维自动化部署**：
  - 健康监控：Docker容器状态监控正常工作
  - 定时巡检：修复RLock死锁问题
- **测试**：580 passed

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ |
| 服务器Web | http://39.106.11.65:9012 | ✅ |
| Freqtrade | http://39.106.11.65:9013 | ✅ **Live模式** |
| mihomo代理 | 127.0.0.1:7890 | ✅ 日本节点 |
| 运维面板 | http://39.106.11.65:9012/ops | ✅ |

### Freqtrade配置
| 项目 | 值 |
|------|------|
| 模式 | **live** (dry_run=false) |
| 交易对 | BTC/USDT, ETH/USDT, SOL/USDT, DOGE/USDT |
| stake_amount | 6 USDT |
| max_open_trades | 4 |
| stoploss | -10% |
| 止盈目标 | +5% |
| 策略 | SampleStrategy |
| 时间框架 | 1H |

---

## 运维指南

### Freqtrade状态检查

```bash
# SSH到服务器
sshpass -p "1933" ssh -o StrictHostKeyChecking=no djy@39.106.11.65

# 查看Bot状态
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/status

# 查看配置（确认dry_run=false）
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/show_config | grep dry_run

# 查看余额
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/balance

# 查看历史交易
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/trades
```

### 日志分析方法

```bash
# 最近日志（检查运行状态）
docker logs quant-freqtrade --since 1h

# 查看交易事件
docker logs quant-freqtrade --since 1h | grep -E 'buy|sell|enter|exit|order'

# 查看错误
docker logs quant-freqtrade --since 1h | grep -E 'error|Error|warning|Warning'

# 查看心跳（确认Bot运行）
docker logs quant-freqtrade --since 10m | grep heartbeat
```

### 重启Freqtrade

```bash
docker restart quant-freqtrade
sleep 20
curl -s -u 'Freqtrader:jianyu0.0.' -X POST http://127.0.0.1:9013/api/v1/start
```

### 清理幽灵交易

如果数据库有dry_run遗留的虚拟交易：

```bash
docker stop quant-freqtrade
rm -f /home/djy/Quant/infra/freqtrade/user_data/tradesv3.*
docker start quant-freqtrade
```

---

## 常见问题

### Q: 为什么订单ID显示 `dry_run_buy_...`？

可能是之前dry_run模式遗留的幽灵交易。清理数据库：
```bash
rm -f /home/djy/Quant/infra/freqtrade/user_data/tradesv3.*
docker restart quant-freqtrade
```

### Q: Bot无法退出交易？

检查实际币安余额是否匹配数据库记录：
```bash
# 查看日志警告
docker logs quant-freqtrade | grep "Not enough amount"
```

### Q: Live模式订单不执行？

确认：
1. API密钥有效（config.private.json）
2. 代理配置正确（config.proxy.mihomo.json）
3. dry_run=false（config.deploy.json）

### Q: Docker构建很慢？

已在Dockerfile配置阿里云镜像加速：
- apt: mirrors.aliyun.com
- pip: mirrors.aliyun.com/pypi/simple/

---

## 后续开发规划

### P8 - 数据分析（2026-05-01完成）

| 任务 | 说明 | 状态 |
|------|------|------|
| 回测可视化 | 收益曲线、统计指标、交易分布图表 | ✅ 完成 |
| 因子分析 | 因子贡献度、相关性矩阵、有效性评分 | ✅ 完成 |
| 交易报告 | 日报/周报自动生成，Markdown格式 | ✅ 完成 |

**新增API端点**：
- GET /api/v1/backtest/{id}/charts - 回测图表
- GET /api/v1/factor/analysis - 因子分析
- GET /api/v1/report/daily/weekly - 交易报告

**新增前端组件**：
- backtest-charts.tsx - 回测图表
- factor-analysis-panel.tsx - 因子分析面板
- report-viewer.tsx - 报告查看器

### P9 - 飞书联动监控告警（2026-05-01完成）

| 任务 | 说明 | 状态 |
|------|------|------|
| 飞书推送集成 | FeishuPushService，消息卡片格式 | ✅ 完成 |
| OpenClaw飞书联动 | 巡检结果、VPN状态自动推送 | ✅ 完成 |
| 告警升级机制 | INFO→WARNING→ERROR→CRITICAL | ✅ 完成 |
| 自动恢复 | Docker容器异常自动重启 | ✅ 完成 |

**新增API端点**：
- POST /api/v1/feishu/test - 测试推送
- GET /api/v1/alert/level - 告警级别
- POST /api/v1/alert/recovery/manual - 手动恢复

**新增前端组件**：
- alert-management-panel.tsx - 告警管理面板

**飞书配置**：
- FEISHU_WEBHOOK_URL - 飞书机器人Webhook URL
- FEISHU_PUSH_ENABLED - 是否启用推送

### P7 - 策略增强（2026-05-01完成）

| 任务 | 说明 | 状态 |
|------|------|------|
| 多策略模板 | StrategyBase、TrendStrategy、GridStrategy | ✅ 完成 |
| 动态止损 | ATR/标准差波动率、自动调整止损比例 | ✅ 完成 |
| 入场评分优化 | 多因子加权评分(RSI/MACD/Volume/Volatility) | ✅ 完成 |

**新增API端点**：
- GET/POST /api/v1/strategy/* - 策略管理
- GET/POST /api/v1/stoploss/* - 止损配置
- GET/POST /api/v1/scoring/* - 评分模型

**新增前端组件**：
- strategy-selector.tsx - 策略选择器
- stoploss-config.tsx - 止损配置面板
- scoring-display.tsx - 评分仪表盘

**测试结果**：68 passed (策略24 + 止损20 + 评分24)

### P6 - 运维自动化（2026-05-01部署完成）

| 任务 | 说明 | 状态 |
|------|------|------|
| 健康监控告警 | Docker容器状态监控，异常推送 | ✅ 完成 |
| 定时巡检触发 | threading.Timer调度巡检 | ✅ 完成（RLock修复） |
| 日志轮转清理 | RotatingFileHandler + docker日志限制 | ✅ 完成 |
| 前端运维面板 | /ops页面展示服务状态 | ✅ 完成 |

**新增API端点**：
- GET /api/v1/health - 健康状态
- POST /api/v1/patrol/start/stop - 巡检控制
- GET /api/v1/logs/status - 日志大小

### P7 - 策略增强（可选）

| 任务 | 说明 |
|------|------|
| 多策略模板 | 趋势/网格/套利策略切换 |
| 动态止损 | 根据波动率调整止损比例 |

### P8 - 数据分析（可选）

| 任务 | 说明 |
|------|------|
| 回测可视化 | 回测结果图表展示 |
| 因子分析 | 分析因子权重对收益影响 |

---

## 开发阶段里程碑

```
P1 ✅ → P2 ✅ → P3 ✅ → P4 ✅ → P5 ✅ → P6 ✅ → P7 ✅ → P8 ✅ → P9 ✅ → WebSocket ✅
```

核心开发阶段P1-P9全部完成，WebSocket实时推送已集成，系统已具备完整的策略管理、数据分析、飞书联动监控告警、实时状态推送能力。

---

## 关键配置

| 配置 | 值 | 说明 |
|------|------|------|
| MIN_ENTRY_SCORE | 0.60 | 入场评分阈值 |
| aiohttp_proxy | http://127.0.0.1:7890 | CCXT async代理格式 |
| PYTHON环境 | conda activate quant | 统一环境 |
| 前端启动 | pnpm start | 不用next dev |
| apt镜像 | mirrors.aliyun.com | 国内加速 |
| pip镜像 | mirrors.aliyun.com/pypi/simple/ | 国内加速 |

---

## 参考文档

| 文档 | 路径 |
|------|------|
| CCXT代理方案 | docs/ccxt-async-proxy-solution.md |
| 部署手册 | docs/deployment-handbook.md |
| 开发手册 | docs/developer-handbook.md |
| 配置清单 | docs/CONFIG_CHECKLIST.md |
| OpenClaw设计 | docs/2026-04-15-openclaw-safe-actions-design.md |

---

## SSH连接

```bash
sshpass -p "1933" ssh -o StrictHostKeyChecking=no djy@39.106.11.65 "命令"
```

---

## 当前状态

- **Freqtrade**: Live模式运行，等待入场信号
- **持仓**: 0/4（空仓）
- **可用资金**: ~14 USDT
- **系统**: 稳定运行
- **挖矿木马**: 已清理