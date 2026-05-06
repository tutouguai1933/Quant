# 服务架构文档

> 最后更新：2026-05-06

---

## 服务清单

| 服务 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| API | quant-api | 9011 | FastAPI 后端服务 |
| Web | quant-web | 9012 | Next.js 前端服务 |
| Freqtrade | quant-freqtrade | 9013 | 量化交易引擎 |
| mihomo | quant-mihomo | 7890/9090 | 代理服务 |
| Prometheus | quant-prometheus | 9090 | 监控数据收集 |
| Grafana | quant-grafana | 3000 | 可视化监控 |
| OpenClaw | quant-openclaw | - | 巡检服务 |

---

## 网络架构

```
                        ┌─────────────────────────────────────┐
                        │          服务器 39.106.11.65         │
                        │                                     │
    浏览器 ──────────────┼──► quant-web (9012)                 │
                        │         │                           │
                        │         ▼                           │
                        │    quant-api (9011)                 │
                        │         │                           │
                        │    ┌────┴────┐                      │
                        │    ▼         ▼                      │
                        │ Freqtrade  mihomo                   │
                        │  (9013)     (7890)                  │
                        │    │         │                      │
                        │    └────┬────┘                      │
                        │         ▼                           │
                        │    Binance API                      │
                        └─────────────────────────────────────┘
```

---

## 缓存机制

### RSI 缓存

**文件位置**: `/app/.runtime/rsi_cache.json`

**TTL**: 60 秒

**API 端点**:
- `GET /api/v1/market/rsi-summary?interval=1d` - 获取 RSI 摘要
- `POST /api/v1/market/rsi-cache/refresh?interval=1d` - 手动刷新缓存

**数据结构**:
```json
{
  "items": [
    {
      "symbol": "BTCUSDT",
      "rsi": 68.2,
      "state": "neutral",
      "signal": "hold",
      "time": "05-06 08:00 进行中"
    }
  ],
  "total": 16,
  "interval": "1d",
  "updated_at": "2026-05-06T12:00:00Z",
  "cached_at": "2026-05-06T12:00:00Z"
}
```

### 执行器运行状态缓存

**TTL**: 10 秒

**说明**: Freqtrade 连接状态、订单数、持仓数等

### 账户状态缓存

**TTL**: 15 秒

**说明**: 并行获取 balances、orders、positions

---

## 自动化状态

**文件位置**: `/app/.runtime/automation_state.json`

**关键字段**:
```json
{
  "mode": "auto_live",
  "paused": false,
  "manual_takeover": false,
  "paused_reason": ""
}
```

**恢复命令**:
```bash
python3 -c "
import json
with open('/home/djy/Quant/.runtime/automation_state.json', 'r+') as f:
    state = json.load(f)
    state['paused'] = False
    state['manual_takeover'] = False
    f.seek(0)
    json.dump(state, f, indent=2)
    f.truncate()
"
```

---

## 认证机制

### 前端认证

- 登录页: `/login`
- 密码: 配置在 `QUANT_ADMIN_PASSWORD`
- Cookie: `quant_admin_token`
- Token 有效期: 7 天

### API 认证

- 大部分读取接口无需认证
- 写入接口需要认证（如执行动作、修改配置）
- Patrol 端点允许内部服务无 token 调用

### Freqtrade 认证

- 用户名: `Freqtrader`
- 密码: `jianyu0.0.`
- Basic Auth

---

## 监控告警

### 飞书推送

- Webhook 已配置
- 告警类型: 容器状态、VPN切换、交易通知
- 测试命令: `curl -X POST http://127.0.0.1:9011/api/v1/feishu/test`

### Grafana 仪表盘

- 访问: `http://127.0.0.1:3000`（需 SSH 隧道）
- 告警规则: 5 条

### Prometheus 指标

- 访问: `http://127.0.0.1:9090`（需 SSH 隧道）
- 采集间隔: 15 秒

---

## 常用运维命令

```bash
# 查看所有容器状态
docker ps --format 'table {{.Names}}\t{{.Status}}'

# 重启服务
docker restart quant-api quant-web

# 查看日志
docker logs quant-api --tail 100 -f

# 检查健康状态
curl http://127.0.0.1:9011/health
curl http://127.0.0.1:9012/
curl -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/ping

# 刷新 RSI 缓存
curl -X POST 'http://127.0.0.1:9011/api/v1/market/rsi-cache/refresh'
```
