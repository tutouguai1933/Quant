# Quant 项目配置清单

> 最后更新：2026-04-29
> 目的：确保所有配置项可追溯，避免遗漏

---

## 一、服务器基础设施配置

### 1.1 SSH 连接
| 项目 | 值 |
|------|------|
| 服务器IP | 39.106.11.65 |
| 用户名 | djy |
| 密码 | 1933 |
| 连接命令 | `sshpass -p "1933" ssh -o StrictHostKeyChecking=no djy@39.106.11.65 "命令"` |

### 1.2 Docker 服务端口
| 服务 | 端口 | 状态 |
|------|------|------|
| API | 9011 | ✅ 运行中 |
| Web | 9012 | ✅ 运行中 |
| Freqtrade | 9013 | ✅ Dry-run模式 |
| mihomo代理 | 7890 | ✅ 日本节点 |
| mihomo控制 | 9090 | ✅ 运行中 |

### 1.3 VPN / mihomo 代理配置
| 项目 | 值 |
|------|------|
| 当前节点 | ★ 日本¹ |
| 出口IP | 154.31.113.7 |
| 代理地址 | http://127.0.0.1:7890 |
| 控制API | http://127.0.0.1:9090 |
| 白名单IP | 39.106.11.65, 202.85.76.66, 154.31.113.7, 154.3.37.169 |

**切换节点命令**：
```bash
curl -X PUT http://127.0.0.1:9090/proxies/BestSSR -d '{"name":"★ 日本¹"}'
```

**验证出口IP**：
```bash
curl -x http://127.0.0.1:7890 https://api.ipify.org
```

---

## 二、Binance API 配置

### 2.1 API 密钥
| 项目 | 值 |
|------|------|
| API Key | djuPgTW90bbowvm8lAYF5Vaa79ZZh7k6Z6Nvqa9mRzuraANnbUsd58QZpfn1e3MB |
| API Secret | UgHHpFhwQtCBlXCVWP8hhLZvc4FoxWAsLdJh6qTpxHXqFF3fsU0JOI5s1Si86sJc |
| 认证状态 | ✅ 正常 |
| 可交易 | True |

### 2.2 IP 白名单要求
- VPN 出口IP必须在白名单内
- 当前白名单：39.106.11.65, 202.85.76.66, 154.31.113.7, 154.3.37.169

---

## 三、Freqtrade 配置

### 3.1 配置文件结构（服务器路径：~/Quant/infra/freqtrade/user_data/）

| 文件 | 用途 | 关键内容 |
|------|------|----------|
| config.base.json | 基础配置 | dry_run=true, timeframe=1h, pair_whitelist |
| config.deploy.json | 部署覆盖 | max_open_trades, stake_amount |
| config.private.json | 私密信息 | API keys, api_server认证 |
| config.proxy.json | 代理配置（默认） | ccxt代理设置 |
| config.proxy.mihomo.json | mihomo代理 | aiohttp_proxy配置 |
| config.proxy.noop.json | 无代理 | 空文件 |

### 3.2 当前生效配置（合并后）
```json
{
  "bot_name": "quant-spot-dryrun",
  "dry_run": true,
  "dry_run_wallet": 1000,
  "max_open_trades": 1,
  "stake_currency": "USDT",
  "stake_amount": 6,
  "timeframe": "1h",
  "stoploss": -0.1,
  "trading_mode": "spot",
  "exchange": {
    "name": "binance",
    "key": "REDACTED",
    "secret": "REDACTED",
    "enable_ws": false,
    "ccxt_config": {
      "enableRateLimit": true,
      "proxies": {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890"
      }
    },
    "ccxt_async_config": {
      "enableRateLimit": true,
      "aiohttp_proxy": "http://127.0.0.1:7890",
      "proxies": {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890"
      }
    },
    "pair_whitelist": ["DOGE/USDT"]
  },
  "api_server": {
    "enabled": true,
    "listen_ip_address": "0.0.0.0",
    "listen_port": 9013,
    "username": "Freqtrader",
    "password": "jianyu0.0."
  }
}
```

### 3.3 API 认证
| 项目 | 值 |
|------|------|
| 用户名 | Freqtrader |
| 密码 | jianyu0.0. |
| JWT Secret | 0dc1ae357fb56d3a8738da4ab3f7a7e06d7b9dc837866cd1dec5979e7d393097 |
| WS Token | 14a83cb840c444e339b3c262d2b081f046567cb4294e684bcb4dac2b894cecc0 |

