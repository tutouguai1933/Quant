# 运维踩坑记录

> 本文档记录运维过程中遇到的问题和解决方案，避免重复踩坑。

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

**可能原因**：
1. SSH服务过载（MaxStartups限制）
2. 阿里云安全中心正在处理安全事件
3. 多次并发SSH连接导致积压

**解决**：
1. 等待几分钟后重试
2. 清理本地卡住的SSH进程：`pkill -f "sshpass.*服务器IP"`

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

## 8. 关键端口清单

| 服务 | 内部端口 | 健康检查端口 | 说明 |
|------|---------|-------------|------|
| Freqtrade | 9013 | **9013** | 注意：不是8080 |
| API | 9011 | 9011 | /health端点 |
| mihomo | 7890 | **9090** | external-controller |
| Grafana | 3000 | 3000 | Web UI |
| Prometheus | 9090 | 9090 | 内部使用 |

---

## 9. 重要提醒

1. **Freqtrade健康检查**：端口是9013，密码是`Freqtrader:jianyu0.0.`
2. **API环境变量**：需要确保容器加载deploy/api.env
3. **SSH连接**：使用密钥认证，密码登录已禁用
4. **代理出口IP**：JP1是154.31.113.7，已在Binance白名单
5. **飞书推送**：Webhook已配置，测试命令`POST /api/v1/feishu/test`