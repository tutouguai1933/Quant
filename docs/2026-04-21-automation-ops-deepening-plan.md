# 自动化运营深化实施方案

## 目标

将自动化运维从"手动触发 + 基础巡检"升级到"定时巡检 + 智能建议 + 安全执行"，坚持分层负责原则：

- **程序负责判断**：确定性业务逻辑、状态聚合、门控决策
- **模型辅助边界**：非预期异常、跨系统协调、人话翻译

---

## 当前状态

### 已完成（Phase 1）

| 模块 | 文件 | 状态 |
|------|------|------|
| 统一快照聚合 | `openclaw_snapshot_service.py` | ✓ 完成 |
| 安全动作策略 | `openclaw_action_policy_service.py` | ✓ 完成 |
| 动作执行服务 | `openclaw_action_service.py` | ✓ 完成 |
| API 路由 | `routes/openclaw.py` | ✓ 完成 |
| 审计记录 | `openclaw_audit_service.py` | ✓ 完成 |
| 重启历史 | `openclaw_restart_history_service.py` | ✓ 完成 |
| 系统动作执行器 | `system_action_executor.py` | ✓ 完成 |

### 已有安全动作白名单

| 动作 | 场景 | 前置条件 |
|------|------|----------|
| `automation_run_cycle` | 自动化周期运行 | ready 状态、无人工接管 |
| `automation_dry_run_only` | 切换到保守模式 | 无人工接管 |
| `automation_clear_non_error_alerts` | 清理非错误告警 | 无人工接管 |
| `system_restart_web` | 重启 Web 服务 | 节流限制内 |
| `system_restart_freqtrade` | 重启 Freqtrade | 节流限制内 |

---

## Phase 2: 强化内层判断

### 2.1 扩展 runtime_guard 结构

当前 `runtime_guard` 只返回 `ready_for_cycle` 和 `blocked_reason`。建议扩展：

```python
runtime_guard = {
    "status": "ready" | "blocked" | "running" | "cooldown" | "attention_required",
    "ready_for_cycle": bool,
    "blocked_reason": str,
    "blockers": [
        {"code": "executor_error", "label": "执行器连接失败", "severity": "high"},
        {"code": "no_candidate", "label": "候选篮子为空", "severity": "medium"},
    ],
    "degrade_mode": "none" | "dry_run_only" | "paused",
    "degrade_reason": str,
    "suggested_action": str,  # 程序建议的下一步动作
    "suggested_action_reason": str,
    "cooldown_ends_at": str,  # 冷却结束时间
    "last_cycle_at": str,
    "cycles_today": int,
    "auto_run_allowed": bool,  # 是否允许 OpenClaw 自动运行
}
```

### 2.2 扩展 recovery_review 结构

当前 `recovery_review` 只返回 `resume_needed`。建议扩展：

```python
recovery_review = {
    "status": "ready" | "attention_required" | "waiting" | "manual",
    "headline": str,
    "detail": str,
    "next_action": str,  # 程序推荐的下一步
    "next_action_reason": str,
    "blockers": [...],
    "operator_steps": [
        {"step": 1, "action": "检查执行器连接", "done": bool},
        {"step": 2, "action": "确认候选篮子不为空", "done": bool},
    ],
    "auto_recoverable": bool,  # 是否允许程序自动恢复
    "manual_required_reason": str,  # 为什么必须人工处理
}
```

### 2.3 新增 suggested_action 字段

在快照中明确返回程序建议的动作：

```python
allowed_safe_actions = [
    {
        "action": "automation_run_cycle",
        "reason": "当前允许继续下一轮自动化",
        "preconditions_met": True,
        "auto_execute": True,  # OpenClaw 可自动执行
        "priority": 1,  # 执行优先级
    },
    {
        "action": "automation_dry_run_only",
        "reason": "执行器异常，建议切到 dry-run only",
        "preconditions_met": True,
        "auto_execute": True,
        "priority": 2,
    },
]
```

---

