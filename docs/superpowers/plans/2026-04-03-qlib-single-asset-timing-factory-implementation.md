# Qlib 单币择时研究工厂 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `BTCUSDT / ETHUSDT / SOLUSDT / DOGEUSDT` 建成一条可复现的单币择时研究主线，让系统能训练、回测、排行并判断哪些候选结果允许进入 `dry-run`。

**Architecture:** 延续现有 `QlibRunner + ResearchService + Control Plane` 结构，在 worker 侧补齐数据切分、规则门、标签、回测和排行榜，在 API 侧输出统一候选摘要，在 WebUI 侧展示“研究结果 -> 是否可进 dry-run -> 下一步动作”。研究层只负责研究和筛选，不直接接管执行器。

**Tech Stack:** Python stdlib、现有 Qlib fallback 结构、FastAPI skeleton、Next.js App Router、unittest

---

## 文件边界

### Worker / 研究层

- Create: `services/worker/qlib_dataset.py`
  - 统一整理 `1h / 4h` K 线样本、按时间切分训练/验证/测试集。
- Create: `services/worker/qlib_rule_gate.py`
  - 规则层门控，负责趋势、波动、量能的最小过滤。
- Create: `services/worker/qlib_backtest.py`
  - 统一回测、统计收益、回撤、胜率、Sharpe、换手。
- Create: `services/worker/qlib_ranking.py`
  - 统一候选排行与 `dry-run` 准入判断。
- Modify: `services/worker/qlib_features.py`
  - 补足 `EMA20 / EMA55 / ATR / RSI / breakout_strength` 等最小择时因子。
- Modify: `services/worker/qlib_labels.py`
  - 从“下一根涨跌”升级成“未来 1-3 天 buy / sell / watch”标签。
- Modify: `services/worker/qlib_runner.py`
  - 串起数据准备、训练、验证、回测、候选输出、报告落盘。
- Test: `services/worker/tests/test_qlib_dataset.py`
- Test: `services/worker/tests/test_qlib_rule_gate.py`
- Test: `services/worker/tests/test_qlib_backtest.py`
- Test: `services/worker/tests/test_qlib_ranking.py`
- Test: `services/worker/tests/test_qlib_runner.py`

### API / 控制平面

- Create: `services/api/app/services/research_factory_service.py`
  - 聚合候选排行、门槛状态、最近可用候选。
- Modify: `services/api/app/services/research_service.py`
  - 暴露统一工厂结果，而不仅是最新训练/推理文件。
- Modify: `services/api/app/services/signal_service.py`
  - 只允许通过 `dry-run` 准入门的研究结果进入真实派发候选。
- Modify: `services/api/app/routes/signals.py`
  - 增加研究工厂运行、候选列表、单币候选读取。
- Test: `services/api/tests/test_research_service.py`
- Test: `services/api/tests/test_signal_service.py`
- Test: `services/api/tests/test_api_skeleton.py`

### WebUI / 页面

- Create: `apps/web/components/research-candidate-board.tsx`
  - 统一展示单币候选排行、研究门槛、下一步动作。
- Modify: `apps/web/lib/api.ts`
  - 增加研究工厂相关 API 调用。
- Modify: `apps/web/app/signals/page.tsx`
  - 主研究按钮显示“训练、回测、排行、准入”结果。
- Modify: `apps/web/app/market/[symbol]/page.tsx`
  - 单币页显示研究候选、规则门、模型门、是否允许进入 `dry-run`。
- Modify: `apps/web/app/strategies/page.tsx`
  - 策略页直接显示“当前研究候选是否允许执行”。
- Test: `tests/test_frontend_refactor.py`
- Test: `tests/test_market_workspace.py`

### 文档

- Modify: `CONTEXT.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/ops-qlib.md`

---

### Task 1: 整理研究数据集与时间切分

**Files:**
- Create: `services/worker/qlib_dataset.py`
- Test: `services/worker/tests/test_qlib_dataset.py`

