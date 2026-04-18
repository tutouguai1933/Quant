# Openclaw 安全动作模式设计

## 1. 目标

这版接入只解决一件事：让 `Openclaw` 成为项目的外层自动化运维代理，在不碰交易决策的前提下，承担低风险的巡检、降级、重启和补跑动作。

最终效果不是“让 Openclaw 接管量化系统”，而是：

- 项目继续负责研究、评估、执行和风控判断
- 项目继续给出统一结论：现在能不能继续跑、为什么不能、下一步该做什么
- `Openclaw` 只负责按这份结论执行安全动作，并把动作记录回任务页

## 2. 范围

### 这版要做

- 让 `Openclaw` 定时读取一份统一的运维快照
- 让 `Openclaw` 只执行白名单里的低风险动作
- 让 `Openclaw` 支持两类动作：
  - 项目 HTTP 动作
  - 服务器上的系统动作
- 让所有 `Openclaw` 动作都能回写成任务或审计记录
- 让任务页能看到“刚刚是 Openclaw 做了什么”

### 这版不做

- 不让 `Openclaw` 自己决定买卖
- 不让 `Openclaw` 自动放开 `live`
- 不让 `Openclaw` 自动解除人工接管
- 不让 `Openclaw` 绕过现有风控、恢复清单和候选门控

## 3. 总体思路

推荐采用“双层守护模式”。

### 内层：项目自己判断

项目内继续使用现有自动化状态收口结果：

- `runtime_guard`
- `recovery_review`
- `control_actions`
- `operator_actions`
- 执行器健康、任务健康、告警摘要

这层负责统一回答：

- 现在是正常、运行中、等待、降级还是人工接管
- 现在为什么不能继续
- 哪些动作是安全的
- 哪些动作只能人工处理

### 外层：Openclaw 只落地动作

`Openclaw` 不自己推理业务含义，只做四件事：

- 拉取统一运维快照
- 判断当前是否命中某条安全动作规则
- 执行动作
- 回写动作结果

这样可以保证整套系统始终只有一份业务口径，避免项目和 `Openclaw` 各自说各自的。

## 4. 统一接口设计

### 4.1 新增统一快照接口

建议新增一个专门给 `Openclaw` 用的统一快照接口，例如：

- `GET /api/v1/ops/openclaw/snapshot`

这份快照不要让 `Openclaw` 自己拼多个接口，而是由项目后端统一聚合后输出。

建议快照至少包含：

- 基础状态
  - `overall_status`
  - `mode`
  - `manual_takeover`
  - `paused`
- 自动化结论
  - `runtime_guard`
  - `recovery_review`
- 执行状态
  - `executor_runtime`
  - `connection_status`
  - `account_state.status`
- 服务状态
  - `api_expected_up`
  - `web_expected_up`
  - `freqtrade_expected_up`
- 安全动作白名单
  - `allowed_safe_actions`
  - `disabled_safe_actions`
  - 每个动作的 `reason`
- 保护边界
  - `live_enable_allowed=false`
  - `manual_takeover_release_allowed=false`
  - `max_restart_attempts`
  - `restart_cooldown_seconds`
- 审计字段
  - `snapshot_id`
  - `generated_at`

### 4.2 新增 Openclaw 安全动作网关

建议新增统一动作入口，例如：

- `POST /api/v1/ops/openclaw/actions/{action}`

原因是这比让 `Openclaw` 直接调用很多现有接口更安全：

- 后端可以二次校验动作是否仍然允许
- 后端可以统一写审计记录
- 后端可以统一补充动作原因、来源和结果

这个入口只允许白名单动作，不允许交易类动作。

## 5. 安全动作白名单

第一版只开放以下动作。

### 5.1 HTTP 安全动作

- `automation_run_cycle`
  - 只在当前允许继续、且没有正在运行的自动化轮次时可执行
- `automation_dry_run_only`
  - 当执行器异常、同步异常或当前需要保守降级时执行
- `automation_clear_non_error_alerts`
  - 只做信息清理，不改变交易风险
- `automation_confirm_alert`
  - 只允许确认预设可确认的告警类型

### 5.2 系统安全动作

- 重启 `api`
- 重启 `web`
- 重启 `freqtrade`

这类动作只允许在以下场景中执行：

- 健康检查失败
- 端口不通
- 进程或容器不存在
- 快照明确提示执行器不可用且允许尝试恢复

### 5.3 明确禁止的动作

- 自动切 `auto_live`
- 自动恢复到 `live`
- 自动解除人工接管
- 自动执行真实下单
- 自动修改候选范围、阈值、因子、策略参数

## 6. Openclaw 决策规则

