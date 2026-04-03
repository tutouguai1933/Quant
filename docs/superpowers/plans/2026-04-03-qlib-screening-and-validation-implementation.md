# Qlib 研究筛选与真实验证闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有单币择时研究工厂之上，补齐更严格的研究筛选门、统一实验对比、执行联动和真实验证闭环。

**Architecture:** 延续现有 `worker -> research_service -> signal_service -> strategies -> Freqtrade` 主链路，不新增重平台。先把研究层的筛选与对比能力做扎实，再把研究结果更深地接进执行决策，最后固定“小额真实验证”的操作流程和状态回写。

**Tech Stack:** Python stdlib、现有 Qlib fallback 结构、FastAPI skeleton、Next.js App Router、unittest

---

## Scope

### In scope

- 更严格的研究筛选门
- 统一研究排行榜和实验对比
- `Qlib -> 策略 -> Freqtrade` 的更深联动
- `dry-run -> 小额 live -> 复盘` 的标准验证流程

### Out of scope

- 多币轮动
- 多模型平台
- `Lean / vn.py / OpenClaw`
- 自动调参和大规模贝叶斯优化

---

## 文件边界

### Worker / 研究层

- Modify: `services/worker/qlib_ranking.py`
  - 扩展更严格的筛选门和失败原因。
- Modify: `services/worker/qlib_runner.py`
  - 输出更稳定的实验摘要和对比字段。
- Create: `services/worker/qlib_experiment_report.py`
  - 统一整理最近训练、最近推理、候选排行和对比摘要。
- Test: `services/worker/tests/test_qlib_ranking.py`
- Test: `services/worker/tests/test_qlib_runner.py`
- Test: `services/worker/tests/test_qlib_experiment_report.py`

### API / 控制平面

- Modify: `services/api/app/services/research_factory_service.py`
  - 暴露统一排行榜、实验对比和推荐执行候选。
- Modify: `services/api/app/services/research_service.py`
  - 统一研究层报告出口。
- Modify: `services/api/app/services/signal_service.py`
  - 让研究准入结果更深地参与信号可派发判断。
- Modify: `services/api/app/services/strategy_workspace_service.py`
  - 给策略页补“当前推荐执行候选”和研究对比摘要。
- Modify: `services/api/app/routes/signals.py`
  - 增加实验对比和推荐候选读取接口。
- Test: `services/api/tests/test_research_service.py`
- Test: `services/api/tests/test_signal_service.py`
- Test: `services/api/tests/test_api_skeleton.py`
- Test: `services/api/tests/test_strategy_workspace_service.py`

### WebUI / 页面

- Modify: `apps/web/lib/api.ts`
  - 增加研究对比和推荐候选接口读取。
- Modify: `apps/web/components/research-candidate-board.tsx`
  - 展示更严格筛选门、失败原因和推荐动作。
- Modify: `apps/web/app/signals/page.tsx`
  - 展示统一研究排行榜和最近实验摘要。
- Modify: `apps/web/app/strategies/page.tsx`
  - 展示“推荐执行候选”和 `dry-run / live` 下一步动作。
- Modify: `apps/web/app/market/[symbol]/page.tsx`
  - 展示单币是否值得继续进入执行页。
- Test: `tests/test_frontend_refactor.py`
- Test: `tests/test_market_workspace.py`

### 文档

- Modify: `CONTEXT.md`
- Modify: `README.md`
- Modify: `plan.md`
- Modify: `docs/architecture.md`
- Modify: `docs/ops-qlib.md`

---

### Task 1: 收紧研究筛选门

**Files:**
- Modify: `services/worker/qlib_ranking.py`
- Test: `services/worker/tests/test_qlib_ranking.py`

- [x] **Step 1: 写失败测试，固定更严格的筛选门**

```python
def test_rank_candidates_fails_when_consecutive_loss_streak_is_too_long() -> None:
    result = rank_candidates(
        [
            {
                "symbol": "BTCUSDT",
                "score": "0.8100",
                "backtest": {
                    "metrics": {
                        "total_return_pct": "14.20",
                        "max_drawdown_pct": "-5.10",
                        "sharpe": "1.10",
                        "win_rate": "0.58",
                        "turnover": "0.24",
                        "max_loss_streak": "4",
                    }
                },
            }
        ]
    )

    assert result["items"][0]["allowed_to_dry_run"] is False
    assert "loss_streak_too_long" in result["items"][0]["dry_run_gate"]["reasons"]
```

- [x] **Step 2: 跑测试确认失败**

Run: `./.venv/bin/python -m unittest services.worker.tests.test_qlib_ranking -v`  
Expected: FAIL，提示还没有 `max_loss_streak` 的筛选逻辑。

- [x] **Step 3: 写最小实现**