## Phase 3: 扩展安全动作白名单

### 3.1 新增 HTTP 安全动作

| 动作 | 场景 | 前置条件 |
|------|------|----------|
| `automation_sync_state` | 同步执行器状态 | 无人工接管 |
| `automation_retry_last_cycle` | 重试失败的周期 | 上轮失败、允许重试 |
| `automation_reload_config` | 重载配置 | 无人工接管 |
| `automation_health_check` | 健康检查 | 总是允许 |

### 3.2 新增系统安全动作

| 动作 | 场景 | 前置条件 |
|------|------|----------|
| `system_reload_freqtrade_config` | 重载 Freqtrade 配置 | 连接正常 |
| `system_sync_freqtrade_state` | 同步 Freqtrade 状态 | 连接正常 |

### 3.3 新增候选/执行相关动作（低风险）

| 动作 | 场景 | 前置条件 |
|------|------|----------|
| `research_run_training` | 运行研究训练 | 候选篮子不为空 |
| `research_run_inference` | 运行研究推理 | 有训练结果 |

---

## Phase 4: 定时巡检机制

### 4.1 新增定时巡检服务

```python
# services/api/app/services/openclaw_patrol_service.py

class OpenclawPatrolService:
    """定时巡检服务，按固定间隔检查系统状态并执行安全动作。"""
    
    PATROL_INTERVALS = {
        "health_check": 60,  # 每分钟健康检查
        "state_sync": 300,   # 每5分钟状态同步
        "cycle_check": 900,  # 每15分钟周期检查
    }
    
    def patrol(self) -> dict:
        """执行一轮巡检。"""
        snapshot = self._snapshot_service.get_snapshot()
        
        # 1. 健康检查
        self._check_service_health(snapshot)
        
        # 2. 状态同步
        self._sync_executor_state(snapshot)
        
        # 3. 自动化周期检查
        self._check_cycle_ready(snapshot)
        
        # 4. 执行程序建议的安全动作
        self._execute_suggested_actions(snapshot)
        
        return {"patrolled": True, "actions_taken": [...]}
```

### 4.2 巡检规则（程序判断）

| 规则 | 触发条件 | 建议动作 |
|------|----------|----------|
| 服务存活 | API/Web/Freqtrade 不可达 | 重启对应服务 |
| 执行器异常 | connection_status=error | 切 dry_run_only |
| 周期就绪 | ready_for_cycle=True 且 cooldown 已过 | run_cycle |
| 告警堆积 | 告警数 > 阈值 | clear_non_error_alerts |
| 同步过期 | 最后同步时间 > 10分钟 | sync_state |

### 4.3 巡检节流

- 同一动作在窗口内最多执行 N 次
- 连续失败后停止自动执行，进入人工处理
- 每轮巡检最多执行 1 个动作（避免连锁反应）

---

## Phase 5: 模型辅助边界场景

### 5.1 模型介入场景

仅当程序规则无法覆盖时，模型才介入：

| 场景 | 程序判断 | 模型辅助 |
|------|----------|----------|
| 多服务同时异常 | 无法确定优先级 | 建议"先重启哪个" |
| 配置漂移 | 检测到漂移但不知原因 | 解释"为什么漂移" |
| 告警解释 | 只有 code/message | 转成人话"发生了什么" |
| 跨系统协调 | 单系统无法决策 | 建议"先恢复哪个系统" |

### 5.2 模型建议流程

```python
def get_model_suggestion(snapshot: dict) -> dict:
    """模型给出辅助建议（须经白名单校验才能执行）。"""
    
    # 模型只返回建议，不直接执行
    suggestion = {
        "suggested_action": str,  # 建议的动作
        "reason": str,  # 建议原因（人话）
        "confidence": float,  # 建议置信度
        "requires_approval": bool,  # 是否需要人工确认
    }
    
    # 建议动作必须通过白名单校验
    if not policy.is_action_allowed(suggestion["suggested_action"]):
        return {"error": "建议动作不在白名单中"}
    
    return suggestion
```

