# Quant 项目审阅报告

> 审阅时间：2026-05-06  
> 审阅依据：`docs/CODEX_REVIEW_PROMPT.md`  
> 审阅方式：线上页面访问、Playwright 自动化、SSH 服务器检查、本地代码对照。  
> 线上地址：`http://39.106.11.65:9012`  
> API 地址：`http://39.106.11.65:9011/api/v1`

---

## 概述

整体项目已经具备可用的量化交易控制平面：前端页面基本可打开，核心容器在线，API 健康检查正常，研究、回测、信号、策略、任务等主线页面已形成统一终端风格。

本次审阅发现的主要问题集中在三类：

- 部分新页面的接口路径拼接错误，导致页面显示 fallback 数据而不是真实数据。
- 部分前端“受保护页面”只在导航里拦截，直接访问页面仍能看到操作界面。
- 运维监控页前后端契约不一致，接口路径、WebSocket channel 和后端路由不匹配。

线上自动化结果：

- Playwright 抽查 19 项，18 项通过，1 项失败。
- 失败项是登录按钮 pending 文案不一致：测试期望 `登录中…`，线上显示 `登录中...`。
- 逐页访问 21 个路由均返回 HTTP 200，未发现页面级崩溃。
- `/analytics`、`/config`、`/ops` 存在内部接口 404。

服务器状态：

- SSH 连接成功，核心容器均在运行。
- `quant-api`、`quant-web` 当前 Docker health 为 `none`，但 API 自身 `/api/v1/health` 返回健康。
- `quant-freqtrade`、`quant-grafana`、`quant-prometheus`、`quant-mihomo`、`quant-openclaw` 显示 healthy。

---

## 页面检查结果

### 首页（/）

- 性能：线上首包快，HTTP 200。
- 逻辑：首页能展示工作台内容，未发现页面崩溃。
- 内容：文案和终端风格一致。
- 问题：侧边栏底部状态仍是硬编码，例如“实盘连接 已连接”，没有从真实接口读取。

### 模型训练（/research）

- 性能：HTTP 200，页面内容完整。
- 逻辑：未登录直接访问仍能看到模型训练页面和训练相关按钮。
- 内容：标题为“模型训练”，与终端化规划一致。
- 问题：页面导航标记为受保护，但实际直达页面没有阻断。

### 回测训练（/backtest）

- 性能：HTTP 200。
- 逻辑：页面可打开，未发现前端崩溃。
- 内容：标题为“回测训练”，符合当前定位。
- 问题：同样存在“导航标记受保护，但直达页面可访问”的一致性问题。

### 选币回测（/evaluation）

- 性能：HTTP 200。
- 逻辑：页面可打开。
- 内容：标题为“选币回测”，与前端终端化方向一致。
- 问题：受保护状态与实际直达访问不一致。

### 因子研究（/features）

- 性能：HTTP 200。
- 逻辑：页面可打开，按钮和输入控件存在。
- 内容：标题为“因子研究”。
- 问题：受保护状态与实际直达访问不一致。

### 信号（/signals）

- 性能：HTTP 200。
- 逻辑：网络抽查没有 404。
- 内容：标题、页面定位基本一致。
- 问题：未发现高优先级问题。

### 参数优化（/hyperopt）

- 性能：HTTP 200。
- 逻辑：前端未登录时显示“需要登录”。
- 内容：定位清晰。
- 问题：后端 `/api/v1/hyperopt/start` 和 `/stop` 路由没有认证保护，存在绕过前端直接调用的风险。

### 数据分析（/analytics）

- 性能：页面 HTTP 200。
- 逻辑：页面内部 6 个接口 404。
- 内容：页面会显示 fallback 数据，容易让用户以为真实数据为空。
- 问题：前端请求 `/api/control/api/v1/analytics...`，后端实际可用路径是 `/api/v1/analytics...`，代理后变成 `/api/v1/api/v1/analytics...`。

### 数据管理（/data）

