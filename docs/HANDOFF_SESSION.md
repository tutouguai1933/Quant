# 接力提示词

## 当前任务状态

### 已完成
1. ✅ 前端 `automation-cycle-history-card.tsx` 已更新，支持：
   - 从 `failure_reason` 计算 `display_status`（兼容旧数据）
   - 显示候选币种列表（TOP 5）
   - 显示任务执行状态
   - 显示 RSI 快照
   - 点击展开详情

2. ✅ 后端 `automation_cycle_history_service.py` 已更新，支持：
   - 计算 `display_status` 字段
   - 提取候选币种 `candidates`
   - 提取 RSI 快照 `rsi_snapshot`
   - 提取任务摘要 `task_summary`

3. ✅ 配置已更新：
   - `QUANT_PATROL_AUTO_START=true` 启用定时巡检
   - `QUANT_PATROL_INTERVAL_MINUTES=15` 每15分钟检查
   - `max_daily_cycle_count=20` 增加每日运行上限

4. ✅ Bug 修复已推送：
   - `fix: 修复 _extract_rsi_snapshot 中 candidates 类型检查` (commit: 0844335)

### 待部署
服务器上的 API 容器需要重建以应用最新代码修复：
```bash
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull && cd infra/deploy && docker compose build api && docker compose up -d --no-deps api"
```

### 验证步骤
部署后执行：
```bash
# 1. 启动巡检服务
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 'docker exec quant-api python3 -c "
import sys
sys.path.insert(0, \"/app/services/api\")
from services.api.app.services.scheduled_patrol_service import scheduled_patrol_service
result = scheduled_patrol_service.start_schedule(interval_minutes=15)
print(result)
"'

# 2. 触发一次自动化周期
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 'docker exec quant-api python3 -c "
import sys
sys.path.insert(0, \"/app/services/api\")
from services.api.app.services.automation_workflow_service import automation_workflow_service
result = automation_workflow_service.run_cycle(source=\"manual_trigger\")
print(\"status:\", result.get(\"status\"))
print(\"recommended_symbol:\", result.get(\"recommended_symbol\"))
print(\"failure_reason:\", result.get(\"failure_reason\"))
"'

# 3. 检查历史记录
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "docker exec quant-api head -60 .runtime/automation_cycle_history.json"
```

## 系统架构说明

### 自动化周期触发流程
1. `scheduled_patrol_service` 每15分钟执行巡检
2. 巡检调用 `openclaw_patrol_service.patrol()`
3. `_check_cycle_ready()` 检查是否满足条件：
   - `suggested_action` 是 `run_cycle`
   - `auto_run_allowed` 为 True
   - `mode` 是 `auto_dry_run` 或 `auto_live`
   - 冷却时间已过
   - 每日限额未达
4. 满足条件则执行 `automation_run_cycle`

### 状态文件位置
- 自动化状态: `.runtime/automation_state.json`
- 周期历史: `.runtime/automation_cycle_history.json`
- 工作台配置: `.runtime/workbench_config.json`

### 相关文件
- `/home/djy/Quant/services/api/app/services/automation_workflow_service.py` - 自动化工作流
- `/home/djy/Quant/services/api/app/services/automation_cycle_history_service.py` - 历史记录服务
- `/home/djy/Quant/services/api/app/services/scheduled_patrol_service.py` - 定时巡检
- `/home/djy/Quant/services/api/app/services/openclaw_patrol_service.py` - 巡检执行
- `/home/djy/Quant/apps/web/components/automation-cycle-history-card.tsx` - 前端组件

## 接力提示词

```
请帮我完成以下任务：

1. 部署最新代码到服务器（API 容器需要重建）：
   - git pull 拉取最新代码
   - 重建 API 容器
   - 启动巡检服务

2. 触发一次自动化周期并验证：
   - 运行 automation_workflow_service.run_cycle()
   - 检查 automation_cycle_history.json 是否有新记录
   - 新记录应包含 candidates、rsi_snapshot、task_summary 字段

3. 如果有问题，查看日志排查：
   - docker logs quant-api --tail 50
   - 检查是否有 Python 错误

服务器信息：
- SSH: ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65
- 项目目录: ~/Quant
- Docker compose: ~/Quant/infra/deploy
```
