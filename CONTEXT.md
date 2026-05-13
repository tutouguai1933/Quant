# Quant 项目状态文档

> 最后更新：2026-05-13

---

## 当前进度

**状态**：系统稳定运行，ML 模型全面升级完成 (P0-P5)

**本次更新（2026-05-13）**：

### ML 基础设施升级
- **P0 模型性能优化**：诊断过拟合（val AUC 0.48→0.64），标签阈值 0.5，L1/L2 正则化，时间块分层抽样
- **P1 特征工程**：因子 13→18 个（trend_strength, momentum_accel, volatility_contraction, volume_price_divergence, bull_bear_ratio），自动重训练集成
- **P2 监控告警**：模型性能下降/重训练完成/模型提升三种告警，飞书/Telegram/Webhook 推送，评估页 ML 预测卡
- **P3 实盘接轨**：ML Live Gate（live_min_ml_probability=0.55），预测追踪器（Brier Score 校准），A/B 对比（ML vs 启发式）
- **P4 模型扩展**：多模型集成（LightGBM+XGBoost 加权融合），Optuna 超参数优化
- **P5 工程完善**：修复 500 错误（QlibRuntimeConfig 构造点缺失），首页资金概览（USDT+策略+现货）

### 前端修复
- **修复 500 错误**：backtest/evaluation/features 三个页面恢复（_build_config 签名缺失新字段）
- **首页资金概览**：可用 USDT（绿色）、策略持仓（盈亏详情）、其他现货（非策略余额）
- **训练页 A/B 对比**：ML 模型 vs 启发式规则并排对比

### 运维
- **磁盘清理**：清理 4.6GB Docker 镜像/构建缓存

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ Healthy |
| 服务器Web | http://39.106.11.65:9012 | ✅ Healthy |
| Freqtrade | http://39.106.11.65:9013 | ✅ Live模式 |
| mihomo代理 | 127.0.0.1:7890 | ✅ Healthy |
| OpenClaw | 巡检服务 | ✅ Healthy |

### 服务架构

```
服务器 (39.106.11.65)
├── quant-api (FastAPI) - 端口 9011
│   ├── ML 模型服务：训练/推理/超参优化/模型管理
│   ├── ML 追踪服务：预测校准/A/B对比
│   ├── 告警推送：飞书/Telegram/Webhook
│   └── 运行时目录：/app/.runtime/
├── quant-web (Next.js) - 端口 9012
│   ├── /training - 训练结果+曲线+特征重要性+A/B对比
│   ├── /models - 模型版本管理（对比/提升）
│   ├── /signals - 信号+ML预测+特征贡献
│   ├── /backtest - 回测训练
│   ├── /evaluation - 选币回测+ML预测
│   ├── /features - 因子研究
│   └── /hyperopt - 参数优化
├── quant-freqtrade - API端口 9013 (内部)
├── quant-mihomo - 代理端口 7890
└── quant-openclaw - 巡检服务 (15分钟周期)
```

---

## ML 模型系统

### 模型架构

```
┌─────────────────────────────────────────────────────────────┐
│                      ML 策略升级架构                          │
├─────────────────────────────────────────────────────────────┤
│  数据层              特征层            模型层               │
│  ┌─────┐           ┌─────┐          ┌─────────┐           │
│  │K线  │──────────▶│18因子│─────────▶│Ensemble │           │
│  │数据 │           │计算  │          │LGBM+XGB │           │
│  └─────┘           └─────┘          └────┬────┘           │
│                                          │                 │
│  ┌───────────────────────────────────────┼──────────────┐  │
│  │                          Gate 验证层   ▼              │  │
│  │   Rule Gate → Backtest Gate → Live Gate → ML Live Gate│  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌────────────────────────────────────────────────────┐    │
│  │  追踪与优化                                         │    │
│  │  ├── MLPredictionTracker：预测 vs 实际校准          │    │
│  │  ├── A/B对比：ML vs 启发式                          │    │
│  │  └── Optuna：自动超参数搜索                          │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 核心文件

| 文件 | 说明 |
|------|------|
| `services/worker/ml/model.py` | LightGBM/XGBoost 模型封装 |
| `services/worker/ml/trainer.py` | 训练器（数据准备/训练/评估） |
| `services/worker/ml/ensemble.py` | 多模型集成预测器 |
| `services/worker/ml/predictor.py` | 推理器 |
| `services/worker/optuna_optimizer.py` | Optuna 超参数优化 |
| `services/worker/model_registry.py` | 模型版本管理 |
| `services/worker/auto_retrain.py` | 自动重训练触发 |
| `services/worker/ml_prediction_tracker.py` | 预测实盘追踪 |
| `services/worker/qlib_features.py` | 18个因子定义与计算 |
| `services/worker/qlib_ranking.py` | 候选排序+Gate验证 |

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/ml/models` | GET | 模型列表 |
| `/ml/models/{id}` | GET | 模型详情 |
| `/ml/models/{id}/promote` | POST | 提升为生产 |
| `/ml/models/production` | GET | 当前生产模型 |
| `/ml/models/training-history` | GET | 训练历史 |
| `/ml/retrain/status` | GET | 重训练状态 |
| `/ml/retrain/trigger` | POST | 触发重训练 |
| `/ml/tracking/calibration` | GET | 预测校准分析 |
| `/ml/tracking/records` | GET | 预测记录 |
| `/ml/tracking/ab-comparison` | GET | A/B 对比 |
| `/ml/hyperopt/status` | GET | 超参优化状态 |
| `/ml/hyperopt/start` | POST | 启动超参优化 |