- 性能：HTTP 200。
- 逻辑：页面可打开。
- 内容：页面标题为“数据工作台”，侧边栏为“数据管理”，命名不完全一致。
- 问题：低优先级命名一致性问题。

### 因子知识库（/factor-knowledge）

- 性能：HTTP 200。
- 逻辑：页面可打开。
- 内容：标题和定位一致。
- 问题：未发现高优先级问题。

### 配置管理（/config）

- 性能：页面 HTTP 200。
- 逻辑：页面内部请求 `/api/v1/config` 和 `/api/v1/config/schema`，在 Web 域名下返回 404。
- 内容：未登录时显示需要登录。
- 问题：前端绕过 `/api/control` 代理，导致线上页面无法加载真实配置；后端配置查询 GET 路由未做认证，修正代理后需要同步补认证策略。

### 策略中心（/strategies）

- 性能：HTTP 200。
- 逻辑：未登录时显示需要登录。
- 内容：页面 H1 为“策略”，侧边栏为“策略中心”，命名不完全一致。
- 问题：低优先级命名一致性问题。

### 运维监控（/ops）

- 性能：页面 HTTP 200。
- 逻辑：页面内部 4 个接口 404，WebSocket 订阅 `health_status` 被后端判定为未知 channel。
- 内容：页面可以显示 fallback 状态，但不是完整真实状态。
- 问题：前端请求 `/api/control/api/v1/health`、`/api/control/api/v1/alerts`、`/api/control/api/v1/patrol/status`、`/api/control/api/v1/patrol/schedule`；后端没有 `/api/v1/alerts` 和 `/api/v1/patrol/status`，`/api/v1/patrol/schedule` 返回结构也不是前端期待的 envelope。

### 任务（/tasks）

- 性能：HTTP 200。
- 逻辑：未登录时显示需要登录。
- 内容：任务页面可访问，已有自动化状态入口。
- 问题：未发现高优先级问题。

### 市场（/market、/market/BTCUSDT）

- 性能：HTTP 200。
- 逻辑：网络抽查没有 404。
- 内容：市场列表正常；当前代码中单币详情页标题已使用标的名称，例如 `BTCUSDT`。
- 问题：未发现高优先级问题。

### 余额 / 持仓 / 订单 / 风险

- 性能：均 HTTP 200。
- 逻辑：持仓、订单、风险页面可打开。
- 内容：空状态和页面标题基本清晰。
- 问题：未发现高优先级问题。

### 登录（/login）

- 性能：HTTP 200。
- 逻辑：登录提交可成功跳转到 `/strategies`。
- 内容：密码 placeholder 没有暴露默认密码。
- 问题：Enter 提交时 pending 文案为 `登录中...`，测试期望 `登录中…`，造成自动化失败。

---

## 功能测试结果

| 项目 | 结果 | 说明 |
|---|---|---|
| 首页访问 | 通过 | HTTP 200 |
| API 健康检查 | 通过 | `/api/v1/health` HTTP 200 |
| 登录流程 | 部分通过 | 提交跳转通过，pending 文案测试失败 |
| 页面 UI 审计 | 通过 | 14 个抽查页面无横向溢出、无亮色块 |
| 网络 404 抽查 | 部分通过 | `/signals`、市场详情通过；`/analytics`、`/config`、`/ops` 额外抽查发现 404 |
| 服务器容器 | 通过 | 核心容器运行中 |
| 运维监控数据 | 未通过 | 路径和契约不匹配 |
| 数据分析真实数据 | 未通过 | 代理路径多拼了一层 `/api/v1` |
| 配置管理真实数据 | 未通过 | 前端请求 Web 域名 `/api/v1/config`，没有走代理 |

---

## 问题清单

