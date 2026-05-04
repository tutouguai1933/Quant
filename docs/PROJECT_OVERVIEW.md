# Quant 项目概览

> **快速理解项目** - 5分钟上手指南
>
> 最后更新：2026-05-05

---

## ⚠️ 开发环境架构（必读）

### 核心原则：开发与部署分离

| 环境 | 位置 | 作用 | 禁止操作 |
|------|------|------|----------|
| **本地WSL** | 开发机 | 代码编辑、Git推送、文档维护 | ❌ 运行Docker容器 |
| **阿里云服务器** | 39.106.11.65 | 运行所有生产服务 | ❌ 直接编辑代码 |

**规则：保证同时只有一个实例在运行（在阿里云服务器上）**

```
本地WSL                    阿里云服务器
┌─────────────┐            ┌─────────────┐
│ 编辑代码    │            │ Docker容器   │
│ git commit  │  ───────>  │ quant-api   │
│ git push    │   SSH部署  │ quant-web   │
│             │            │ quant-freq  │
│ ❌不运行服务│            │ ...         │
└─────────────┘            └─────────────┘
```

---

## 一句话描述

**Quant = Freqtrade量化交易 + 自研控制平面API + Web前端 + 自动化运维**

---

## 系统架构（5层）

```
┌─────────────────────────────────────────────────────────┐
│  Web前端 (Next.js)          http://39.106.11.65:9012    │
├─────────────────────────────────────────────────────────┤
│  API控制平面 (FastAPI)       http://39.106.11.65:9011    │
│  - 告警推送、策略管理、信号处理                           │
├─────────────────────────────────────────────────────────┤
│  Freqtrade交易引擎          http://39.106.11.65:9013    │
│  - EnhancedStrategy策略、Live模式                        │
├─────────────────────────────────────────────────────────┤
│  OpenClaw自动化             巡检、VPN切换、自动恢复       │
├─────────────────────────────────────────────────────────┤
│  基础设施层                                                 │
│  - mihomo代理(7890/9090) - Grafana(3000) - Prometheus    │
└─────────────────────────────────────────────────────────┘
```

---

## 目录结构（核心）

```
Quant/
├── services/           # 后端服务
│   ├── api/            # FastAPI控制平面（核心）
│   ├── openclaw/       # 自动化巡检服务
│   └── worker/         # 后台任务处理
├── apps/web/           # Next.js前端
├── infra/              # 基础设施配置
│   ├── freqtrade/      # Freqtrade配置和策略
│   ├── grafana/        # Grafana仪表盘
│   └── deploy/         # 环境变量和部署配置
├── scripts/            # 运维脚本
└── docs/               # 文档（详细）
```

---

## 5个核心容器

| 容器 | 端口 | 作用 | 健康检查 |
|------|------|------|----------|
| quant-api | 9011 | 控制平面API | `/healthz` |
| quant-web | 9012 | Web前端 | HTTP 200 |
| quant-freqtrade | 9013 | 交易引擎 | `curl ping` |
| quant-openclaw | - | 自动化巡检 | 内部API |
| quant-mihomo | 7890/9090 | 代理 | `external-controller` |

---

## 当前配置

| 项目 | 值 |
|------|------|
| 模式 | **Live实盘** (dry_run=false) |
| 策略 | EnhancedStrategy |
| stake_amount | **6 USDT** |
| max_open_trades | **3** |
| 交易对 | **15个**主流币 |
| RSI入场 | **45** |
| 最低ROI | **3%** (扣手续费后净收益2.8%) |
| 订单类型 | **IOC** (防止重复挂单) |
| 余额 | **~21 USDT** |
| 代理出口IP | 154.31.113.7 (JP1) |

---

## 关键认证

| 服务 | 认证 |
|------|------|
| Freqtrade API | `Freqtrader:jianyu0.0.` |
| API Admin | `admin:1933` |
| Grafana | `admin:admin123` |
| SSH | 密钥认证（`~/.ssh/id_aliyun_djy`） |

---

## 飞书告警

- **Webhook**: 已配置
- **告警来源**: trade_monitor.sh, proxy_switch.sh（统一通过API发送）
- **测试**: `curl -X POST http://127.0.0.1:9011/api/v1/feishu/test`

---

## 快速诊断

```bash
# 一键检查
docker ps --format 'table {{.Names}}\t{{.Status}}' --filter "name=quant"
curl -s -u 'Freqtrader:jianyu0.0.' http://127.0.0.1:9013/api/v1/status
curl -s http://127.0.0.1:9011/api/v1/health | jq '.data.summary'
```

---

## 相关文档

| 文档 | 内容 |
|------|------|
| [OPS_HANDBOOK.md](OPS_HANDBOOK.md) | 运维手册 |
| [DEV_HANDBOOK.md](DEV_HANDBOOK.md) | 开发手册 |
| [HANDOVER.md](HANDOVER.md) | **接力开发提示词** |
| [ops-troubleshooting.md](ops-troubleshooting.md) | 踩坑记录 |