# Quant 项目状态文档

> 最后更新：2026-05-20

---

## 当前进度

**状态**：系统稳定运行，ML 模型参数优化完成，EnhancedStrategy 策略优化完成

**本次更新（2026-05-20）**：

### ML 模型参数优化
- **时间框架**：从 4h+1h 多时间框架改为 4h 单一时间框架（提升样本质量）
- **回看天数**：30天 → 60天（最佳性价比）
- **模型参数**：num_leaves 8→31, learning_rate 0.03→0.02, reg_alpha/reg_lambda 0.5→0.1, min_child_samples 50→20, n_estimators 100→200
- **效果**：验证AUC 0.51→0.64（+25%）
- **超时修复**：openclaw_scheduler 180s→300s, action timeout 120s→300s, training task 600s→900s

### EnhancedStrategy 策略参数优化
- **rsi_entry_threshold**：50→32（日均信号14次→2-3次，只抓真正超卖）
- **atr_multiplier**：3.0→2.0（适中止损距离）
- **max_day_loss_pct**：8.3%→5%（收紧日亏损上限）
- **ROI**：60min 4%→3%, 120min 3%→2%（更容易触发止盈）
- **rsi_exit_threshold**：74→72

### 自动化周期恢复
- **原因**：5月11日执行失败触发人工接管，8天未运行
- **修复**：清理manual_takeover状态、重置失败计数、重启服务
- **当前**：正常运行，每15分钟执行一次

---

## 系统状态

### 服务状态
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ Healthy |
| 服务器Web | http://39.106.11.65:9012 | ✅ Healthy |
| Freqtrade | EnhancedStrategy | ✅ RUNNING |
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
├── quant-freqtrade (EnhancedStrategy) - RSI策略
├── quant-mihomo - 代理端口 7890
└── quant-openclaw - 巡检服务 (15分钟周期)
```

---

## 双策略架构

### 1. EnhancedStrategy（RSI策略，Freqtrade）

| 参数 | 旧值 | 新值 | 说明 |
|------|------|------|------|
| rsi_entry_threshold | 50 | **32** | RSI入场阈值 |
| rsi_exit_threshold | 74 | **72** | RSI出场阈值 |
| atr_multiplier | 3.0 | **2.0** | ATR止损倍数 |
| max_day_loss_pct | 8.3% | **5%** | 日亏损上限 |
| max_consecutive_losses | 4 | 4 | 连续亏损暂停 |
| stoploss | -8% | -8% | 止损 |
| ROI | 8/5/4/3 | 8/5/3/2 | 止盈目标 |
| trading_pairs | 15个 | 15个 | 固定白名单 |

### 2. 自动化周期策略（ML策略）

| 参数 | 旧值 | 新值 |
|------|------|------|
| 时间框架 | 4h + 1h | **4h** |
| 回看天数 | 30天 | **60天** |
| num_leaves | 8 | **31** |
| learning_rate | 0.03 | **0.02** |
| reg_alpha/reg_lambda | 0.5 | **0.1** |
| min_child_samples | 50 | **20** |
| n_estimators | 100 | **200** |
| 运行频率 | 15分钟 | 15分钟 |

---

## ML 模型系统

### 当前配置

```python
DEFAULT_LIGHTGBM_PARAMS = {
    "num_leaves": 31,
    "learning_rate": 0.02,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "min_child_samples": 20,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "n_estimators": 200,
    "early_stopping_rounds": 15,
}
```

### 关键超时配置

| 参数 | 旧值 | 新值 | 文件 |
|------|------|------|------|
| cycle_check timeout | 180s | **300s** | openclaw_scheduler.py |
| action timeout | 120s | **300s** | openclaw_patrol_service.py |
| research_train timeout | 600s | **900s** | tasks/scheduler.py |

---

## 前端页面状态

| 页面 | 路由 | 状态 |
|------|------|------|
| 工作台首页 | `/` | ✅ |
| 模型训练 | `/training` | ✅ |
| 模型管理 | `/models` | ✅ |
| 回测训练 | `/backtest` | ✅ |
| 选币回测 | `/evaluation` | ✅ |
| 因子研究 | `/features` | ✅ |
| 参数优化 | `/hyperopt` | ✅ |
| 信号 | `/signals` | ✅ |

---

## 部署命令速查

```bash
# API
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "cd ~/Quant && git pull && cd infra/deploy && docker compose build api && docker compose up -d --no-deps api"

# Web
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "cd ~/Quant && git pull && cd infra/deploy && docker compose build web && docker compose up -d --no-deps web"

# Freqtrade 重启
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "docker stop quant-freqtrade && docker rm quant-freqtrade && cd ~/Quant/infra/freqtrade && docker compose up -d freqtrade"

# OpenClaw 重启
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "cd ~/Quant/infra/deploy && docker compose restart openclaw"

# 磁盘清理
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 \
  "docker builder prune --force && docker image prune --force"
```

---

## 参考文档

| 文档 | 内容 |
|------|------|
| [AGENTS.md](AGENTS.md) | 开发规则和部署规范 |
| [README.md](README.md) | 项目概览 |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | 部署详细说明 |
| [docs/SERVICE_ARCHITECTURE.md](docs/SERVICE_ARCHITECTURE.md) | 服务架构 |
| [docs/ops-troubleshooting.md](docs/ops-troubleshooting.md) | 运维踩坑记录 |
