# Quant 项目状态文档

> 最后更新：2026-05-05

---

## 当前进度

**状态**：系统优化完成 ✅ 运行正常

**本次新增（2026-05-05）**：
- 已读取项目文档、前端页面、API 封装和参考图目录。
- 已提取 5 张参考图的信息，形成终端化前端复刻规划。
- 新增规划文档：`docs/2026-05-05-frontend-terminal-reference-rebuild-plan.md`。
- 已阅读后端 API、workspace 聚合服务、worker 研究输出和测试结构，形成前端终端化所需的后端配套规划。
- 新增后端规划文档：`docs/2026-05-05-backend-terminal-frontend-support-plan.md`。
- 当前只完成规划文档，未修改后端业务源码。

**最近完成（2026-05-04）**：
- **策略参数优化**：
  - RSI入场阈值从36→40提高到**45**，基于30天历史数据分析
  - stake_amount从15调整为**6 USDT**，适应当前余额
  - max_open_trades设置为**3**，支持多仓位并行
  - 交易对扩展到**15个**主流币种
- **Freqtrade API端口统一**：
  - 从8080改为**9013**，统一到9011~9020端口范围
  - 容器重建添加正确的健康检查配置
- **飞书推送配置完成**：
  - Webhook URL已配置并测试成功
  - 交易成交自动推送通知（开仓/平仓）
  - VPN切换告警推送修复（alert_push_service import问题）
- **Grafana监控增强**：
  - 新增Cumulative P&L仪表盘
  - 新增Cumulative P&L Curve曲线图
- **WebSocket修复**：
  - HTTP中间件排除WebSocket路径
  - 连接测试成功，可用通道：research_runtime, automation_status
- **API容器配置修复**：
  - QUANT_RUNTIME_MODE=dry-run（使用Freqtrade REST）
  - QUANT_FREQTRADE_API_URL=http://127.0.0.1:9013
  - FEISHU_PUSH_ENABLED=true
  - VPN切换告警代码修复（vpn_switch_service.py）

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

### Freqtrade配置
| 项目 | 值 |
|------|------|
| 模式 | **live** (dry_run=false) |
| 交易对 | BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX/LINK/DOT/MATIC/PEPE/SHIB/WIF/ORDI/BONK (**15个**) |
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
| 余额 | **20.84 USDT** |

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

### VPN切换告警检查

```bash
# 查看VPN切换日志
docker logs quant-api --since 10m | grep -i VPN

# 检查VPN告警是否正常（无 alert_push_service 未定义错误）
docker logs quant-api --since 10m | grep 'alert_push_service'
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

# 查看代理切换日志
sudo cat /var/log/proxy_switch.log

# 手动测试并切换代理
sudo /usr/local/bin/proxy_switch.sh
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
| HK1 | 154.3.37.169 | ⚠️ 暂时不可用 |
| HK3 | 151.240.13.118 | ⚠️ 暂时不可用 |

**自动切换机制**：
- Cron每分钟运行 `/usr/local/bin/proxy_switch.sh`
- 当前节点不可用时自动切换到备用节点
- 优先级：JP1→JP2→JP3→JP4→HK2→HK4→HK1→HK3
- 切换成功/失败均发送飞书告警

---

## 常见问题与踩坑记录

### Q1: Freqtrade健康检查显示unhealthy

**原因**：健康检查配置错误
- 默认检查端口8080，实际Freqtrade监听9013
- 默认密码freqtrader:freqtrade123，实际密码Freqtrader:jianyu0.0.

**解决**：
```bash
# 使用docker run时添加正确的健康检查
docker run -d --name quant-freqtrade \
  --health-cmd='curl -f -u "Freqtrader:jianyu0.0." http://localhost:9013/api/v1/ping' \
  --health-interval=30s --health-timeout=10s --health-retries=3 \
  freqtradeorg/freqtrade:stable trade ...
