# 系统优化：可信训练-回测闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把系统的"训练→验证→回测→选币"主干修到数据可信、数字可信、能真正选出可交易候选，让 100 轮 0 成功的自动化周期开始产出结果。

**Architecture:** 4 个并行工作流 + 1 个串行收尾：(A) 数据量扩展（60天→1-2年）；(B) 回测重写为真实交易模拟；(C) walk-forward 验证启用 + 预测函数接真模型；(D) 阈值/假指标修复与展示对齐。A/B/C/D 文件互不重叠，可并行实现、并行 review，最后统一回归 + 部署验证。

**Tech Stack:** Python 3.11（FastAPI + LightGBM）、`services/worker/qlib_*.py`（训练/回测/验证）、`services/api/app/services/`（研究工作台/自动化）、`infra/deploy/api.env`（环境变量）、pytest。

---

## 背景事实（2026-08-08 实测确认）

1. **数据量**：训练只用 60 天（workbench `data.lookback_days=60`），每币 4h K 线约 360 根，训练样本 1649。Binance kline API 支持 `start_ts/end_ts` 分页（每页 1000 根），`KlineSyncService.backfill(days=)` 已支持任意天数分页回填。
2. **回测是假模拟**：`run_backtest`（qlib_backtest.py）只是把样本的 `future_return_pct` 求和 + 统计（Sharpe/胜率），**不是模拟真实交易**（无开仓/止损/平仓过程）。样本 2 个时"胜率 100%"是假指标。
3. **walk-forward 未启用**：`enable_walk_forward=False`（默认），且 `_build_walk_forward_report` 的预测函数是"恒等正比例"（`return [pos_rate] * len(test_rows)`）——即使打开也不是真模型预测。
4. **阈值 0.55 之谜已破解**：容器 `dry_run_min_score=0.45`（api.env），但自动化状态显示"阈值 0.550"——因为推理链 `_resolve_thresholds`（qlib_ranking.py:508）优先读 `payload.get("dry_run_min_score")`（workbench threshold preset `standard_gate=0.55`），**env 的 0.45 被 preset 覆盖**。
5. **前端展示残留**：`research/workspace` 显示 `model_key: heuristic_v1`、`backend: qlib-fallback`——是旧训练产物残留，最新训练其实是 lightgbm（val_auc 0.62）。
6. **测试基线**：`python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q` 当前 49 failed / 827 passed（全部 pre-existing 环境问题）；worker 测试套件 `python3 -m pytest services/worker/tests -q` 有 26 failed（既有断言过时）。**本计划所有改动后，失败集合不得新增。**

---

## 文件依赖图（并行分组依据）

```
┌─ Workflow A: 数据量扩展 ─────────────────────────────┐
│ services/worker/qlib_dataset.py (lookback过滤)      │
│ services/api/app/services/data_workspace_service.py │
│ services/api/app/services/research_service.py       │
│ infra/deploy/api.env (api.env 服务器手动改)          │
└─────────────────────────────────────────────────────┘
┌─ Workflow B: 回测重写 ───────────────────────────────┐
│ services/worker/qlib_backtest.py  (核心重写)         │
│ services/api/app/services/validation_workflow_service.py (指标消费适配) │
│ services/worker/tests/test_qlib_backtest.py          │
└─────────────────────────────────────────────────────┘
┌─ Workflow C: walk-forward 启用 ──────────────────────┐
│ services/worker/qlib_walk_forward.py (预测函数接真模型)│
│ services/worker/qlib_runner.py (enable 接线+报告)     │
│ services/worker/tests/test_qlib_walk_forward.py       │
└─────────────────────────────────────────────────────┘
┌─ Workflow D: 阈值/假指标/展示 ───────────────────────┐
│ services/api/app/services/workbench_config_service.py (preset 默认值) │
│ services/worker/qlib_ranking.py (最小样本保护)        │
│ services/api/app/services/research_workspace_service.py (模型展示对齐) │
│ services/api/tests/ 对应测试                          │
└─────────────────────────────────────────────────────┘
```

**关键约束**：A/B/C/D 四个 workflow 修改的文件集合互不重叠（除 D 的 ranking.py 与 C 的 runner.py 之外无交集）。**qlib_runner.py 只能由 Workflow C 碰**；**qlib_backtest.py 只能由 Workflow B 碰**。若实现中发现需要改其他 workflow 的文件，停下来报告，由控制器协调。

---

## 阶段 0：基线快照（控制器执行，串行）

### Task 0.1: 记录基线

- [ ] **Step 1: 跑全量基线**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | tail -3`
Expected: 49 failed / 827 passed 上下（记录精确数字）

- [ ] **Step 2: 保存失败列表**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | grep '^FAILED' | sort > /tmp/opencode/baseline_api.txt`
Expected: 文件生成

- [ ] **Step 3: worker 基线**

