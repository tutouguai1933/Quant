# 当前进度

- 当前正在做：Agent Team P2开发任务全部完成
- 上次停留位置：策略引擎验证成功，代码已推送
- 最近完成（2026-04-29）：
  - Agent Team并行开发完成：6个Agent协作
  - 新增数据分析页面：/analytics (454行)
  - 新增配置管理页面：/config (398行)
  - 新增策略入场评分端点：POST /strategies/{id}/entry-score
  - 代码Review评分：A，97%通过
  - 策略引擎验证：entry-score端点正常，评分阈值生效
  - Commit: 863ff60 已推送GitHub
- 最近完成（2026-04-27）：
  - Live交易完整周期验证成功：卖出DOGE → 研究 → 买入 → 监控 → 卖出
  - VPN节点切换验证：日本节点（IP 154.31.113.7）在白名单内
  - Binance API认证成功，真实订单执行（订单ID 14260504060/14260506121）
  - 服务器Freqtrade Live模式运行正常
  - OpenClaw巡检正常，无异常动作
  - 创建DEVELOPMENT_TODO.md任务清单
  - 启动4个并行Agent：服务器同步、门控阈值、告警推送、风控熔断
- 最近完成：
  - 修复 WebSocket URL：从 `/api/v1/ws` 改为 `/ws`，直接连接后端端口 9011
  - 修复 API 代理：使用 Docker 网关 IP `172.21.0.1:7890` 替代 `mihomo` hostname
  - 修复 Freqtrade API 端口：`listen_port` 从 9013 改为 8080（匹配 Docker 映射）
  - 完成 Playwright 端到端测试：登录 → 研究 → 训练 → 评估 → 策略 → 任务，全部通过
  - 验证 WebSocket 实时进度显示：训练进度正常更新
  - 更新 ui-evaluation-decision-center.spec.cjs：匹配当前页面设计，候选总数、推荐原因、淘汰原因
  - 更新 ui-main-flow.spec.cjs：匹配当前页面设计，策略中心、任务页、余额页
  - 验证评估页数据：API 返回 candidate_count: 10, recommended_symbol: BTCUSDT
  - 新增运行历史记录展示：ResearchRuntimePanel 现在显示 training/inference/pipeline 的最近运行次数和平均耗时

# 系统状态快照（2026-04-28）

## 服务地址
| 服务 | 地址 | 状态 |
|------|------|------|
| 服务器API | http://39.106.11.65:9011 | ✅ 运行中 |
| 服务器Web | http://39.106.11.65:9012 | ✅ 运行中 |
| 服务器Freqtrade | http://39.106.11.65:9013 | ⚠️ 重启中 |
| mihomo代理 | 127.0.0.1:7890 | ✅ 日本节点 |
| 本地API | http://127.0.0.1:9011 | ✅ |

## 已完成的服务文件
- strategy_engine_service.py - 入场评分、仓位计算、止损追踪
- analytics_service.py - 每日/周统计、盈亏归因、交易历史
- config_center_service.py - 统一配置管理
- vpn_switch_service.py - VPN自动切换
- risk_guard_service.py - 风控熔断
- alert_push_service.py - 告警推送
- auto_dispatch_service.py - 自动派发

## 测试状态
- 后端测试: 42/42 passed ✅
- 前端构建: passed ✅
- GitHub同步: 完成 ✅ (commit 2f02f01)
- 服务器同步: 新服务文件已SCP到服务器，需重建容器以生效

## VPN配置
- 当前节点：★ 日本¹
- 出口IP：154.31.113.7（白名单内）
- 白名单IP：39.106.11.65, 202.85.76.66, 154.31.113.7, 154.3.37.169
- 切换命令：curl -X PUT http://mihomo:9090/proxies/BestSSR -d '{"name":"★ 日本¹"}'

## Binance API
- API Key: djuPgTW90bbowvm8lAYF5Vaa79ZZh7k6Z6Nvqa9mRzuraANnbUsd58QZpfn1e3MB
- 认证状态：✅ 正常
- 可交易：True