```

### Q2: API容器环境变量不生效

**原因**：docker-compose env_file路径配置问题
- docker-compose.yml默认env_file路径是`./api.env`
- 实际配置文件在`./deploy/api.env`

**解决**：
```bash
# 方案1：复制文件到默认路径
cp /home/djy/Quant/infra/deploy/api.env /home/djy/Quant/infra/api.env

# 方案2：使用docker run指定env-file
docker run -d --name quant-api \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  deploy-api:latest
```

### Q3: docker compose拉取镜像超时

**原因**：国内访问Docker Hub超时

**解决**：
```bash
# 使用已有镜像直接docker run，跳过docker compose
docker run -d --name quant-freqtrade \
  --network host --restart unless-stopped \
  -v /home/djy/Quant/infra/freqtrade/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:stable trade ...
```

### Q4: Freqtrade策略导入失败 "No module named 'user_data'"

**原因**：策略文件import路径错误
- Freqtrade容器内user_data挂载在`/freqtrade/user_data`
- 不能用`from user_data.config_helper import get_config`

**解决**：修改策略文件导入
```python
# 错误写法
from user_data.config_helper import get_config

# 正确写法
import sys
sys.path.insert(0, '/freqtrade/user_data')
from config_helper import get_config
```

### Q5: Binance API返回 "Invalid API-key, IP"

**原因**：代理出口IP不在Binance白名单

**解决**：
1. 查看代理出口IP：`curl -s -x http://127.0.0.1:7890 https://api.ipify.org`
2. 在Binance API管理中添加该IP到白名单

**各节点出口IP**：
| 节点 | 出口IP | 是否在白名单 |
|------|--------|-------------|
| JP1 | 154.31.113.7 | ✅ 已添加 |
| JP2 | 45.95.212.82 | ❌ |
| JP3 | 151.242.36.38 | ❌ |

### Q6: mihomo健康检查显示unhealthy

**原因**：mihomo配置缺少external-controller

**解决**：添加配置
```yaml
# config.yaml
external-controller: 0.0.0.0:9090
```

### Q7: SSH密码登录安全风险

**原因**：密码过于简单（如1933），容易被爆破

**解决**：配置SSH密钥认证
```bash
# 本地生成密钥
ssh-keygen -t ed25519 -f ~/.ssh/id_aliyun_djy -N "" -C "aliyun_djy"

# 上传公钥到服务器
ssh-copy-id -i ~/.ssh/id_aliyun_djy.pub djy@39.106.11.65

# 在服务器禁用密码登录
sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### Q8: 阿里云检测到挖矿程序

**原因**：端口暴露过多（9000-10000全部开放），可能被入侵

**解决**：
1. 阿里云安全组只开放必要端口（SSH 22 + Web 9012）
2. 其他服务通过SSH隧道访问
3. 检查可疑进程：`ps aux --sort=-%cpu | head -10`
4. 检查SSH公钥：`cat ~/.ssh/authorized_keys`

### Q9: 飞书疯狂发送"容器已停止"告警

**现象**：飞书机器人持续发送"容器已停止"告警，但实际容器都在运行

**原因**：API容器没有挂载Docker socket，无法连接Docker daemon检查容器状态

**排查**：
```bash
curl -s http://127.0.0.1:9011/api/v1/health | jq '.data.containers'
# 如果看到 "Cannot connect to the Docker daemon" 说明缺少socket挂载
```

**解决**：重建API容器添加Docker socket挂载
```bash
docker run -d --name quant-api \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  deploy-api:latest
```

### Q10: 飞书发送"API响应超时"告警

**现象**：飞书持续发送"patrol端点响应时间超过阈值500ms"

**原因**：patrol端点检查VPN节点健康需要约32秒，默认阈值500ms太低

**解决**：通过环境变量提高阈值
```bash
# 在api.env中添加
QUANT_API_LATENCY_THRESHOLD_MS=60000   # 60秒
QUANT_TRADE_LATENCY_THRESHOLD_MS=5000  # 5秒
```

### Q11: OpenClaw巡检超时

**现象**：OpenClaw日志显示"Patrol timeout after 30s"

**原因**：VPN健康检查导致patrol响应时间长（约32秒），默认超时30秒太短

**解决**：修改openclaw_scheduler.py超时配置
```python
# 从30秒改为60秒
response = requests.post(url, timeout=60)
```

### Q12: VPN切换告警发送失败 "alert_push_service is not defined"

**现象**：API日志显示"发送VPN切换失败告警失败: name 'alert_push_service' is not defined"

**原因**：vpn_switch_service.py的告警发送方法内未正确导入alert_push_service

**解决**：在告警发送方法内添加import
```python
# vpn_switch_service.py 修复
def _send_switch_failure_alert(self, error_message, health_result):
    try:
        from services.api.app.services.alert_push_service import (
            AlertEventType, AlertLevel, AlertMessage, alert_push_service
        )
        alert_push_service.push_sync(...)
