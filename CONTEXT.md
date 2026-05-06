# Quant 项目状态文档

> 最后更新：2026-05-06 20:20

---

## 当前进度

**状态**：系统优化完成 ✅ 运行正常

**本次新增（2026-05-06 晚）**：
- **API性能优化**：
  - 新增 TTLCache 服务，RSI摘要缓存60秒
  - Strategy workspace 并行获取账户数据（balances/orders/positions）
  - 执行器运行状态缓存10秒
  - 响应时间从 1m44s 降至 20ms（缓存命中）
- **RSI缓存文件机制**：
  - 新增 `rsi_cache_service.py` 管理预计算RSI结果
  - API优先从缓存文件读取，避免实时调用Binance
  - 新增 `POST /api/v1/market/rsi-cache/refresh` 手动刷新
  - 时间格式改为 `05-06 08:00 进行中`（直观显示K线状态）
- **服务重复问题修复**：
  - 清理 WSL 本地重复的 Docker 容器
  - WSL 本地不再运行 quant-api/quant-web/quant-freqtrade
  - 所有服务统一在服务器运行
- **Patrol认证修复**：
  - 允许内部服务无 token 调用 patrol 端点
  - 修复飞书"容器已停止"告警（HTTP 500 → 200）
- **币种更新**：
  - MATIC 已下线，替换为 POL
- **自动化恢复**：
  - 修复自动化系统暂停状态（从4月30日暂停中恢复）

**本次新增（2026-05-06 早）**：
- 已按 `docs/CODEX_REVIEW_PROMPT.md` 对项目做线上和代码结合审阅。
- 已通过 Playwright、curl、SSH 检查线上页面、API、容器和日志。
- 新增审阅报告：`docs/research/2026-05-06-codex-project-review.md`。
- 关键发现：`/analytics`、`/ops`、`/config` 存在接口路径或契约不一致；`/hyperopt` 后端动作接口缺少认证保护；部分受保护页面可直接访问。

**本次新增（2026-05-05 晚）**：
- **前端 UI 优化完成**：
  - 侧边栏导航修复：添加缺失入口（/ops、/analytics、/config）
  - 命名统一：/signals→"信号"、/strategies→"策略中心"
  - 添加 protected 标记到需要认证的页面
  - 空状态优化：market、balances、orders 页面添加错误提示和引导
  - market/[symbol] 页面改用 TerminalShell 统一风格
  - 面包屑命名与侧边栏分组一致
- **新增参数优化页面**：
  - `/hyperopt` 页面支持 Freqtrade Hyperopt 参数调优
  - 后端新增 `/api/v1/hyperopt/*` API 路由
- **全局 loading 优化**：
  - 更新 `loading.tsx` 使用终端风格骨架屏
  - 优化页面切换体验

**运维能力达成**：100%，所有5个核心容器healthy

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ Healthy |
| 服务器Web | http://39.106.11.65:9012 | ✅ Healthy |
| Freqtrade | http://39.106.11.65:9013 | ✅ **Healthy (Live模式)** |
| mihomo代理 | 127.0.0.1:7890 | ✅ Healthy（JP1节点，自动切换）|
| Prometheus | http://127.0.0.1:9090 | ✅ Healthy |
| Grafana | http://127.0.0.1:3000 | ✅ Healthy |
| 飞书推送 | Webhook已配置 | ✅ **测试成功，推送正常** |
| OpenClaw | 巡检服务 | ✅ Healthy（已修复认证问题） |

### 服务架构

```
服务器 (39.106.11.65)
├── quant-api (FastAPI) - 端口 9011
│   ├── RSI缓存: /app/.runtime/rsi_cache.json
│   ├── 自动化状态: /app/.runtime/automation_state.json
│   └── 并行获取账户数据，响应时间 ~20ms
├── quant-web (Next.js) - 端口 9012
├── quant-freqtrade - API端口 9013 (内部)
├── quant-mihomo - 代理端口 7890, 控制端口 9090
├── quant-prometheus - 端口 9090
├── quant-grafana - 端口 3000
└── quant-openclaw - 巡检服务
```