### Gate 体系

| Gate | 说明 | 关键阈值 |
|------|------|----------|
| Rule Gate | 规则门控（EMA/ATR/成交量） | volume_ratio≥0.8 |
| Backtest Gate | 回测指标（收益/回撤/Sharpe） | sharpe≥0.25, drawdown≤15% |
| Validation Gate | 验证指标一致性 | sample≥12 |
| Consistency Gate | 训练/验证/回测一致性 | 漂移≤1.5% |
| Live Gate | 实盘准入门槛 | score≥0.65, win_rate≥55% |
| **ML Live Gate** | **ML 预测额外门槛** | **probability≥0.55** |

---

## 双策略架构

### 1. Freqtrade 独立策略 (EnhancedStrategy)

| 项目 | 值 |
|------|------|
| 类型 | 实时交易策略 |
| 交易对 | 16个（固定白名单） |
| RSI入场阈值 | 50 |
| RSI出场阈值 | 80 |
| 止损 | -8% |

### 2. 自动化周期策略 (Automation Cycle)

| 项目 | 值 |
|------|------|
| 类型 | ML 驱动的周期策略 |
| 运行频率 | 每15分钟 |
| 模型 | LightGBM + XGBoost 集成 |
| 特征 | 18个因子 |
| 候选选择 | 只选TOP1 |
| 实盘门槛 | Live Gate + ML Live Gate |

---

## 前端页面状态

| 页面 | 路由 | 状态 |
|------|------|------|
| 工作台首页 | `/` | ✅ 资金概览+策略持仓+现货余额 |
| 模型训练 | `/training` | ✅ 训练曲线+A/B对比 |
| 模型管理 | `/models` | ✅ 版本管理/对比/提升 |
| 回测训练 | `/backtest` | ✅ 恢复正常 |
| 选币回测 | `/evaluation` | ✅ ML预测卡 |
| 因子研究 | `/features` | ✅ 恢复正常 |
| 参数优化 | `/hyperopt` | ✅ 恢复正常 |
| 信号 | `/signals` | ✅ ML预测+特征贡献 |

---

## 部署命令速查

```bash
# API
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "cd ~/Quant && git pull && cd infra/deploy && docker compose build api && docker compose up -d --no-deps api"

# Web
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "cd ~/Quant && git pull && cd infra/deploy && docker compose build web && docker compose up -d --no-deps web"

# 磁盘清理
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "docker builder prune --force && docker image prune --force"
```

---

## 参考文档

| 文档 | 内容 |
|------|------|
| [AGENTS.md](AGENTS.md) | 开发规则和部署规范 |
| [docs/roadmap.md](docs/roadmap.md) | 路线图 |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | 部署详细说明 |
| [docs/DEV_HANDBOOK.md](docs/DEV_HANDBOOK.md) | 开发手册 |
| [docs/SERVICE_ARCHITECTURE.md](docs/SERVICE_ARCHITECTURE.md) | 服务架构 |
| [docs/ops-troubleshooting.md](docs/ops-troubleshooting.md) | 运维踩坑记录 |
