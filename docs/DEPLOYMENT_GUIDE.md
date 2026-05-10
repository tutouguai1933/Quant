# 部署指南

> 最后更新：2026-05-11

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

# 2. 重建并部署
cd infra/deploy
docker compose build api web
docker compose up -d api web

# 3. 查看日志
docker logs quant-api --tail 50
docker logs quant-web --tail 50
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
| Freqtrade | 8080 | 仅内部访问 |
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
curl -u 'Freqtrader:jianyu0.0.' http://localhost:8080/api/v1/ping

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
- **stake_amount**: 10 USDT（避免NOTIONAL过滤器问题）

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

**解决方案**: 已添加缓存层
- `FreqtradeRestClient.get_snapshot()`: 5秒TTL
- `AutomationWorkflowService.get_status()`: 60秒TTL
- `ValidationWorkflowService.build_report()`: 60秒TTL
- `OpenClawSnapshotService.get_snapshot()`: 60秒TTL + 线程锁

### 3. 自动化暂停/手动接管

**检查状态**:
```bash
curl -s http://localhost:9011/api/v1/system/status | python3 -m json.tool
```

**恢复自动运行**:
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
| AutomationWorkflowService | get_status() | 60秒 | `services/api/app/services/automation_workflow_service.py` |
| ValidationWorkflowService | build_report() | 60秒 | `services/api/app/services/validation_workflow_service.py` |
| OpenClawSnapshotService | get_snapshot() | 60秒 | `services/api/app/services/openclaw_snapshot_service.py` |

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
QUANT_RUNTIME_MODE=dry-run  # 或 live
QUANT_MARKET_SYMBOLS=BTCUSDT,ETHUSDT,...
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
```