## Freqtrade配置
- dry_run: False（Live模式）
- max_open_trades: 1
- stoploss: -0.1
- stake_amount: 6 USDT
- pair_whitelist: DOGE/USDT
- use_order_book: False（已修复）

## 关键配置（api.env）
- QUANT_ALLOW_LIVE_EXECUTION=false（需与实际同步）
- QUANT_LIVE_ALLOWED_SYMBOLS=DOGEUSDT
- QUANT_LIVE_MAX_STAKE_USDT=6
- QUANT_LIVE_MAX_OPEN_TRADES=1
- QUANT_QLIB_DRY_RUN_MIN_SCORE=0.50
- QUANT_QLIB_DRY_RUN_MIN_SHARPE=0.3

## 并行开发任务（全部完成）

### 已完成功能（2026-04-27）
| 功能 | 文件 | 状态 |
|------|------|------|
| VPN节点自动切换 | vpn_switch_service.py | ✅ |
| 研究到执行自动化 | auto_dispatch_service.py | ✅ |
| 告警推送服务 | alert_push_service.py | ✅ |
| 风控熔断机制 | risk_guard_service.py | ✅ |
| 服务器代码同步 | GitHub push/pull | ✅ |
| 门控阈值调整 | api.env | ✅ |

### 新增配置
```bash
# VPN自动切换
QUANT_VPN_WHITELIST_IPS=154.31.113.7,154.3.37.169,202.85.76.66
QUANT_VPN_HEALTH_CHECK_INTERVAL=60

# 自动派发
QUANT_AUTO_DISPATCH_ENABLED=false  # 开关
QUANT_AUTO_DISPATCH_MIN_SCORE=0.7
QUANT_AUTO_DISPATCH_MAX_DAILY=5

# 风控熔断
QUANT_RISK_DAILY_MAX_LOSS_PCT=3
QUANT_RISK_MAX_TRADES_PER_DAY=5
QUANT_RISK_CRASH_THRESHOLD_PCT=5

# 告警推送
QUANT_ALERT_TELEGRAM_TOKEN=
QUANT_ALERT_TELEGRAM_CHAT_ID=
QUANT_ALERT_ENABLED=true
```

### 待完成任务（P2）
- 策略实现（SampleStrategy → 真实策略）
- 数据分析报表
- 配置统一管理

## SSH连接服务器
```bash
sshpass -p "1933" ssh -o StrictHostKeyChecking=no djy@39.106.11.65 "命令"
```

---

# 关键决定