### 前端页面清单
| 路由 | 页面名称 | 分组 | 认证 |
|------|----------|------|------|
| `/` | 工作台 | 研究 | - |
| `/research` | 模型训练 | 研究 | ✓ |
| `/backtest` | 回测训练 | 研究 | ✓ |
| `/evaluation` | 选币回测 | 研究 | ✓ |
| `/features` | 因子研究 | 研究 | ✓ |
| `/signals` | 信号 | 研究 | - |
| `/hyperopt` | 参数优化 | 研究 | ✓ |
| `/analytics` | 数据分析 | 研究 | - |
| `/data` | 数据管理 | 数据与知识 | - |
| `/factor-knowledge` | 因子知识库 | 数据与知识 | - |
| `/config` | 配置管理 | 数据与知识 | - |
| `/strategies` | 策略中心 | 运营 | ✓ |
| `/ops` | 运维监控 | 运营 | - |
| `/tasks` | 任务 | 运营 | ✓ |
| `/market` | 市场 | 工具 | - |
| `/market/[symbol]` | 市场详情 | 工具 | - |
| `/balances` | 余额 | 工具 | - |
| `/positions` | 持仓 | 工具 | - |
| `/orders` | 订单 | 工具 | - |
| `/risk` | 风险 | 工具 | ✓ |
| `/login` | 登录 | - | - |

### Freqtrade配置
| 项目 | 值 |
|------|------|
| 模式 | **live** (dry_run=false) |
| 交易对 | BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX/LINK/DOT/POL/PEPE/SHIB/WIF/ORDI/BONK (**16个**) |
| stake_amount | **6 USDT** (单笔投入) |
| max_open_trades | **3** (并行仓位) |
| stoploss | -8% |
| 止盈目标 | 8%主目标，120分钟后最低**3%**（已考虑手续费） |
| 订单类型 | **IOC** (Immediate Or Cancel，防止重复挂单) |
| 策略 | EnhancedStrategy |
| RSI入场阈值 | **45** (超卖触发，基于历史数据分析) |
| RSI出场阈值 | **74** |
| 时间框架 | 1H |
| 风控 | 日亏损8.3%限额，连续亏损4次暂停 |
| API端口 | **9013**（9011~9020端口范围）|
| API认证 | Freqtrader:jianyu0.0. |
| 余额 | **~21 USDT** |

---

## 运维指南

### SSH连接（密钥认证）

```bash
# 使用密钥连接（密码登录已禁用）
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65

# Windows PowerShell
ssh -i C:\Users\19332\Desktop\id_aliyun_djy djy@39.106.11.65

# 私钥位置
# - WSL: ~/.ssh/id_aliyun_djy
# - Windows桌面: id_aliyun_djy
```

### 标准部署流程

```bash
# 1. 本地修改代码
git add . && git commit -m "xxx" && git push

# 2. SSH到服务器
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65

# 3. 拉取代码
cd ~/Quant && git pull

# 4. 重新构建并部署
cd infra/deploy
docker compose build api web
docker compose up -d --no-deps api web

# 5. 验证
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

### RSI缓存管理

```bash
# 刷新 RSI 缓存（手动）
curl -X POST 'http://127.0.0.1:9011/api/v1/market/rsi-cache/refresh?interval=1d'

# 查看 RSI 缓存内容
docker exec quant-api cat /app/.runtime/rsi_cache.json | head -50

# 清除 RSI 缓存
docker exec quant-api rm /app/.runtime/rsi_cache.json
```

### 自动化状态管理

```bash
# 查看自动化状态
cat ~/Quant/.runtime/automation_state.json | python3 -m json.tool | head -30