- [ ] **Step 1: 写失败测试，固定四个币种、双周期和时间切分口径**

```python
def test_build_dataset_bundle_returns_train_valid_test_splits() -> None:
    bundle = build_dataset_bundle(
        symbol="BTCUSDT",
        candles_1h=sample_candles(96),
        candles_4h=sample_candles(48, step_hours=4),
    )

    assert bundle.symbol == "BTCUSDT"
    assert bundle.timeframe == "4h"
    assert bundle.training_rows
    assert bundle.validation_rows
    assert bundle.testing_rows
    assert bundle.training_rows[-1]["generated_at"] < bundle.validation_rows[0]["generated_at"]
    assert bundle.validation_rows[-1]["generated_at"] < bundle.testing_rows[0]["generated_at"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_dataset -v`  
Expected: FAIL，提示 `build_dataset_bundle` 或新模块不存在。

- [ ] **Step 3: 写最小实现**

```python
@dataclass(slots=True)
class DatasetBundle:
    symbol: str
    timeframe: str
    training_rows: list[dict[str, object]]
    validation_rows: list[dict[str, object]]
    testing_rows: list[dict[str, object]]


def build_dataset_bundle(
    *,
    symbol: str,
    candles_1h: list[dict[str, object]],
    candles_4h: list[dict[str, object]],
) -> DatasetBundle:
    feature_rows = build_feature_rows(symbol, candles_4h)
    label_rows = build_label_rows(symbol, candles_4h)
    merged_rows = _merge_feature_and_label_rows(feature_rows, label_rows)
    return _split_dataset(symbol=symbol, rows=merged_rows, timeframe="4h")
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_dataset -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/worker/qlib_dataset.py services/worker/tests/test_qlib_dataset.py
git commit -m "feat: add qlib dataset bundle split"
```

### Task 2: 扩展因子与 1-3 天标签

**Files:**
- Modify: `services/worker/qlib_features.py`
- Modify: `services/worker/qlib_labels.py`
- Modify: `services/worker/tests/test_qlib_runner.py`

- [ ] **Step 1: 写失败测试，固定 EMA20 / EMA55 / ATR / RSI / 1-3 天标签输出**

```python
def test_feature_builder_outputs_timing_columns() -> None:
    rows = build_feature_rows("BTCUSDT", sample_candles(80))

    assert "ema20_gap_pct" in rows[-1]
    assert "ema55_gap_pct" in rows[-1]
    assert "atr_pct" in rows[-1]
    assert "rsi14" in rows[-1]


def test_label_builder_outputs_buy_sell_watch_for_1_to_3_day_window() -> None:
    rows = build_label_rows("BTCUSDT", sample_candles(80))

    assert rows[-5]["label"] in {"buy", "sell", "watch"}
    assert rows[-5]["holding_window"] == "1-3d"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_runner -v`  
Expected: FAIL，提示缺少新列或标签字段。

- [ ] **Step 3: 写最小实现**

```python
FEATURE_COLUMNS = (
    "symbol",
    "generated_at",
    "close_return_pct",
    "range_pct",
    "body_pct",
    "volume_ratio",
    "trend_gap_pct",
    "ema20_gap_pct",
    "ema55_gap_pct",
    "atr_pct",
    "rsi14",
    "breakout_strength",
)


LABEL_COLUMNS = (
    "symbol",
    "generated_at",
    "future_return_pct",
    "label",
    "holding_window",
    "is_trainable",
)
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_runner -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/worker/qlib_features.py services/worker/qlib_labels.py services/worker/tests/test_qlib_runner.py
git commit -m "feat: add timing factors and 1-3 day labels"
```

### Task 3: 增加规则层门控

**Files:**
- Create: `services/worker/qlib_rule_gate.py`
- Test: `services/worker/tests/test_qlib_rule_gate.py`

- [ ] **Step 1: 写失败测试，固定规则门的三个核心判断**