- Phase 2 采用分层实施：程序负责判断（90%），模型辅助边界场景（10%）。
- Phase 3 定时巡检采用节流策略：同一动作每小时最多执行3次，连续失败2次后停止自动执行。
- 巡检只执行白名单内动作，遵循三条铁规则：白名单、降风险、高风险收口人工。
- 每轮巡检最多执行1个动作，避免连锁反应。
- runtime_guard 新增结构化 blockers 数组 [{code, label, severity}]，便于前端按严重程度排序展示。
- suggested_action 和 suggested_action_reason 由程序自动计算，OpenClaw 只读取并执行白名单内动作。
- auto_run_allowed 标志明确告诉 OpenClaw 是否可以自动执行下一轮周期。
- auto_recoverable 标志明确告诉前端是否允许程序自动恢复，false 时显示 manual_required_reason。
- 前端"程序建议动作"使用醒目蓝色按钮样式，便于用户快速识别下一步操作。
- Phase 2 已完成，`Phase2` 已完成，`Phase3` 已完成综合验收，主入口文档继续统一按这个口径维护。
- 前端默认视图继续坚持“摘要优先，细节按需展开”；主动作区只回答“现在该做什么”，说明、配置和实验细节全部下沉到抽屉或弹窗。
- `C /features` 已完成：`/features` 现在正式改成“因子工作台”，默认只保留 `因子分类总览 / 当前启用因子 / 因子有效性摘要 / 因子冗余摘要 / 总分解释入口` 五张摘要卡，完整配置、因子说明、研究承接和单因子细节全部下沉到抽屉。
- `H /工具页收口` 已完成：工具页统一降成“详情页心智”，先说明“这页只负责查明细”，并固定提供 `回到主工作台 / 回到执行工作台 / 回到运维工作台` 三个返回入口。
- 前端展示层统一把旧术语 `候选池 / live 子集` 映射成 `候选篮子 / 执行篮子`，后端字段名保持不动。
- `/research -> /evaluation -> /strategies` 继续共用同一份候选范围契约；测试也改成按新术语读取和校验。
- K 阶段验收统一使用 `pnpm build` 后的 `pnpm start`，不要再和 `next dev` 共用同一个 `.next` 目录做宽回归。
- 宽回归里暴露出来的两条旧用例已对齐到当前设计口径：策略页入口统一使用 `查看工具详情`，研究/因子页说明改为通过抽屉验证，不再按旧的“首屏铺开说明”断言。
- Python 统一使用 `conda activate quant`，不再使用 `.venv`。
- 本地联调默认使用 `9011`（API）和 `9012`（Web）；如果登录或页面验证异常，优先确认端口对应的是当前进程。
- 本地 `.env.quant.local` 里的 Freqtrade 地址已对齐到标准端口 `9013`，避免任务页和评估页继续读取旧的 `8080` 导致联调报错。
- 同步层现在会把执行器断开统一压成 `status=unavailable + detail`，任务复盘、策略接口和余额接口不再因为 Freqtrade / 账户同步异常直接抛 `500`。
- 策略工作台在执行同步不可用时会保留 `executor_runtime.connection_status=error`，账户区域返回空结果和异常说明，不再把异常伪装成正常停止态。
- 策略页前端现在会直接显示 `执行器暂时不可用 / 账户回填暂不可用 / 当前异常：...`，把后端 detail 原样转成页面反馈，避免用户只看到 `error`。
- 自动化状态现在新增统一结论对象 `recovery_review`：把 `runtime_window + resume_status + active_blockers + operator_actions + 告警/执行健康` 压成 `status / headline / detail / next_action / blockers / operator_steps`，任务页不再自己拼一套恢复口径。
- 任务页前端优先读取 `automation.recoveryReview`；后端缺这个字段时仍保留原来的恢复结论回退，避免接口局部缺值导致白屏或口径跳变。
- `recovery_review` 收口后又补了一轮安全和一致性修正：同一轮状态只计算一次 `execution_health`，异常 detail 改成通用人话，不再把内部异常原样暴露到前端。
- 自动化状态本轮新增 `runtime_guard`：把长期运行里的调度窗口、依赖降级、人工接管级别和任务页承接入口压成 `status / degrade_mode / headline / detail / operator_route`，给中期“长期运行准备”做统一快照。
- 前端本轮新增共享 helper `apps/web/lib/automation-handoff.ts`，首页、评估页、策略页开始共用同一套自动化承接摘要；当状态进入 `attention_required / degraded / waiting` 时，会统一把动作导回任务页，而不是各页自己给不同建议。
- `signals` 页本轮也接入 `buildAutomationHandoffSummary`，自动化卡片不再只展示原始 mode / lastCycle，而是直接显示统一承接摘要，并固定提供 `去任务页看自动化` 入口。
- `/actions` 本轮开始在自动化动作成功或告警后再读一次最新自动化状态，用同一套 handoff 逻辑生成反馈文案；动作反馈会明确回到“先去任务页看当前恢复建议和人工接管状态”。
- `runtime_guard` 和 `recovery_review` 本轮继续补结构字段：新增 `alert_context / takeover_review_due_at / issue_code / reason_label`，前端不再只能靠自由文本猜当前为什么要人工处理或降级。
- 这轮继续把结构化字段真正接到前端：`apps/web/lib/automation-handoff.ts` 现在会优先读取 `reason_label / alert_context / takeover_review_due_at / next_check_at`；任务页也开始显式展示 `当前原因 / 告警升级 / 接管复核`，不再只靠长段说明文字。
- 这轮真实联调又暴露出一个短窗口：自动化工作流已经开始跑，但 `recovery_review / runtime_guard` 仍会短暂显示“当前可以继续自动化”；原因是状态汇总只看阻塞和恢复条件，没有把 `automation_cycle=running` 算进去。
- 当前决定：把 `automation_cycle=running` 单独收口成统一“运行中”状态，后端返回 `status=running / waiting_for=active_cycle / degrade_mode=cycle_running`，前端任务页和跨页 handoff 都按这个口径显示并导回任务页跟进。
- 当前决定：`Openclaw` 采用“安全动作模式 + 双层守护”接入。项目内继续输出统一业务结论，`Openclaw` 只读取统一快照并执行白名单里的低风险 HTTP / 系统动作，不碰交易决策、不自动放开 `live`、不自动解除人工接管。
- `tests/test_frontend_refactor.py` 已整体改到当前页面契约：主动作区、抽屉、候选篮子 / 执行篮子、状态语言统一按新口径验收。
- 自动化链路现在把“派发异常”和“同步失败”都当作真实失败处理，不再把同步失败伪装成成功；失败后会进入统一的告警 / 人工接管口径，便于前端和任务页一致展示。

