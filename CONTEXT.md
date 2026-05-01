# Quant 项目状态文档

> 最后更新：2026-05-02

---

## 当前进度

**状态**：运维能力完善 ✅ 完成

**最近完成（2026-05-02）**：
- **SSH安全加固**：密钥认证配置，禁用密码登录，删除可疑公钥
- **Freqtrade健康检查修复**：端口从8080改为9013，密码配置正确
- **飞书Webhook配置**：配置完成并测试推送成功
- **API容器env_file修复**：修复docker-compose env_file路径问题
- **mihomo健康检查修复**：添加external-controller端口9090
- **Binance代理IP白名单**：JP1节点出口IP `154.31.113.7` 已在白名单
- **飞书告警问题修复**：
  - API容器缺少Docker socket导致误报容器停止
  - OpenClaw超时从30秒增加到60秒
  - API延迟阈值从500ms提高到60秒
- **运维能力达成**：100%，所有8个容器healthy

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ Healthy |
| 服务器Web | http://39.106.11.65:9012 | ✅ Healthy |
| Freqtrade | http://39.106.11.65:9013 | ✅ **Healthy (Live模式)** |
| mihomo代理 | 127.0.0.1:7890 | ✅ Healthy（JP1节点）|
| Prometheus | http://127.0.0.1:9090 | ✅ Healthy |
| Grafana | http://127.0.0.1:3000 | ✅ Healthy |
| 飞书推送 | Webhook已配置 | ✅ 测试成功 |

### Freqtrade配置
| 项目 | 值 |
|------|------|
| 模式 | **live** (dry_run=false) |
| 交易对 | BTC/USDT, ETH/USDT, SOL/USDT, DOGE/USDT |
| stake_amount | 6 USDT |
| max_open_trades | 1 |
| stoploss | -10% |
| 止盈目标 | +5% |
| 策略 | SampleStrategy |
| 时间框架 | 1H |
| API端口 | **9013**（注意：健康检查用此端口）|
| API认证 | Freqtrader:jianyu0.0. |

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
```

### mihomo代理检查

```bash
# 测试代理连接
curl -s -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping

# 查看当前使用的代理节点
curl -s 'http://127.0.0.1:9090/proxies/PROXY' | jq '.now'

# 查看出口IP
curl -s -x http://127.0.0.1:7890 https://api.ipify.org

# 切换代理节点
curl -s -X PUT 'http://127.0.0.1:9090/proxies/PROXY' \
  -H 'Content-Type: application/json' \
  -d '{"name": "JP2"}'
```

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
| 飞书Webhook | 已配置 | 推送测试成功 |
| MIN_ENTRY_SCORE | 0.60 | 入场评分阈值 |
| API延迟阈值 | **60000ms** | patrol端点不触发告警 |
| OpenClaw超时 | **60秒** | 从30秒增加 |
| Docker socket | **必须挂载** | API容器检查容器状态 |

---

## 参考文档

| 文档 | 路径 |
|------|------|
| 部署手册 | docs/deployment-handbook.md |
| 开发手册 | docs/developer-handbook.md |
| 飞书配置 | docs/feishu-webhook-setup.md |
| CCXT代理方案 | docs/ccxt-async-proxy-solution.md |

---

## 当前状态

- **Freqtrade**: Live模式运行，ETH持仓盈利11.88%
- **mihomo**: Healthy，JP1节点，出口IP 154.31.113.7
- **余额**: ~20.8 USDT
- **系统**: 8/8容器healthy，运维能力100%
- **安全**: SSH密钥认证，可疑公钥已清理