Run: `python3 -m pytest services/worker/tests -q 2>&1 | grep '^FAILED' | sort > /tmp/opencode/baseline_worker.txt`
Expected: 文件生成（约 26 failed）

- [ ] **Step 4: 提交基线记录**

```bash
cd /home/djy/Quant
git add -A && git commit -m "chore: 记录优化前测试基线" --allow-empty
```

---

## Workflow A：数据量扩展（60 天 → 1 年）

**目标**：训练数据从 60 天扩展到 365 天，让模型见过牛熊震荡完整周期。

### Task A1: 数据回填支持长窗口

**Files:**
- Modify: `services/api/app/services/kline_sync_service.py`（`backfill`/`_backfill_one` 已支持分页，验证长窗口正确性并补测试）
- Test: `services/worker/tests/test_qlib_dataset.py`（追加 lookback 过滤测试）

- [ ] **Step 1: 写失败测试（验证 1 年 lookback 过滤正确）**

```python
def test_filter_candles_one_year_lookback_keeps_full_window():
    """365 天回看：2016 根 4h K 线应全部保留。"""
    from services.worker.qlib_dataset import _filter_candles_by_lookback_days
    import time
    now_ms = int(time.time() * 1000)
    step_ms = 4 * 3600 * 1000
    candles = [
        {
            "open_time": now_ms - (2015 - i) * step_ms,
            "close_time": now_ms - (2015 - i) * step_ms + step_ms - 1,
            "open": "100", "high": "101", "low": "99", "close": "100", "volume": "10",
        }
        for i in range(2016)
    ]
    filtered = _filter_candles_by_lookback_days(candles, lookback_days=365)
    assert len(filtered) == 2016
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_dataset.py -q`
Expected: 新测试失败或通过（若通过说明过滤已正确，则改为验证"365 天窗口确实截断到 2016 根"的边界用例）

- [ ] **Step 3: 实现/确认 `_filter_candles_by_lookback_days`**

先读 `services/worker/qlib_dataset.py` 的 `_filter_candles_by_lookback_days`（约 342 行）确认实现：`earliest_allowed_open = latest_close_time - lookback_days*86400000`。若实现正确则测试应通过；若不正确则修复（保持签名）。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/tests/test_qlib_dataset.py services/worker/qlib_dataset.py
git commit -m "test: 验证365天数据回看过滤正确性"
```

### Task A2: 研究工作台数据默认窗口改为 1 年

**Files:**
- Modify: `services/api/app/services/data_workspace_service.py`（默认 lookback_days 30→365）
- Modify: `services/api/app/services/research_service.py`（默认 lookback_days 30→365）
- Test: `services/api/tests/test_data_workspace_service.py`（如有，追加；没有则跳过测试只改默认值）

- [ ] **Step 1: 读现状**

读 `data_workspace_service.py:53`（`lookback_days = max(int(configured_data.get("lookback_days", 30) or 30), 1)`）和 `research_service.py:335`（同 30 默认）。

- [ ] **Step 2: 写失败测试（验证默认值变 365）**

`data_workspace_service.py` 的 lookback_days 在方法内行内读取（约 53 行 `configured_data.get("lookback_days", 30)`），没有独立方法。测试改为直接验证模块行为——通过 `_build_preview` 的 fetch_limit 推断：

```python
def test_workbench_default_lookback_is_one_year():
    """数据工作台默认回看 365 天（4h 周期换算 2190 根）。"""
    from services.api.app.services.data_workspace_service import _resolve_preview_fetch_limit

    limit = _resolve_preview_fetch_limit(
        interval="4h", limit=120, lookback_days=365,
        window_mode="rolling", start_date="", end_date="",
    )
    assert limit >= 2190  # 365天 × 6根/天
```

（若 `_resolve_preview_fetch_limit` 的签名与上面不同，以读代码后的真实签名为准调整参数；断言意图不变：365 天 4h 需要至少 2190 根。）

- [ ] **Step 3: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests/test_data_workspace_service.py -q`
Expected: FAIL（默认值仍 30）

- [ ] **Step 4: 实现**

两处默认值 30 → 365：
- `data_workspace_service.py:53`：`configured_data.get("lookback_days", 365)`
- `research_service.py:335`：`data_config.get("lookback_days", 365)`

- [ ] **Step 5: 跑测试确认通过**

Run: 同上命令
Expected: 通过

- [ ] **Step 6: 提交**

```bash
cd /home/djy/Quant
git add services/api/app/services/data_workspace_service.py services/api/app/services/research_service.py services/api/tests/test_data_workspace_service.py
git commit -m "feat: 研究工作台默认数据窗口扩展至365天"
```

### Task A3: 服务器配置生效（api.env + workbench 配置）