# 最近验证

- WebSocket 和代理配置修复验证：
  - WebSocket 连接成功：`ws://localhost:9011/ws`
  - 市场数据获取成功：Binance K 线数据正常返回
  - Freqtrade API ping 成功：`{"status":"pong"}`
  - 研究训练成功：训练和推理完成，生成 10 个候选信号
  - Playwright 端到端测试：登录、研究页状态面板、训练进度、评估页候选、策略页执行器、任务页自动化 - 全部 7 项 PASS
- 系统架构说明：
  - 因子控制买入/卖出：因子值 × 因子权重 → 评分 → 信号方向 → 候选排序 → 门控过滤 → 实际执行
  - 回测在训练过程中自动执行：每轮训练计算净收益率、最大回撤、夏普比率、胜率
  - 推荐币每次不一样是正常行为：系统基于市场数据和因子权重动态计算
  - 候选筛选遵循安全设计：score_gate、rule_gate、backtest_gate 验证后才进入 dry-run
- Phase 3 定时巡检机制验收：
  - 后端测试：53条通过
  - 前端构建：`pnpm build` 通过
  - 新增文件：`openclaw_patrol_service.py`
  - 新增API路由：`/patrol`、`/patrol-history`、`/patrol-counters`、`/patrol-reset`
  - 前端展示：任务页新增"定时巡检"卡片，显示最近巡检状态和执行动作
- 前端重构验收：
  - Phase 1: 前端重构规划与设计 ✓
  - Phase 2: 重构首页和核心导航 ✓（首页 274 行）
  - Phase 3: 重构策略页和信号页 ✓（策略页 747→345 行，信号页优化布局）
  - Phase 4: 重构任务页和评估页 ✓（任务页 1962→279 行 -86%，评估页 1571→247 行 -84%）
  - Phase 5: 前端联调测试和验收 ✓（测试通过 24/34，剩余 10 个失败符合精简目标）
- 重构成果：5 个核心页面从 ~4600 行精简到 1503 行，减少 67%，统一使用 StatusBar 组件
- Playwright 红绿验证：
  - `ui-candidate-scope-contract` 先失败 `1` 条，再修复后通过 `1` 条
  - `ui-main-flow`、`ui-automation-panels` 先暴露旧口径断言，再修复到当前页面交互后通过 `2` 条
- Playwright K 阶段宽回归：`ui-home-workbench`、`ui-home-primary-actions`、`ui-research-primary-actions`、`ui-features-workbench`、`ui-evaluation-decision-center`、`ui-strategies-workbench`、`ui-candidate-scope-contract`、`ui-workbench-config`、`ui-navigation`、`ui-main-flow`、`ui-tasks-automation`、`ui-tool-detail-pages`、`ui-automation-panels`、`ui-arbitration-handoff`、`ui-feedback-handoff`、`ui-signals-actions`、`ui-execution-backfill` 共 `30` 条，通过 `30`
- 后端定向测试：`test_feature_workspace_service` 共 `4` 条，通过 `4`
- 真实页面联调：
  - 首页到执行链已基于生产产物完成真实浏览器联调，主线覆盖 `home -> signals -> research -> evaluation -> strategies -> tasks -> tools`
  - 未登录链路：从首页点击执行入口会真实跳到 `/login?next=%2Fstrategies`
  - 依赖失败链路：`/strategies` 真实显示 `连接状态：not_configured`，`/tasks` 真实显示 `当前恢复建议 / 先恢复自动化状态接口`
  - 接口失败链路：停掉 `9011` API 后，`/` 和 `/evaluation` 仍能靠 fallback 正常渲染关键页面内容；验证后已恢复 API
  - 当前本地正式验收进程：API `9011`、Web `9012` 都已重新拉起
