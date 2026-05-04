# 运维踩坑记录

> 本文档记录运维过程中遇到的问题和解决方案，避免重复踩坑。
>
> **最后更新：2026-05-04**

---

## 0. 最新变更（2026-05-04）

### 0.1 系统优化汇总

| 优化项 | 变更前 | 变更后 | 说明 |
|--------|--------|--------|------|
| **RSI入场阈值** | 36→40 | **45** | 增加入场机会，基于30天历史数据分析 |
| **stake_amount** | 15 USDT | **6 USDT** | 适应当前20.5 USDT余额 |
| **交易对白名单** | 4个 | **15个** | BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX/LINK/DOT/MATIC/PEPE/SHIB/WIF/ORDI/BONK |
| **max_open_trades** | 1 | **3** | 并行多仓位 |
| **Freqtrade API端口** | 8080 | **9013** | 统一到9011~9020端口范围 |
| **飞书Webhook** | 未配置 | **已配置** | 交易成交通知推送 |
| **Grafana面板** | 基础面板 | **新增盈亏面板** | Cumulative P&L仪表盘和曲线图 |
| **WebSocket** | 断开 | **已修复** | 中间件排除WebSocket路径 |
| **VPN告警** | 发送失败 | **已修复** | alert_push_service import问题 |
| **订单类型** | limit | **IOC** | 防止重复挂单问题 |
| **ROI最低阈值** | 2% | **3%** | 扣除手续费后仍有合理利润 |

### 0.2 重复订单问题（2026-05-04发现）

**现象**：币安订单历史显示SHIB有2笔买入（5721930334和5721930336），但Freqtrade只追踪了一笔

**排查过程**：
```bash
# 查询币安完整订单历史
docker exec quant-freqtrade python3 -c "
import ccxt.async_support as ccxt
import asyncio
async def main():
    binance = ccxt.binance({...})
    orders = await binance.fetch_orders('SHIB/USDT', since=binance.milliseconds() - 86400000*2)
    for o in orders:
        print(f'订单ID: {o[\"id\"]}, 类型: {o[\"side\"]}, 时间: {o[\"datetime\"]}')
    await binance.close()
asyncio.run(main())
"

# 查看Freqtrade日志是否有订单创建记录
docker logs quant-freqtrade --since 30h | grep "Order.*created.*SHIB"
```

**根本原因**：
1. 订单5721930334在Freqtrade日志中完全没有记录，来源不明
2. 可能是网络重试导致币安收到两次请求
3. 策略代码`self.logger`未定义导致custom_stake_amount异常

**解决方案**：
1. 配置IOC订单防止重复挂单：
```json
// config.live.base.json
"order_time_in_force": {
  "entry": "IOC",
  "exit": "IOC"
}
```

2. 修复策略logger问题：
```python
# EnhancedStrategy.py
import logging

class EnhancedStrategy(IStrategy):
    logger = logging.getLogger(__name__)  # 添加这行
```

**验证**：
```bash
curl -s -u 'Freqtrader:jianyu0.0.' 'http://127.0.0.1:9013/api/v1/show_config' | jq '.minimal_roi'
# 应显示IOC配置
```

### 0.3 ROI未考虑手续费问题（2026-05-04发现）

**现象**：SHIB交易盈利2.06%，但扣除0.2%手续费后净收益仅1.86%

**原因分析**：
```
买入手续费: 0.1%
卖出手续费: 0.1%
总手续费: 0.20%

原ROI配置:
120分钟后: ROI 2.0% → 净收益 1.80% ❌ 太低
```

**解决方案**：提高最低ROI到3%
```python
# EnhancedStrategy.py
minimal_roi = {
    "0": 0.08,    # 8% → 净收益7.80%
    "30": 0.05,   # 5% → 净收益4.80%
    "60": 0.04,   # 4% → 净收益3.80%
    "120": 0.03   # 3% → 净收益2.80% ✅
}
```

**验证**：
```bash
curl -s -u 'Freqtrader:jianyu0.0.' 'http://127.0.0.1:9013/api/v1/show_config' | jq '.minimal_roi'
```

**现象**：飞书告警"Unable to create trade for SHIB/USDT: Available balance lower than stake amount"

**原因**：
- stake_amount=15 USDT，但余额只有20.5 USDT
- max_open_trades=3，需要45 USDT总余额

**解决**：降低stake_amount到6 USDT，单笔仓位变小，3仓位需要18 USDT足够

### 0.3 飞书推送频率限制