| 优先级 | 页面/模块 | 问题描述 | 建议方案 |
|---|---|---|---|
| 高 | `/analytics` | 数据分析页所有核心接口请求成 `/api/control/api/v1/analytics...`，线上 API 日志显示实际落到 `/api/v1/api/v1/analytics...` 并返回 404。 | 统一 `fetchJson` 调用约定，客户端传入路径不要带 `/api/v1`，或在 `resolveControlPlaneUrl()` 中规范化去重。 |
| 高 | `/ops` | 运维监控页健康、告警、巡检状态接口 404，页面显示 fallback 数据，无法反映真实运维状态。 | 前端改为 `/api/control/health`、`/api/control/patrol/schedule`；新增或改用真实告警接口；后端补 `/patrol/status` 或前端改读 `/patrol/schedule`。 |
| 高 | `/hyperopt` 后端 | 参数优化的 `POST /api/v1/hyperopt/start`、`/stop` 没有认证校验，前端虽然拦截登录，但 API 可被绕过调用。 | 在 hyperopt 路由增加 `auth_service.require_control_plane_access()`，并让前端 action 继续带 session token。 |
| 中 | `/config` | 配置页请求 `/api/v1/config`，在 Web 服务上直接 404，没有走 `/api/control` 代理。 | 改为 `/api/control/config` 和 `/api/control/config/schema`，或复用 `fetchJson()` 的统一路径。 |
| 中 | 配置 API | `GET /api/v1/config`、`/schema`、`/sections/{section}` 当前无认证，和“配置管理需登录”的页面定位不一致。 | 至少对详细配置和 section 查询加认证；schema 是否公开需明确边界。 |
| 中 | 受保护页面 | `/research`、`/backtest`、`/evaluation`、`/features` 在侧边栏标记 protected，但未登录直接访问仍可看到页面内容和部分操作入口。 | 页面级也做 session 判断；未登录时展示统一“需要登录”卡片或重定向。 |
| 中 | WebSocket | `/ops` 订阅 `health_status`，后端 channel 列表不包含该值，API 日志出现 `Unknown channel: health_status`。 | 后端补 channel 常量和推送，或前端改订已有 channel。 |
| 中 | 运行模式展示 | `CONTEXT.md` 写 Freqtrade 是 live，但服务器 `quant-api` 环境为 `QUANT_RUNTIME_MODE=dry-run`、`QUANT_ALLOW_LIVE_EXECUTION=false`。 | 前端和文档应区分“Freqtrade 容器 live”和“控制面执行开关 dry-run/禁止 live”。 |
| 低 | 登录测试 | pending 文案实际为 `登录中...`，测试期望 `登录中…`。 | 统一文案，建议保留中文省略号或调整测试期望。 |
| 低 | 页面命名 | `/strategies` H1 是“策略”，侧边栏是“策略中心”；`/data` H1 是“数据工作台”，侧边栏是“数据管理”。 | 统一 H1、面包屑和侧边栏命名。 |
| 低 | 容器健康 | `quant-api`、`quant-web` Docker health 显示 `none`，虽然应用健康接口正常。 | 给 API 和 Web 容器补 Docker healthcheck，方便 `docker ps` 直接判断。 |

---

## 代码证据

| 问题 | 代码位置 |
|---|---|
| analytics 路径带 `/api/v1`，客户端代理也会加 API base | `apps/web/lib/api.ts:1178`、`apps/web/lib/api.ts:1270`、`apps/web/lib/api.ts:4576` |
| config 页面绕过 `/api/control` 代理 | `apps/web/app/config/page.tsx:124` |
| ops 页面路径带 `/api/v1` 且请求不存在的 alerts/status | `apps/web/app/ops/page.tsx:353`、`apps/web/app/ops/page.tsx:378`、`apps/web/app/ops/page.tsx:400` |
| 后端 patrol 只有 `/schedule`，没有 `/status` | `services/api/app/routes/patrol.py:71` |
| hyperopt POST 没有认证参数和认证调用 | `services/api/app/routes/hyperopt.py:80`、`services/api/app/routes/hyperopt.py:143` |
| config GET 查询未认证 | `services/api/app/routes/config.py:81`、`services/api/app/routes/config.py:100` |
| protected 路由列表不含 research/backtest/evaluation/features/hyperopt/config | `apps/web/lib/api.ts:1117` |
| 终端侧边栏将 research/backtest/evaluation/features/hyperopt 标记 protected | `apps/web/components/terminal/terminal-sidebar.tsx:38` |