### 5.3 模型输出边界

- 模型只能返回**建议**，不能直接触发执行
- 建议动作必须通过白名单校验
- 高置信度建议可自动执行（需配置），低置信度需人工确认
- 所有模型建议必须记录审计日志

---

## Phase 6: 审计与可观测性

### 6.1 扩展审计记录

```python
audit_record = {
    "id": str,
    "timestamp": str,
    "source": "program" | "patrol" | "model_suggestion" | "manual",
    "action": str,
    "reason": str,
    "snapshot_id": str,
    "before_state": dict,
    "after_state": dict,
    "success": bool,
    "model_confidence": float | None,  # 如果有模型建议
    "requires_approval": bool,
    "approved_by": str | None,  # 如果需要人工确认
}
```

### 6.2 任务页展示优化

新增"OpenClaw 运维摘要"区域：

```
最近一轮巡检：2026-04-21 22:30
状态：正常

最近动作：
- 22:25 执行器健康检查 ✓
- 22:20 清理了 3 条信息级告警 ✓
- 22:15 自动运行周期 ✓

当前建议：无，系统正常运行
```

---

## 实施顺序

### 批次 1：内层判断强化（P0）

1. 扩展 `runtime_guard` 结构
2. 扩展 `recovery_review` 结构  
3. 在快照中添加 `suggested_action` 字段
4. 更新前端任务页展示新字段

### 批次 2：定时巡检机制（P1）

1. 创建 `openclaw_patrol_service.py`
2. 注册定时任务（每分钟/每5分钟/每15分钟）
3. 实现巡检规则和节流逻辑
4. 在任务页展示巡检状态

### 批次 3：安全动作扩展（P2）

1. 新增 HTTP 安全动作白名单
2. 新增系统安全动作白名单
3. 实现动作执行逻辑
4. 更新策略服务校验

### 批次 4：模型辅助集成（P3）

1. 创建模型建议接口
2. 实现建议校验流程
3. 添加置信度和人工确认逻辑
4. 完善审计记录

---

## 验收标准

### Phase 2 完成

- `runtime_guard` 返回完整结构
- `recovery_review` 返回完整结构
- 快照包含 `suggested_action` 字段
- 任务页展示新增字段

### Phase 3 完成

- 定时巡检每分钟执行
- 服务异常自动重启（节流内）
- 告警堆积自动清理
- 周期就绪自动运行

### Phase 4 完成

- 模型能给出辅助建议
- 建议动作通过白名单校验
- 审计记录包含模型置信度
- 低置信度建议需人工确认

### 整体验收

- 服务掉线后，程序能在限定次数内自动恢复
- 执行器异常时，程序自动切到 dry-run only
- 自动化就绪时，程序自动补跑周期
- 人工接管时，程序不擅自恢复
- 所有动作可在任务页回看
- 整个过程不自动放开 live

---

## 风险边界

坚持三条铁规则：

1. **只能做白名单动作**：不在白名单的动作一律禁止
2. **只能降风险，不能放大风险**：自动切 dry-run，不自动切 live
3. **高风险场景收口到人工**：连续失败、异常、接管都转人工处理

---

## 文件清单

### 新建文件

- `services/api/app/services/openclaw_patrol_service.py`
- `services/api/app/services/model_suggestion_service.py`
- `docs/2026-04-21-automation-ops-deepening-plan.md`（本文件）

### 修改文件

- `services/api/app/services/automation_service.py` - 扩展 runtime_guard
- `services/api/app/services/openclaw_snapshot_service.py` - 扩展快照结构
- `services/api/app/services/openclaw_action_policy_service.py` - 扩展白名单
- `services/api/app/services/openclaw_action_service.py` - 新增动作执行
- `services/api/app/routes/openclaw.py` - 新增巡检 API
- `apps/web/app/tasks/page.tsx` - 展示巡检状态

---

## 下一步

确认后开始实施批次 1（内层判断强化）。