```python
if max_loss_streak > Decimal("3"):
    failures.append("loss_streak_too_long")
if sample_count < Decimal("20"):
    failures.append("sample_count_too_low")
```

- [x] **Step 4: 再跑测试确认通过**

Run: `./.venv/bin/python -m unittest services.worker.tests.test_qlib_ranking -v`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add services/worker/qlib_ranking.py services/worker/tests/test_qlib_ranking.py
git commit -m "feat: tighten qlib research gate"
```

### Task 2: 输出统一实验对比摘要

**Files:**
- Create: `services/worker/qlib_experiment_report.py`
- Modify: `services/worker/qlib_runner.py`
- Test: `services/worker/tests/test_qlib_experiment_report.py`
- Test: `services/worker/tests/test_qlib_runner.py`

- [x] **Step 1: 写失败测试，固定实验对比摘要结构**

```python
def test_build_experiment_report_returns_latest_training_and_candidate_summary() -> None:
    report = build_experiment_report(
        latest_training={"model_version": "m1", "backtest": {"metrics": {"sharpe": "1.10"}}},
        latest_inference={"signals": [{"symbol": "BTCUSDT"}]},
        candidates={"items": [{"symbol": "BTCUSDT", "allowed_to_dry_run": True}]},
    )

    assert report["overview"]["candidate_count"] == 1
    assert report["overview"]["ready_count"] == 1
    assert report["latest_training"]["model_version"] == "m1"
```

- [x] **Step 2: 跑测试确认失败**

Run: `./.venv/bin/python -m unittest services.worker.tests.test_qlib_experiment_report -v`  
Expected: FAIL，提示模块或函数不存在。

- [x] **Step 3: 写最小实现**

```python
def build_experiment_report(*, latest_training, latest_inference, candidates):
    items = list((candidates or {}).get("items", []))
    return {
        "overview": {
            "candidate_count": len(items),
            "ready_count": sum(1 for item in items if item.get("allowed_to_dry_run")),
            "signal_count": len(list((latest_inference or {}).get("signals", []))),
        },
        "latest_training": dict(latest_training or {}),
        "latest_inference": dict(latest_inference or {}),
        "candidates": items,
    }
```

- [x] **Step 4: 再跑测试确认通过**

Run: `./.venv/bin/python -m unittest services.worker.tests.test_qlib_experiment_report services.worker.tests.test_qlib_runner -v`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add services/worker/qlib_experiment_report.py services/worker/qlib_runner.py services/worker/tests/test_qlib_experiment_report.py services/worker/tests/test_qlib_runner.py
git commit -m "feat: add qlib experiment comparison report"
```

### Task 3: 把研究对比结果接进 API 主出口

**Files:**
- Modify: `services/api/app/services/research_factory_service.py`
- Modify: `services/api/app/services/research_service.py`
- Modify: `services/api/app/routes/signals.py`
- Test: `services/api/tests/test_research_service.py`
- Test: `services/api/tests/test_api_skeleton.py`

- [x] **Step 1: 写失败测试，固定研究对比接口输出**

```python
def test_research_report_route_returns_experiment_overview() -> None:
    response = signals_route.get_research_report()

    assert response["data"]["item"]["overview"]["candidate_count"] >= 0
    assert "latest_training" in response["data"]["item"]
    assert "latest_inference" in response["data"]["item"]
```

- [x] **Step 2: 跑测试确认失败**

Run: `./.venv/bin/python -m unittest services.api.tests.test_research_service services.api.tests.test_api_skeleton -v`  
Expected: FAIL，提示 API 还没有对比摘要字段或结构不一致。

- [x] **Step 3: 写最小实现**

```python
report = build_experiment_report(
    latest_training=latest.get("latest_training"),
    latest_inference=latest.get("latest_inference"),
    candidates={"items": candidates},
)
```

- [x] **Step 4: 再跑测试确认通过**

Run: `./.venv/bin/python -m unittest services.api.tests.test_research_service services.api.tests.test_api_skeleton -v`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add services/api/app/services/research_factory_service.py services/api/app/services/research_service.py services/api/app/routes/signals.py services/api/tests/test_research_service.py services/api/tests/test_api_skeleton.py
git commit -m "feat: expose qlib experiment comparison api"
```

### Task 4: 让研究结果更深地参与执行决策

**Files:**
- Modify: `services/api/app/services/signal_service.py`
- Modify: `services/api/app/services/strategy_workspace_service.py`
- Test: `services/api/tests/test_signal_service.py`
- Test: `services/api/tests/test_strategy_workspace_service.py`

- [x] **Step 1: 写失败测试，固定“只有当前推荐候选才允许优先进入执行页”**

```python
def test_strategy_workspace_prefers_ready_research_candidate() -> None:
    item = workspace_service.get_workspace()

    assert item["research_recommendation"]["symbol"] == "BTCUSDT"
    assert item["research_recommendation"]["allowed_to_dry_run"] is True