# 恢复自动化（如果暂停）
python3 << 'EOF'
import json
with open('/home/djy/Quant/.runtime/automation_state.json', 'r') as f:
    state = json.load(f)
state['paused'] = False
state['manual_takeover'] = False
state['paused_reason'] = ''
with open('/home/djy/Quant/.runtime/automation_state.json', 'w') as f:
    json.dump(state, f, indent=2)
print('已恢复自动化')
EOF
```

### Freqtrade状态检查

```bash
# 查看Bot状态
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/status

# 查看配置（确认dry_run=false）
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/show_config | jq '.dry_run'

# 查看余额
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/balance | jq '.total'

# 查看持仓
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/status | jq '.[] | {pair, profit_pct}'
```

### 容器管理

```bash
# 查看所有容器状态
docker ps --format 'table {{.Names}}\t{{.Status}}'

# 重启单个容器
docker restart quant-freqtrade

# 查看容器日志
docker logs quant-freqtrade --since 1h

# 检查容器健康检查配置
docker inspect quant-freqtrade --format '{{json .Config.Healthcheck}}' | jq '.'
```

### 飞书推送测试

```bash
# 测试飞书推送
curl -s -X POST http://127.0.0.1:9011/api/v1/feishu/test | jq '.'

# 查看飞书配置状态
curl -s http://127.0.0.1:9011/api/v1/feishu/config | jq '.'

# 查看飞书服务状态
curl -s http://127.0.0.1:9011/api/v1/feishu/status | jq '.'
```

### mihomo代理检查

```bash
# 测试代理连接
curl -s -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping

# 查看当前使用的代理节点
curl -s 'http://127.0.0.1:9090/proxies/PROXY' | jq '.now'

# 查看出口IP
curl -s -x http://127.0.0.1:7890 https://api.ipify.org

# 手动切换代理节点
curl -s -X PUT 'http://127.0.0.1:9090/proxies/PROXY' \
  -H 'Content-Type: application/json' \
  -d '{"name": "JP2"}'
```

### 代理节点出口IP（Binance白名单已完成）

| 节点 | 出口IP | 状态 |
|------|--------|------|
| JP1 | 154.31.113.7 | ✅ 正常 |
| JP2 | 45.95.212.82 | ✅ 正常 |
| JP3 | 151.242.36.38 | ✅ 正常 |
| JP4 | 151.242.36.39 | ✅ 正常 |
| HK2 | 202.85.76.66 | ✅ 正常 |
| HK4 | 151.240.13.123 | ✅ 正常 |

---

## 常见问题与踩坑记录

### Q1: 本地 Docker 服务重复

**现象**：WSL 本地和服务器都在运行 quant-api、quant-web 等服务

**原因**：本地误执行了 `docker compose up -d`

**解决**：
```bash
# 停止并删除本地容器
docker stop quant-web quant-api quant-freqtrade quant-mihomo
docker rm quant-web quant-api quant-freqtrade quant-mihomo

# 确认本地无重复服务
docker ps -a | grep quant
```

### Q2: RSI 摘要请求超时

**现象**：RSI 概览显示 "⚠️ 请求超时..."

**原因**：实时调用 Binance API 获取所有币种 K 线很慢

**解决**：
- RSI 已添加缓存机制，首次请求后缓存 60 秒
- 可手动刷新缓存：`POST /api/v1/market/rsi-cache/refresh`

### Q3: 飞书报 "容器已停止"

**现象**：飞书持续发送 "容器已停止: quant-openclaw"

**原因**：patrol 端点需要认证，openclaw 容器调用时无 token

**解决**：已修改 patrol 端点，允许内部服务无 token 调用

### Q4: 自动化系统暂停

**现象**：选币和交易没有运行

**原因**：4月30日触发风控，自动化进入暂停状态

**解决**：
```bash
# 检查状态
cat ~/Quant/.runtime/automation_state.json | grep paused

