# 部署指南

> 最后更新：2026-05-13

本文档记录项目部署的完整流程和常见问题解决方案。

---

## 一、服务器信息

- **服务器IP**: 39.106.11.65
- **系统**: Ubuntu 22.04
- **用户**: djy
- **项目路径**: `/home/djy/Quant`

---

## 二、快速部署

### SSH连接

```bash
# 使用密钥连接
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
```

### 标准部署流程

```bash
# 1. 拉取代码
cd /home/djy/Quant && git pull

# 2. 重建镜像
docker build -f services/api/Dockerfile -t quant-api:latest .

# 3. 部署 API（使用 host 网络模式）
docker stop quant-api && docker rm quant-api
docker run -d --name quant-api --network host \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  -v /home/djy/Quant/.runtime:/app/.runtime \
  quant-api:latest

# 4. 查看日志
docker logs quant-api --tail 50
```

### 重要：Docker 网络配置

**必须使用 `--network host` 模式**，原因：

1. Freqtrade 使用 host 网络模式，监听 `0.0.0.0:9013`
2. API 容器需要访问 Freqtrade API
3. 桥接模式下 `127.0.0.1` 指向容器内部，无法访问宿主机服务

**错误示例**（会导致 Freqtrade 连接失败）：
```bash
docker run -d --name quant-api -p 9011:9011 ...  # ❌ 桥接模式
```

**正确示例**：
```bash
docker run -d --name quant-api --network host ...  # ✅ host 模式
```

### 常用命令

```bash
# 查看容器状态
docker ps --format "table {{.Names}}\t{{.Status}}"

# 重启服务
docker restart quant-api quant-web

# 查看资源使用
docker stats --no-stream

# 清理磁盘
docker system prune -f && docker builder prune -f
```

---

## 三、服务端口

| 服务 | 内部端口 | 外部访问 |
|------|----------|----------|
| API | 9011 | http://39.106.11.65:9011 |
| Web | 9012 | http://39.106.11.65:9012 |
| Freqtrade | 9013 | 仅内部访问 |
| Grafana | 3000 | 需SSH隧道 |
| Prometheus | 9090 | 需SSH隧道 |

---

## 四、健康检查

```bash
# API健康检查
curl http://localhost:9011/health

# Web健康检查
curl http://localhost:9012/

# Freqtrade健康检查
curl -u 'Freqtrader:jianyu0.0.' http://localhost:9013/api/v1/ping

# 系统状态
curl http://localhost:9011/api/v1/system/status
```

---

## 五、运维巡检

### OpenClaw 巡检服务

OpenClaw 是自动化运维巡检服务，负责：

- **health_check**: 每60秒执行健康检查
- **state_sync**: 每300秒同步状态
- **cycle_check**: 每900秒检查自动化周期

### 巡检记录位置

```bash
# 巡检记录
/home/djy/Quant/infra/data/runtime/openclaw_patrol_records.json

# 审计记录
/home/djy/Quant/infra/data/runtime/openclaw_audit_records.json

# 自动化状态
/home/djy/Quant/infra/data/runtime/automation_state.json
```

### 手动触发巡检

```bash
# 健康检查
curl -X POST "http://localhost:9011/api/v1/openclaw/patrol?patrol_type=health_check"

# 状态同步
curl -X POST "http://localhost:9011/api/v1/openclaw/patrol?patrol_type=state_sync"

# 周期检查
curl -X POST "http://localhost:9011/api/v1/openclaw/patrol?patrol_type=cycle_check"
```

---

## 六、双策略架构

系统采用双策略架构：

### 1. Freqtrade EnhancedStrategy

- **类型**: 实时交易策略
- **运行位置**: quant-freqtrade 容器
- **配置**: `/home/djy/Quant/infra/freqtrade/user_data/config.live.base.json`
- **stake_amount**: 8 USDT（避免NOTIONAL过滤器问题）

### 2. Automation Cycle

- **类型**: 自动化周期策略
- **运行位置**: quant-api + quant-openclaw
- **模式**: auto_live / dry_run
- **状态文件**: `/home/djy/Quant/infra/data/runtime/automation_state.json`

### 为什么近期可能无交易

系统正常运行但可能无交易的原因：

1. **候选币种未通过验证**: 成交量不足、未来收益预测非正
2. **dry-run模式**: 候选币种成交量不足以进入live模式
3. **风控检查**: 策略判断当前市场条件不满足入场标准

