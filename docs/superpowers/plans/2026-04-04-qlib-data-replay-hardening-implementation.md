# Qlib 数据、回测、复盘与执行稳定性加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 `Qlib -> dry-run -> 小额 live -> 复盘` 主链上，补齐数据基座、实验记录、回测真实性、筛选门、固定复盘和执行稳定性。

**Architecture:** 继续沿用现有 `services/worker -> services/api -> WebUI -> Freqtrade` 主链，不引入新平台。先把研究运行目录里的数据快照和实验账本做稳定，再把回测假设和筛选门收紧，最后补一个统一复盘出口和执行健康摘要。

**Tech Stack:** Python stdlib、现有 Qlib fallback 结构、FastAPI skeleton、unittest

---

## Scope

### In scope

- 数据快照和运行目录标准化
- 训练/推理实验记录统一化
- 最小回测接近真实交易
- 更严格的研究筛选门
- 固定 `dry-run -> 小额 live -> 复盘` 复盘出口
- 执行侧健康摘要和稳定性状态

### Out of scope

- 新模型和自动调参
- 多币轮动
- 多市场执行
- 新前端大改版

---

## 文件边界

### Worker / 研究层

- Modify: `services/worker/qlib_config.py`
- Modify: `services/worker/qlib_dataset.py`
- Modify: `services/worker/qlib_backtest.py`
- Modify: `services/worker/qlib_runner.py`
- Modify: `services/worker/qlib_experiment_report.py`
- Modify: `services/worker/qlib_ranking.py`
- Test: `services/worker/tests/test_qlib_runner.py`
- Test: `services/worker/tests/test_qlib_backtest.py`
- Test: `services/worker/tests/test_qlib_ranking.py`

### API / 控制平面

- Create: `services/api/app/services/validation_workflow_service.py`
- Modify: `services/api/app/services/research_service.py`
- Modify: `services/api/app/services/research_factory_service.py`
- Modify: `services/api/app/services/sync_service.py`
- Modify: `services/api/app/tasks/scheduler.py`
- Modify: `services/api/app/routes/tasks.py`
- Modify: `services/api/app/routes/signals.py`
- Test: `services/api/tests/test_research_service.py`
- Test: `services/api/tests/test_risk_and_tasks.py`
- Test: `services/api/tests/test_api_skeleton.py`

### 文档

- Modify: `CONTEXT.md`
- Modify: `README.md`
- Modify: `plan.md`
- Modify: `docs/architecture.md`
- Modify: `docs/ops-qlib.md`

---

### Task 1: 数据基座标准化

**Files:**
- Modify: `services/worker/qlib_config.py`
- Modify: `services/worker/qlib_dataset.py`
- Modify: `services/worker/qlib_runner.py`
- Test: `services/worker/tests/test_qlib_runner.py`

- [ ] 让研究运行目录新增稳定的数据快照路径，例如 `dataset/latest_dataset_snapshot.json`
- [ ] 训练和推理写入数据快照摘要，至少包含：币种、周期、每段样本数、生成时间、数据签名
- [ ] 训练和推理结果都带出 `dataset_snapshot` 和 `dataset_snapshot_path`
- [ ] 跑 `python3 -m unittest services.worker.tests.test_qlib_runner -v`
- [ ] Commit：`feat: add qlib dataset snapshot ledger`

### Task 2: 研究流程与实验记录标准化

**Files:**
- Modify: `services/worker/qlib_runner.py`
- Modify: `services/worker/qlib_experiment_report.py`
- Modify: `services/api/app/services/research_service.py`
- Test: `services/worker/tests/test_qlib_runner.py`
- Test: `services/api/tests/test_research_service.py`

- [ ] 给运行目录增加统一实验账本，例如 `runs/experiment_index.json`
- [ ] 每次训练和推理都往账本追加一条轻量记录，至少包含：run_id、run_type、model_version、dataset_snapshot_path、generated_at、status
- [ ] 统一研究报告补充最近实验列表，不再只看“最近一次训练 / 最近一次推理”
- [ ] 跑 `python3 -m unittest services.worker.tests.test_qlib_runner services.api.tests.test_research_service -v`
- [ ] Commit：`feat: add qlib experiment ledger`