```python
def test_rule_gate_blocks_when_trend_is_broken() -> None:
    decision = evaluate_rule_gate(
        {
            "ema20_gap_pct": "-1.2000",
            "ema55_gap_pct": "-2.4000",
            "atr_pct": "6.3000",
            "volume_ratio": "0.8000",
        }
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "trend_broken"


def test_rule_gate_allows_when_trend_and_volume_confirm() -> None:
    decision = evaluate_rule_gate(
        {
            "ema20_gap_pct": "1.4000",
            "ema55_gap_pct": "2.3000",
            "atr_pct": "2.2000",
            "volume_ratio": "1.1500",
        }
    )

    assert decision["allowed"] is True
    assert decision["reason"] == "ready"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_rule_gate -v`  
Expected: FAIL，提示模块或函数不存在。

- [ ] **Step 3: 写最小实现**

```python
def evaluate_rule_gate(feature_row: dict[str, object]) -> dict[str, object]:
    ema20_gap = _to_decimal(feature_row.get("ema20_gap_pct"))
    ema55_gap = _to_decimal(feature_row.get("ema55_gap_pct"))
    atr_pct = _to_decimal(feature_row.get("atr_pct"))
    volume_ratio = _to_decimal(feature_row.get("volume_ratio"))

    if ema20_gap <= 0 or ema55_gap <= 0:
        return {"allowed": False, "reason": "trend_broken"}
    if atr_pct >= Decimal("5"):
        return {"allowed": False, "reason": "volatility_too_high"}
    if volume_ratio < Decimal("1"):
        return {"allowed": False, "reason": "volume_not_confirmed"}
    return {"allowed": True, "reason": "ready"}
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_rule_gate -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/worker/qlib_rule_gate.py services/worker/tests/test_qlib_rule_gate.py
git commit -m "feat: add qlib rule gate"
```

### Task 4: 统一训练、时间序列验证与最小回测

**Files:**
- Create: `services/worker/qlib_backtest.py`
- Modify: `services/worker/qlib_runner.py`
- Test: `services/worker/tests/test_qlib_backtest.py`
- Test: `services/worker/tests/test_qlib_runner.py`

- [ ] **Step 1: 写失败测试，固定回测指标和时间序列验证输出**

```python
def test_backtest_report_contains_core_metrics() -> None:
    report = run_backtest(
        rows=sample_ranked_rows(),
        holding_window="1-3d",
    )

    assert set(report["metrics"].keys()) == {
        "total_return_pct",
        "max_drawdown_pct",
        "sharpe",
        "win_rate",
        "turnover",
    }


def test_runner_training_writes_validation_and_backtest_sections() -> None:
    result = runner.train(dataset=sample_dataset())

    assert "validation" in result
    assert "backtest" in result
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_backtest services.worker.tests.test_qlib_runner -v`  
Expected: FAIL，提示缺少 `backtest` 或 `validation` 字段。

- [ ] **Step 3: 写最小实现**

```python
def run_backtest(*, rows: list[dict[str, object]], holding_window: str) -> dict[str, object]:
    metrics = {
        "total_return_pct": _format_float(_sum_return(rows)),
        "max_drawdown_pct": _format_float(_max_drawdown(rows)),
        "sharpe": _format_float(_sharpe(rows)),
        "win_rate": _format_float(_win_rate(rows)),
        "turnover": _format_float(_turnover(rows)),
    }
    return {"holding_window": holding_window, "metrics": metrics}
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_backtest services.worker.tests.test_qlib_runner -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/worker/qlib_backtest.py services/worker/qlib_runner.py services/worker/tests/test_qlib_backtest.py services/worker/tests/test_qlib_runner.py
git commit -m "feat: add qlib validation and backtest report"
```

### Task 5: 生成候选排行榜与 dry-run 准入门

**Files:**
- Create: `services/worker/qlib_ranking.py`
- Modify: `services/worker/qlib_runner.py`
- Test: `services/worker/tests/test_qlib_ranking.py`