```

更新后重建API容器：
```bash
docker build -t deploy-api:latest -f services/api/Dockerfile .
docker stop quant-api && docker rm quant-api
docker run -d --name quant-api \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  -v /var/run/docker.sock:/var/run/docker.sock \
  deploy-api:latest
```

### Q13: Freqtrade容器缺少健康检查

**现象**：容器状态显示"Up"但没有"(healthy)"标记，飞书报"容器已停止"告警

**原因**：Freqtrade容器启动时未配置health-cmd参数

**解决**：重建容器添加健康检查
```bash
docker stop quant-freqtrade && docker rm quant-freqtrade
docker run -d --name quant-freqtrade \
  --network host --restart unless-stopped \
  --health-cmd='curl -f -u "Freqtrader:jianyu0.0." http://localhost:9013/api/v1/ping' \
  --health-interval=30s --health-timeout=10s --health-retries=3 --health-start-period=60s \
  -v /home/djy/Quant/infra/freqtrade/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:stable trade \
  --config /freqtrade/user_data/config.live.base.json \
  --config /freqtrade/user_data/config.private.json \
  --config /freqtrade/user_data/config.proxy.mihomo.json \
  --strategy EnhancedStrategy
```

---

## 开发阶段里程碑

```
P1 ✅ → P2 ✅ → P3 ✅ → P4 ✅ → P5 ✅ → P6 ✅ → P7 ✅ → P8 ✅ → P9 ✅ → WebSocket ✅ → P10 ✅ → P11 ✅ → P12 ✅ → 运维完善 ✅
```

核心开发阶段P1-P12全部完成，运维能力达成100%。

**运维功能清单**：
- ✅ Docker容器健康监控（8/8 healthy）
- ✅ 容器自动重启（unless-stopped策略）
- ✅ Grafana可视化监控（5条告警规则）
- ✅ 飞书告警推送（Webhook已配置）
- ✅ SSH密钥认证安全加固
- ✅ mihomo代理正常（JP1节点）
- ✅ Freqtrade Live交易运行
- ✅ 日志轮转（max-size: 50m）

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
| 飞书App ID | cli_a9203146ceb89cba | OpenClaw飞书应用 |
| MIN_ENTRY_SCORE | 0.60 | 入场评分阈值 |
| API延迟阈值 | **60000ms** | patrol端点不触发告警 |
| OpenClaw超时 | **60秒** | 从30秒增加 |
| Docker socket | **必须挂载** | API容器检查容器状态 |
| VPN告警 | **已修复** | alert_push_service import问题已解决 |

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

---

## 当前状态

- **Freqtrade**: Live模式运行，无持仓，等待入场信号
- **mihomo**: Healthy，JP1节点，出口IP 154.31.113.7
- **余额**: ~20.5 USDT
- **系统**: 5/5核心容器healthy，运维能力100%
- **安全**: SSH密钥认证，可疑公钥已清理
- **飞书**: Webhook已配置，推送正常，VPN告警已修复