# 恢复自动化
python3 -c "
import json
with open('/home/djy/Quant/.runtime/automation_state.json', 'r+') as f:
    state = json.load(f)
    state['paused'] = False
    state['manual_takeover'] = False
    f.seek(0)
    json.dump(state, f, indent=2)
    f.truncate()
print('已恢复')
"
```

### Q5: MATIC 币种数据异常

**现象**：MATIC 显示过时数据

**原因**：MATIC 在 Binance 已升级为 POL

**解决**：已更新配置，将 MATICUSDT 替换为 POLUSDT

---

## 开发阶段里程碑

```
P1 ✅ → P2 ✅ → P3 ✅ → P4 ✅ → P5 ✅ → P6 ✅ → P7 ✅ → P8 ✅ → P9 ✅ → WebSocket ✅ → P10 ✅ → P11 ✅ → P12 ✅ → 运维完善 ✅ → 终端风格重构 ✅ → 性能优化 ✅
```

核心开发阶段P1-P12全部完成，运维能力达成100%，前端终端风格重构完成，API性能优化完成。

**运维功能清单**：
- ✅ Docker容器健康监控（5/5 healthy）
- ✅ 容器自动重启（unless-stopped策略）
- ✅ Grafana可视化监控（5条告警规则）
- ✅ 飞书告警推送（Webhook已配置）
- ✅ SSH密钥认证安全加固
- ✅ mihomo代理正常（JP1节点）
- ✅ Freqtrade Live交易运行
- ✅ 日志轮转（max-size: 50m）
- ✅ 前端终端风格统一
- ✅ API性能优化（缓存机制）
- ✅ RSI缓存文件支持

---

## 关键配置

| 配置 | 值 | 说明 |
|------|------|------|
| SSH认证 | 密钥认证 | 密码登录已禁用 |
| SSH私钥 | ~/.ssh/id_aliyun_djy | Windows桌面也有备份 |
| Freqtrade端口 | **9013** | 健康检查端口 |
| Freqtrade认证 | Freqtrader:jianyu0.0. | API Basic Auth |
| mihomo控制器 | 0.0.0.0:9090 | 健康检查端口 |
| 代理出口IP | 154.31.113.7 | JP1节点，已在白名单 |
| 飞书Webhook | **已配置** | 推送测试成功 |
| RSI缓存 | /app/.runtime/rsi_cache.json | 60秒 TTL |
| 自动化状态 | /app/.runtime/automation_state.json | - |

---

## 参考文档

**核心文档（分层结构）**：
| 文档 | 内容 | 用途 |
|------|------|------|
| [PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | 5分钟项目概览 | 快速理解系统 |
| [OPS_HANDBOOK.md](docs/OPS_HANDBOOK.md) | 运维手册 | 日常运维命令 |
| [DEV_HANDBOOK.md](docs/DEV_HANDBOOK.md) | 开发手册 | 代码结构和API |
| [HANDOVER.md](docs/HANDOVER.md) | **接力开发提示词** | 新Session启动 |
| [ops-troubleshooting.md](docs/ops-troubleshooting.md) | 踩坑记录 | 故障排查 |

**专题文档**：
| 文档 | 内容 |
|------|------|
| docs/feishu-webhook-setup.md | 飞书配置 |
| docs/ccxt-async-proxy-solution.md | CCXT代理方案 |
| docs/2026-05-05-frontend-terminal-reference-rebuild-plan.md | 终端风格重构规划 |

---

## 当前状态

- **Freqtrade**: Live模式运行，等待入场信号
- **mihomo**: Healthy，JP1节点，出口IP 154.31.113.7
- **余额**: ~21 USDT
- **系统**: 5/5核心容器healthy，运维能力100%
- **安全**: SSH密钥认证，可疑公钥已清理
- **飞书**: Webhook已配置，推送正常
- **前端**: 终端风格重构完成，21个页面已迁移
- **API**: 性能优化完成，缓存机制正常
- **自动化**: 已恢复运行