```

- [x] **Step 2: 跑测试确认失败**

Run: `./.venv/bin/python -m unittest services.api.tests.test_signal_service services.api.tests.test_strategy_workspace_service -v`  
Expected: FAIL，提示策略工作台还没有推荐候选字段。

- [x] **Step 3: 写最小实现**

```python
ready_items = [item for item in candidates if item.get("allowed_to_dry_run")]
recommendation = ready_items[0] if ready_items else None
```

- [x] **Step 4: 再跑测试确认通过**

Run: `./.venv/bin/python -m unittest services.api.tests.test_signal_service services.api.tests.test_strategy_workspace_service -v`  
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add services/api/app/services/signal_service.py services/api/app/services/strategy_workspace_service.py services/api/tests/test_signal_service.py services/api/tests/test_strategy_workspace_service.py
git commit -m "feat: use qlib recommendation in execution workspace"
```

### Task 5: 固定真实验证工作流

**Files:**
- Modify: `docs/ops-qlib.md`
- Modify: `README.md`
- Modify: `plan.md`
- Modify: `CONTEXT.md`

- [ ] **Step 1: 写文档约束，固定真实验证顺序**

```markdown
1. 研究训练
2. 研究推理
3. 查看候选排行榜
4. 只挑允许进入 dry-run 的候选
5. 先跑 dry-run
6. dry-run 稳定后才允许进入小额 live
7. live 完成后回看余额、订单、持仓、任务、风险
```

- [ ] **Step 2: 写最小进度记录**

```markdown
- 当前下一阶段：先做研究筛选门，再做实验对比，再做执行联动，最后固定真实验证流程
```

- [ ] **Step 3: 手工自查文档一致性**

Run: `rg -n "研究筛选|实验对比|真实验证|dry-run|live" README.md plan.md docs/ops-qlib.md CONTEXT.md`  
Expected: 能看到同一套顺序，不互相矛盾。

- [ ] **Step 4: Commit**

```bash
git add README.md plan.md CONTEXT.md docs/ops-qlib.md
git commit -m "docs: record qlib validation workflow"
```

### Task 6: 页面展示统一研究排行榜和下一步动作

**Files:**
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/components/research-candidate-board.tsx`
- Modify: `apps/web/app/signals/page.tsx`
- Modify: `apps/web/app/strategies/page.tsx`
- Modify: `apps/web/app/market/[symbol]/page.tsx`
- Test: `tests/test_frontend_refactor.py`
- Test: `tests/test_market_workspace.py`

- [ ] **Step 1: 写失败测试，固定页面上会看到统一候选和下一步动作**

```python
def test_research_candidate_board_shows_next_action_copy(self) -> None:
    content = (WEB_COMPONENTS / "research-candidate-board.tsx").read_text(encoding="utf-8")

    self.assertIn("下一步动作", content)
    self.assertIn("允许进入 dry-run", content)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `./.venv/bin/python -m unittest tests.test_frontend_refactor tests.test_market_workspace -v`  
Expected: FAIL，提示前端文案或字段还没接上。

- [ ] **Step 3: 写最小实现**

```tsx
<p>下一步动作：{item.allowed_to_dry_run ? "进入 dry-run" : "继续观察"}</p>
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `./.venv/bin/python -m unittest tests.test_frontend_refactor tests.test_market_workspace -v`  
Expected: PASS

- [ ] **Step 5: 构建验证**

Run: `cd apps/web && pnpm build`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/web/lib/api.ts apps/web/components/research-candidate-board.tsx apps/web/app/signals/page.tsx apps/web/app/strategies/page.tsx apps/web/app/market/[symbol]/page.tsx tests/test_frontend_refactor.py tests/test_market_workspace.py
git commit -m "feat: show qlib ranking workflow in ui"
```

---

## Validation Matrix

- Worker:
  - `./.venv/bin/python -m unittest discover -s services/worker/tests -v`
- API:
  - `./.venv/bin/python -m unittest services.api.tests.test_research_service services.api.tests.test_signal_service services.api.tests.test_api_skeleton services.api.tests.test_strategy_workspace_service -v`
- Frontend:
  - `./.venv/bin/python -m unittest tests.test_frontend_refactor tests.test_market_workspace -v`
  - `cd apps/web && pnpm build`

## Review Checkpoints

- Task 1 完成后：检查筛选门是不是只增加约束，没有改坏现有候选结构。
- Task 3 完成后：检查研究报告、候选快照、统一 API 三处字段是否一致。
- Task 4 完成后：检查研究推荐是否只是辅助执行，不会绕过现有安全门。
- Task 6 完成后：做页面真验证，确认用户能看懂“当前推荐什么、下一步该做什么”。