查看具体原因：
```bash
# 查看最新周期状态
cat /home/djy/Quant/infra/data/runtime/automation_state.json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  print('状态:', d['last_cycle']['status']); \
  print('原因:', d['last_cycle']['failure_reason']); \
  print('消息:', d['last_cycle']['message'])"
```

---

## 七、常见问题

### 1. API返回空数据

**原因**: 代码修改后没有重新部署到服务器

**解决**:
```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "cd /home/djy/Quant && git pull && \
   cd infra/deploy && docker compose build api && docker compose up -d api"
```

### 2. Patrol接口超时（已解决）

**原因**: 多个服务串行调用导致响应时间超过60秒

**优化历程**:
1. 添加缓存层（初始60s TTL）
2. 发现缓存频繁失效：OpenClaw health_check 间隔60s 与缓存 TTL 60s 匹配，导致每次巡检都命中空缓存
3. 将 3 个核心缓存 TTL 从 60s 提高到 120s，避免与 OpenClaw 60s 巡检间隔冲突

**当前缓存配置**:
- `FreqtradeRestClient.get_snapshot()`: 5秒TTL
- `AutomationWorkflowService.get_status()`: 120秒TTL
- `ValidationWorkflowService.build_report()`: 120秒TTL
- `OpenClawSnapshotService.get_snapshot()`: 120秒TTL + 线程锁

### 3. 自动化暂停/手动接管

**检查状态**:
```bash
curl -s http://localhost:9011/api/v1/system/status | python3 -m json.tool
```

**恢复自动运行（推荐：API 方式）**:
```bash
TOKEN=$(curl -s -X POST 'http://localhost:9011/api/v1/auth/login?username=admin&password=<password>' | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['item']['token'])")

# 先切到 dry_run_only 清除异常状态
curl -s -X POST "http://localhost:9011/api/v1/tasks/automation/dry-run-only?token=$TOKEN"

# 再切回 auto_live
curl -s -X POST "http://localhost:9011/api/v1/tasks/automation/configure?token=$TOKEN&mode=auto_live"
```

**备选：直接编辑状态文件**:
```python
import json
path = "/home/djy/Quant/infra/data/runtime/automation_state.json"
with open(path, 'r+') as f:
    state = json.load(f)
    state['paused'] = False
    state['manual_takeover'] = False
    state['paused_reason'] = ""
    f.seek(0)
    json.dump(state, f, indent=2)
    f.truncate()
```

### 4. Binance NOTIONAL过滤器错误

**原因**: 交易金额低于5 USDT

**解决方案**: 
- stake_amount 已调整为 10 USDT
- 小额dust资产可使用 Binance Dust Transfer API 转为BNB

### 5. 磁盘空间不足

**检查**:
```bash
df -h
docker system df
```

**清理**:
```bash
docker system prune -f
docker builder prune -f
```

---

## 八、缓存TTL配置

| 服务 | 方法 | TTL | 文件 |
|------|------|-----|------|
| FreqtradeRestClient | get_snapshot() | 5秒 | `services/api/app/adapters/freqtrade/rest_client.py` |
| AutomationWorkflowService | get_status() | 120秒 | `services/api/app/services/automation_workflow_service.py` |
| ValidationWorkflowService | build_report() | 120秒 | `services/api/app/services/validation_workflow_service.py` |
| OpenClawSnapshotService | get_snapshot() | 120秒 | `services/api/app/services/openclaw_snapshot_service.py` |

### 缓存实现模式

```python
class SomeService:
    _CACHE_TTL = 60.0
    
    def __init__(self):
        self._cache = None
        self._cache_time = 0.0
        self._cache_lock = threading.Lock()  # 多线程场景
    
    def get_data(self):
        # 快速检查（无锁）
        if self._cache is not None and (time.time() - self._cache_time) < self._CACHE_TTL:
            return self._cache
        
        with self._cache_lock:
            # 双重检查（有锁）
            if self._cache is not None and (time.time() - self._cache_time) < self._CACHE_TTL:
                return self._cache
            
            # 计算新数据
            data = self._compute_data()
            
            # 关键：使用当前时间而非方法开始时的时间
            self._cache = data
            self._cache_time = time.time()
            return data
```

---

## 九、监控告警

### Grafana

```bash
# SSH隧道访问
ssh -L 3000:localhost:3000 djy@39.106.11.65
# 浏览器访问 http://localhost:3000
```

### Prometheus

```bash
# SSH隧道访问
ssh -L 9090:localhost:9090 djy@39.106.11.65
# 浏览器访问 http://localhost:9090
```