### 3.4 常用 API 端点
```bash
# Ping
curl -u Freqtrader:jianyu0.0. http://127.0.0.1:9013/api/v1/ping

# 启动Bot
curl -u Freqtrader:jianyu0.0. -X POST http://127.0.0.1:9013/api/v1/start

# 停止Bot
curl -u Freqtrader:jianyu0.0. -X POST http://127.0.0.1:9013/api/v1/stop

# 查看状态
curl -u Freqtrader:jianyu0.0. http://127.0.0.1:9013/api/v1/status

# 查看配置
curl -u Freqtrader:jianyu0.0. http://127.0.0.1:9013/api/v1/show_config
```

---

## 四、API 服务配置（api.env）

### 4.1 运行模式
| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| QUANT_RUNTIME_MODE | dry-run | 运行模式 |
| QUANT_MARKET_SYMBOLS | BTCUSDT,ETHUSDT,SOLUSDT,DOGEUSDT | 关注的币种 |

### 4.2 Binance 配置
| 配置项 | 当前值 |
|--------|--------|
| BINANCE_API_KEY | （从Freqtrade private config读取） |
| BINANCE_API_SECRET | （从Freqtrade private config读取） |
| QUANT_BINANCE_MARKET_BASE_URL | https://api.binance.com |
| QUANT_BINANCE_ACCOUNT_BASE_URL | https://api.binance.com |
| QUANT_BINANCE_TIMEOUT_SECONDS | 10 |

### 4.3 Live 执行配置
| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| QUANT_ALLOW_LIVE_EXECUTION | false | 是否允许真实交易 |
| QUANT_LIVE_ALLOWED_SYMBOLS | DOGEUSDT | 允许交易的币种 |
| QUANT_LIVE_MAX_STAKE_USDT | 6 | 单笔最大金额 |
| QUANT_LIVE_MAX_OPEN_TRADES | 1 | 最大持仓数 |

### 4.4 VPN 自动切换配置
| 配置项 | 当前值 |
|--------|--------|
| QUANT_MIHOMO_API_URL | http://mihomo:9090 |
| QUANT_MIHOMO_PROXY_URL | http://mihomo:7890 |
| QUANT_VPN_HEALTH_CHECK_URL | https://api.binance.com/api/v3/ping |
| QUANT_VPN_HEALTH_CHECK_INTERVAL | 60 |
| QUANT_VPN_WHITELIST_IPS | 154.31.113.7,154.3.37.169,202.85.76.66 |
| QUANT_VPN_AVAILABLE_NODES | 香港¹,香港²,日本¹,日本²,美国¹,美国² |

### 4.5 自动派发配置
| 配置项 | 当前值 |
|--------|--------|
| QUANT_AUTO_DISPATCH_ENABLED | false |
| QUANT_AUTO_DISPATCH_INTERVAL | 300 |
| QUANT_AUTO_DISPATCH_MIN_SCORE | 0.7 |
| QUANT_AUTO_DISPATCH_MAX_DAILY | 5 |
| QUANT_AUTO_DISPATCH_REQUIRE_DRY_RUN_GATE | true |
| QUANT_AUTO_DISPATCH_REQUIRE_LIVE_GATE | false |

### 4.6 策略引擎配置
| 配置项 | 当前值 | 说明 |
|--------|--------|------|
| QUANT_STRATEGY_MIN_ENTRY_SCORE | 0.7 → 0.60 | 入场最低评分 |
| QUANT_STRATEGY_TRAILING_STOP_TRIGGER | 0.02 | 移动止损触发阈值 |
| QUANT_STRATEGY_TRAILING_STOP_DISTANCE | 0.01 | 移动止损距离 |
| QUANT_STRATEGY_PROFIT_EXIT_RATIO | 0.05 | 盈利退出比例 |
| QUANT_STRATEGY_MAX_HOLDING_HOURS | 48 | 最大持仓时长 |
| QUANT_STRATEGY_BASE_POSITION_RATIO | 0.25 | 基础仓位比例 |
| QUANT_STRATEGY_MAX_POSITION_RATIO | 0.50 | 最大仓位比例 |

### 4.7 风控熔断配置
| 配置项 | 当前值 |
|--------|--------|
| QUANT_RISK_DAILY_MAX_LOSS_PCT | 3 |
| QUANT_RISK_MAX_TRADES_PER_DAY | 5 |
| QUANT_RISK_CRASH_THRESHOLD_PCT | 5 |

### 4.8 告警推送配置
| 配置项 | 当前值 |
|--------|--------|
| QUANT_ALERT_ENABLED | true |
| QUANT_ALERT_TELEGRAM_TOKEN | （待配置） |
| QUANT_ALERT_TELEGRAM_CHAT_ID | （待配置） |
| QUANT_ALERT_WEBHOOK_URL | （待配置） |