`Openclaw` 的规则要尽量固定、短、可审计，不做开放式推理。

### 6.1 服务存活规则

如果 `api` 或 `web` 不可达：

1. 先做一次健康检查
2. 若仍失败，执行对应服务重启
3. 等待固定冷却时间
4. 再次探活
5. 若仍失败，停止自动动作并写入人工处理记录

### 6.2 执行器异常规则

如果快照显示执行器异常或同步异常：

1. 优先调用 `automation_dry_run_only`
2. 如允许，再尝试重启 `freqtrade`
3. 若恢复失败，保持保守状态并要求人工接管

这里的原则是“先降级，再恢复”，而不是“先重启，赌它恢复”。

### 6.3 自动化卡住规则

如果快照显示：

- 当前没有人工接管
- 当前没有错误级阻塞
- 当前不在运行中
- 当前允许继续下一轮

则可以执行一次 `automation_run_cycle`。

如果快照显示正在运行或处于冷却窗口，`Openclaw` 只能等待，不能补跑第二轮。

### 6.4 人工接管规则

如果当前是人工接管：

- `Openclaw` 不得自动恢复
- `Openclaw` 只能记录、提醒和保持当前状态
- 超过接管复核时间时，写回“需要人工复核”的任务记录

### 6.5 重启节流规则

为防止抖动重启，所有系统动作要带节流：

- 同一服务在固定窗口内最多重启 `N` 次
- 连续失败达到阈值后，进入“只报警不再自动重试”

## 7. 审计与任务页承接

### 7.1 审计记录

所有 `Openclaw` 动作都必须留下统一记录，来源写成：

- `source=openclaw`

建议记录：

- 动作类型
- 动作目标
- 触发原因
- 动作前状态
- 动作后结果
- 是否成功
- 失败原因
- 关联快照编号

### 7.2 任务页展示

任务页后续需要增加一块面向运维的摘要：

- 最近一次 `Openclaw` 动作
- 为什么触发
- 执行成功还是失败
- 现在是否还需要人工处理

用户在任务页看到的应该是一句人话：

- “Openclaw 已将系统切到 dry-run only，因为执行器连接失败”
- “Openclaw 已尝试重启 Freqtrade，但恢复失败，当前仍需人工处理”

## 8. 模块边界

建议拆成四个职责明确的部分。

### 8.1 快照聚合层

建议新增：

- `services/api/app/services/openclaw_snapshot_service.py`

职责：

- 聚合 `automation`、`strategies`、服务状态和动作白名单
- 输出给 `Openclaw` 的唯一结构化快照

### 8.2 动作策略层

建议新增：

- `services/api/app/services/openclaw_action_policy_service.py`

职责：

- 定义哪些动作允许
- 定义每个动作的前置条件
- 禁止危险动作进入安全模式

### 8.3 动作执行层

建议新增：

- `services/api/app/services/openclaw_action_service.py`

职责：

- 执行 HTTP 安全动作
- 记录动作结果
- 返回标准执行结果

### 8.4 外层适配层

`Openclaw` 在服务器侧实现：

- 拉快照
- 检查本机服务
- 执行白名单系统动作
- 调用项目动作网关

这个外层不应该把业务规则再写一遍，只做“按快照执行”。

## 9. 第一阶段上线范围

第一阶段只做最小闭环，目标是让它先成为“安全保守的运维代理”。

### 第一阶段包含

- 统一快照接口
- 安全动作网关
- 三个系统动作：
  - 重启 `api`
  - 重启 `web`
  - 重启 `freqtrade`
- 两个 HTTP 动作：
  - `automation_run_cycle`
  - `automation_dry_run_only`
- 任务/审计回写
- 任务页展示最近一次 `Openclaw` 动作

### 第一阶段不包含

- 自动放开 `live`
- 自动解除人工接管
- 自动改配置
- 自动处理交易类异常

## 10. 验收标准

第一阶段通过，至少要满足下面这些条件。

- 服务掉线后，`Openclaw` 能在限定次数内自动恢复
- 自动化允许继续时，`Openclaw` 能安全补跑下一轮
- 执行器异常时，`Openclaw` 会优先切到 `dry-run only`
- 人工接管时，`Openclaw` 不会擅自恢复
- 所有 `Openclaw` 动作都能在任务页回看
- 整个过程中不会自动放开 `live`

## 11. 风险与边界

这条线最大的风险不是“重启失败”，而是“自动化运维权过大”。

所以必须坚持三条铁规则：

- 只能做白名单动作
- 只能降风险，不能自动放大风险
- 高风险场景一律收口到任务页和人工接管

如果后续要扩到更强自治，也必须在这版稳定后再做，不应该一开始就放开。
