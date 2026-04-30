# Quant 项目状态文档

> 最后更新：2026-04-30

---

## 当前进度

**状态**：P5 开发完成，Live模式运行

**最近完成（2026-04-30）**：
- **P5 开发**：
  - WebSocket实时推送：Token认证、通道白名单、线程锁保护
  - 前端图表可视化：4个图表组件（盈亏曲线、策略对比、时间线、归因饼图）
  - CCXT代理方案：async版本使用 `aiohttp_proxy` 配置
  - Live模式切换：真实交易已激活
  - 幽灵交易清理：解决dry_run遗留虚拟交易问题
- **测试**：464 passed (100%)

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ |
| 服务器Web | http://39.106.11.65:9012 | ✅ |
| Freqtrade | http://39.106.11.65:9013 | ✅ **Live模式** |
| mihomo代理 | 127.0.0.1:7890 | ✅ 日本节点 |

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

---

## 已完成功能

| 阶段 | 核心功能 |
|------|----------|
| P1 | VPN切换、自动化调度、告警推送、风控熔断、配置中心 |
| P2 | SampleStrategy策略、数据分析API、配置统一接口 |
| P3 | 文件锁保护、研究评分集成(本地×0.6+研究×0.4) |
| P4 | 测试修复、多币种扩展(BTC/ETH/SOL/DOGE) |
| P5 | WebSocket推送、前端图表、代理方案、Live模式 |

---

## 关键配置

| 配置 | 值 | 说明 |
|------|------|------|
| MIN_ENTRY_SCORE | 0.60 | 入场评分阈值 |
| aiohttp_proxy | http://127.0.0.1:7890 | CCXT async代理格式 |
| PYTHON环境 | conda activate quant | 统一环境 |
| 前端启动 | pnpm start | 不用next dev |

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