**Files:**
- Modify: `infra/deploy/api.env`（本地 + 服务器各一份，gitignored 需手动同步）
- Modify: 服务器 `infra/data/runtime/workbench_config.json`（data.lookback_days 60→365）

- [ ] **Step 1: 本地 api.env 加配置**

在本地 `infra/deploy/api.env` 末尾追加：

```
# 数据窗口（2026-08-08 优化：训练数据 60天 → 365天）
QUANT_QLIB_LOOKBACK_DAYS=365
```

- [ ] **Step 2: 提交（api.env 是 gitignored，只提交文档说明）**

```bash
cd /home/djy/Quant
git add -A && git commit -m "docs: 记录数据窗口扩展配置说明" --allow-empty
```

（api.env 不进 git，部署时手动同步。）

- [ ] **Step 3: 验证 qlib_dataset 的 lookback 解析读 env**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && QUANT_QLIB_LOOKBACK_DAYS=365 python3 -c "import os; os.environ['QUANT_QLIB_RUNTIME_ROOT']='/tmp/qlib-test'; from services.worker.qlib_config import load_qlib_config; c=load_qlib_config(); print('lookback_days:', c.lookback_days)"`
Expected: 365

---

## Workflow B：回测重写为真实交易模拟（核心）

**目标**：把"求和统计"重写成"逐 K 线模拟交易"——有信号开仓、止损止盈平仓、成本扣减，输出真实的资金曲线。

### Task B1: 定义交易模拟核心（保持旧接口兼容）

**Files:**
- Modify: `services/worker/qlib_backtest.py`
- Test: `services/worker/tests/test_qlib_backtest.py`（重写追加）

- [ ] **Step 1: 先读旧实现**

读 `services/worker/qlib_backtest.py` 全文（253 行），理解 `run_backtest` 的输入（rows 含 future_return_pct、generated_at、symbol、label）和输出结构（metrics + series）。

- [ ] **Step 2: 写失败测试（真实模拟核心）**

```python
def test_simulate_trades_opens_and_closes():
    """模拟交易：有买入信号时开仓，价格到达止损/止盈时平仓。"""
    from services.worker.qlib_backtest import simulate_trades

    rows = [
        {"generated_at": 1000, "label": "buy", "future_return_pct": "0.5"},
        {"generated_at": 2000, "label": "watch", "future_return_pct": "-2.0"},   # 触发止损
        {"generated_at": 3000, "label": "watch", "future_return_pct": "3.0"},
    ]
    result = simulate_trades(rows, stop_loss_pct=-1.5, take_profit_pct=5.0, fee_pct=0.1)
    assert result["trades_count"] == 1
    assert result["trades"][0]["exit_reason"] == "stop_loss"
    assert result["final_nav"] < 1.0  # 亏损
```

**关键设计（先读旧代码再定签名）**：
- 输入：带 label（buy/watch/sell）的样本行序列，每行有 future_return_pct（模拟"持有一根 K 线的收益"）
- 逻辑：遇到 buy 开仓（成本价=前一根 close），随后每根按 future_return_pct 累计，达到 stop_loss_pct 平仓（stop_loss），达到 take_profit_pct 平仓（take_profit），窗口结束未触发则按最终收益平仓（window_end）
- 输出：`{"trades": [...], "trades_count": N, "final_nav": float, "max_drawdown_pct": float, "win_rate": float, "sharpe": float}`
- 每笔交易扣 fee_pct（开+平各一次）
- **兼容性**：`run_backtest` 的签名和返回结构（metrics/series 字段名）保持不变，内部改用 simulate_trades 结果填充 metrics；`sample_count` 保留

- [ ] **Step 3: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_backtest.py -q`
Expected: FAIL with `ImportError: cannot import name 'simulate_trades'`

- [ ] **Step 4: 实现 simulate_trades**

