# Quant 项目接力开发提示词

> **给下一个Claude Session的启动提示词**
>
> 最后更新：2026-05-05

---

## ⚠️ 开发环境架构（必读）

### 核心原则：开发与部署分离

| 环境 | 位置 | 作用 |
|------|------|------|
| **开发环境** | 本地WSL | 代码编辑、Git提交、文档维护 |
| **生产环境** | 阿里云服务器 39.106.11.65 | 运行所有Docker服务 |

**规则：**
- ✅ 本地WSL：修改代码 → git push
- ✅ 阿里云服务器：git pull → docker compose build → docker compose up
- ❌ **禁止在本地WSL运行Docker容器**（会导致混淆和端口冲突）
- ❌ **禁止在阿里云服务器直接编辑代码**（应通过Git同步）

### SSH连接方式

```bash
# 本地WSL连接阿里云服务器
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65

# 密钥位置：~/.ssh/id_aliyun_djy
```

---

## 启动提示词（复制粘贴给Claude）

```
我正在继续Quant量化交易系统的开发和运维工作。

## ⚠️ 开发环境规则
- 本地WSL：只用于代码编辑和Git推送，不运行服务
- 阿里云服务器(39.106.11.65)：运行所有生产服务
- SSH密钥：~/.ssh/id_aliyun_djy

## 项目概况
- Quant = Freqtrade交易引擎 + FastAPI控制平面 + Next.js前端 + 自动化运维
- Live实盘模式，运行于阿里云服务器 39.106.11.65
- 当前余额约21 USDT，16个交易对白名单

## 核心服务（阿里云服务器上的5个容器）
- quant-api (9011): FastAPI控制平面，市场数据、告警推送
- quant-freqtrade (9013): Freqtrade交易引擎，EnhancedStrategy策略
- quant-web (9012): Next.js前端
- quant-openclaw: 自动化巡检服务
- quant-mihomo (7890/9090): 代理服务，出口IP 154.31.113.7

## 关键认证
- Freqtrade API: `Freqtrader:jianyu0.0.`
- API Admin: `admin:1933`
- SSH: 密钥认证 `~/.ssh/id_aliyun_djy`

## 文档位置
- 项目概览: docs/PROJECT_OVERVIEW.md
- 运维手册: docs/OPS_HANDBOOK.md
- 开发手册: docs/DEV_HANDBOOK.md（含开发流程规范）
- 踩坑记录: docs/ops-troubleshooting.md

## 请先阅读 docs/DEV_HANDBOOK.md 了解开发流程规则，然后：
1. SSH到阿里云服务器检查状态：ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "docker ps"
2. 检查market API：ssh ... "curl -s http://127.0.0.1:9011/api/v1/market | jq '.data.items | length'"
3. 确认返回16个symbols（BTCUSDT、ETHUSDT等）

请告诉我当前系统运行状态，以及有什么需要我继续开发或运维的工作。
```

---

## 远程状态检查命令（在本地WSL执行）

```bash
# 一键诊断（通过SSH）
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "
docker ps --format 'table {{.Names}}\t{{.Status}}' --filter 'name=quant'
echo '--- Market API ---'
curl -s http://127.0.0.1:9011/api/v1/market | jq '.data.items | length'
echo '--- Freqtrade ---'
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/balance | jq '.total'
"
```

---

## 最近完成的工作（2026-05-05）

| 完成项 | 内容 |
|--------|------|
| 容器健康检查修复 | 修复docker inspect模板报错导致的"容器已停止"误报 |
| 开发流程规范 | 明确WSL只用于开发，阿里云服务器用于运行，通过Git同步 |
| 文档更新 | 更新DEV_HANDBOOK、OPS_HANDBOOK、HANDOVER、PROJECT_OVERVIEW |
| Git同步流程 | 建立本地推送→服务器pull→重建容器的标准流程 |

### 容器健康检查修复详情

**问题**：飞书持续收到"容器已停止"误报，但容器实际正常运行

**原因**：`health_monitor_service.py`和`auto_recovery_service.py`使用`{{.State.Health.Status}}`模板，当容器没有Health属性时docker inspect报错

**修复**：使用安全的Go模板语法
```python
# 修复前（会报错）
"{{.State.Status}}|{{.State.Health.Status}}|{{.Id}}"

# 修复后（安全）
"{{.State.Status}}|{{.Id}}"
"{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
```

---

## 当前系统状态（2026-05-05）

| 服务 | 状态 | 说明 |
|------|------|------|
| quant-api | ✅ Running | Market API返回16个symbols |
| quant-web | ✅ Running | 前端正常访问 |
| quant-freqtrade | ✅ Running | 交易引擎正常 |
| quant-mihomo | ✅ Running | 代理工作正常 |

### Market白名单（16个币种）

```
BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT, XRPUSDT, DOGEUSDT,
ADAUSDT, LINKUSDT, AVAXUSDT, DOTUSDT, MATICUSDT,
PEPEUSDT, SHIBUSDT, WIFUSDT, ORDIUSDT, BONKUSDT
```

---

## 待办事项

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | Grafana告警规则优化 | 添加更多交易指标监控 |
| P2 | RSI历史Tab完善 | 单币页面RSI历史展示 |
| P3 | 策略回测 | 测试不同RSI参数效果 |

---

## 部署流程（标准操作）

```bash
# 1. 本地修改代码并推送
git add . && git commit -m "fix: xxx" && git push

# 2. SSH到服务器拉取并重建
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "
cd ~/Quant && git pull &&
cd ~/Quant/infra/deploy && docker compose build &&
docker compose up -d
"
```

---

## 关键配置文件路径

```
infra/deploy/api.env           # API环境变量
infra/freqtrade/user_data/config.live.base.json  # Freqtrade主配置
infra/freqtrade/user_data/strategies/EnhancedStrategy.py  # 策略代码
infra/grafana/dashboards/quant-overview.json  # Grafana仪表盘
```

---

## 常见问题快速修复

### Market API返回空数据
```bash
# 检查代理配置
ssh ... "docker exec quant-api env | grep -i proxy"
# 应显示 HTTP_PROXY=http://127.0.0.1:7890

# 测试Binance连接
ssh ... "docker exec quant-api curl -s 'https://api.binance.com/api/v3/ping'"
```

### 容器unhealthy
```bash
ssh ... "docker logs quant-api --tail 20"
```

### 需要重建服务
```bash
ssh ... "cd ~/Quant/infra/deploy && docker compose build api && docker compose up -d api"
```