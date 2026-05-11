# 长期运行稳定性加固方案

## 一、稳定性问题清单（按严重程度排序）

### 高危（立即修复）

| # | 问题 | 影响范围 | 文件位置 |
|---|------|---------|---------|
| 1 | CycleLock 锁文件无超时清理机制 | 进程退出后锁残留，阻塞后续自动化 | `cycle_lock.py` |
| 2 | 状态持久化无原子写入保护 | 写入崩溃导致状态损坏 | `automation_service.py` |
| 3 | Freqtrade REST 客户端重试无时间上限 | 长时间阻塞影响调度 | `rest_client.py` |
| 4 | TaskScheduler 任务执行无超时控制 | 任务可能无限阻塞 | `scheduler.py` |

### 中危（重要改进）

| # | 问题 | 影响范围 | 文件位置 |
|---|------|---------|---------|
| 5 | retry_utils 装饰器未广泛使用 | 依赖故障时直接失败 | 多个服务 |
| 6 | 前端 API 降级缺少状态标识 | 无法区分降级数据 | `api.ts` |
| 7 | sync_service 异常处理不完整 | 异常被吞掉，无恢复路径 | `sync_service.py` |
| 8 | automation_workflow_service 异常覆盖不全 | 部分调用无保护 | `automation_workflow_service.py` |

### 低危（后续优化）

| # | 问题 | 文件位置 |
|---|------|---------|
| 9 | api-error-fallback 缺少操作引导 | `api-error-fallback.tsx` |
| 10 | 健康摘要计算链过长 | `automation_workflow_service.py` |
| 11 | 日限重置无自动跨天触发 | `automation_service.py` |

---

## 二、加固方案要点

### 问题 1：CycleLock stale lock 检测

- 锁文件写入 `{pid, timestamp}`
- 检测进程是否存活
- 自动清理陈旧锁

### 问题 2：状态原子写入

- 临时文件 + rename 原子写入
- 保留最近 3 个备份版本
- 加载失败时从备份恢复

### 问题 3：Freqtrade 总超时

- 新增 `max_total_timeout_seconds` 配置
- 动态计算剩余重试次数

### 问题 4：任务超时控制

- 为每个任务类型设置默认超时
- 使用 threading + signal 实现超时

---

## 三、开发任务拆分

### P0 立即修复（10h）

| 任务 | 文件路径 | 估时 |
|-----|---------|-----|
| T1: CycleLock stale lock 检测 | `cycle_lock.py` | 2h |
| T2: 状态原子写入与备份 | `automation_service.py` | 3h |
| T3: Freqtrade 总超时上限 | `rest_client.py` | 2h |
| T4: TaskScheduler 任务超时 | `scheduler.py` | 3h |

### P1 重要改进（11h）

| 任务 | 文件路径 | 估时 |
|-----|---------|-----|
| T5: 统一应用 retry_utils | 多个服务 | 4h |
| T6: 前端降级响应增强 | `api.ts` | 3h |
| T7: sync_service 告警与恢复 | `sync_service.py` | 2h |
| T8: workflow_service 异常补全 | `automation_workflow_service.py` | 2h |

### P2 后续优化（4h）

| 任务 | 估时 |
|-----|-----|
| T9: error-fallback 交互增强 | 1h |
| T10: 健康摘要异常隔离 | 2h |
| T11: 日限自动跨天 | 1h |

---

## 四、执行顺序

```
P0: T1 → T2 → T4 → T3 (10h)
P1: T5 → T7 → T8 → T6 (11h)
P2: T9 → T10 → T11 (4h)
```

**总估时：25 小时**