```python
def simulate_trades(
    rows: list[dict[str, object]],
    *,
    stop_loss_pct: float = -8.0,
    take_profit_pct: float = 8.0,
    fee_pct: float = 0.1,
    max_holding_bars: int = 18,
) -> dict[str, object]:
    """逐 K 线模拟交易：信号开仓，止损/止盈/窗口结束平仓。

    每行样本的 future_return_pct 视为"持有一根 K 线的收益率"。
    遇到 label=buy 开仓，后续每根累计收益；触达 stop_loss 或 take_profit
    平仓，或持有 max_holding_bars 根后按窗口结束平仓。
    """
    trades: list[dict[str, object]] = []
    position: dict[str, object] | None = None
    nav = 1.0
    nav_series: list[float] = []
    peak_nav = 1.0
    max_drawdown = 0.0
    wins = 0

    for row in rows:
        ret = float(row.get("future_return_pct", 0.0) or 0.0)
        if position is None and str(row.get("label", "")) == "buy":
            position = {
                "entry_bar": row.get("generated_at"),
                "bars_held": 0,
                "cum_return": -fee_pct,  # 开仓手续费
            }
            continue
        if position is not None:
            position["bars_held"] += 1
            position["cum_return"] += ret
            cum = float(position["cum_return"])
            exit_reason = None
            if cum <= stop_loss_pct:
                exit_reason = "stop_loss"
            elif cum >= take_profit_pct:
                exit_reason = "take_profit"
            elif position["bars_held"] >= max_holding_bars:
                exit_reason = "window_end"
            if exit_reason:
                cum -= fee_pct  # 平仓手续费
                profit = cum
                nav *= 1 + profit / 100.0
                if profit > 0:
                    wins += 1
                trades.append({
                    "entry_bar": position["entry_bar"],
                    "exit_bar": row.get("generated_at"),
                    "bars_held": position["bars_held"],
                    "return_pct": round(profit, 4),
                    "exit_reason": exit_reason,
                })
                position = None
        nav_series.append(nav)
        peak_nav = max(peak_nav, nav)
        max_drawdown = max(max_drawdown, (peak_nav - nav) / peak_nav * 100)

    if position is not None:
        # 序列结束时仍持仓：按当前累计收益平仓
        profit = float(position["cum_return"]) - fee_pct
        nav *= 1 + profit / 100.0
        if profit > 0:
            wins += 1
        trades.append({
            "entry_bar": position["entry_bar"],
            "exit_bar": "end",
            "bars_held": position["bars_held"],
            "return_pct": round(profit, 4),
            "exit_reason": "end_of_series",
        })

    total = len(trades)
    return {
        "trades": trades,
        "trades_count": total,
        "final_nav": round(nav, 4),
        "max_drawdown_pct": round(max_drawdown, 4),
        "win_rate": round(wins / total, 4) if total else 0.0,
        "sharpe": _sharpe_ratio([t["return_pct"] for t in trades]) if total else 0.0,
    }
```

- [ ] **Step 5: 跑测试确认通过**

Run: 同上命令
Expected: 新测试通过；旧测试若因结构变化失败，调整旧断言（metrics 字段名不变，值可能变化属预期，更新断言值）

- [ ] **Step 6: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_backtest.py services/worker/tests/test_qlib_backtest.py
git commit -m "feat: 回测重写为真实交易模拟(开仓/止损/止盈/平仓)"
```

### Task B2: run_backtest 内部接入模拟 + 最小样本保护

**Files:**
- Modify: `services/worker/qlib_backtest.py`（run_backtest 内部改用 simulate_trades）
- Test: `services/worker/tests/test_qlib_backtest.py`（追加）

- [ ] **Step 1: 写失败测试（run_backtest 现在输出模拟指标）**

```python
def test_run_backtest_uses_simulation_metrics():
    """run_backtest 输出真实模拟指标（含 trades_count）。"""
    from services.worker.qlib_backtest import run_backtest

    rows = [
        {"generated_at": 1000, "label": "buy", "future_return_pct": "0.5"},
        {"generated_at": 2000, "label": "watch", "future_return_pct": "-2.0"},
        {"generated_at": 3000, "label": "watch", "future_return_pct": "3.0"},
    ]
    report = run_backtest(rows=rows, holding_window="1-3d", fee_bps=10, slippage_bps=5)
    metrics = report["metrics"]
    assert "trades_count" in metrics
    assert "final_nav" in metrics
    assert int(metrics["trades_count"]) >= 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_backtest.py -q`
Expected: FAIL with `KeyError: 'trades_count'`

- [ ] **Step 3: 实现**

在 `run_backtest` 内：把原来的"求和统计"替换为调用 `simulate_trades`，metrics 保持原字段名（total_return_pct/net_return_pct/win_rate/sharpe/max_drawdown_pct/sample_count）并**新增** `trades_count`、`final_nav`、`exit_reasons` 字段。cost 参数映射：`fee_pct = (fee_bps + slippage_bps) / 100`（单边合计，模拟函数内部开平各扣一次）。原 `_build_performance_series` 继续用模拟后的 nav 序列。

**重要**：`sample_count` 语义改为"参与模拟的样本行数"；`win_rate/sharpe` 改为基于模拟交易结果。旧字段值变化属预期，同步更新旧测试断言。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_backtest.py services/worker/tests/test_qlib_backtest.py
git commit -m "feat: run_backtest接入真实模拟并新增最小样本保护字段"
```

### Task B3: 验证层消费新指标（validation_workflow）

**Files:**
- Modify: `services/api/app/services/validation_workflow_service.py`（如消费 win_rate/sharpe 的地方适配）
- Test: `services/api/tests/test_validation_workflow_service.py`（如有）

- [ ] **Step 1: 读消费点**

Run: `cd /home/djy/Quant && grep -rn 'win_rate\|sharpe\|total_return_pct' services/api/app/services/validation_workflow_service.py | head -10`
Expected: 找到消费回测指标的代码行