### 4.9 模型建议配置
| 配置项 | 当前值 |
|--------|--------|
| QUANT_MODEL_SUGGESTION_ENABLED | false |
| QUANT_MODEL_THRESHOLD_RANGE | 0.05 |
| QUANT_MODEL_PROVIDER | anthropic |
| QUANT_MODEL_TIMEOUT_SECONDS | 30 |
| QUANT_MODEL_MAX_TOKENS | 1024 |

---

## 五、管理后台配置

| 配置项 | 当前值 |
|--------|--------|
| QUANT_ADMIN_USERNAME | admin |
| QUANT_ADMIN_PASSWORD | 1933 |
| QUANT_SESSION_TTL_SECONDS | 604800 (7天) |

---

## 六、已完成的服务文件清单

| 服务文件 | 功能 | 状态 |
|----------|------|------|
| strategy_engine_service.py | 入场评分、仓位计算、止损追踪 | ✅ |
| analytics_service.py | 每日/周统计、盈亏归因 | ✅ |
| config_center_service.py | 统一配置管理、多币种白名单 | ✅ |
| vpn_switch_service.py | VPN自动切换 | ✅ |
| risk_guard_service.py | 风控熔断 | ✅ |
| alert_push_service.py | 告警推送（Telegram/Webhook） | ✅ |
| auto_dispatch_service.py | 自动派发 | ✅ |
| indicator_service.py | RSI/MACD/成交量趋势 | ✅ |
| performance_monitor_service.py | API延迟追踪、P50/P95/P99 | ✅ |
| backtest_validation_service.py | 历史数据回测 | ✅ |
| model_suggestion_service.py | 边界场景检测 | ✅ |
| openclaw_patrol_service.py | 定时巡检 | ✅ |

---

## 七、新增 API 端点清单

| 端点 | 方法 | 功能 |
|------|------|------|
| /api/v1/performance | GET | 性能统计数据 |
| /api/v1/model/status | GET | 模型建议状态 |
| /api/v1/config/pairs | GET | 交易对白名单 |
| /api/v1/backtest/run | POST | 执行回测 |
| /api/v1/strategies/{id}/entry-score | POST | 入场评分计算 |
| /api/v1/patrol | GET | 定时巡检状态 |
| /api/v1/patrol-history | GET | 巡检历史 |
| /api/v1/patrol-counters | GET | 巡检计数器 |
| /api/v1/patrol-reset | POST | 重置巡检计数 |

---

## 八、本地开发配置

### 8.1 Python 环境
| 项目 | 值 |
|------|------|
| 环境名称 | quant |
| 激活命令 | `conda activate quant` |
| 注意 | 不使用 `.venv` |

### 8.2 本地端口
| 服务 | 端口 |
|------|------|
| API | 9011 |
| Web | 9012 |
| Freqtrade | 9013 |

### 8.3 前端开发
| 项目 | 值 |
|------|------|
| 构建命令 | `pnpm build` |
| 启动命令 | `pnpm start` |
| 注意 | 验收使用 `pnpm start`，不与 `next dev` 共用 `.next` |

---

## 九、已知问题与注意事项

### 9.1 Freqtrade Live 模式代理问题
- **问题**：ccxt async 无法通过 HTTP 代理访问 Binance 私有 API (`sapi/v1/capital/config/getall`)
- **现状**：使用 dry_run 模式运行
- **解决方案待定**：
  - 尝试 SOCKS5 代理（需安装 aiohttp-socks）
  - 或使用环境变量 HTTP_PROXY 让 curl 可用，但 ccxt async 仍失败

### 9.2 配置文件权限
- 服务器上 `~/Quant/infra/freqtrade/user_data/` 目录属 www 用户
- 需要通过 docker 或特殊方式修改配置文件

### 9.3 mihomo 配置
- 配置文件：服务器 `/root/mihomo/config.yaml`
- MMDB 下载：有时会超时，需使用简化配置避免 GEOIP 规则

---

## 十、运维命令速查

### 10.1 重启服务
```bash
# 重启所有服务
cd ~/Quant/infra/deploy && docker compose restart

# 重启单个服务
docker compose restart api
docker compose restart web
docker compose restart freqtrade
docker compose restart mihomo
```

### 10.2 查看日志
```bash
docker logs quant-api --tail 50
docker logs quant-web --tail 50
docker logs quant-freqtrade --tail 50
docker logs quant-mihomo --tail 50
```

### 10.3 同步代码
```bash
# 本地推送
git push origin master

# 服务器拉取
ssh djy@39.106.11.65 "cd ~/Quant && git pull"
```