---

## 线上验证证据

### 页面访问

21 个路由均返回 HTTP 200：

`/`、`/research`、`/backtest`、`/evaluation`、`/features`、`/signals`、`/hyperopt`、`/analytics`、`/data`、`/factor-knowledge`、`/config`、`/strategies`、`/ops`、`/tasks`、`/market`、`/market/BTCUSDT`、`/balances`、`/positions`、`/orders`、`/risk`、`/login`。

### 自动化测试

```bash
QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011/api/v1 pnpm exec playwright test tests/ui-login-flow.spec.cjs tests/ui-audit.spec.cjs tests/ui-network.spec.cjs --reporter=line
```

结果：

- 18 通过。
- 1 失败。
- 失败原因：`登录中…` 与 `登录中...` 文案不一致。

### API 路径验证

```bash
curl http://39.106.11.65:9011/api/v1/analytics
curl http://39.106.11.65:9012/api/control/api/v1/analytics
curl http://39.106.11.65:9012/api/control/analytics
curl http://39.106.11.65:9011/api/v1/config/schema
curl http://39.106.11.65:9012/api/v1/config/schema
```

结果：

- API 直连 analytics：200。
- 错误代理 analytics：404。
- 正确代理 analytics：200。
- API 直连 config schema：200。
- Web 域名直接 `/api/v1/config/schema`：404。

### SSH 容器检查

服务器时间：2026-05-06 00:26 CST。

容器状态：

- `quant-api`：Up。
- `quant-web`：Up。
- `quant-freqtrade`：Up，healthy。
- `quant-grafana`：Up，healthy。
- `quant-prometheus`：Up，healthy。
- `quant-mihomo`：Up，healthy。
- `quant-openclaw`：Up，healthy。

---

## 优化建议

1. 先修统一 API 路径规范。

   当前最大影响是页面实际拿不到真实数据。建议统一规定：前端客户端调用 `fetchJson()` 时只传业务路径，例如 `/analytics`、`/health`、`/config`，不要传 `/api/v1/...`。

2. 再修运维监控页契约。

   `/ops` 是控制平面可信度最高的页面之一，应该优先保证它显示真实健康、告警、巡检状态。

3. 然后补后端认证边界。

   所有“会启动任务、停止任务、查看配置、影响运行状态”的接口都应以后端认证为准，前端登录拦截只能作为体验层。

4. 最后统一页面标题和受保护规则。

   侧边栏、页面 H1、面包屑、`PROTECTED_ROUTE_PATHS` 应保持同一份语义，避免用户和测试对页面状态判断不一致。

---

## 总结

项目整体可运行，主流程页面没有明显崩溃，终端化 UI 已基本落地。当前最需要优先处理的是“新页面看起来可用，但真实接口没有接上”的问题，尤其是 `/analytics`、`/ops`、`/config` 三个页面；其次是后端认证边界，避免只靠前端登录提示保护敏感动作。

---

## 第二轮代码层面补充审阅

> 补充时间：2026-05-06  
> 补充范围：前端页面代码、共享组件、API 封装、后端路由认证、线上性能和服务器日志。  
> 补充方式：静态代码搜索、Playwright 性能采集、SSH 服务器日志检查。

### 补充结论

第二轮审阅确认：页面首屏加载速度整体不慢，但接口调用规范、后端动作认证和自动化运维真实状态仍有明显缺口。当前风险不是“页面打不开”，而是“页面看起来正常，但有些数据是 fallback，有些动作接口可绕过前端登录直接调用”。

线上性能采样结果：