- [ ] **Step 2: 适配**

若消费的是 `metrics["win_rate"]`/`metrics["sharpe"]` 等字段，确认新模拟指标字段名兼容（`win_rate`/`sharpe` 字段名不变，只是值来源变了——**通常无需改代码**）。若读到 `metrics["sample_count"]` 判断样本量，确认语义（模拟样本数）可接受或改为读 `trades_count`。最小改动，保持消费逻辑不变。

- [ ] **Step 3: 跑相关测试**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests/test_validation_workflow_service.py -q`
Expected: 通过（若有失败且是字段名问题，修消费代码）

- [ ] **Step 4: 提交**

```bash
cd /home/djy/Quant
git add -A
git commit -m "feat: 验证层适配模拟回测指标"
```

---

## Workflow C：walk-forward 验证启用（真模型预测）

**目标**：打开时间序列验证，预测函数从"恒等正比例"改为真 LightGBM 模型预测。

### Task C1: 预测函数接真模型

**Files:**
- Modify: `services/worker/qlib_walk_forward.py`
- Test: `services/worker/tests/test_qlib_walk_forward.py`（追加）

- [ ] **Step 1: 读现状**

读 `services/worker/qlib_walk_forward.py` 全文和 `services/worker/qlib_runner.py` 的 `_build_walk_forward_report`（约 1000 行，预测函数是 `return [pos_rate] * len(test_rows)`）。

- [ ] **Step 2: 写失败测试（预测函数支持模型回调）**

```python
def test_run_with_model_predictor_uses_predictions():
    """walk-forward 使用模型预测函数而非恒等比例。"""
    from services.worker.qlib_walk_forward import WalkForwardConfig, WalkForwardValidator

    rows = []
    for i in range(200):
        rows.append({
            "open_time": 1712000000000 + i * 3600000,
            "generated_at": 1712000000000 + i * 3600000,
            "future_return_pct": str((i % 10) - 4),
        })

    calls = {"count": 0}

    def fake_predictor(train_rows, test_rows):
        calls["count"] += 1
        # 返回与 test_rows 等长的预测，模拟模型输出
        return [0.6 if i % 2 == 0 else 0.4 for i in range(len(test_rows))]

    validator = WalkForwardValidator()
    config = WalkForwardConfig(n_folds=4, min_train_bars=50, gap_bars=6)
    report = validator.run(fake_predictor, rows, config)
    assert calls["count"] == 4  # 每折调用一次
    assert report.folds
```

- [ ] **Step 3: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_walk_forward.py -q`
Expected: FAIL（若 run 已支持回调则检查断言——calls count 或 fold 数不符）

- [ ] **Step 4: 实现**

读 `WalkForwardValidator.run` 现有签名，确认已接收 predictor 回调。若已支持（runner 里传 `_predict`），则本任务改为验证并补强测试；若不支持，给 `run` 加 `predictor` 参数。保持向后兼容（无 predictor 时用默认恒等比例）。

- [ ] **Step 5: 跑测试确认通过**

Run: 同上命令
Expected: 全部通过

- [ ] **Step 6: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_walk_forward.py services/worker/tests/test_qlib_walk_forward.py
git commit -m "feat: walk-forward支持模型预测回调"
```

### Task C2: runner 的 walk-forward 预测函数接真模型 + 启用开关

**Files:**
- Modify: `services/worker/qlib_runner.py`（`_build_walk_forward_report` 的 `_predict` 用真模型）
- Test: `services/worker/tests/test_qlib_runner.py`（追加）

- [ ] **Step 1: 写失败测试（启用 walk-forward 后报告含 fold 指标）**

```python
def test_walk_forward_report_built_when_enabled():
    """开启 walk-forward 后训练报告包含 folds。"""
    import tempfile
    from pathlib import Path
    from services.worker.qlib_runner import QlibRunner
    from services.worker.qlib_config import QlibRuntimeConfig

    with tempfile.TemporaryDirectory() as tmp:
        config = QlibRuntimeConfig()
        config.enable_walk_forward = True
        config.paths.runtime_root = Path(tmp) / "runtime"
        runner = QlibRunner(config=config)
        rows = [
            {"generated_at": 1712000000000 + i * 3600000, "future_return_pct": "0.5", "ema20_gap_pct": "1", "ema55_gap_pct": "2", "body_pct": "1", "volume_ratio": "1", "trend_gap_pct": "1", "breakout_strength": "1", "trend_strength": "1", "volatility_contraction": "50", "volume_price_divergence": "0", "bull_bear_ratio": "1", "rsi14": "50", "cci20": "0", "stoch_k14": "50"}
            for i in range(120)
        ]
        report = runner._build_walk_forward_report_for_test(rows)  # 方法名以实际为准
        assert report is not None
        assert report["folds"]