### Task 3: 回测贴近真实交易

**Files:**
- Modify: `services/worker/qlib_config.py`
- Modify: `services/worker/qlib_backtest.py`
- Modify: `services/worker/qlib_runner.py`
- Test: `services/worker/tests/test_qlib_backtest.py`
- Test: `services/worker/tests/test_qlib_runner.py`

- [ ] 给研究配置增加最小回测假设：手续费 bps、滑点 bps
- [ ] 回测结果同时输出 gross / net 收益、成本影响和假设快照
- [ ] 训练摘要和候选回测都统一使用同一套假设
- [ ] 跑 `python3 -m unittest services.worker.tests.test_qlib_backtest services.worker.tests.test_qlib_runner -v`
- [ ] Commit：`feat: add qlib realistic backtest assumptions`

### Task 4: 研究筛选门升级

**Files:**
- Modify: `services/worker/qlib_ranking.py`
- Modify: `services/worker/qlib_experiment_report.py`
- Test: `services/worker/tests/test_qlib_ranking.py`

- [ ] 候选准入门改为优先看净收益而不是毛收益
- [ ] 新增验证和回测漂移约束，避免“验证看起来好、净回测一扣成本就塌”
- [ ] 统一研究报告把失败原因按“规则门 / 验证门 / 回测门”分组
- [ ] 跑 `python3 -m unittest services.worker.tests.test_qlib_ranking -v`
- [ ] Commit：`feat: tighten qlib screening gates with net metrics`

### Task 5: 固定复盘机制

**Files:**
- Create: `services/api/app/services/validation_workflow_service.py`
- Modify: `services/api/app/routes/tasks.py`
- Modify: `services/api/app/routes/signals.py`
- Test: `services/api/tests/test_risk_and_tasks.py`
- Test: `services/api/tests/test_api_skeleton.py`

- [ ] 新增统一复盘服务，把研究报告、最近任务、余额、订单、持仓收成一个“验证工作流复盘”
- [ ] 增加读取接口，固定输出 `dry-run -> 小额 live -> 复盘` 当前走到哪一步、哪里失败
- [ ] 让复盘结果明确区分“继续研究 / 可进 dry-run / 可进 live / 已完成复盘”
- [ ] 跑 `python3 -m unittest services.api.tests.test_risk_and_tasks services.api.tests.test_api_skeleton -v`
- [ ] Commit：`feat: add validation workflow replay report`

### Task 6: 执行侧稳定能力补齐

**Files:**
- Modify: `services/api/app/tasks/scheduler.py`
- Modify: `services/api/app/services/sync_service.py`
- Modify: `services/api/app/services/validation_workflow_service.py`
- Test: `services/api/tests/test_risk_and_tasks.py`

- [ ] 任务调度器记录最近成功/失败的 `train / sync / reconcile / review` 状态
- [ ] 执行快照补充同步健康摘要，例如最近成功同步时间、最近失败任务、状态是否陈旧
- [ ] 复盘报告带出执行健康状态，避免“研究通过了，但执行链已经失联”
- [ ] 跑 `python3 -m unittest services.api.tests.test_risk_and_tasks -v`
- [ ] Commit：`feat: add execution health summary`

---

## 收口验证

- [ ] 运行 `python3 -m unittest services.worker.tests.test_qlib_runner services.worker.tests.test_qlib_backtest services.worker.tests.test_qlib_ranking -v`
- [ ] 运行 `python3 -m unittest services.api.tests.test_research_service services.api.tests.test_risk_and_tasks services.api.tests.test_api_skeleton -v`
- [ ] 运行 `python3 -m py_compile services/worker/qlib_config.py services/worker/qlib_backtest.py services/worker/qlib_runner.py services/worker/qlib_experiment_report.py services/worker/qlib_ranking.py services/api/app/services/research_service.py services/api/app/services/validation_workflow_service.py services/api/app/services/sync_service.py services/api/app/tasks/scheduler.py`
- [ ] 更新 `CONTEXT.md`
- [ ] 需要时更新 `README.md`、`plan.md`、`docs/architecture.md`、`docs/ops-qlib.md`
- [ ] Commit：`feat: harden qlib data replay and execution flow`