- 大多数页面 `load` 在 50-200ms 内完成。
- `/evaluation` 本轮采样约 1341ms，是抽查页面里最慢的一个。
- `/market` 发起 13 个 API 相关请求，是抽查页面里请求数量最多的页面。
- `/analytics`、`/config`、`/ops` 仍有控制台 404 错误。

### 补充问题清单

| 优先级 | 页面/模块 | 问题描述 | 建议方案 |
|---|---|---|---|
| 高 | 后端运维动作 | `/api/v1/patrol/start`、`/stop`、`/run-now` 没有认证保护；这些接口可改变巡检调度或立即执行巡检。 | 给 patrol 路由加 `auth_service.require_control_plane_access()`，前端通过 `/api/control` 自动带 session。 |
| 高 | 后端健康/日志动作 | `/api/v1/health/monitoring/start`、`/stop`、`/api/v1/logs/cleanup` 缺少认证保护。 | 所有会启动、停止、清理、重启、恢复的运维动作统一要求认证。 |
| 高 | OpenClaw 动作 | `/api/v1/openclaw/actions`、`/patrol` 可触发自动化动作，但路由层未看到认证校验。 | 在 openclaw 动作路由加认证，并保留动作审计记录。 |
| 高 | Hyperopt 未认证实测 | 未带 token 直接 `POST /api/v1/hyperopt/start` 返回 200，并创建了 `hyperopt-1` 内存任务；随后已调用 `/stop` 恢复到 idle。 | 立即补后端认证；前端登录状态不能作为唯一保护。 |
| 中 | 共享组件 API 路径 | 多个共享组件仍直接请求 `/api/v1/...`，如果后续被挂载到页面，线上 Web 域名下会绕过 `/api/control` 代理并 404。 | 统一改用 `resolveControlPlaneUrl()` 或 `fetchJson()`，并规定调用参数不要带 `/api/v1`。 |
| 中 | 回测曲线真实性 | `BacktestChartService` 已不直接返回 demo，但仍会用总收益、日期范围和正弦噪声反推收益曲线，并标记 `data_quality: real`。 | 没有真实逐日序列时返回空图表和 warning，不要把反推曲线标为真实。 |
| 中 | 页面文件过大 | `tasks/page.tsx` 611 行、`data/page.tsx` 577 行、`strategies/page.tsx` 512 行；多个后端服务超过 1000 行。 | 拆分为数据 hook、视图区块和操作组件，降低后续修改风险。 |
| 中 | 自动化运维稳定性 | 服务器日志持续出现 `Temporary failure in name resolution`、`VPN切换被节流`、`获取可用节点列表失败`。 | `/ops` 和 `/tasks` 应把这些真实异常显式呈现，不应只显示正常 fallback。 |
| 中 | WebSocket 发送异常 | API 日志出现 `Failed to send to ...` 和 `WebSocket is not connected. Need to call "accept" first.`。 | 检查 WebSocket 连接生命周期，断开连接后应先清理连接再推送。 |
| 低 | 前端性能结构 | 多数页面是 client component，通过 `useEffect` 再拉 session 和数据，首屏先渲染壳层，再更新数据。 | 对只读工作台可考虑服务端预取或统一 workspace 聚合，减少客户端请求数量和闪烁。 |

### 代码证据补充