```

（以读代码后的真实签名为准调整——`_build_walk_forward_report(bundle, metrics)` 接收 bundle，测试可构造最小 bundle 或直接测其内部预测函数。）

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_runner.py -q`
Expected: 按测试实际断言确认失败点

- [ ] **Step 3: 实现**

在 `_build_walk_forward_report` 的 `_predict` 函数中，改用真模型预测：
- 从 `self._config` 读 model_type/model_params
- 若 lightgbm/xgboost：用 `services.worker.ml.trainer.ModelTrainer` 在 train_rows 上训练轻量模型，对 test_rows 预测概率
- 预测失败时降级为 pos_rate 恒等（保持现有容错）
- 从 `metrics`（model_type/model_path）判断是否已有训练好的模型文件可复用，有则用 `ModelPredictor` 加载预测（比每折重训更快）

**注意**：`_build_walk_forward_report` 是只读分析，不在训练主链上（训练走 `train()`），所以接模型预测属于"验证增强"，失败不影响主训练。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 通过

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_runner.py services/worker/tests/test_qlib_runner.py
git commit -m "feat: walk-forward预测接入真模型"
```

### Task C3: 启用配置（本地 api.env + 服务器）

**Files:**
- Modify: `infra/deploy/api.env`（本地，服务器部署时同步）

- [ ] **Step 1: 本地 api.env 追加**

```
# walk-forward 时间序列验证（2026-08-08 优化开启）
QUANT_QLIB_ENABLE_WALK_FORWARD=true
```

- [ ] **Step 2: 验证 env 解析**

Run: `cd /home/djy/Quant && QUANT_QLIB_ENABLE_WALK_FORWARD=true python3 -c "import os; os.environ['QUANT_QLIB_RUNTIME_ROOT']='/tmp/qlib-test'; from services.worker.qlib_config import load_qlib_config; c=load_qlib_config(); print('enable_walk_forward:', c.enable_walk_forward)"`
Expected: True

- [ ] **Step 3: 提交**

```bash
cd /home/djy/Quant
git add -A && git commit -m "docs: walk-forward 启用配置说明" --allow-empty
```

---

## Workflow D：阈值/假指标/展示修复

### Task D1: threshold preset 默认值对齐（0.55 → 0.45）

**Files:**
- Modify: `services/api/app/services/workbench_config_service.py`（THRESHOLD_PRESET_VALUES 的 standard_gate）
- Test: `services/api/tests/test_workbench_config_service.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
def test_standard_gate_default_score_is_045():
    """标准门槛预设的 dry_run 分数默认 0.45（与 env 一致，不再覆盖为 0.55）。"""
    from services.api.app.services.workbench_config_service import THRESHOLD_PRESET_VALUES

    preset = THRESHOLD_PRESET_VALUES["standard_gate"]
    assert preset["dry_run_min_score"] == "0.45"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests/test_workbench_config_service.py -q`
Expected: FAIL（当前 0.55）

- [ ] **Step 3: 实现**

`workbench_config_service.py:304`：`"dry_run_min_score": "0.55"` → `"0.45"`（standard_gate 预设）。其余预设（strict_live_gate 0.6、exploratory_dry_run 0.48）不动。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 通过

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/api/app/services/workbench_config_service.py services/api/tests/test_workbench_config_service.py
git commit -m "fix: standard_gate预设分数0.55->0.45, 与env一致"
```

### Task D2: 最小样本保护（假指标防护）

**Files:**
- Modify: `services/worker/qlib_ranking.py`（`_evaluate_score_gate`/backtest gate 加样本保护）
- Test: `services/worker/tests/test_qlib_ranking.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
def test_backtest_gate_rejects_tiny_sample():
    """样本过少时回测门直接拦截（防止2个样本造出100%胜率假指标）。"""
    from services.worker.qlib_ranking import _evaluate_backtest_gate

    thresholds = {"dry_run_min_sample_count": 20, "dry_run_min_net_return_pct": "0", "dry_run_min_sharpe": "0.25", "dry_run_max_drawdown_pct": "15", "dry_run_min_win_rate": "0.5"}
    metrics = {
        "trades_count": "2", "sample_count": "2",
        "net_return_pct": "5.0", "sharpe": "44.0", "win_rate": "1.0", "max_drawdown_pct": "0",
    }
    result = _evaluate_backtest_gate(metrics, thresholds=thresholds)
    assert result["status"] == "failed"
    assert any("insufficient" in r or "样本" in r for r in result["reasons"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_ranking.py -q`
Expected: FAIL（当前 2 样本也能通过）

- [ ] **Step 3: 实现**

在 `_evaluate_backtest_gate`（约 204 行）开头加样本保护：

