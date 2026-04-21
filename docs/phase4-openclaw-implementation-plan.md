# OpenClaw 安全动作模式实施方案

## 一、现状分析

### 1.1 已实现的基础框架

| 组件 | 文件路径 | 状态 |
|------|----------|------|
| 快照聚合服务 | `services/api/app/services/openclaw_snapshot_service.py` | 已实现 |
| 动作策略服务 | `services/api/app/services/openclaw_action_policy_service.py` | 已实现 |
| 动作执行服务 | `services/api/app/services/openclaw_action_service.py` | 已实现 |
| API 路由 | `services/api/app/routes/openclaw.py` | 已实现 |
| 前端展示 | `apps/web/app/tasks/page.tsx` | 已展示基础状态 |

### 1.2 待补充的功能

1. 系统动作实现：重启 api/web/freqtrade 服务
2. 独立审计记录存储
3. 服务状态探测增强
4. 运维审计展示
5. 保护边界验证增强

---

## 二、动作白名单清单（第一阶段）

### HTTP 安全动作

| 动作名 | 说明 | 前置条件 | 实现状态 |
|--------|------|----------|----------|
| `automation_run_cycle` | 运行自动化周期 | `ready_for_cycle=true`, `manual_takeover=false` | 已实现 |
| `automation_dry_run_only` | 切到 dry-run only | `manual_takeover=false` | 已实现 |
| `automation_clear_non_error_alerts` | 清理非错误告警 | `manual_takeover=false` | 已实现 |
| `automation_confirm_alert` | 确认告警 | 告警存在且可确认 | 已实现 |

### 系统安全动作（新增）

| 动作名 | 说明 | 前置条件 | 实现状态 |
|--------|------|----------|----------|
| `system_restart_api` | 重启 API 服务 | 服务不可达，重启次数未超限 | 需实现 |
| `system_restart_web` | 重启 Web 服务 | 服务不可达，重启次数未超限 | 需实现 |
| `system_restart_freqtrade` | 重启 Freqtrade | 执行器异常，重启次数未超限 | 需实现 |

### 明确禁止的动作

| 动作名 | 说明 | 禁止原因 |
|--------|------|----------|
| `automation_auto_live` | 切到 auto_live | 高风险，需人工确认 |
| `automation_resume` | 恢复自动化 | 可能绕过人工接管检查 |
| `automation_release_takeover` | 解除人工接管 | 高风险，必须人工处理 |
| `execute_order` | 执行订单 | 交易决策，不应触碰 |
| `modify_strategy` | 修改策略 | 配置变更，需人工确认 |

---

## 三、开发任务拆分

### 第一批次（基础框架）

| 任务 | 文件路径 | 说明 |
|-----|---------|------|
| T1: 新增审计服务 | `services/openclaw_audit_service.py` | 记录动作审计 |
| T2: 新增重启历史服务 | `services/openclaw_restart_history_service.py` | 管理重启节流 |
| T3: 新增服务健康检查 | `services/service_health_service.py` | 探测各服务状态 |

### 第二批次（核心逻辑）

| 任务 | 文件路径 | 说明 |
|-----|---------|------|
| T4: 增强动作策略服务 | `openclaw_action_policy_service.py` | 新增系统动作白名单 |
| T5: 新增系统动作执行器 | `services/system_action_executor.py` | 执行重启服务 |
| T6: 增强动作执行服务 | `openclaw_action_service.py` | 集成审计和系统动作 |

### 第三批次（API 和前端）

| 任务 | 文件路径 | 说明 |
|-----|---------|------|
| T7: 增强快照服务 | `openclaw_snapshot_service.py` | 添加服务健康字段 |
| T8: 增强 API 路由 | `routes/openclaw.py` | 新增审计和重启历史接口 |
| T9: 前端 API 增强 | `apps/web/lib/api.ts` | 新增 OpenClaw API |
| T10: 前端任务页增强 | `apps/web/app/tasks/page.tsx` | 展示动作历史 |

---

## 四、验收标准

| 验收项 | 验收标准 |
|--------|----------|
| 服务重启 | 能在限定次数内自动重启不可达服务 |
| 自动化补跑 | 允许继续时能安全触发下一轮 |
| 执行器异常 | 异常时优先切到 dry-run only |
| 人工接管 | 接管状态下不执行任何安全动作 |
| 动作审计 | 所有动作都有审计记录可追溯 |
| 保护边界 | 不会自动放开 live、不会解除接管 |