| 问题 | 代码位置 |
|---|---|
| 侧边栏系统状态硬编码 | `apps/web/components/terminal/terminal-sidebar.tsx:76` |
| 共享组件直接请求 `/api/v1` | `apps/web/components/backtest-charts.tsx:62`、`apps/web/components/factor-analysis-panel.tsx:69`、`apps/web/components/strategy-selector.tsx:56`、`apps/web/components/stoploss-config.tsx:67`、`apps/web/components/report-viewer.tsx:116` |
| patrol 动作缺认证 | `services/api/app/routes/patrol.py:29`、`services/api/app/routes/patrol.py:53`、`services/api/app/routes/patrol.py:92` |
| health/logs 动作缺认证 | `services/api/app/routes/health.py:113`、`services/api/app/routes/health.py:138`、`services/api/app/routes/health.py:208` |
| OpenClaw 动作缺认证 | `services/api/app/routes/openclaw.py:55`、`services/api/app/routes/openclaw.py:118` |
| Hyperopt 动作缺认证 | `services/api/app/routes/hyperopt.py:80`、`services/api/app/routes/hyperopt.py:143` |
| 回测曲线仍由总收益反推 | `services/api/app/services/backtest_chart_service.py:82`、`services/api/app/services/backtest_chart_service.py:209` |
| 大页面超过 500 行 | `apps/web/app/tasks/page.tsx`、`apps/web/app/data/page.tsx`、`apps/web/app/strategies/page.tsx` |
| 超大后端聚合服务 | `services/api/app/services/evaluation_workspace_service.py`、`services/api/app/services/workbench_config_service.py`、`services/api/app/services/automation_service.py` |

### Playwright 补充验证

#### 线上性能采样

采样脚本登录后逐页访问 20 个核心页面，记录 `loadMs`、API 请求数、控制台错误和失败响应。

重点结果：

| 页面 | loadMs | API 数 | 失败响应 | 说明 |
|---|---:|---:|---:|---|
| `/evaluation` | 1341ms | 1 | 0 | 本轮最慢页面 |
| `/market` | 88ms | 13 | 0 | API 请求最多 |
| `/analytics` | 115ms | 7 | 6 | analytics 接口全部 404 |
| `/config` | 195ms | 4 | 2 | config 接口 404 |
| `/ops` | 114ms | 5 | 4 | health/alerts/patrol 接口 404 |

### SSH 服务器补充验证

容器状态：

- `quant-api`：Up 24 minutes。
- `quant-web`：Up 31 minutes。
- `quant-freqtrade`：Up 3 hours，healthy。
- 其他监控和代理容器均在运行。

关键环境变量：

- `quant-api`：`QUANT_RUNTIME_MODE=dry-run`。
- `quant-api`：`QUANT_ALLOW_LIVE_EXECUTION=false`。
- `quant-api`：`QUANT_FREQTRADE_API_URL=http://127.0.0.1:9013`。
- `quant-web`：`QUANT_API_BASE_URL=http://127.0.0.1:9011/api/v1`。

近期 API 日志异常：

- `/api/v1/api/v1/analytics...` 404。
- `/api/v1/api/v1/health` 404。
- `/api/v1/patrol/status` 404。
- `/api/v1/alerts?limit=20` 404。
- `Unknown channel: health_status`。
- `Temporary failure in name resolution`。
- `VPN切换被节流`。
- `Failed to send to ...`。

### 未认证动作验证说明

本轮为了确认认证缺陷，执行了一次未认证：

```bash
POST http://39.106.11.65:9011/api/v1/hyperopt/start
```

结果：

- 返回 HTTP 200。
- 创建内存态任务 `hyperopt-1`。
- 因服务器控制面当前是 `QUANT_RUNTIME_MODE=dry-run`，没有触发真实 Freqtrade live hyperopt。
- 随后已调用未认证 `/api/v1/hyperopt/stop`，状态恢复为 `idle`。

这个验证说明：风险真实存在，修复必须放在后端路由层。

---

## 第三轮全项目代码审阅汇总

> 补充时间：2026-05-06  
> 补充范围：前端页面、共享 API 层、后端路由、WebSocket、部署文件、自动化测试。  
> 补充方式：并发静态代码扫描、关键文件逐段阅读、与前两轮线上验证结果交叉核对。

### 本轮结论

本轮从代码层面确认：当前项目的主要风险不是页面样式，而是控制面契约没有统一。前端有多套 API 调用方式，后端认证策略按路由零散实现，测试又允许 fallback 数据通过，导致“页面能打开”不等于“真实功能可用”。

### 新增和归并缺陷

