# Freqtrade 真实集成计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前内存态的 Freqtrade 最小适配器升级成真实的加密执行层，但继续保持 `demo / dry-run / live` 的安全边界。

**Architecture:** 控制平面继续负责统一任务和页面，真实执行改由 Freqtrade REST API 承担。第一阶段先打通读取状态、控制 bot、同步订单持仓和 dry-run 执行，不提前开放真实下单。

**Tech Stack:** Python、FastAPI、标准库 HTTP、Freqtrade REST API、现有 unittest、WebUI 现有页面

**运行约定：** 所有 Python 相关命令默认在 conda 环境 `quant` 中执行。

---

## 范围

### 本计划要做

- 真实 Freqtrade REST 客户端
- 运行模式和连接配置收敛
- bot `start / stop / pause` 控制
- 订单、成交、持仓、策略状态同步
- dry-run 和 live 的安全边界检查
- 控制平面页面和文档对齐

### 本计划不做

- 真实 live 自动下单开放
- 策略参数在线编辑器
- 多交易所
- Lean / vn.py 实现

## 文件规划

### 新建

- `services/api/app/adapters/freqtrade/rest_client.py`
  负责真实 Freqtrade HTTP 调用、认证、错误处理
- `services/api/app/services/freqtrade_runtime_service.py`
  负责把运行模式、连接状态、安全边界收成统一视图
- `services/api/tests/test_freqtrade_rest_client.py`
  负责真实客户端的单元测试
- `services/api/tests/test_freqtrade_runtime_service.py`
  负责运行模式和安全边界测试
- `docs/ops-freqtrade.md`
  负责真实 Freqtrade 接入说明、配置、验收步骤

### 修改

- `services/api/app/adapters/freqtrade/client.py`
  从纯内存实现升级为门面，支持 `memory` 和 `rest` 两种后端
- `services/api/app/services/execution_service.py`
  接入真实运行模式判断
- `services/api/app/services/sync_service.py`
  改成优先读取真实 Freqtrade 快照
- `services/api/app/routes/strategies.py`
  对接真实 start / stop / pause
- `services/api/app/routes/orders.py`
  返回真实 Freqtrade 订单 / 成交同步结果
- `services/api/app/routes/positions.py`
  返回真实持仓同步结果
- `services/api/app/routes/tasks.py`
  增加 Freqtrade 同步任务记录
- `apps/web/app/strategies/page.tsx`
  展示执行器连接状态和运行模式
- `apps/web/app/orders/page.tsx`
  展示真实同步来源和状态
- `apps/web/app/positions/page.tsx`
  展示真实同步来源和状态
- `apps/web/lib/api.ts`
  对接新的执行器状态字段
- `README.md`
- `docs/architecture.md`
- `docs/api.md`
- `CONTEXT.md`

## Todo List

- [x] 配置模型里收敛 Freqtrade URL、用户名、密码和运行模式
- [x] 新增真实 Freqtrade REST 客户端
- [x] 保留内存态后端作为无配置回退
- [x] 打通 bot `start / stop / pause`
- [x] 打通订单、成交、持仓、策略状态同步
- [x] 在策略页显示真实执行器状态
- [x] 在订单页、持仓页显示真实同步来源
- [x] 补 dry-run / live 安全边界测试
- [x] 补真实接入运维文档
- [ ] 完成端到端 dry-run 验收

## 任务拆分

### Task 1：整理配置与运行模式

- [x] 新增或收敛 Freqtrade 配置项：地址、认证、模式、启用开关
- [x] 写失败测试：无配置时应回退到内存态
- [x] 写失败测试：`live` 无确认开关时必须拒绝
- [x] 实现最小配置读取和模式守卫
- [x] 运行目标测试并确认通过

### Task 2：实现真实 REST 客户端

- [x] 写失败测试：健康检查、策略状态、订单、持仓读取
- [x] 写失败测试：网络错误和非 200 返回时给出明确错误
- [x] 实现最小 GET / POST 封装
- [x] 实现 bot 状态、订单、持仓、交易对读取
- [x] 运行目标测试并确认通过

### Task 3：升级执行门面

- [x] 写失败测试：有配置时走 REST，无配置时走内存态
- [x] 把 `client.py` 改成统一门面
- [x] 保留当前测试兼容
- [x] 运行执行与同步相关测试并确认通过

### Task 4：接入策略控制与同步

- [x] 写失败测试：`start / stop / pause` 路由应返回真实执行器状态
- [x] 写失败测试：订单页、持仓页应返回真实来源标签
- [x] 修改路由与服务实现
- [x] 运行后端相关测试并确认通过

### Task 5：更新前端状态展示

- [x] 写失败测试：策略页显示执行器连接状态
- [x] 写失败测试：订单页、持仓页显示同步来源
- [x] 实现最小页面改动
- [x] 运行前端测试、类型检查和构建

### Task 6：文档和验收

- [x] 新增 `docs/ops-freqtrade.md`
- [x] 更新 README、架构、接口、CONTEXT
- [x] 完成真实 dry-run 页面验证
- [x] 在 Todo 中勾掉已完成项

## 当前完成说明

- 已完成 `memory / rest` 双后端门面
- 已完成 `demo / dry-run / live` 安全边界收敛
- 已修正关键安全问题：
  - `demo` 和 `live` 不会因为残留 Freqtrade 凭据误碰真实 bot
  - `dry-run` 会校验远端 Freqtrade 的真实模式，不接受本地自报模式
  - 策略页、订单页、持仓页现在统一读取同一份执行器运行快照
  - `start / pause / stop` 当前明确只控制整台 Freqtrade 执行器，避免误导成“单策略控制”
- 已完成真实页面验证：
  - 登录后策略页会显示 `已解锁`
  - 策略页会显示执行器状态和“执行器控制”说明
  - 点击“启动策略”后，页面能看到 `running`
  - 点击“派发最新信号”后，订单页能看到 `filled`
  - 点击“派发最新信号”后，持仓页能看到 `BTC/USDT` 和 `long`
- 当前仍未完成的是“接入一台真实 Freqtrade REST 服务并完成整条端到端 dry-run 验收”

## 验收标准

- 控制平面可以识别当前是内存态还是 Freqtrade REST 模式
- 有真实 Freqtrade 配置时，策略控制接口能返回真实状态
- 订单页和持仓页能显示真实同步来源
- `live` 仍默认不开放
- 页面上能看见执行器状态变化，不只是后端日志变化

## 建议验证命令

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest discover -s services/api/tests -v
python -m unittest discover -s tests -v
cd apps/web && pnpm exec tsc --noEmit && pnpm build
```

预期结果：

- 后端测试通过
- 前端测试通过
- 类型检查通过
- 构建通过