- [ ] **Step 1: 写失败测试，固定候选排行和准入判断**

```python
def test_rank_candidates_marks_dry_run_ready_only_when_metrics_pass() -> None:
    result = rank_candidates(
        [
            {
                "symbol": "BTCUSDT",
                "strategy_template": "trend_breakout_timing",
                "score": "0.7800",
                "backtest": {"metrics": {"total_return_pct": "14.20", "max_drawdown_pct": "-5.10", "sharpe": "1.10", "win_rate": "0.58", "turnover": "0.24"}},
            }
        ]
    )

    assert result["items"][0]["dry_run_gate"]["status"] == "passed"
    assert result["items"][0]["allowed_to_dry_run"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_ranking -v`  
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
def rank_candidates(items: list[dict[str, object]]) -> dict[str, object]:
    ranked = sorted(items, key=lambda item: Decimal(str(item.get("score", "0"))), reverse=True)
    normalized = [_normalize_candidate(item) for item in ranked]
    return {"items": normalized}
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `.venv/bin/python -m unittest services.worker.tests.test_qlib_ranking -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/worker/qlib_ranking.py services/worker/qlib_runner.py services/worker/tests/test_qlib_ranking.py
git commit -m "feat: add qlib candidate ranking gate"
```

### Task 6: 把研究工厂结果接入 API

**Files:**
- Create: `services/api/app/services/research_factory_service.py`
- Modify: `services/api/app/services/research_service.py`
- Modify: `services/api/app/routes/signals.py`
- Test: `services/api/tests/test_research_service.py`
- Test: `services/api/tests/test_api_skeleton.py`

- [ ] **Step 1: 写失败测试，固定候选列表接口和单币摘要接口**

```python
def test_research_service_returns_ranked_candidates() -> None:
    payload = research_service.get_factory_snapshot()

    assert "candidates" in payload
    assert "summary" in payload


def test_signals_route_exposes_research_candidates() -> None:
    response = get_research_candidates()

    assert response["data"]["items"] is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest services.api.tests.test_research_service services.api.tests.test_api_skeleton -v`  
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
class ResearchFactoryService:
    def build_snapshot(self) -> dict[str, object]:
        latest = research_service.get_latest_result()
        inference = dict(latest.get("latest_inference") or {})
        items = list((inference.get("candidates") or {}).get("items", []))
        return {
            "summary": {
                "candidate_count": len(items),
                "ready_count": sum(1 for item in items if item.get("allowed_to_dry_run")),
            },
            "candidates": items,
        }
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `.venv/bin/python -m unittest services.api.tests.test_research_service services.api.tests.test_api_skeleton -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/research_factory_service.py services/api/app/services/research_service.py services/api/app/routes/signals.py services/api/tests/test_research_service.py services/api/tests/test_api_skeleton.py
git commit -m "feat: expose qlib research factory snapshot"
```

### Task 7: 把 dry-run 准入门接进信号主链路

**Files:**
- Modify: `services/api/app/services/signal_service.py`
- Modify: `services/api/tests/test_signal_service.py`

- [ ] **Step 1: 写失败测试，固定“不通过研究门槛不能进入可派发候选”**

```python
def test_qlib_signal_without_dry_run_gate_is_not_dispatchable() -> None:
    signal_service.ingest_signal(
        {
            "symbol": "BTCUSDT",
            "side": "long",
            "score": "0.78",
            "confidence": "0.81",
            "target_weight": "0.25",
            "generated_at": "2026-04-03T00:00:00+00:00",
            "source": "qlib",
            "strategy_id": 1,
        }
    )

    claimed = signal_service.claim_latest_dispatchable_signal(strategy_id=1)
    assert claimed is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest services.api.tests.test_signal_service -v`  
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```python
def _is_dispatchable_research_signal(signal: SignalContract) -> bool:
    if str(signal.source) != SignalSource.QLIB.value:
        return True
    metadata = dict(getattr(signal, "payload", {}) or {})
    gate = dict(metadata.get("dry_run_gate") or {})
    return str(gate.get("status", "")).strip() == "passed"
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `.venv/bin/python -m unittest services.api.tests.test_signal_service -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/signal_service.py services/api/tests/test_signal_service.py
git commit -m "feat: gate qlib signals before dry-run"
```

### Task 8: 在页面上展示研究候选和下一步动作

**Files:**
- Create: `apps/web/components/research-candidate-board.tsx`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/signals/page.tsx`
- Modify: `apps/web/app/market/[symbol]/page.tsx`
- Modify: `apps/web/app/strategies/page.tsx`
- Test: `tests/test_frontend_refactor.py`
- Test: `tests/test_market_workspace.py`

