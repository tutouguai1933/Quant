# Quant 运维手册

> **运维快速参考** - 部署、监控、故障排查
>
> 最后更新：2026-05-05

---

## ⚠️ 开发环境架构

### 服务运行位置

**所有服务运行在阿里云服务器 39.106.11.65，不在本地WSL运行。**

| 环境 | IP | 作用 |
|------|-----|------|
| 本地WSL | 动态 | 代码编辑、Git推送 |
| 阿里云服务器 | 39.106.11.65 (公网) / 172.22.73.168 (私网) | 运行所有Docker容器 |

---

## 1. SSH连接

```bash
# 密钥认证（密码登录已禁用）
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65

# Windows PowerShell
ssh -i C:\Users\19332\Desktop\id_aliyun_djy djy@39.106.11.65
```

---

## 2. 容器管理

### 查看状态
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}' --filter "name=quant"
docker logs quant-freqtrade --since 1h
docker inspect quant-api --format '{{.State.Health.Status}}'
```

### 重启服务
```bash
docker restart quant-api quant-freqtrade quant-web
docker restart quant-mihomo quant-openclaw
```

### 健康检查配置
```bash
# Freqtrade健康检查命令
--health-cmd='curl -f -u "Freqtrader:jianyu0.0." http://localhost:9013/api/v1/ping'
--health-interval=30s --health-timeout=10s --health-retries=3
```

---

## 3. Freqtrade操作

### 状态检查
```bash
# 查看持仓
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/status | jq '.[] | {pair, profit_pct}'

# 查看余额
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/balance | jq '.total'

# 查看配置
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/show_config | jq '.stake_amount, .max_open_trades'
```

### 手动操作
```bash
# 强制买入（需要force_entry_enable=true）
curl -X POST -u 'Freqtrader:jianyu0.0.' "http://127.0.0.1:9013/api/v1/forceentry?pair=BTC/USDT"

# 强制卖出
curl -X POST -u 'Freqtrader:jianyu0.0.' "http://127.0.0.1:9013/api/v1/forceexit?tradeid=1"
```

### 配置文件位置
```
infra/freqtrade/user_data/
├── config.live.base.json  # 主配置（端口9013、stake=6、pairs=15）
├── config.private.json    # API密钥和认证
├── config.proxy.mihomo.json  # 代理配置
└── strategies/EnhancedStrategy.py  # 策略代码
```

---

## 4. 代理管理

### 检查状态
```bash
# 当前节点
curl -s 'http://127.0.0.1:9090/proxies/PROXY' | jq '.now'

# 出口IP
curl -s -x http://127.0.0.1:7890 https://api.ipify.org

# 测试Binance连接
curl -s -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping
```

### 切换节点
```bash
# 手动切换
curl -X PUT 'http://127.0.0.1:9090/proxies/PROXY' \
  -H 'Content-Type: application/json' \
  -d '{"name": "JP1"}'
```

### 白名单IP（Binance）
| 节点 | 出口IP |
|------|--------|
| JP1 | 154.31.113.7 ✅ |
| JP2 | 45.95.212.82 ✅ |
| HK2 | 202.85.76.66 ✅ |

---

## 5. 告警系统

### 飞书测试
```bash
curl -X POST http://127.0.0.1:9011/api/v1/feishu/test | jq '.'
```

### 告警来源（已统一）
| 来源 | 频率 | 内容 |
|------|------|------|
| trade_monitor.sh | 每分钟 | 余额、持仓 |
| proxy_switch.sh | 每分钟 | VPN节点 |
| API性能监控 | 实时 | 慢响应(>60s) |

### 查看发送日志
```bash
docker exec quant-api cat /var/log/feishu_send.log | tail -10
```

---

## 6. 监控面板

### Grafana
```bash
# 访问（需SSH隧道）
ssh -L 3000:127.0.0.1:3000 djy@39.106.11.65
# 浏览器打开 http://localhost:3000
# 登录: admin / admin123
```

### Prometheus
```bash
curl -s http://127.0.0.1:9090/api/v1/query?query=freqtrade_total_profit | jq '.'
```

---

## 7. 常见故障排查

### 容器unhealthy
```bash
# 检查健康检查配置
docker inspect quant-freqtrade --format '{{json .Config.Healthcheck}}' | jq '.'
# 重建容器添加健康检查
```

### VPN不可用
```bash
# 查看日志
cat /var/log/proxy_switch.log | tail -10
# 手动切换
curl -X PUT 'http://127.0.0.1:9090/proxies/PROXY' -d '{"name":"JP1"}'
```

### 飞书不推送
```bash
# 检查Webhook配置
curl -s http://127.0.0.1:9011/api/v1/feishu/config | jq '.'
# 检查环境变量
docker exec quant-api env | grep WEBHOOK
```

### API连接失败
```bash
# 检查QUANT_RUNTIME_MODE
docker exec quant-api env | grep RUNTIME
# 应为: QUANT_RUNTIME_MODE=dry-run
# Freqtrade URL: http://127.0.0.1:9013
```

---

## 8. 关键端口

| 服务 | 端口 | 说明 |
|------|------|------|
| API | 9011 | 控制平面 |
| Web | 9012 | 前端 |
| Freqtrade | **9013** | 交易API |
| mihomo代理 | 7890 | HTTP代理 |
| mihomo控制 | 9090 | API控制 |
| Grafana | 3000 | 监控面板 |
| Prometheus | 9090 | 指标存储 |

---

## 9. 定时任务

```bash
# root crontab
* * * * * /usr/local/bin/proxy_switch.sh    # VPN检测
* * * * * /usr/local/bin/trade_monitor.sh   # 余额监控
```

---

## 10. 紧急操作

### 停止所有交易
```bash
# 停止Freqtrade
docker stop quant-freqtrade
```

### 重启全部服务
```bash
docker restart quant-api quant-freqtrade quant-web quant-openclaw quant-mihomo
```

### 查看系统状态
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
curl -s http://127.0.0.1:9011/api/v1/health | jq '.data.summary'
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/balance | jq '.total'
```