```python
def _evaluate_backtest_gate(metrics: dict[str, object], *, thresholds: dict[str, Decimal | int]) -> dict[str, object]:
    """回测门：模拟交易指标达标且样本量足够才放行。"""
    sample_count = int(str(metrics.get("trades_count") or metrics.get("sample_count") or "0"))
    min_sample = int(thresholds["dry_run_min_sample_count"])
    if sample_count < min_sample:
        return {"status": "failed", "reasons": [f"insufficient_trades (模拟交易 {sample_count} 笔 < 最少 {min_sample} 笔)"]}
    # ...原有判断逻辑不变
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 通过（旧测试若用 2 样本断言"通过"，需把样本数改大或改断言）

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_ranking.py services/worker/tests/test_qlib_ranking.py
git commit -m "fix: 回测门加最小样本保护, 防止假指标"
```

### Task D3: 模型展示对齐（heuristic_v1 → lightgbm）

**Files:**
- Modify: `services/api/app/services/research_workspace_service.py`（模型视图取最新训练结果）
- Test: `services/api/tests/test_research_workspace_service.py`（如有）

- [ ] **Step 1: 读现状**

读 `research_workspace_service.py` 中模型视图构建处（搜索 model_key/model_version/backend），找到显示 `heuristic_v1`/`qlib-fallback` 的来源（可能是从旧 training 结果或固定默认值）。

- [ ] **Step 2: 写失败测试**

```python
def test_model_view_reflects_latest_training():
    """模型视图应反映最新训练（lightgbm），而非残留的 heuristic_v1。"""
    from services.api.app.services.research_workspace_service import ResearchWorkspaceService

    service = object.__new__(ResearchWorkspaceService)
    service._read_latest_training = lambda: {
        "metrics": {"model_type": "lightgbm"},
        "model_version": "qlib-minimal-20260807163614",
        "backend": "qlib",
    }
    view = service._build_model_view()  # 方法名以实际为准
    assert view["model_type"] == "lightgbm"
    assert view["model_key"] != "heuristic_v1"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests/test_research_workspace_service.py -q`
Expected: 按实际断言确认失败点

- [ ] **Step 4: 实现**

模型视图改为从最新 training 结果（`metrics.model_type`）读取，而非固定默认值/旧残留。读不到时回退显示"无训练记录"而不是 heuristic_v1。

- [ ] **Step 5: 跑测试确认通过**

Run: 同上命令
Expected: 通过

- [ ] **Step 6: 提交**

```bash
cd /home/djy/Quant
git add services/api/app/services/research_workspace_service.py services/api/tests/test_research_workspace_service.py
git commit -m "fix: 模型视图对齐最新训练结果, 清除heuristic_v1残留"
```

---

## 阶段 3：全量回归 + 部署验证（串行收尾）

### Task F1: 全量回归

- [ ] **Step 1: 跑 api 全量**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | grep '^FAILED' | sort > /tmp/opencode/after_api.txt; comm -13 /tmp/opencode/baseline_api.txt /tmp/opencode/after_api.txt`
Expected: 无新增失败（comm 输出为空）

- [ ] **Step 2: 跑 worker 全量**

Run: `python3 -m pytest services/worker/tests -q 2>&1 | grep '^FAILED' | sort > /tmp/opencode/after_worker.txt; comm -13 /tmp/opencode/baseline_worker.txt /tmp/opencode/after_worker.txt`
Expected: 无新增失败

- [ ] **Step 3: 推送**

```bash
cd /home/djy/Quant && git push origin master
```

### Task F2: 服务器部署（api.env 同步 + 构建重启）

- [ ] **Step 1: 拉代码**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "git -C /home/djy/Quant pull"`
Expected: 代码更新

- [ ] **Step 2: 同步 api.env（本地追加的三行配置）**

Run: 在本地确认新增行后，用 ssh 管道把三行追加到服务器 api.env：

```bash
ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "grep -q QUANT_QLIB_LOOKBACK_DAYS /home/djy/Quant/infra/deploy/api.env || cat >> /home/djy/Quant/infra/deploy/api.env <<'EOF'

# 数据窗口（2026-08-08 优化：训练数据 60天 → 365天）
QUANT_QLIB_LOOKBACK_DAYS=365
# walk-forward 时间序列验证（2026-08-08 优化开启）
QUANT_QLIB_ENABLE_WALK_FORWARD=true
EOF"
```

- [ ] **Step 3: 改服务器 workbench_config.json 的 lookback_days**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "python3 -c \"
import json
path='/home/djy/Quant/infra/data/runtime/workbench_config.json'
with open(path) as f: d=json.load(f)
d.setdefault('data',{})['lookback_days']=365
with open(path,'w') as f: json.dump(d,f,ensure_ascii=False,indent=2)
print('workbench lookback_days -> 365')
\""`
Expected: 输出确认

- [ ] **Step 4: 重建重启 api（nohup 防 OOM）**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "nohup bash -c 'cd /home/djy/Quant/infra/deploy && docker compose build api 2>&1 && docker compose up -d --no-deps api 2>&1 && docker compose restart api 2>&1' > /tmp/build_opt.log 2>&1 & echo started"`
Expected: started；等待构建完成（约 3-5 分钟，用 tail 轮询）