- [ ] **Step 1: 写失败测试，固定页面要出现的关键文案**

```python
def test_symbol_page_shows_research_gate_and_next_step() -> None:
    html = render_symbol_page_with_candidate()

    assert "研究候选" in html
    assert "是否允许进入 dry-run" in html
    assert "下一步动作" in html


def test_signals_page_shows_factory_summary() -> None:
    html = render_signals_page_with_factory_summary()

    assert "候选排行榜" in html
    assert "可进入 dry-run" in html
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest tests.test_frontend_refactor tests.test_market_workspace -v`  
Expected: FAIL

- [ ] **Step 3: 写最小实现**

```tsx
export function ResearchCandidateBoard({ summary, items }: ResearchCandidateBoardProps) {
  return (
    <section>
      <h2>研究候选</h2>
      <p>可进入 dry-run：{summary.readyCount}</p>
      <ul>{items.map((item) => <li key={item.symbol}>{item.symbol} / {item.dryRunGate.status}</li>)}</ul>
    </section>
  );
}
```

- [ ] **Step 4: 再跑测试确认通过**

Run: `.venv/bin/python -m unittest tests.test_frontend_refactor tests.test_market_workspace -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/research-candidate-board.tsx apps/web/lib/api.ts apps/web/app/signals/page.tsx apps/web/app/market/[symbol]/page.tsx apps/web/app/strategies/page.tsx tests/test_frontend_refactor.py tests/test_market_workspace.py
git commit -m "feat: show qlib candidate board in workspace"
```

### Task 9: 收口文档、运行说明和验收路径

**Files:**
- Modify: `CONTEXT.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/ops-qlib.md`

- [ ] **Step 1: 更新当前进度**

```md
- 当前正在做：Qlib 单币择时研究工厂第一版。
- 当前能力：四个固定币种、1-3 天持有周期、规则门 + ML 门、候选排行、dry-run 准入门。
```

- [ ] **Step 2: 更新 README 和架构说明**

```md
## Qlib 单币择时研究工厂

- 研究范围：BTC / ETH / SOL / DOGE
- 输出内容：回测指标、候选排行、dry-run 准入状态
- 当前不做：币种轮动、复杂深度学习、直接实盘执行
```

- [ ] **Step 3: 补运行与验收命令**

```bash
.venv/bin/python -m unittest services/worker/tests/test_qlib_runner.py -v
.venv/bin/python -m unittest services/api/tests/test_research_service.py -v
.venv/bin/python -m unittest tests/test_market_workspace.py -v
```

- [ ] **Step 4: Commit**

```bash
git add CONTEXT.md README.md docs/architecture.md docs/ops-qlib.md
git commit -m "docs: record qlib timing factory workflow"
```

---

## 计划自检

- 这份计划覆盖了 spec 里的四个核心目标：单币择时、双层门控、统一回测评估、候选准入。
- 计划吸收了 `quant-method-shared.md` 里真正值得落地的点：
  - 先做完整 pipeline，再谈更复杂模型
  - 特征少而稳
  - 时间序列切分
  - 类别不平衡与特征筛选留在研究主线里
  - 回测和评估是固定出口
- 当前计划没有引入新依赖，也没有把 `Qlib` 变成执行器。