**现象**：飞书返回`{'code': 11232, 'msg': 'frequency limited'}`

**原因**：短时间内发送过多推送触发飞书频率限制

**解决**：推送间隔控制，避免频繁推送

### 0.4 VPN切换告警修复

**现象**：API日志显示"发送VPN切换失败告警失败: name 'alert_push_service' is not defined"

**原因**：vpn_switch_service.py的告警发送方法内未正确导入alert_push_service模块

**解决**：在告警发送方法内部添加import语句
```python
def _send_switch_failure_alert(self, error_message, health_result):
    try:
        from services.api.app.services.alert_push_service import (
            AlertEventType, AlertLevel, AlertMessage, alert_push_service
        )
        alert_push_service.push_sync(...)
```

### 0.5 Freqtrade容器健康检查修复

**现象**：容器状态显示"Up"但没有"(healthy)"标记，飞书报"容器已停止: quant-freqtrade"告警

**原因**：Freqtrade容器启动时未配置health-cmd参数

**解决**：重建容器添加正确的健康检查
```bash
docker run -d --name quant-freqtrade \
  --health-cmd='curl -f -u "Freqtrader:jianyu0.0." http://localhost:9013/api/v1/ping' \
  --health-interval=30s --health-timeout=10s --health-retries=3 --health-start-period=60s \
  ...
```

### 0.6 VPN节点名称不匹配导致切换失败

**现象**：飞书告警"VPN节点自动切换失败: 所有节点尝试失败，已尝试: []"

**原因**：vpn_switch_service.py中DEFAULT_AVAILABLE_NODES使用中文Unicode名称（日本¹、香港²），与实际mihomo节点名称（JP1、HK1）不匹配

**解决**：更新DEFAULT_AVAILABLE_NODES使用实际节点名称
```python
DEFAULT_AVAILABLE_NODES = [
    "JP1", "JP2", "JP3", "JP4",  # 日本节点
    "HK1", "HK2", "HK3", "HK4",  # 香港节点
    "IEPL-HK", "IPLC-JP",        # 专线节点
]
```

---

## 1. Docker容器问题

### 1.1 Freqtrade健康检查unhealthy

**现象**：容器显示`unhealthy`，但API正常响应

**原因**：
- 健康检查端口配置错误（8080 vs 9013）
- 健康检查认证密码错误（freqtrader:freqtrade123 vs Freqtrader:jianyu0.0.）

**排查命令**：
```bash
# 查看健康检查配置
docker inspect quant-freqtrade --format '{{json .Config.Healthcheck}}' | jq '.'

# 测试健康检查端点
docker exec quant-freqtrade curl -f -u "Freqtrader:jianyu0.0." http://localhost:9013/api/v1/ping
```

**解决**：使用docker run添加正确的健康检查参数
```bash
docker run -d --name quant-freqtrade \
  --network host --restart unless-stopped \
  --health-cmd='curl -f -u "Freqtrader:jianyu0.0." http://localhost:9013/api/v1/ping' \
  --health-interval=30s --health-timeout=10s --health-retries=3 --health-start-period=30s \
  -v /home/djy/Quant/infra/freqtrade/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:stable trade --config ...
```

### 1.2 API容器环境变量不生效

**现象**：`docker exec quant-api env | grep FEISHU`返回空

**原因**：docker-compose.yml中env_file路径默认为`./api.env`，实际文件在`./deploy/api.env`

**排查命令**：
```bash
# 检查docker-compose env_file配置
grep -A20 'api:' docker-compose.yml | grep env_file

# 检查env文件位置
ls -la deploy/api.env
```

**解决**：
```bash
# 方案1：复制到默认路径
cp deploy/api.env api.env

# 方案2：使用docker run直接指定
docker run -d --name quant-api \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  deploy-api:latest
```

### 1.3 docker compose镜像拉取超时

**现象**：`docker compose up`时报`context deadline exceeded`

**原因**：国内访问Docker Hub超时

**解决**：使用已有镜像直接docker run
```bash
# 查看已有镜像
docker images

# 直接运行，不使用compose
docker run -d --name quant-api ...
```

---

## 2. Freqtrade策略问题

### 2.1 策略导入失败

**现象**：`No module named 'user_data'`

**原因**：容器内user_data路径为`/freqtrade/user_data`，import路径不正确

**解决**：修改策略文件
```python
# 错误
from user_data.config_helper import get_config

# 正确
import sys
sys.path.insert(0, '/freqtrade/user_data')
from config_helper import get_config
```