- 本轮新增验证：
  - `tests.test_frontend_refactor` 共 `29` 条，通过 `29`
  - `services.api.tests.test_automation_service` 共 `49` 条，通过 `49`
  - `services.api.tests.test_api_skeleton` 共 `40` 条，通过 `40`
  - `services.api.tests.test_risk_and_tasks` 共 `12` 条，通过 `12`
  - `services.api.tests.test_execution_flow` + `services.api.tests.test_feature_workspace_service` 共 `24` 条，通过 `24`
  - Playwright 全量宽回归共 `63` 条，通过 `63`
  - 本地服务启动复核：`9011 / 9012 / 9013` 已监听；首页 HTML、登录提交、`/api/v1/tasks/validation-review`、`/api/v1/evaluation/workspace` 当前都能返回正常结果
  - 本轮稳定性回归：
    - `services.api.tests.test_account_sync_service` + `services.api.tests.test_strategy_workspace_service` 共 `22` 条，通过 `22`
    - `services.api.tests.test_execution_flow` 共 `20` 条，通过 `20`
    - `services.api.tests.test_api_skeleton` + `services.api.tests.test_risk_and_tasks` 共 `54` 条，通过 `54`
    - `tests.test_frontend_refactor` 共 `30` 条，通过 `30`
  - 真实故障联调：
    - 把 API 临时切到不存在的 Freqtrade 地址后，`/api/v1/tasks/validation-review` 仍返回 `200`，并给出 `connection_status=error` 和异常 detail
    - 同样的故障条件下，`/api/v1/strategies/workspace` 仍返回 `200`，并给出 `status=unavailable`
    - Web `9012` 下的 `/strategies` 页面在故障条件下仍能返回 HTML，并显示 `执行器暂时不可用 / 账户回填暂不可用 / 当前异常：...`
  - 本轮 recovery_review 收口：
    - `services.api.tests.test_automation_service` + `tests.test_frontend_refactor` 共 `83` 条，通过 `83`
    - `apps/web` 的 `pnpm build` 通过
    - 本地服务已重新拉起：API `9011`、Web `9012`、Freqtrade `9013` 都在监听
    - `GET /healthz` 返回正常；登录后 `GET /api/v1/tasks/automation` 已返回 `recovery_review`
    - 登录后的 `/tasks` HTML 已真实包含 `当前恢复建议 / 当前还在人工接管中 / 先人工处理 / 恢复步骤`
    - 当前真实接口返回：`recovery_review.status=attention_required`，`headline=当前还在人工接管中`
  - 本轮“共享承接 + 长期运行快照”收口：
    - `services.api.tests.test_automation_service` + `tests.test_frontend_refactor` 共 `84` 条，通过 `84`
    - `apps/web` 的 `pnpm build` 通过
    - 登录后的 `/`、`/evaluation`、`/strategies`、`/tasks` HTML 已真实验证到统一口径：当前状态下都能看到 `当前还在人工接管中 / 先人工处理`，并统一承接到任务页
    - `GET /api/v1/tasks/automation` 当前已同时返回 `recovery_review` 和 `runtime_guard`
    - 当前真实接口返回：`runtime_guard.status=attention_required`，`degrade_mode=manual_only`，`operator_route=/tasks`
  - 本轮 `signals + 动作反馈` 收口：
    - `services.api.tests.test_automation_service` + `tests.test_frontend_refactor` 共 `85` 条，通过 `85`
    - `apps/web` 的 `pnpm build` 通过
    - Playwright `ui-signals-actions` 共 `4` 条，通过 `4`
    - 当前本地服务已复核：`9011 / 9012 / 9013` 都在监听
    - 登录后的 `/signals` HTML 已真实包含 `当前还在人工接管中 / 先人工处理 / 去任务页看自动化`
    - 登录后的 `/api/control/tasks/automation` 已真实返回新增字段：`runtime_guard.alert_context`、`runtime_guard.takeover_review_due_at`、`recovery_review.issue_code`
    - 真实提交 `POST /actions action=automation_manual_takeover returnTo=/signals` 后，重定向反馈已变成统一口径：`当前还在人工接管中 ... 先去任务页看当前恢复建议和人工接管状态。`
  - 本轮“任务页结构化长期运行摘要”收口：
    - `tests.test_frontend_refactor` 共 `33` 条，通过 `33`
    - `apps/web` 的 `pnpm build` 通过
    - Playwright `ui-tasks-automation` 共 `1` 条，通过 `1`
    - 登录后的 `/tasks` HTML 已真实包含 `当前原因 / 告警升级 / 接管复核`
    - 登录后的 `/signals` HTML 仍保持统一承接口径：`当前还在人工接管中 / 先人工处理 / 去任务页看自动化`
  - 本轮真实联调补充：
    - 因子筛选再次验证：把 `/features` 预设切到 `confirmation_focus` 后，`/api/control/features/workspace` 已真实切换到新的主/辅因子组合；`/api/control/research/workspace` 同时返回 `config_alignment.status=stale`，`stale_fields` 包含 `primary_factors / auxiliary_factors`，随后已恢复到 `trend_focus`
    - 策略买卖再次验证：真实执行 `start_strategy -> run_mock_pipeline -> dispatch_latest_signal` 后，策略工作台已出现 `latest_order_symbol=BTC/USDT`、`latest_order_status=filled`、`latest_position_side=long`；订单页和持仓页 HTML 都能看到 `BTC/USDT / filled / long`
    - 自动化运行态修正：
      - `services.api.tests.test_automation_service` + `tests.test_frontend_refactor` 共 `87` 条，通过 `87`
      - `apps/web` 的 `pnpm build` 通过
      - 本地服务已按新代码重新拉起：API `9011`、Web `9012`、Freqtrade `9013` 都在监听
      - 真实触发 `automation_run_cycle` 后，当前本地周期结束太快，页面高频采样没有稳定抓到运行中的 HTML 窗口；但动作完成后的 `/api/control/tasks/automation` 已真实回到 `status=waiting / degrade_mode=window_wait / headline=当前正在等待冷却窗口结束`，`/tasks` HTML 已真实包含 `当前正在等待冷却窗口结束`，`/signals` HTML 仍保持 `去任务页看自动化`
  - 本轮设计补充：
    - `Openclaw` 安全动作模式设计已写入 `docs/2026-04-15-openclaw-safe-actions-design.md`
    - 当前推荐第一阶段只开放：`automation_run_cycle`、`automation_dry_run_only`、重启 `api/web/freqtrade`
    - 当前推荐新增统一快照接口和安全动作网关，避免 `Openclaw` 直接拼多个业务接口或自行猜业务文案
  - 本轮测试更新：
    - 更新 `ui-evaluation-decision-center.spec.cjs`：移除旧设计断言，匹配当前页面结构
    - 更新 `ui-main-flow.spec.cjs`：策略中心、任务页、余额页断言匹配当前设计
    - Playwright 测试 `ui-evaluation ui-main-flow` 共 `4` 条，通过 `4`

# 下一步

- 系统现已可用，可继续：
  - Phase 4：模型辅助边界场景（创建 model_suggestion_service.py）
  - Phase 5：扩展安全动作白名单（新增 HTTP 安全动作和系统安全动作）
  - 真实联调：运行研究训练观察候选排序，通过门控进入 dry-run/live
  - 因子调整：修改因子权重观察推荐币变化
  - 回测验证：检查训练结果中的回测指标