| 优先级 | 模块 | 问题描述 | 建议方案 |
|---|---|---|---|
| 高 | 前端 API 规范 | `resolveControlPlaneUrl()` 只是把 base 和 path 拼接，没有去重 `/api/v1`；调用方一旦传入 `/api/v1/...`，线上就会变成 `/api/v1/api/v1/...`。这不是 `/analytics` 单点问题，`/ops`、`/strategies` 入场评分等也存在同类写法。 | 在 `resolveControlPlaneUrl()` / `buildUpstreamApiUrl()` 中集中规范化 path；同时规定业务层只传 `/analytics`、`/health` 这类业务路径。 |
| 高 | 后端认证边界 | 多个会改变运行状态的 POST/PUT/DELETE 路由没有统一认证，包括巡检、OpenClaw 动作、健康监控、日志清理、回测运行、交易所切换、告警处理、仓位管理等。 | 建立“控制动作默认必须认证”的路由规范；除公开只读健康检查外，所有状态变更接口统一接入 `auth_service.require_control_plane_access()`。 |
| 高 | `/actions` 服务端动作 | `run_mock_pipeline` 仍然存在且 `requiresToken: false`，未登录也能通过服务端 action 触发演示信号流水线。 | 删除生产入口或改为仅开发环境可用；如果保留，必须要求登录并在页面明确标注为演示动作。 |
| 高 | 测试有效性 | 现有前端测试大量只验证页面文字和元素存在，且有用例明确允许 fallback 或真实数据二选一；这会让接口 404、代理路径错误、假数据展示都通过测试。 | 增加契约测试：关键页面必须验证真实接口 200、响应字段符合页面消费结构、页面不能在 404 时静默显示成功态。 |
| 中 | 前端直连 API | 多个组件仍直接 `fetch("/api/v1/...")`，包括回测图表、告警管理、止损配置、策略选择、因子分析、报告查看等；这些组件一旦挂到页面，在 Web 域名下会绕过 `/api/control`。 | 所有浏览器端请求统一走 `/api/control` 或共享 API client；禁止组件内硬编码 `/api/v1`。 |
| 中 | 降级状态展示 | `network_error`、`request_timeout` 被定义为不触发降级提示，多个工作台函数在失败时返回 fallback 数据；用户很难区分真实数据和本地兜底。 | fallback 可以保留，但必须在页面显式显示“当前是兜底数据/接口不可用”，并把错误记录到统一状态条。 |
| 中 | `/ops` 契约 | 前端请求 `/alerts`、`/patrol/status` 和 `health_status` channel，但后端没有对应路由或 channel；`/patrol/schedule` 返回结构也不是前端期待的 envelope。 | 以前端页面为准补齐后端路由和 channel，或改前端读取已有接口；WebSocket channel 常量要和页面订阅同源维护。 |
| 中 | 回测真实性 | `BacktestChartService` 仍用总收益、日期范围和正弦噪声反推收益曲线，并标记 `data_quality: real`。这会让非真实逐日收益看起来像真实回测曲线。 | 没有逐日 equity/trade 序列时返回空图和 warning；只有真实序列才允许标记 `real`。 |
| 中 | 页面内容完整性 | `/backtest` 的 K 线标签显示“暂未实现”，`/research` 的 IC 图表直接传空数组；页面结构已完成，但关键内容仍缺真实数据链路。 | 与后端输出契约对齐，补真实 K 线叠加、IC 序列和交易记录；未接上前在页面标题旁标注“数据未接入”。 |
| 中 | 文件规模 | `apps/web/lib/api.ts` 约 4887 行，多个页面和后端服务超过 500 行；API 类型、请求、fallback、归一化逻辑混在一个文件里。 | 拆成 `client`、`types`、`normalizers`、`fallbacks`、各业务域 API 模块；页面拆成数据 hook 和展示组件。 |
| 中 | 部署一致性 | 仓库部署文件里给 API/Web 配了 healthcheck，但线上容器曾显示 Docker health 为 `none`；说明当前运行容器和部署模板可能不一致。 | 用部署脚本重新对齐容器定义；上线后把 `docker inspect` healthcheck 纳入验收。 |
| 中 | 配置与凭据治理 | 文档、上下文和示例文件里出现了大量连接地址、默认账号或敏感配置线索；如果仓库外流，会增加控制面暴露风险。 | 真实凭据只放服务器环境变量或密钥管理；文档仅保留占位符，并增加一次密钥轮换检查。 |
| 低 | 页面命名 | 侧边栏、面包屑、H1 仍有少量不一致：如 `策略中心` 页面 H1 是“策略”，`配置管理` 页面 H1 是“配置”，`数据管理` 页面 H1 是“数据工作台”。 | 建立页面元数据表，侧边栏、面包屑、H1、登录页受保护说明都从同一份配置生成。 |