### 2.2 Binance连接认证失败

**现象**：`{"code":-2015,"msg":"Invalid API-key, IP, or permissions for action."}`

**原因**：代理出口IP不在Binance白名单

**排查命令**：
```bash
# 查看代理出口IP
curl -s -x http://127.0.0.1:7890 https://api.ipify.org

# 测试Binance连接
curl -s -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping
```

**解决**：在Binance API管理中添加出口IP到白名单

---

## 3. mihomo代理问题

### 3.1 mihomo健康检查unhealthy

**现象**：容器显示`unhealthy`

**原因**：缺少`external-controller`配置

**解决**：添加配置
```yaml
external-controller: 0.0.0.0:9090
```

### 3.2 mihomo GEOIP下载失败

**现象**：`can't download MMDB: context deadline exceeded`

**原因**：使用GEOIP规则需要下载MMDB文件，国内网络超时

**解决**：使用域名规则代替GEOIP规则，避免MMDB下载
```yaml
rules:
  # 使用域名规则，不用GEOIP
  - DOMAIN-SUFFIX,binance.com,PROXY
  - DOMAIN-SUFFIX,aliyun.com,DIRECT
  # 不使用 GEOIP,CN,DIRECT 这种规则
```

---

## 4. SSH安全问题

### 4.1 SSH连接超时

**现象**：`Connection timed out during banner exchange`

**根本原因**：
1. SSH `MaxStartups` 默认值太小（10:30:100），并发连接超过10个开始拒绝
2. 内存不足（1.6Gi）导致系统响应慢
3. Agent Team多agent同时SSH连接触发限制

**已修复方案**（2026-05-02）：
```bash
# 1. 增加Swap到2G
sudo fallocate -l 1G /swapfile2
sudo chmod 600 /swapfile2
sudo mkswap /swapfile2
sudo swapon /swapfile2
echo '/swapfile2 none swap sw 0 0' | sudo tee -a /etc/fstab

# 2. 修复SSHD配置
sudo tee -a /etc/ssh/sshd_config << 'EOF'
MaxStartups 100:30:200
MaxSessions 50
LoginGraceTime 60
EOF
sudo systemctl restart ssh
```

### 4.2 可疑SSH公钥

**现象**：发现注释为随机字符串的公钥（如`skp-2zejcn8s5ke54kabc8nj`）

**排查命令**：
```bash
# 检查所有用户的authorized_keys
cat ~/.ssh/authorized_keys
sudo cat /root/.ssh/authorized_keys

# 检查文件创建时间
ls -la ~/.ssh/authorized_keys
sudo ls -la /root/.ssh/authorized_keys
```

**解决**：删除可疑公钥
```bash
sed -i '/可疑注释/d' ~/.ssh/authorized_keys
```

---

## 5. 阿里云安全问题

### 5.1 挖矿程序告警

**现象**：收到阿里云邮件"挖矿程序，已拦截"

**排查命令**：
```bash
# 检查CPU使用率异常进程
ps aux --sort=-%cpu | head -15

# 检查挖矿关键词进程
ps aux | grep -iE 'xmrig|minerd|kdevtmpfsi|kinsing'

# 检查可疑网络连接
netstat -tunlp | grep ESTABLISHED
```

**预防措施**：
1. 阿里云安全组只开放必要端口
2. SSH禁用密码登录，使用密钥认证
3. 定期检查进程和网络连接

---

## 6. 飞书推送问题

### 6.1 飞书疯狂发送"容器已停止"告警

**现象**：飞书机器人持续发送"容器已停止: quant-api"等告警，但实际容器都在运行

**根本原因**：API容器没有挂载Docker socket，无法连接Docker daemon检查容器状态

**排查命令**：
```bash
# 测试health端点，看是否有Docker连接错误
curl -s http://127.0.0.1:9011/api/v1/health | jq '.data.containers'

# 如果看到 "Cannot connect to the Docker daemon" 说明缺少socket挂载
```

**解决**：重建API容器添加Docker socket挂载
```bash
docker stop quant-api && docker rm quant-api
docker run -d --name quant-api \
  --network host --restart unless-stopped \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  -v /home/djy/Quant:/home/djy/Quant \
  -v /var/run/docker.sock:/var/run/docker.sock \
  deploy-api:latest
```

验证：
```bash
curl -s http://127.0.0.1:9011/api/v1/health | jq '.data.summary'
# 应该显示 exited: 0, healthy: 5
```

