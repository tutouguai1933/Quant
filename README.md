# Quant

面向个人开发者的加密货币量化研究与执行工作台。  
核心主链：`数据 -> 特征 -> 研究 -> 回测 -> 评估 -> dry-run -> 小额 live -> 复盘`

## 当前状态

| 阶段 | 状态 |
|------|------|
| phase1 | ✅ 已完成 - 主链打通 |
| phase2 | ✅ 已完成 - 工作台可配置 |
| phase3 | ✅ 已完成 - 综合验收 |
| phase4 | ✅ 已完成 - 前端信息架构重构 |
| phase-i | ✅ 已完成 - 视觉交互统一 |
| phase-j | ✅ 已完成 - 多因子主线补强 |
| phase-k | ✅ 已完成 - 综合验收 |
| 运维完善 | ✅ 已完成 |
| 性能优化 | ✅ 已完成 |

**最近更新（2026-05-08）**：
- 自动化周期历史增强（RSI快照、候选币种、任务状态）
- 配置管理界面修复
- 规则门控参数优化

## 这套系统现在能做什么

### 已经可用

- 读取 Binance 真实行情和余额
- 跑 `Freqtrade` 的 `dry-run` 和小额 `live`
- 跑 `Qlib` 训练、推理、筛选、复盘
- 看统一研究报告和评估结论
- 自动化选币、巡检、告警
- 飞书推送告警通知

### 核心功能

| 模块 | 功能 |
|------|------|
| 研究工作流 | 训练 → 推理 → 筛选 → 评估 |
| 自动化系统 | 定时巡检、自动选币、风控熔断 |
| 规则门控 | 趋势/波动/量能过滤、评分验证 |
| 执行引擎 | Freqtrade 集成、dry-run/live 模式 |
| 监控告警 | Prometheus + Grafana + 飞书 |

## 系统导览

### 快速接手顺序

1. **[AGENTS.md](AGENTS.md)** - 开发规则和部署规范（必读）
2. **[CONTEXT.md](CONTEXT.md)** - 当前系统状态
3. **[docs/HANDOFF_SESSION.md](docs/HANDOFF_SESSION.md)** - 会话接力文档

### 详细文档

| 文档 | 内容 |
|------|------|
| [docs/startup-and-config.md](docs/startup-and-config.md) | 启动和配置说明 |
| [docs/architecture.md](docs/architecture.md) | 系统架构 |
| [docs/developer-handbook.md](docs/developer-handbook.md) | 开发手册 |
| [docs/deployment-handbook.md](docs/deployment-handbook.md) | 部署手册 |
| [docs/user-handbook.md](docs/user-handbook.md) | 用户手册 |

## 前端页面结构

### 主工作区
- `/` - 工作台（首页）
- `/research` - 模型训练
- `/evaluation` - 选币评估
- `/strategies` - 策略中心
- `/tasks` - 任务管理

### 工具页
- `/market` - 市场行情
- `/balances` - 账户余额
- `/positions` - 当前持仓
- `/orders` - 订单记录
- `/risk` - 风险管理

### 配置与数据
- `/config` - 配置管理
- `/data` - 数据管理
- `/features` - 因子研究
- `/signals` - 信号列表

## 本地开发

### 环境准备

```bash
# 激活 Conda 环境
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
```

### 启动服务

```bash
# API
cd /home/djy/Quant
python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 9011

# Web
cd /home/djy/Quant/apps/web
pnpm build && pnpm start
```

### 标准端口

| 服务 | 端口 |
|------|------|
| API | 9011 |
| Web | 9012 |
| Freqtrade | 9013 |

## 部署方式

> **重要**：所有 Docker 服务必须在服务器上运行，本地只做代码编辑

### SSH 连接

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
```

### 标准部署流程

```bash
# 1. 本地推送代码
git add . && git commit -m "xxx" && git push

# 2. SSH 到服务器
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65

# 3. 拉取并重建
cd ~/Quant && git pull
cd infra/deploy
docker compose build api web && docker compose up -d --no-deps api web
```

### 服务器地址

| 服务 | 地址 |
|------|------|
| Web | http://39.106.11.65:9012 |
| API | http://39.106.11.65:9011 |

## 测试

```bash
# 后端测试
python -m unittest discover -s services/api/tests -v
python -m unittest discover -s services/worker/tests -v

# 前端构建
cd apps/web && pnpm build

# 前端测试
QUANT_WEB_BASE_URL=http://127.0.0.1:9012 QUANT_API_BASE_URL=http://127.0.0.1:9011 pnpm exec playwright test
```

## 关键配置

### 规则门控参数（infra/deploy/api.env）

```bash
QUANT_QLIB_RULE_MIN_VOLUME_RATIO=0.8    # 成交量阈值
QUANT_QLIB_RULE_MAX_ATR_PCT=5           # 波动率上限
QUANT_QLIB_DRY_RUN_MIN_SCORE=0.45       # 最小评分
```

### 自动化参数

```bash
QUANT_PATROL_AUTO_START=true            # 启动定时巡检
QUANT_PATROL_INTERVAL_MINUTES=15        # 巡检间隔
```

## 项目结构

```
Quant/
├── apps/web/           # Next.js 前端
├── services/
│   ├── api/           # FastAPI 后端
│   ├── worker/        # Qlib 工作进程
│   └── openclaw/      # 巡检服务
├── infra/
│   ├── deploy/        # Docker Compose 配置
│   ├── freqtrade/     # Freqtrade 配置
│   └── mihomo/        # 代理配置
├── docs/              # 文档
├── AGENTS.md          # 开发规则
├── CONTEXT.md         # 系统状态
└── README.md          # 本文件
```

## 搜索记录

- 本轮无新增外部方案搜索
- 文档已按结构整理

## 归档说明

早期阶段文档已移至 [docs/archive/README.md](docs/archive/README.md)
