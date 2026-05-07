# 会话接力文档

## 最近更新：2026-05-08

---

## 已完成功能

### 1. 自动化周期历史增强

**前端组件**: `apps/web/components/automation-cycle-history-card.tsx`

- ✅ 显示候选币种列表（TOP 5）
- ✅ 显示任务执行状态（train/infer/signal/review）
- ✅ 显示 RSI 快照（颜色指示：红色超买/绿色超卖）
- ✅ 显示具体拦截原因（中文翻译）
- ✅ 点击展开详情

**后端服务**: `services/api/app/services/automation_cycle_history_service.py`

- ✅ 提取并保存 RSI 快照数据
- ✅ 从 RSI 缓存获取相关币种 RSI 值
- ✅ 每次获取历史时重新加载文件（解决多进程数据不同步问题）

### 2. 配置管理界面修复

**问题**：Docker 容器中没有 api.env 文件，配置通过 docker-compose 的 env_file 注入为环境变量

**修复**：`services/api/app/services/config_center_service.py`

- `_read_env_file` 方法现在同时读取系统环境变量
- 环境变量优先级高于文件中的值

### 3. 规则门控参数调整

**服务器配置**: `infra/deploy/api.env`

```bash
QUANT_QLIB_RULE_MIN_VOLUME_RATIO=0.8  # 成交量阈值从 1.0 调整为 0.8
```

---

## 系统架构说明

### 自动化周期触发流程

1. `scheduled_patrol_service` 每 15 分钟执行巡检
2. 巡检调用 `openclaw_patrol_service.patrol()`
3. `_check_cycle_ready()` 检查是否满足条件：
   - `suggested_action` 是 `run_cycle`
   - `auto_run_allowed` 为 True
   - `mode` 是 `auto_dry_run` 或 `auto_live`
   - 冷却时间已过
   - 每日限额未达
4. 满足条件则执行 `automation_run_cycle`

### 规则门控拦截原因

| 英文代码 | 中文含义 | 说明 |
|---------|---------|------|
| `volume_not_confirmed` | 成交量不足 | 当前成交量低于历史平均的 80% |
| `volatility_too_high` | 波动率过高 | ATR 波动率超过阈值 |
| `validation_future_return_not_positive` | 预测收益为负 | 回测预测收益不满足要求 |
| `trend_broken` | 趋势破位 | EMA 趋势线破位 |
| `score_too_low` | 评分过低 | 综合评分低于阈值 |

### 状态文件位置

| 文件 | 说明 |
|------|------|
| `.runtime/automation_state.json` | 自动化状态 |
| `.runtime/automation_cycle_history.json` | 周期历史 |
| `.runtime/workbench_config.json` | 工作台配置 |
| `.runtime/rsi_cache.json` | RSI 缓存数据 |

---

## 部署命令

### 重建并部署 API 容器

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && cd infra/deploy && docker compose build api && docker compose up -d --no-deps api"
```

### 重建并部署 Web 容器

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && cd infra/deploy && docker compose build web && docker compose up -d --no-deps web"
```

### 启动定时巡检服务

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 'docker exec quant-api python3 -c "
import sys
sys.path.insert(0, \"/app/services/api\")
from services.api.app.services.scheduled_patrol_service import scheduled_patrol_service
result = scheduled_patrol_service.start_schedule(interval_minutes=15)
print(result)
"'
```

### 手动触发自动化周期

```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 'docker exec quant-api python3 -c "
import sys
sys.path.insert(0, \"/app/services/api\")
from services.api.app.services.automation_workflow_service import automation_workflow_service
result = automation_workflow_service.run_cycle(source=\"manual_trigger\")
print(\"status:\", result.get(\"status\"))
print(\"recommended_symbol:\", result.get(\"recommended_symbol\"))
"'
```

---

## 相关文件索引

### 自动化工作流

| 文件 | 说明 |
|------|------|
| `services/api/app/services/automation_workflow_service.py` | 自动化工作流主服务 |
| `services/api/app/services/automation_service.py` | 自动化状态管理 |
| `services/api/app/services/automation_cycle_history_service.py` | 历史记录服务 |
| `services/api/app/services/scheduled_patrol_service.py` | 定时巡检服务 |
| `services/api/app/services/openclaw_patrol_service.py` | 巡检执行服务 |

### 规则门控

| 文件 | 说明 |
|------|------|
| `services/worker/qlib_rule_gate.py` | 规则门控（趋势/波动/量能过滤） |
| `services/worker/qlib_ranking.py` | 候选评分与验证 |
| `services/worker/qlib_config.py` | Qlib 配置加载 |

### 前端组件

| 文件 | 说明 |
|------|------|
| `apps/web/components/automation-cycle-history-card.tsx` | 自动化周期历史卡片 |
| `apps/web/app/config/page.tsx` | 配置管理页面 |

---

## 接力提示词

```
请帮我检查系统运行状态：

1. 检查自动化状态：
   - 查看 .runtime/automation_state.json
   - 确认定时巡检服务是否运行

2. 检查最新周期历史：
   - 查看 .runtime/automation_cycle_history.json
   - 确认 RSI 快照和候选币种数据是否正常

3. 如果有拦截，分析拦截原因：
   - 查看具体的 failure_reason 和 message
   - 分析是否需要调整规则门控参数

服务器信息：
- SSH: ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
- 项目目录: ~/Quant
- Docker compose: ~/Quant/infra/deploy
```