### 6.3 API响应超时告警（patrol端点）

**现象**：飞书持续发送"API端点 /api/v1/openclaw/patrol 响应时间超过阈值500ms"

**原因**：
- patrol端点检查VPN节点健康需要约32秒
- 默认API延迟阈值是500ms，远低于patrol实际响应时间

**解决**：通过环境变量提高阈值
```bash
# 在api.env中添加
QUANT_API_LATENCY_THRESHOLD_MS=60000   # 60秒，patrol不会触发
QUANT_TRADE_LATENCY_THRESHOLD_MS=5000  # 5秒，交易端点阈值

# 重启API容器
docker restart quant-api
```

**验证配置生效**：
```bash
docker exec quant-api env | grep LATENCY
# QUANT_API_LATENCY_THRESHOLD_MS=60000
```

### 6.4 容器状态显示"unknown"导致误报

**现象**：飞书告警显示"容器已停止: quant-api"和"容器已停止: quant-web"，但容器实际运行正常

**根本原因**：
1. quant-api和quant-web容器没有配置健康检查(Health属性不存在)
2. `auto_recovery_service.py`和`health_monitor_service.py`都使用`{{.State.Health.Status}}`模板，当Health不存在时报错"map has no entry for key 'Health'"
3. docker inspect失败导致返回"unknown"状态，被误判为"exited"触发告警

**排查命令**：
```bash
# 检查容器是否有Health属性
docker inspect quant-api --format '{{.State.Health.Status}}'
# 如果报错 "map has no entry for key 'Health'" 说明没有健康检查

# 查看health端点返回的容器状态
curl -s http://127.0.0.1:9011/api/v1/health | jq '.data.containers[] | {name, status}'
# 如果显示 "unknown" 说明健康检查失败
```

**解决**：
1. 修复auto_recovery_service.py使用安全的模板语法：
```python
# 修复后的docker inspect模板
"--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
```

2. 重建容器添加健康检查：
```bash
# quant-api
docker stop quant-api && docker rm quant-api
docker run -d --name quant-api --network host --restart unless-stopped \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /home/djy/Quant:/home/djy/Quant \
  --health-cmd='curl -f http://localhost:9011/healthz' \
  --health-interval=30s --health-timeout=10s --health-retries=3 \
  deploy-api:latest

# quant-web
docker stop quant-web && docker rm quant-web
docker run -d --name quant-web --network host --restart unless-stopped \
  --health-cmd='curl -f http://localhost:9012' \
  --health-interval=30s --health-timeout=10s --health-retries=3 \
  quant-web:latest
```

**验证**：
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}' --filter 'name=quant'
# 应显示 quant-api Up X minutes (healthy)
curl -s http://127.0.0.1:9011/api/v1/health | jq '.data.summary'
# 应显示 healthy: 5, unhealthy: 0
```

---

## 7. 飞书推送显示"Webhook URL未配置"

**现象**：飞书机器人持续发送"容器已停止"告警

**原因**：
1. OpenClaw巡检超时（默认30秒，但patrol需要32秒）
2. patrol服务检查VPN节点时DNS临时失败
3. 检查失败触发飞书告警推送

**排查命令**：
```bash
# 检查OpenClaw日志
docker logs quant-openclaw --since 5m | grep timeout

# 检查API patrol响应时间
time curl -s -X POST 'http://127.0.0.1:9011/api/v1/openclaw/patrol?patrol_type=health_check'

# 检查VPN切换日志
docker logs quant-api --since 5m | grep -E 'VPN|节点|告警'
```

**解决**：增加OpenClaw超时配置
```python
# openclaw_scheduler.py
response = requests.post(url, timeout=60)  # 从30改为60
```

更新后复制到容器内并重启：
```bash
docker cp services/openclaw/openclaw_scheduler.py quant-openclaw:/app/
docker restart quant-openclaw
```

### 6.2 飞书推送显示"Webhook URL未配置"

**现象**：测试推送返回`飞书 Webhook URL 未配置`

**原因**：API容器没有加载到FEISHU环境变量（参考1.2）

**解决**：确保容器加载env_file，重启后测试
```bash
docker restart quant-api
sleep 15
curl -s -X POST http://127.0.0.1:9011/api/v1/feishu/test | jq '.'
```

---

## 7. 快速诊断脚本

```bash
# 一键诊断脚本
echo '=== Docker容器状态 ==='
docker ps --format 'table {{.Names}}\t{{.Status}}'