### 关键代码证据

| 问题 | 代码位置 |
|---|---|
| API path 只拼接不规范化 | `apps/web/lib/api.ts:1178`、`apps/web/lib/api.ts:1233` |
| analytics 传入 `/api/v1` 导致重复前缀 | `apps/web/lib/api.ts:4577`、`apps/web/lib/api.ts:4584`、`apps/web/lib/api.ts:4592` |
| strategies 入场评分也传入 `/api/v1` | `apps/web/lib/api.ts:4707` |
| config 页面浏览器端直连 `/api/v1` | `apps/web/app/config/page.tsx:124`、`apps/web/app/config/page.tsx:127` |
| ops 页面请求不存在或契约不一致的路径 | `apps/web/app/ops/page.tsx:136`、`apps/web/app/ops/page.tsx:353`、`apps/web/app/ops/page.tsx:378`、`apps/web/app/ops/page.tsx:400` |
| WebSocket 仅声明两个 channel | `services/api/app/websocket/channels.py:10` |
| WebSocket 发送失败后没有清理失效连接 | `services/api/app/websocket/manager.py:110`、`services/api/app/websocket/manager.py:117` |
| 演示流水线未要求登录 | `apps/web/app/actions/route.ts:365` |
| patrol 动作未认证 | `services/api/app/routes/patrol.py:29`、`services/api/app/routes/patrol.py:53`、`services/api/app/routes/patrol.py:92` |
| openclaw 动作和计数器重置未认证 | `services/api/app/routes/openclaw.py:55`、`services/api/app/routes/openclaw.py:118`、`services/api/app/routes/openclaw.py:178` |
| health/logs 状态变更未认证 | `services/api/app/routes/health.py:113`、`services/api/app/routes/health.py:138`、`services/api/app/routes/health.py:208` |
| 更多未认证状态变更路由 | `services/api/app/routes/backtest_validation.py:76`、`services/api/app/routes/exchange.py:88`、`services/api/app/routes/alert_management.py:197`、`services/api/app/routes/position_management.py:177` |
| 回测曲线由总收益反推但标记真实 | `services/api/app/services/backtest_chart_service.py:82`、`services/api/app/services/backtest_chart_service.py:91`、`services/api/app/services/backtest_chart_service.py:209` |
| 页面关键内容未接入真实序列 | `apps/web/app/backtest/page.tsx:337`、`apps/web/app/research/page.tsx:440` |
| 页面标题命名不一致 | `apps/web/app/strategies/page.tsx:180`、`apps/web/app/config/page.tsx:201`、`apps/web/app/data/page.tsx:135` |
| 线上部署模板和容器状态需对齐 | `infra/deploy/docker-compose.yml:76`、`infra/deploy/docker-compose.yml:99` |

### 建议修复顺序

1. 先修 API 路径规范和 `/api/v1` 去重问题，因为它直接影响真实数据能否显示。
2. 同步修后端认证边界，优先覆盖所有状态变更接口。
3. 再修 `/ops` 契约和 WebSocket channel，让运维页面能代表真实状态。
4. 然后清理 fallback 展示策略，避免接口失败时页面仍像正常运行。
5. 最后拆分超大文件并补测试，把“真实接口可用”纳入自动化验收。