### Task F3: 服务器验证

- [ ] **Step 1: 健康检查**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "curl -s -m 10 http://localhost:9011/health"`
Expected: `{"data":{"status":"ok",...}}`

- [ ] **Step 2: 验证配置生效**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "docker exec quant-api python3 -c \"
import os
os.environ['QUANT_QLIB_RUNTIME_ROOT']='/app/.runtime/qlib'
from services.worker.qlib_config import load_qlib_config
c = load_qlib_config()
print('lookback_days:', c.lookback_days)
print('enable_walk_forward:', c.enable_walk_forward)
\""`
Expected: 365 / True

- [ ] **Step 3: 验证回测新指标**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "docker exec quant-api python3 -c \"
from services.worker.qlib_backtest import run_backtest
rows = [{'generated_at': 1000+i, 'label': 'buy' if i==0 else 'watch', 'future_return_pct': str(0.5 if i%3 else -1.5)} for i in range(40)]
r = run_backtest(rows=rows, holding_window='1-3d', fee_bps=10, slippage_bps=5)
print('trades_count:', r['metrics'].get('trades_count'))
print('final_nav:', r['metrics'].get('final_nav'))
\""`
Expected: trades_count > 0，final_nav 为真实模拟值

- [ ] **Step 4: 触发一轮训练验证数据量**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "curl -s -X POST 'http://127.0.0.1:9011/api/v1/openclaw/patrol?patrol_type=cycle_check' | python3 -m json.tool | head -20"`
Expected: 巡检正常；后续观察训练日志确认样本量增长（训练样本应达 1万+）

- [ ] **Step 5: 观察自动化周期**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "cat /home/djy/Quant/infra/data/runtime/automation_state.json | python3 -c \"
import sys,json; d=json.load(sys.stdin)
lc=d.get('last_cycle',{})
print('状态:', lc.get('status'), '| 推荐:', lc.get('recommended_symbol'))
print('消息:', lc.get('message'))
print('train:', lc.get('train_task',{}).get('status'))
\""`
Expected: 训练成功；若仍 score_too_low 属预期（阈值 0.45 后分数仍不够说明模型需要时间学习长数据）

- [ ] **Step 6: 提交验证记录**

```bash
cd /home/djy/Quant
git add -A && git commit -m "docs: 记录系统优化部署验证结果" --allow-empty
git push origin master
```

---

## 部署与回滚

- 每次 commit 独立可回滚：`git revert <commit>` 后重新部署
- Workflow A/B/C/D 全部完成后统一部署一次（避免反复构建，服务器 1.6G 内存构建有 OOM 风险，必须 nohup 后台执行）
- 若 365 天数据导致训练超时（每 15 分钟周期会变慢），方案：数据 365 天但训练频率可调（`QUANT_QLIB_` 相关配置），或先观察一轮训练实际耗时再决定
- 阈值 0.45 是"先跑起来"的临时值，观察 dry-run 1-2 周后根据真实表现回调

## 风险与注意

1. **回测重写影响面**：`run_backtest` 被 runner/验证层消费，字段名保留但值语义变化（win_rate/sharpe 现在基于模拟交易）。Task B3 专门适配消费点，回归必须过。
2. **walk-forward 接模型耗时**：每折训练轻量模型会增加训练时长（原 22s → 可能 1-2 分钟）。若超时（自动化周期 900s 上限足够），观察后决定是否降低 n_folds 或 min_train_bars。
3. **365 天数据拉取耗时**：16 币 × 4h × 365 天 ≈ 每币 2190 根 = 3 页请求，首次拉取约 16×3=48 次请求，几秒内完成；KlineStore 落盘 3.4G+（当前 23M），注意磁盘（当前 57% 使用）。
4. **阈值 preset 修改影响**：standard_gate 0.55→0.45 会放宽所有使用该预设的页面门槛，属预期（先跑起来）；strict_live_gate/exploratory 不动。
5. **测试基线**：api 49 failed / worker 26 failed 均为 pre-existing，改动后失败集合 ⊆ 基线；worker 测试中 test_qlib_backtest.py 旧断言因指标语义变化需更新（Task B1/B2 内处理）。
6. **并行冲突红线**：qlib_runner.py 只归 Workflow C；qlib_backtest.py 只归 Workflow B；workbench_config_service.py 只归 Workflow D；data_workspace_service.py/research_service.py 只归 Workflow A。越界改动会与并行 agent 冲突，必须上报控制器。