echo ''
echo '=== 健康检查状态 ==='
curl -s http://127.0.0.1:9011/api/v1/health | jq '.data.summary'

echo ''
echo '=== Freqtrade状态 ==='
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/status | jq '.[] | {pair, profit_pct}'

echo ''
echo '=== mihomo代理 ==='
curl -s 'http://127.0.0.1:9090/proxies/PROXY' | jq '.now'
curl -s -x http://127.0.0.1:7890 https://api.ipify.org

echo ''
echo '=== Grafana告警 ==='
curl -s -u admin:admin123 http://127.0.0.1:3000/api/v1/provisioning/alert-rules | jq '.[].title'
```

---

## 8. VPN切换告警问题

### 8.1 VPN切换告警发送失败

**现象**：API日志显示`发送VPN切换失败告警失败: name 'alert_push_service' is not defined`

**根本原因**：`vpn_switch_service.py`中的告警发送方法使用了`alert_push_service`，但未在方法内部导入

**排查命令**：
```bash
# 查看VPN切换告警错误
docker logs quant-api --since 10m | grep 'alert_push_service'
```

**解决**：在告警发送方法内部添加import语句
```python
# vpn_switch_service.py 修复（4个方法）
def _send_switch_success_alert(self, switch_result, previous_health):
    try:
        from services.api.app.services.alert_push_service import (
            AlertEventType, AlertLevel, AlertMessage, alert_push_service
        )
        alert_push_service.push_sync(...)

def _send_switch_failure_alert(self, error_message, health_result):
    try:
        from services.api.app.services.alert_push_service import (
            AlertEventType, AlertLevel, AlertMessage, alert_push_service
        )
        alert_push_service.push_sync(...)

# 异步版本也需要同样修复
async def _send_switch_success_alert_async(...)
async def _send_switch_failure_alert_async(...)
```

更新后重建API容器：
```bash
docker build -t deploy-api:latest -f services/api/Dockerfile .
docker stop quant-api && docker rm quant-api
docker run -d --name quant-api \
  --network host --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /home/djy/Quant:/home/djy/Quant \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  deploy-api:latest
```

---

## 9. Freqtrade容器健康检查问题

### 9.1 Freqtrade容器缺少健康检查

**现象**：容器状态显示"Up"但没有"(healthy)"标记，飞书持续发送"容器已停止: quant-freqtrade"告警

**根本原因**：Freqtrade容器启动时未配置`--health-cmd`参数

**排查命令**：
```bash
# 检查健康检查配置（返回null表示未配置）
docker inspect quant-freqtrade --format '{{json .Config.Healthcheck}}' | jq '.'.

# 手动测试健康检查命令
docker exec quant-freqtrade curl -f -u "Freqtrader:jianyu0.0." http://localhost:9013/api/v1/ping
```

**解决**：重建容器添加正确的健康检查
```bash
# 停止并删除旧容器
docker stop quant-freqtrade && docker rm quant-freqtrade

# 使用正确的健康检查参数重建
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

验证：
```bash
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep freqtrade
# 应显示：quant-freqtrade   Up X minutes (healthy)
```

### 9.2 Freqtrade健康检查端口错误

**现象**：健康检查失败，日志显示"Connection refused"

**原因**：健康检查使用端口8080，但Freqtrade实际监听9013

**解决**：确保健康检查命令使用正确端口
```bash
# 正确的健康检查命令（端口9013）
--health-cmd='curl -f -u "Freqtrader:jianyu0.0." http://localhost:9013/api/v1/ping'
```

---

## 10. 关键端口清单

| 服务 | 内部端口 | 健康检查端口 | 说明 |
|------|---------|-------------|------|
| Freqtrade | 9013 | **9013** | 注意：不是8080 |
| API | 9011 | 9011 | /health端点 |
| mihomo | 7890 | **9090** | external-controller |
| Grafana | 3000 | 3000 | Web UI |
| Prometheus | 9090 | 9090 | 内部使用 |

---

## 11. 重要提醒

1. **Freqtrade健康检查**：端口是9013，密码是`Freqtrader:jianyu0.0.`
2. **API环境变量**：需要确保容器加载deploy/api.env
3. **SSH连接**：使用密钥认证，密码登录已禁用
4. **代理出口IP**：JP1是154.31.113.7，已在Binance白名单
5. **飞书推送**：Webhook已配置，测试命令`POST /api/v1/feishu/test`
6. **VPN告警**：alert_push_service import问题已修复
7. **容器健康检查**：Freqtrade必须配置health-cmd参数