### 飞书告警

```bash
# 测试飞书推送
curl -X POST http://localhost:9011/api/v1/feishu/test
```

---

## 十、配置文件

| 服务 | 配置文件 | 说明 |
|------|----------|------|
| API | `infra/deploy/api.env` | 环境变量 |
| Freqtrade | `infra/freqtrade/user_data/config.live.base.json` | 交易配置 |
| Mihomo | `infra/mihomo/config.yaml` | 代理配置 |
| OpenClaw | 环境变量 | 巡检间隔 |

### 关键环境变量

```bash
# 运行模式
QUANT_RUNTIME_MODE=live  # live | dry-run | demo

# 市场配置
QUANT_MARKET_SYMBOLS=BTCUSDT,ETHUSDT,...

# Binance API
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx

# Freqtrade API（必须配置才能连接）
QUANT_FREQTRADE_API_URL=http://127.0.0.1:9013
QUANT_FREQTRADE_API_USERNAME=Freqtrader
QUANT_FREQTRADE_API_PASSWORD=xxx
```

---

## 十一、ML 自动优化模块

### 功能概述

系统已集成 ML 自动优化模块，包括：

| 功能 | API 端点 | 说明 |
|------|----------|------|
| 模型注册表 | `/api/v1/ml/models` | 版本管理、对比、提升 |
| 重训练检查 | `/api/v1/ml/retrain/status` | 自动触发条件检查 |
| 超参数优化 | `/api/v1/ml/hyperopt/start` | Optuna 自动调参 |
| 后台调度 | `/api/v1/ml/hyperopt/schedule` | 定期自动优化 |

### 相关配置

```bash
# 重训练配置
QUANT_RETRAIN_INTERVAL_DAYS=7
QUANT_PERFORMANCE_DROP_THRESHOLD=0.05
QUANT_MIN_RETRAIN_INTERVAL_HOURS=6

# 超参数优化配置
QUANT_HYPEROPT_ENABLED=true
QUANT_HYPEROPT_INTERVAL_HOURS=24
QUANT_HYPEROPT_N_TRIALS=50
```

### 持久化目录

```
/home/djy/Quant/.runtime/
├── registry/              # 模型注册表
│   └── model_index.json
├── best_params.json       # 最优参数存储
└── dataset/               # 数据集缓存
    └── cache/
```

### 常用命令

```bash
# 查看模型列表
curl -s http://localhost:9011/api/v1/ml/models | jq '.data.total'

# 查看生产模型
curl -s http://localhost:9011/api/v1/ml/models/production | jq '.data.version_id'

# 启动超参数优化
TOKEN=$(curl -s -X POST 'http://localhost:9011/api/v1/auth/login?username=admin&password=xxx' | jq -r '.data.item.token')
curl -X POST "http://localhost:9011/api/v1/ml/hyperopt/start?token=$TOKEN&n_trials=10"

# 查看重训练状态
curl -s http://localhost:9011/api/v1/ml/retrain/status | jq '.data'
```

---

## 十二、故障排查清单

### Freqtrade 连接失败

**症状**: 首页显示"实盘连接断开"

**排查步骤**:

1. 检查 Freqtrade 是否运行：
```bash
docker ps | grep freqtrade
curl -u 'Freqtrader:xxx' http://127.0.0.1:9013/api/v1/ping
```

2. 检查 API 容器网络模式：
```bash
docker inspect quant-api --format '{{.HostConfig.NetworkMode}}'
# 应该显示 "host"
```

3. 检查环境变量是否加载：
```bash
docker exec quant-api env | grep FREQTRADE
```

4. 检查代理代码使用的地址：
```bash
docker exec quant-api python3 -c "from services.api.app.routes.freqtrade_proxy import FREQTRADE_HOST; print(FREQTRADE_HOST)"
# 应该显示 http://127.0.0.1:9013 或 http://172.17.0.1:9013
```

### 环境变量未生效

**原因**: 使用 `-v` 挂载 `.env` 文件不会自动加载到进程环境

**解决**: 使用 `--env-file` 参数：
```bash
docker run -d --name quant-api --network host \
  --env-file /home/djy/Quant/infra/deploy/api.env \
  ...
```

### 模型注册表为空

**原因**: 训练后模型未自动注册

**排查**:
1. 检查持久化目录是否存在：`ls /home/djy/Quant/.runtime/registry/`
2. 触发一次训练：`POST /api/v1/tasks/train`
3. 检查训练日志中是否有注册相关警告
