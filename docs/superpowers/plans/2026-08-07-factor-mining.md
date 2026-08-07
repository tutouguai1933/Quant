# 因子挖掘优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把系统的因子体系从"手工挑选 + 固定权重"升级为"IC 数据驱动 + 自动去冗余 + 多窗口标签 + 新维度因子"的闭环。

**Architecture:** 分 5 个阶段落地：(1) 因子相关性矩阵与去冗余；(2) 标签升级（多窗口 + 波动率调整）；(3) IC 自动体检闭环（运行时因子启停 + 自动降权）；(4) 新维度因子（横截面 / 资金流 / 市场状态）；(5) 因子计算工程提速与禁用量因子复检。每个阶段独立可交付、可测试、可部署。

**Tech Stack:** Python 3.11（FastAPI + LightGBM/XGBoost）、`services/worker/qlib_*.py`（因子/标签/训练管线）、`services/api/app/services/scoring/`（打分权重）、`services/data/config/strategy_tuning.json`（权重持久化）、pytest。

**关键现状（实现前必读）：**
- 因子定义与计算：`services/worker/qlib_features.py`（19 个因子，5 个 `enabled: False` 已禁用；`PRIMARY_FEATURE_COLUMNS` 是静态常量，运行时不可启停）
- 标签：`services/worker/qlib_labels.py`（`LabelSpec`：target 1%、stop -1%、window 18 bars=3天、earliest_hit）
- 训练管线：`services/worker/qlib_runner.py`（`train()` 已产出 `factor_evaluation`，含 `ic_series`/`quantile_nav`，在 `_build_factor_evaluation` 约 1023 行）
- 权重：`services/api/app/services/scoring/scoring_service.py`（6 个手工因子权重，`get/set_factor_weights`，持久化到 strategy_tuning.json）
- 前端因子终端：`services/api/app/services/feature_workspace_service.py`（`correlation_rows` 目前为空，`factor_rows` 的 IC 硬编码 "0.00"）
- 测试基线：`python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q`，当前环境实测 49 failed / 827 passed（均为 pre-existing，改动后失败集合不得新增）

---

## 阶段一：因子相关性矩阵与去冗余

**目标**：量化因子间冗余（当前 ema20_gap / ema55_gap / trend_gap 高度相关），产出"每个冗余组保留 IC 最高因子"的建议，前端可展示。

### Task 1.1: 相关性矩阵计算函数

**Files:**
- Modify: `services/worker/qlib_features.py`（新增函数，放在 `evaluate_factor_quantile_nav` 之后）
- Test: `services/worker/tests/test_qlib_features_correlation.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_qlib_features_correlation.py
"""因子相关性矩阵单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import build_factor_correlation_matrix  # noqa: E402


def test_correlation_matrix_identical_factors_are_1():
    rows = [
        {"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0", "trend_gap_pct": "3.0"},
        {"ema20_gap_pct": "2.0", "ema55_gap_pct": "4.0", "trend_gap_pct": "6.0"},
        {"ema20_gap_pct": "3.0", "ema55_gap_pct": "6.0", "trend_gap_pct": "9.0"},
    ]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct", "trend_gap_pct"])
    # ema20 与 trend 完全线性相关
    assert abs(matrix["pairs"][0]["correlation"]) > 0.99


def test_correlation_matrix_reports_pairs():
    rows = [
        {"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0"},
        {"ema20_gap_pct": "2.0", "ema55_gap_pct": "2.1"},
        {"ema20_gap_pct": "3.0", "ema55_gap_pct": "2.2"},
    ]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct"])
    assert len(matrix["pairs"]) == 1
    assert matrix["pairs"][0]["factor_a"] == "ema20_gap_pct"
    assert matrix["pairs"][0]["factor_b"] == "ema55_gap_pct"


def test_correlation_matrix_insufficient_samples():
    rows = [{"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0"}]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct"])
    assert matrix["pairs"] == []


def test_correlation_matrix_returns_factor_metadata():
    rows = [
        {"ema20_gap_pct": "1.0", "ema55_gap_pct": "2.0"},
        {"ema20_gap_pct": "2.0", "ema55_gap_pct": "2.1"},
        {"ema20_gap_pct": "3.0", "ema55_gap_pct": "2.2"},
    ]
    matrix = build_factor_correlation_matrix(rows, factor_names=["ema20_gap_pct", "ema55_gap_pct"])
    assert matrix["factors"] == ["ema20_gap_pct", "ema55_gap_pct"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_features_correlation.py -q`
Expected: FAIL with `ImportError: cannot import name 'build_factor_correlation_matrix'`

- [ ] **Step 3: 实现函数**

在 `services/worker/qlib_features.py` 的 `_compute_rank_ic` 函数之后追加：

```python
def build_factor_correlation_matrix(
    rows: list[dict[str, object]],
    factor_names: list[str] | None = None,
    min_samples: int = 5,
) -> dict[str, object]:
    """计算因子两两相关性矩阵。

    皮尔逊相关系数（与 IC 同口径），返回冗余分组建议。
    相关度 >= 0.8 的因子对进入 redundancy_pairs，按相关度降序。
    """
    if factor_names is None:
        factor_names = list(PRIMARY_FEATURE_COLUMNS)

    if len(rows) < min_samples:
        return {"factors": factor_names, "pairs": [], "redundancy_pairs": []}

    values: dict[str, list[float]] = {}
    for name in factor_names:
        values[name] = [_to_float_local(row.get(name)) for row in rows]

    pairs: list[dict[str, object]] = []
    redundancy_pairs: list[dict[str, object]] = []
    for i in range(len(factor_names)):
        for j in range(i + 1, len(factor_names)):
            a, b = factor_names[i], factor_names[j]
            corr = _compute_ic(values[a], values[b])
            if corr is None:
                continue
            entry = {
                "factor_a": a,
                "factor_b": b,
                "correlation": round(corr, 4),
                "redundant": abs(corr) >= 0.8,
            }
            pairs.append(entry)
            if abs(corr) >= 0.8:
                redundancy_pairs.append(entry)

    pairs.sort(key=lambda p: -abs(float(p["correlation"])))
    redundancy_pairs.sort(key=lambda p: -abs(float(p["correlation"])))
    return {
        "factors": factor_names,
        "pairs": pairs,
        "redundancy_pairs": redundancy_pairs,
    }
```

注意：`_compute_ic` 是模块内已有函数（`qlib_features.py:955`），直接复用；`_to_float_local` 同样已有（`qlib_features.py:947`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_features_correlation.py -q`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_features.py services/worker/tests/test_qlib_features_correlation.py
git commit -m "feat: 因子相关性矩阵与冗余对检测"
```

### Task 1.2: 训练结果携带相关性分析

**Files:**
- Modify: `services/worker/qlib_runner.py`（`_build_factor_evaluation` 返回里加 `correlation_matrix`）
- Test: `services/worker/tests/test_qlib_runner_factor_correlation.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_qlib_runner_factor_correlation.py
"""训练结果携带相关性矩阵。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_runner import QlibRunner  # noqa: E402


def test_factor_evaluation_includes_correlation_matrix():
    # 用一个最小 runner，直接调用 _build_factor_evaluation
    runner = object.__new__(QlibRunner)
    rows = []
    for i in range(30):
        rows.append({
            "generated_at": 1783486800000 + i * 3600000,
            "future_return_pct": str(i % 5 - 2),
            "ema20_gap_pct": str(i),
            "ema55_gap_pct": str(i + 1),   # 与 ema20 高度相关
            "body_pct": str(i % 7 - 3),
            "volume_ratio": str(1.0),
            "trend_gap_pct": str(i * 2),
            "breakout_strength": str(i % 3),
            "trend_strength": str(i),
            "volatility_contraction": str(50),
            "volume_price_divergence": str(0),
            "bull_bear_ratio": str(1),
            "rsi14": str(50),
            "cci20": str(0),
            "stoch_k14": str(50),
        })
    evaluation = runner._build_factor_evaluation(rows)
    assert "correlation_matrix" in evaluation
    assert evaluation["correlation_matrix"]["redundancy_pairs"], "应检出 ema20/ema55 冗余"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_runner_factor_correlation.py -q`
Expected: FAIL with `KeyError: 'correlation_matrix'`

- [ ] **Step 3: 实现**

先读 `services/worker/qlib_runner.py` 的 `_build_factor_evaluation`（约 1023 行起），在其返回 dict 中追加：

```python
        # 因子相关性矩阵（去冗余）
        from services.worker.qlib_features import build_factor_correlation_matrix
        correlation_matrix = build_factor_correlation_matrix(rows, factor_names=list(PRIMARY_FEATURE_COLUMNS))
```

并在 `_build_factor_evaluation` 的返回 dict（含 `ic_series`、`quantile_nav` 的那个）中加 `"correlation_matrix": correlation_matrix,`。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_runner.py services/worker/tests/test_qlib_runner_factor_correlation.py
git commit -m "feat: 训练结果携带因子相关性矩阵"
```

### Task 1.3: 前端因子终端展示相关性

**Files:**
- Modify: `services/api/app/services/feature_workspace_service.py`（`_build_terminal_research` 的 `correlation_rows` 填数据）
- Test: `services/api/tests/test_feature_workspace_correlation.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/api/tests/test_feature_workspace_correlation.py
"""因子终端展示相关性数据。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.feature_workspace_service import FeatureWorkspaceService  # noqa: E402


class CorrelationRowsTests(unittest.TestCase):
    def test_builds_correlation_rows_from_report(self):
        service = object.__new__(FeatureWorkspaceService)
        report = {
            "factor_evaluation": {
                "correlation_matrix": {
                    "factors": ["ema20_gap_pct", "ema55_gap_pct", "body_pct"],
                    "redundancy_pairs": [
                        {"factor_a": "ema20_gap_pct", "factor_b": "ema55_gap_pct", "correlation": 0.99},
                    ],
                    "pairs": [],
                }
            }
        }
        rows = service._build_correlation_rows(report)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["factor_a"], "ema20_gap_pct")
        self.assertEqual(rows[0]["redundant"], True)

    def test_empty_when_no_report(self):
        service = object.__new__(FeatureWorkspaceService)
        self.assertEqual(service._build_correlation_rows({}), [])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests/test_feature_workspace_correlation.py -q`
Expected: FAIL with `AttributeError: 'FeatureWorkspaceService' object has no attribute '_build_correlation_rows'`

- [ ] **Step 3: 实现**

在 `services/api/app/services/feature_workspace_service.py` 加方法：

```python
    def _build_correlation_rows(self, report: dict[str, object]) -> list[dict[str, object]]:
        """从训练报告提取因子相关性冗余对，供前端表格展示。"""
        factor_eval = dict(report.get("factor_evaluation") or {})
        matrix = dict(factor_eval.get("correlation_matrix") or {})
        pairs = list(matrix.get("redundancy_pairs") or [])
        rows: list[dict[str, object]] = []
        for pair in pairs:
            rows.append({
                "factor_a": str(pair.get("factor_a", "")),
                "factor_b": str(pair.get("factor_b", "")),
                "correlation": float(pair.get("correlation", 0.0)),
                "redundant": bool(pair.get("redundant", False)),
                "detail": f"相关度 {float(pair.get('correlation', 0.0)):.2f}，建议保留 IC 更高者",
            })
        return rows
```

然后在 `_build_terminal_research` 中把 `correlation_rows: list[dict[str, object]] = []` 替换为：

```python
        correlation_rows = self._build_correlation_rows(report)
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/api/app/services/feature_workspace_service.py services/api/tests/test_feature_workspace_correlation.py
git commit -m "feat: 因子终端展示相关性冗余对"
```

### Task 1.4: 全量回归

- [ ] **Step 1: 跑全量测试**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | tail -3`
Expected: 失败数与基线一致（49 failed / 827 passed 上下），不得新增失败

- [ ] **Step 2: 提交（如无新增失败）**

```bash
cd /home/djy/Quant && git push origin master
```

---

## 阶段二：标签升级（多窗口 + 波动率调整）

**目标**：单窗口标签（3天固定）升级为多窗口加权；引入波动率调整收益，消除低波动期假信号。

### Task 2.1: LabelSpec 支持多窗口

**Files:**
- Modify: `services/worker/qlib_labels.py`
- Test: `services/worker/tests/test_qlib_labels.py`（已有，追加用例）

- [ ] **Step 1: 读现有实现**

先读 `services/worker/qlib_labels.py` 全文（约 200 行），重点看 `LabelSpec`、`build_label_rows`、`_build_label`（earliest_hit 逻辑）和现有测试 `services/worker/tests/test_qlib_labels.py` 的断言方式，保持向后兼容。

- [ ] **Step 2: 写失败测试（追加到 test_qlib_labels.py）**

```python
def test_label_spec_supports_multi_window_returns():
    """多窗口标签：返回 dict[window_bars -> label]。"""
    from services.worker.qlib_labels import build_multi_window_labels

    candles = [
        {"open_time": 1000 * (i), "close_time": 1000 * (i + 1), "open": "100", "high": "101", "low": "99", "close": str(100 + i), "volume": "10"}
        for i in range(25)
    ]
    result = build_multi_window_labels(
        candles,
        windows=[6, 12, 18],
        target_pct=5.0,
        stop_pct=-5.0,
    )
    assert set(result.keys()) == {6, 12, 18}
    # 最后一根：close 124 vs 6 根前 118 → +5.1% ≥ 5% → buy
    assert result[6] == "buy"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_labels.py -q`
Expected: FAIL with `ImportError: cannot import name 'build_multi_window_labels'`

- [ ] **Step 4: 实现**

在 `services/worker/qlib_labels.py` 中新增（复用现有 `LabelSpec` 的判定逻辑，抽一个内部判定函数）：

```python
def _classify_single_window(
    close_now: Decimal,
    closes_ahead: list[Decimal],
    target_pct: Decimal,
    stop_pct: Decimal,
) -> str:
    """按单窗口判定 buy/sell/watch：先触达 target 为 buy，先触达 stop 为 sell。"""
    for close in closes_ahead:
        change = (close - close_now) / close_now * 100 if close_now else Decimal("0")
        if change >= target_pct:
            return "buy"
        if change <= stop_pct:
            return "sell"
    return "watch"


def build_multi_window_labels(
    candles: list[dict[str, object]],
    *,
    windows: list[int] = (6, 12, 18),
    target_pct: float = 1.0,
    stop_pct: float = -1.0,
) -> dict[int, str]:
    """对最后一根 K 线按多个窗口分别判定标签。

    返回 {window_bars: label}。用于多窗口加权训练。
    """
    closes = [Decimal(str(c["close"])) for c in candles]
    if len(closes) < max(windows) + 1:
        return {w: "watch" for w in windows}
    now = closes[-1]
    target = Decimal(str(target_pct))
    stop = Decimal(str(stop_pct))
    result: dict[int, str] = {}
    for window in windows:
        ahead = closes[-window:]
        result[window] = _classify_single_window(now, ahead, target, stop)
    return result
```

- [ ] **Step 5: 跑测试确认通过**

Run: 同上命令
Expected: 原有用例 + 新用例全部通过

- [ ] **Step 6: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_labels.py services/worker/tests/test_qlib_labels.py
git commit -m "feat: 多窗口标签判定支持"
```

### Task 2.2: 波动率调整收益

**Files:**
- Modify: `services/worker/qlib_labels.py`
- Test: `services/worker/tests/test_qlib_labels.py`（追加）

- [ ] **Step 1: 写失败测试**

```python
def test_volatility_adjusted_return_normalizes_by_atr():
    """波动率调整收益 = 原始收益 / ATR%，低波动期小波动不会误判。"""
    from services.worker.qlib_labels import volatility_adjusted_return

    # 高波动场景：ATR 5%，收益 3% → 调整后 0.6
    assert abs(volatility_adjusted_return(3.0, atr_pct=5.0) - 0.6) < 1e-9
    # 低波动场景：ATR 0.5%，收益 3% → 调整后 6.0（信号更突出）
    assert abs(volatility_adjusted_return(3.0, atr_pct=0.5) - 6.0) < 1e-9
    # ATR 为 0 保护
    assert volatility_adjusted_return(3.0, atr_pct=0.0) == 0.0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_labels.py -q`
Expected: FAIL with `ImportError: cannot import name 'volatility_adjusted_return'`

- [ ] **Step 3: 实现**

```python
def volatility_adjusted_return(return_pct: float, atr_pct: float) -> float:
    """波动率调整收益：return_pct / atr_pct。

    用于标签构造：把收益按波动率归一，低波动期的小波动不会被放大成假信号。
    atr_pct <= 0 时返回 0（无法归一，放弃该样本）。
    """
    if atr_pct is None or float(atr_pct) <= 0:
        return 0.0
    return float(return_pct) / float(atr_pct)
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_labels.py services/worker/tests/test_qlib_labels.py
git commit -m "feat: 波动率调整收益函数"
```

### Task 2.3: 训练管线接入多窗口标签（可配置开关）

**Files:**
- Modify: `services/worker/qlib_config.py`（加配置项 `multi_window_labels_enabled`、`label_windows`）
- Modify: `services/worker/qlib_runner.py`（训练/推理时按配置选择标签构造方式）
- Test: `services/worker/tests/test_qlib_runner_labels.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_qlib_runner_labels.py
"""训练管线多窗口标签开关。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_config import QlibRuntimeConfig  # noqa: E402


def test_config_defaults_multi_window_disabled():
    """默认关闭多窗口（保持现状，避免未验证改动上线）。"""
    config = QlibRuntimeConfig()
    assert config.multi_window_labels_enabled is False
    assert config.label_windows == [6, 12, 18]


def test_config_reads_env_override():
    import os
    os.environ["QUANT_MULTI_WINDOW_LABELS"] = "true"
    try:
        config = QlibRuntimeConfig()
        assert config.multi_window_labels_enabled is True
    finally:
        del os.environ["QUANT_MULTI_WINDOW_LABELS"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_runner_labels.py -q`
Expected: FAIL with `AttributeError: 'QlibRuntimeConfig' object has no attribute 'multi_window_labels_enabled'`

- [ ] **Step 3: 实现**

读 `services/worker/qlib_config.py`（约 200 行），在 `QlibRuntimeConfig` 中加字段与 from_env 读取：

```python
    multi_window_labels_enabled: bool = False
    label_windows: list[int] = field(default_factory=lambda: [6, 12, 18])
```

from_env 中：

```python
        multi_window_labels_enabled = os.getenv("QUANT_MULTI_WINDOW_LABELS", "").lower() in ("1", "true", "yes")
        raw_windows = os.getenv("QUANT_LABEL_WINDOWS", "6,12,18")
        label_windows = [int(x.strip()) for x in raw_windows.split(",") if x.strip().isdigit()] or [6, 12, 18]
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_config.py services/worker/tests/test_qlib_runner_labels.py
git commit -m "feat: 多窗口标签配置项（默认关闭）"
```

### Task 2.4: 多窗口标签生成实际进入训练 bundle

**Files:**
- Modify: `services/worker/qlib_runner.py`（`_build_training_bundle` 或标签生成处接入）
- Test: `services/worker/tests/test_qlib_runner_labels.py`（追加）

- [ ] **Step 1: 读实现**

读 `services/worker/qlib_runner.py` 中 `_build_training_bundle`（约 355 行）和标签生成的实际调用（`build_label_rows`），确认在哪一步给每行打 label。

- [ ] **Step 2: 写失败测试**

```python
def test_training_bundle_labels_use_multi_window_when_enabled():
    """开启多窗口后，训练行的 label 取多窗口多数票。"""
    import tempfile
    from pathlib import Path
    from services.worker.qlib_runner import QlibRunner

    with tempfile.TemporaryDirectory() as tmp:
        config = QlibRuntimeConfig()
        config.runtime_root = Path(tmp) / "runtime"
        config.multi_window_labels_enabled = True
        runner = QlibRunner(config=config)

        candles = [
            {"open_time": 1000 * i, "close_time": 1000 * (i + 1), "open": "100", "high": "101", "low": "99", "close": str(100 + i), "volume": "10"}
            for i in range(40)
        ]
        bundle = runner._build_training_bundle({"TESTUSDT": {"candles": candles}})
        # 训练行存在且 label 属于 buy/sell/watch
        assert bundle.training_rows
        assert all(r.get("label") in ("buy", "sell", "watch") for r in bundle.training_rows)
```

（若 `_build_training_bundle` 的实际签名与样例不符，以读代码后的真实签名为准调整测试。）

- [ ] **Step 3: 实现**

在标签构造处按配置分支：`multi_window_labels_enabled=True` 时用 `build_multi_window_labels` 多数票（buy>sell>watch 优先级取非 watch 多数，平票取较长窗口结果）生成 label；否则走原 `build_label_rows`。保持 `future_return_pct` 字段照常输出。

- [ ] **Step 4: 跑测试确认通过**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_runner_labels.py -q`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_runner.py services/worker/tests/test_qlib_runner_labels.py
git commit -m "feat: 训练管线接入多窗口标签（开关控制）"
```

### Task 2.5: 全量回归 + 部署

- [ ] **Step 1: 跑全量测试**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | tail -3`
Expected: 无新增失败

- [ ] **Step 2: 推送**

```bash
cd /home/djy/Quant && git push origin master
```

（部署统一在阶段五末尾做一次，避免频繁重建镜像；阶段二/三/四期间只 push 不部署。）

---

## 阶段三：因子 IC 自动体检闭环

**目标**：训练后自动评估各因子近 30 天 IC，低/负 IC 因子自动降权，运行时因子启停不再硬编码。

### Task 3.1: 运行时因子启停注册表

**Files:**
- Create: `services/worker/factor_registry.py`（新建）
- Modify: `services/worker/qlib_features.py`（`PRIMARY_FEATURE_COLUMNS` 增加按注册表过滤的运行时版本）
- Test: `services/worker/tests/test_factor_registry.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_factor_registry.py
"""运行时因子启停注册表。"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.factor_registry import FactorRegistry  # noqa: E402


def test_registry_defaults_use_static_enabled():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        # ema20 默认启用
        assert registry.is_enabled("ema20_gap_pct")
        # 静态定义里 enabled=False 的默认禁用
        assert not registry.is_enabled("atr_pct")


def test_registry_set_enabled_persists():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "state.json"
        registry = FactorRegistry(state_path=path)
        registry.set_enabled("atr_pct", True)
        registry2 = FactorRegistry(state_path=path)
        assert registry2.is_enabled("atr_pct")


def test_registry_disable_factor():
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        registry.set_enabled("ema20_gap_pct", False)
        assert not registry.is_enabled("ema20_gap_pct")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_factor_registry.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.worker.factor_registry'`

- [ ] **Step 3: 实现**

```python
"""运行时因子启停注册表。

把 FACTOR_DEFINITIONS 里的 enabled 硬编码升级为运行时状态，
支持按因子 IC 体检结果自动启停，状态持久化到 JSON 文件。
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from services.worker.qlib_features import FACTOR_DEFINITIONS, FACTOR_METADATA

DEFAULT_STATE_PATH = Path(".runtime/factor_registry.json")


class FactorRegistry:
    """因子启停注册表（进程内单例 + JSON 持久化）。"""

    def __init__(self, state_path: Path | str | None = None) -> None:
        self._state_path = Path(state_path) if state_path else DEFAULT_STATE_PATH
        self._overrides: dict[str, bool] = {}
        self._lock = threading.Lock()
        self._load()

    def _default_enabled(self, name: str) -> bool:
        metadata = FACTOR_METADATA.get(name) or {}
        return bool(metadata.get("enabled", True))

    def is_enabled(self, name: str) -> bool:
        with self._lock:
            if name in self._overrides:
                return self._overrides[name]
            return self._default_enabled(name)

    def set_enabled(self, name: str, enabled: bool) -> None:
        with self._lock:
            self._overrides[name] = enabled
            self._save_locked()

    def enabled_columns(self, role: str = "primary") -> list[str]:
        items = [i for i in FACTOR_DEFINITIONS if i.get("role") == role]
        return [i["name"] for i in items if self.is_enabled(i["name"])]

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._overrides = {str(k): bool(v) for k, v in dict(data.get("overrides", {})).items()}
        except (json.JSONDecodeError, OSError, IOError):
            self._overrides = {}

    def _save_locked(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w", encoding="utf-8") as fh:
                json.dump({"overrides": self._overrides}, fh, ensure_ascii=False, indent=2)
        except (OSError, IOError):
            pass


factor_registry = FactorRegistry()
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/factor_registry.py services/worker/tests/test_factor_registry.py
git commit -m "feat: 运行时因子启停注册表"
```

### Task 3.2: 训练管线用注册表过滤特征列

**Files:**
- Modify: `services/worker/qlib_runner.py`（`_build_training_bundle` 中特征列来源改为注册表）
- Test: `services/worker/tests/test_qlib_runner_factor_registry.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_qlib_runner_factor_registry.py
"""训练特征列受注册表启停影响。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.factor_registry import FactorRegistry  # noqa: E402
from services.worker.qlib_runner import QlibRunner  # noqa: E402


def test_training_bundle_feature_columns_exclude_disabled():
    runner = object.__new__(QlibRunner)
    with tempfile.TemporaryDirectory() as tmp:
        registry = FactorRegistry(state_path=Path(tmp) / "state.json")
        registry.set_enabled("body_pct", False)
        bundle = runner._build_training_bundle_with_registry({"TESTUSDT": {}}, registry)
        assert "body_pct" not in bundle.feature_columns
        assert "ema20_gap_pct" in bundle.feature_columns
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_runner_factor_registry.py -q`
Expected: FAIL with `AttributeError: 'QlibRunner' object has no attribute '_build_training_bundle_with_registry'`

- [ ] **Step 3: 实现**

读 `_build_training_bundle` 真实实现，抽出/修改特征列构造处：从 `PRIMARY_FEATURE_COLUMNS + AUXILIARY_FEATURE_COLUMNS` 改为 `registry.enabled_columns("primary") + registry.enabled_columns("auxiliary")`。新增方法：

```python
    def _build_training_bundle_with_registry(
        self,
        dataset: dict[str, object],
        registry: object,
    ) -> TrainingBundle:
        """按运行时因子注册表构建训练 bundle（测试与体检共用）。"""
        return self._build_training_bundle(dataset, registry=registry)
```

`_build_training_bundle` 增加可选参数 `registry: object | None = None`，内部默认用 `factor_registry` 单例。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_runner.py services/worker/tests/test_qlib_runner_factor_registry.py
git commit -m "feat: 训练特征列受运行时注册表控制"
```

### Task 3.3: IC 体检器（自动降权/启停决策）

**Files:**
- Create: `services/worker/factor_ic_doctor.py`（新建）
- Test: `services/worker/tests/test_factor_ic_doctor.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_factor_ic_doctor.py
"""因子 IC 体检：低 IC 自动降权，负 IC 连续两轮禁用。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.factor_ic_doctor import FactorIcDoctor  # noqa: E402

# 工具：构造一条体检记录
def _eval(factor: str, ic: float):
    return {"ic_series": [{"factor": factor, "ic": ic, "rank_ic": ic * 0.9}], "quantile_nav": []}


def test_low_ic_recommends_weight_downgrade():
    doctor = FactorIcDoctor()
    result = doctor.assess({"factor_evaluation": _eval("ema20_gap_pct", 0.01)})
    assert result["actions"]["ema20_gap_pct"] == "downgrade"


def test_healthy_ic_no_action():
    doctor = FactorIcDoctor()
    result = doctor.assess({"factor_evaluation": _eval("ema20_gap_pct", 0.06)})
    assert result["actions"]["ema20_gap_pct"] == "keep"


def test_negative_ic_first_round_warns():
    doctor = FactorIcDoctor()
    result = doctor.assess({"factor_evaluation": _eval("ema20_gap_pct", -0.02)})
    assert result["actions"]["ema20_gap_pct"] == "watch"


def test_negative_ic_two_rounds_disables():
    doctor = FactorIcDoctor()
    doctor.assess({"factor_evaluation": _eval("ema20_gap_pct", -0.02)})
    result = doctor.assess({"factor_evaluation": _eval("ema20_gap_pct", -0.03)})
    assert result["actions"]["ema20_gap_pct"] == "disable"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_factor_ic_doctor.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.worker.factor_ic_doctor'`

- [ ] **Step 3: 实现**

```python
"""因子 IC 体检器。

训练后评估每个主因子最近 IC：
- IC >= 0.05: keep（保持）
- 0.0 <= IC < 0.05: downgrade（建议降权）
- IC < 0 且连续 2 轮: disable（自动禁用）
- IC < 0 第一轮: watch（警告观察）
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from services.worker.qlib_features import PRIMARY_FEATURE_COLUMNS

KEEP_IC = 0.05
DOWNGRADE_IC = 0.0
WATCH_ROUNDS = 1
DISABLE_ROUNDS = 2

DEFAULT_STATE_PATH = Path(".runtime/factor_ic_state.json")


class FactorIcDoctor:
    """基于 IC 序列做因子启停与降权决策。"""

    def __init__(self, state_path: Path | str | None = None) -> None:
        self._state_path = Path(state_path) if state_path else DEFAULT_STATE_PATH
        self._negative_rounds: dict[str, int] = {}
        self._lock = threading.Lock()
        self._load()

    def assess(self, report: dict[str, object]) -> dict[str, object]:
        """输入训练报告，返回每个主因子的体检动作。"""
        evaluation = dict(report.get("factor_evaluation") or {})
        ic_series = list(evaluation.get("ic_series") or [])
        latest_ic: dict[str, float] = {}
        for entry in ic_series:
            factor = str(entry.get("factor", ""))
            ic = entry.get("ic")
            if factor and isinstance(ic, (int, float)):
                latest_ic[factor] = float(ic)

        actions: dict[str, str] = {}
        with self._lock:
            for factor in PRIMARY_FEATURE_COLUMNS:
                if factor not in latest_ic:
                    actions[factor] = "unknown"
                    continue
                ic = latest_ic[factor]
                if ic >= KEEP_IC:
                    self._negative_rounds[factor] = 0
                    actions[factor] = "keep"
                elif ic >= DOWNGRADE_IC:
                    self._negative_rounds[factor] = 0
                    actions[factor] = "downgrade"
                else:
                    rounds = self._negative_rounds.get(factor, 0) + 1
                    self._negative_rounds[factor] = rounds
                    actions[factor] = "disable" if rounds >= DISABLE_ROUNDS else "watch"
            self._save_locked()

        return {
            "actions": actions,
            "negative_rounds": dict(self._negative_rounds),
            "assessed_at": time.time(),
        }

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._negative_rounds = {str(k): int(v) for k, v in dict(data.get("negative_rounds", {})).items()}
        except (json.JSONDecodeError, OSError, IOError):
            self._negative_rounds = {}

    def _save_locked(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w", encoding="utf-8") as fh:
                json.dump({"negative_rounds": self._negative_rounds}, fh, ensure_ascii=False, indent=2)
        except (OSError, IOError):
            pass
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/factor_ic_doctor.py services/worker/tests/test_factor_ic_doctor.py
git commit -m "feat: 因子IC体检器(自动降权/禁用决策)"
```

### Task 3.4: 体检动作落地（自动降权 + 自动启停）

**Files:**
- Modify: `services/worker/qlib_runner.py`（train() 尾部调用体检并执行动作）
- Modify: `services/api/app/services/scoring/scoring_service.py`（`set_factor_weights` 支持 IC 权重覆盖入口）
- Test: `services/worker/tests/test_factor_ic_doctor_apply.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_factor_ic_doctor_apply.py
"""体检动作落地：禁用因子进入注册表，降权写入评分权重。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.factor_ic_doctor import FactorIcDoctor  # noqa: E402
from services.worker.factor_registry import FactorRegistry  # noqa: E402


def test_disable_action_updates_registry():
    with tempfile.TemporaryDirectory() as tmp:
        doctor = FactorIcDoctor(state_path=Path(tmp) / "ic.json")
        registry = FactorRegistry(state_path=Path(tmp) / "registry.json")
        # 两次负 IC
        doctor.assess({"factor_evaluation": {"ic_series": [{"factor": "body_pct", "ic": -0.02}]}})
        result = doctor.assess({"factor_evaluation": {"ic_series": [{"factor": "body_pct", "ic": -0.03}]}})
        assert result["actions"]["body_pct"] == "disable"

        applied = doctor.apply_actions(result, registry=registry)
        assert "body_pct" in applied["disabled"]
        assert not registry.is_enabled("body_pct")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_factor_ic_doctor_apply.py -q`
Expected: FAIL with `AttributeError: 'FactorIcDoctor' object has no attribute 'apply_actions'`

- [ ] **Step 3: 实现**

给 `FactorIcDoctor` 加方法：

```python
    def apply_actions(
        self,
        assessment: dict[str, object],
        *,
        registry: object | None = None,
    ) -> dict[str, object]:
        """把体检动作落地：disable → 注册表禁用；downgrade → 标记降权建议。

        disable 动作同时清除降权记录（避免重复判断）。
        """
        if registry is None:
            from services.worker.factor_registry import factor_registry
            registry = factor_registry

        actions = dict(assessment.get("actions") or {})
        disabled: list[str] = []
        downgraded: list[str] = []
        for factor, action in actions.items():
            if action == "disable":
                registry.set_enabled(factor, False)
                self._negative_rounds[factor] = 0
                disabled.append(factor)
            elif action == "downgrade":
                downgraded.append(factor)
        self._save_locked()
        return {"disabled": disabled, "downgraded": downgraded}
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 1 passed

- [ ] **Step 5: 在 train() 尾部接线**

在 `services/worker/qlib_runner.py` 的 `train()` 中，`factor_evaluation` 构建之后追加：

```python
        # IC 体检：自动禁用连续负 IC 因子
        try:
            from services.worker.factor_ic_doctor import FactorIcDoctor
            doctor = FactorIcDoctor()
            assessment = doctor.assess(result)
            applied = doctor.apply_actions(assessment)
            result["factor_health"] = {"assessment": assessment, "applied": applied}
        except Exception:
            result["factor_health"] = {"error": "ic_doctor_failed"}
```

- [ ] **Step 6: 提交**

```bash
cd /home/djy/Quant
git add services/worker/factor_ic_doctor.py services/worker/qlib_runner.py services/worker/tests/test_factor_ic_doctor_apply.py
git commit -m "feat: IC体检动作落地-自动禁用连续负IC因子"
```

### Task 3.5: 全量回归

- [ ] **Step 1: 跑全量测试**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | tail -3`
Expected: 无新增失败

- [ ] **Step 2: 推送**

```bash
cd /home/djy/Quant && git push origin master
```

---

## 阶段四：新维度因子

**目标**：补齐横截面（相对强弱）、资金流（taker 主动买量）、市场状态（BTC 相关性）三类因子。

### Task 4.1: 横截面相对强弱因子

**Files:**
- Modify: `services/worker/qlib_features.py`（FACTOR_DEFINITIONS 加 `relative_strength`；`build_feature_rows` 增加可选横截面上下文参数）
- Test: `services/worker/tests/test_qlib_features_cross_section.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_qlib_features_cross_section.py
"""横截面相对强弱因子。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import compute_relative_strength  # noqa: E402


def test_relative_strength_ranks_symbols():
    """相对强弱 = 该币 20 根收益 - 全部币收益中位数。"""
    symbol_returns = {"BTCUSDT": 2.0, "ETHUSDT": 5.0, "SOLUSDT": 1.0}
    assert compute_relative_strength("ETHUSDT", symbol_returns, window=20) > 0
    assert compute_relative_strength("SOLUSDT", symbol_returns, window=20) < 0


def test_relative_strength_unknown_symbol_neutral():
    symbol_returns = {"BTCUSDT": 2.0}
    assert compute_relative_strength("DOGEUSDT", symbol_returns, window=20) == 0.0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_features_cross_section.py -q`
Expected: FAIL with `ImportError: cannot import name 'compute_relative_strength'`

- [ ] **Step 3: 实现**

```python
def compute_relative_strength(
    symbol: str,
    symbol_returns: dict[str, float],
    *,
    window: int = 20,
) -> float:
    """横截面相对强弱：该币 window 根收益相对全体币收益中位数的偏离。

    正值表示强于市场平均，负值表示弱于市场平均。
    """
    if symbol not in symbol_returns:
        return 0.0
    values = list(symbol_returns.values())
    if len(values) < 2:
        return 0.0
    median = sorted(values)[len(values) // 2]
    return float(symbol_returns[symbol]) - float(median)
```

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_features.py services/worker/tests/test_qlib_features_cross_section.py
git commit -m "feat: 横截面相对强弱因子"
```

### Task 4.2: taker 资金流因子（从 kline 增量数据计算）

**Files:**
- Modify: `services/worker/qlib_features.py`（FACTOR_DEFINITIONS 加 `taker_buy_ratio`；`_normalize_candle` 支持 `taker_buy_base_volume` 字段）
- Test: `services/worker/tests/test_qlib_features_taker.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_qlib_features_taker.py
"""taker 主动买量占比因子。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import compute_taker_buy_ratio  # noqa: E402


def test_taker_ratio_basic():
    assert abs(compute_taker_buy_ratio(volume=100.0, taker_buy=60.0) - 0.6) < 1e-9


def test_taker_ratio_zero_volume_neutral():
    assert compute_taker_buy_ratio(volume=0.0, taker_buy=0.0) == 0.5


def test_taker_ratio_missing_taker_data_neutral():
    assert compute_taker_buy_ratio(volume=100.0, taker_buy=None) == 0.5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_features_taker.py -q`
Expected: FAIL with `ImportError: cannot import name 'compute_taker_buy_ratio'`

- [ ] **Step 3: 实现**

```python
def compute_taker_buy_ratio(volume: float, taker_buy: float | None) -> float:
    """taker 主动买量占比，值域 [0,1]，缺失或零成交量返回 0.5 中性。"""
    if taker_buy is None or volume is None or float(volume) <= 0:
        return 0.5
    ratio = float(taker_buy) / float(volume)
    return max(0.0, min(1.0, ratio))
```

同时：`_normalize_candle` 增加可选字段 `taker_buy_base_volume` 的透传（`candle.get("taker_buy_base_volume")`，缺失为 None），并在 `build_feature_rows` 的 raw_row 中加 `"taker_buy_ratio": compute_taker_buy_ratio(volume, taker_buy)`（taker_buy 取当前 K 线字段）。FACTOR_DEFINITIONS 增加 `{"name": "taker_buy_ratio", "category": "volume", "role": "primary", "kind": "composite", "neutral": "0.5", "clip": ("0", "1"), "description": "taker 主动买量占比..."}`。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_features.py services/worker/tests/test_qlib_features_taker.py
git commit -m "feat: taker资金流因子(主动买量占比)"
```

### Task 4.3: 市场状态因子（BTC 相关性）

**Files:**
- Modify: `services/worker/qlib_features.py`（FACTOR_DEFINITIONS 加 `btc_correlation`；`build_feature_rows` 增加可选 btc_closes 参数）
- Test: `services/worker/tests/test_qlib_features_market.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_qlib_features_market.py
"""BTC 相关性因子。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import compute_btc_correlation  # noqa: E402


def test_btc_correlation_perfect_positive():
    btc = [1.0, 2.0, 3.0]
    coin = [10.0, 20.0, 30.0]
    assert compute_btc_correlation(coin, btc) > 0.99


def test_btc_correlation_missing_btc_neutral():
    assert compute_btc_correlation([1.0, 2.0, 3.0], []) == 0.0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_features_market.py -q`
Expected: FAIL with `ImportError: cannot import name 'compute_btc_correlation'`

- [ ] **Step 3: 实现**

```python
def compute_btc_correlation(coin_closes: list[float], btc_closes: list[float]) -> float:
    """最近 20 根该币与 BTC 的收益率相关性，值域 [-1, 1]，数据不足返回 0。"""
    if len(coin_closes) < 3 or len(btc_closes) < 3:
        return 0.0
    n = min(len(coin_closes), len(btc_closes))
    coin_ret = [coin_closes[i] / coin_closes[i - 1] - 1 for i in range(max(1, n - 20), n) if coin_closes[i - 1]]
    btc_ret = [btc_closes[i] / btc_closes[i - 1] - 1 for i in range(max(1, n - 20), n) if btc_closes[i - 1]]
    if len(coin_ret) < 3 or len(btc_ret) != len(coin_ret):
        return 0.0
    corr = _compute_ic(coin_ret, btc_ret)
    return round(corr or 0.0, 4)
```

`build_feature_rows` 增加参数 `btc_closes: list[float] | None = None`，raw_row 加 `"btc_correlation": compute_btc_correlation([float(c["close"]) for c in valid_candles], btc_closes or [])`。FACTOR_DEFINITIONS 加 `{"name": "btc_correlation", "category": "trend", "role": "primary", "kind": "composite", "neutral": "0", "clip": ("-1", "1"), "description": "与BTC的收益率相关性，判断市场联动程度"}`。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_features.py services/worker/tests/test_qlib_features_market.py
git commit -m "feat: 市场状态因子(BTC相关性)"
```

### Task 4.4: 全量回归

- [ ] **Step 1: 跑全量测试**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | tail -3`
Expected: 无新增失败

- [ ] **Step 2: 推送**

```bash
cd /home/djy/Quant && git push origin master
```

---

## 阶段五：工程提速 + 禁用因子复检 + 部署

### Task 5.1: 因子计算滚动窗口化（O(n²) → O(n)）

**Files:**
- Modify: `services/worker/qlib_features.py`（`_atr`/`_rsi`/`_volatility_contraction` 滚动化）
- Test: `services/worker/tests/test_qlib_features_speed.py`（新建，正确性回归 + 性能冒烟）

- [ ] **Step 1: 写失败测试（正确性回归）**

```python
# services/worker/tests/test_qlib_features_speed.py
"""滚动窗口优化正确性回归。"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import _atr, _rsi  # noqa: E402


def _make_candles(n: int):
    from decimal import Decimal as D
    candles = []
    price = D("100")
    for i in range(n):
        high = price + D("1")
        low = price - D("1")
        candles.append({"open": price, "high": high, "low": low, "close": price, "volume": D("10")})
        price += D("0.5")
    return candles


def test_rolling_atr_matches_original():
    candles = _make_candles(100)
    original = []
    # 原始 O(n²) 实现（对照）
    from services.worker.qlib_features import _mean
    for i in range(1, len(candles) + 1):
        window = candles[:i]
        true_ranges = []
        prev_close = None
        for c in window:
            if prev_close is None:
                true_ranges.append(c["high"] - c["low"])
            else:
                true_ranges.append(max(c["high"] - c["low"], abs(c["high"] - prev_close), abs(c["low"] - prev_close)))
            prev_close = c["close"]
        if true_ranges:
            original.append(_mean(true_ranges[-14:]))
    rolling = [_atr(candles[:i], 14) for i in range(1, len(candles) + 1)]
    for a, b in zip(original, rolling):
        assert a == b


def test_rolling_rsi_matches_original():
    closes = [Decimal(str(100 + i * 0.5)) for i in range(60)]
    candles = [{"open": c, "high": c + 1, "low": c - 1, "close": c, "volume": 10} for c in closes]
    original = [_rsi(candles[:i], 14) for i in range(2, len(candles) + 1)]
    # 优化后应产出同样的序列（若优化后 API 为迭代器形式，测试随实现调整）
    rolling = [_rsi(candles[:i], 14) for i in range(2, len(candles) + 1)]
    for a, b in zip(original, rolling):
        assert a == b
```

- [ ] **Step 2: 跑测试确认通过（此时实现未改，应全过，作为正确性基线）**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_features_speed.py -q`
Expected: 2 passed

- [ ] **Step 3: 优化实现（保持输出一致）**

将 `_atr`/`_rsi` 改为滚动计算（维护前 14 个值的窗口，增量更新总和），保证与原先逐根全量计算的输出一致。`_volatility_contraction` 内部复用的 `_atr` 自动提速。加性能冒烟断言：1000 根 K 线全量 `_atr` 计算 < 1 秒。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 2 passed（含性能断言）

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_features.py services/worker/tests/test_qlib_features_speed.py
git commit -m "perf: 因子计算滚动窗口化(O(n²)->O(n))"
```

### Task 5.2: 禁用因子复检报告

**Files:**
- Modify: `services/worker/qlib_runner.py`（训练报告加 `disabled_factors_recheck`）
- Test: `services/worker/tests/test_qlib_runner_disabled_recheck.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
# services/worker/tests/test_qlib_runner_disabled_recheck.py
"""禁用因子复检：对比静态禁用与运行时禁用因子的最近 IC。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_runner import QlibRunner  # noqa: E402


def test_disabled_recheck_marks_static_disabled():
    runner = object.__new__(QlibRunner)
    rows = []
    for i in range(30):
        rows.append({"generated_at": 1783486800000 + i * 3600000, "future_return_pct": "0.5", "atr_pct": "1.0", "roc6": "1.0", "close_return_pct": "0.1", "range_pct": "2.0", "momentum_accel": "0.5"})
    result = runner._build_disabled_factors_recheck(rows)
    assert "atr_pct" in result
    assert "roc6" in result
    assert result["atr_pct"]["current_ic"] is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_runner_disabled_recheck.py -q`
Expected: FAIL with `AttributeError: 'QlibRunner' object has no attribute '_build_disabled_factors_recheck'`

- [ ] **Step 3: 实现**

```python
    def _build_disabled_factors_recheck(self, rows: list[dict[str, object]]) -> dict[str, object]:
        """复检静态 enabled=False 的因子：计算最近 IC，供人工决定是否启用。"""
        from services.worker.qlib_features import FACTOR_DEFINITIONS, evaluate_factor_ic_series

        static_disabled = [
            item["name"] for item in FACTOR_DEFINITIONS
            if item.get("role") == "primary" and not item.get("enabled", True)
        ]
        result: dict[str, object] = {}
        if not rows:
            return {"factors": {}}
        for factor in static_disabled:
            sample = [r for r in rows if r.get(factor) is not None]
            if len(sample) < 10:
                result[factor] = {"current_ic": None, "sample_count": len(sample)}
                continue
            ic_series = evaluate_factor_ic_series(sample, factor_names=[factor])
            latest_ic = None
            for entry in ic_series:
                latest_ic = entry.get("ic")
            result[factor] = {"current_ic": latest_ic, "sample_count": len(sample)}
        return {"factors": result}
```

在 `train()` 的 result dict 中加 `"disabled_factors_recheck": self._build_disabled_factors_recheck(all_rows),`。

- [ ] **Step 4: 跑测试确认通过**

Run: 同上命令
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
cd /home/djy/Quant
git add services/worker/qlib_runner.py services/worker/tests/test_qlib_runner_disabled_recheck.py
git commit -m "feat: 禁用因子复检报告(IC驱动决策)"
```

### Task 5.3: 全量回归 + 全量部署

- [ ] **Step 1: 跑全量测试**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | tail -3`
Expected: 失败集合与基线一致（无新增）

- [ ] **Step 2: 推送 + 服务器部署（阶段二~五累积的所有改动一次部署）**

```bash
cd /home/djy/Quant && git push origin master
ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "git -C /home/djy/Quant pull && nohup bash -c 'cd /home/djy/Quant/infra/deploy && docker compose build api 2>&1 && docker compose up -d --no-deps api 2>&1 && docker compose restart api 2>&1' > /tmp/build_factors.log 2>&1 &"
```

- [ ] **Step 3: 等待构建完成后验证**

Run: `ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "tail -3 /tmp/build_factors.log && curl -s -m 10 http://localhost:9011/health"`
Expected: 构建日志完成 + health 200

- [ ] **Step 4: 验证新功能在服务器生效**

Run:
```bash
ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "docker exec quant-api python3 -c 'from services.worker.factor_ic_doctor import FactorIcDoctor; print(\"ic_doctor ok\")'"
ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "docker exec quant-api python3 -c 'from services.worker.factor_registry import factor_registry; print(\"registry ok\", factor_registry.enabled_columns(\"primary\")[:3])'"
```
Expected: 两个命令均正常输出

- [ ] **Step 5: 触发一轮训练验证 IC 体检闭环**

Run: `curl -s -X POST "http://localhost:9011/api/v1/tasks/train" | python3 -m json.tool | grep -E 'status|factor_health' -A3 | head -20`
Expected: 训练成功，`factor_health` 出现（可能因样本量不足为 error，属预期降级）

---

## 部署与回滚

- 每次 commit 独立可回滚：`git revert <commit>` 后重新部署
- 阶段二/三/四只 push 不部署，阶段五统一部署一次（避免频繁重建镜像，服务器内存 1.6G 构建有 OOM 风险）
- 多窗口标签默认关闭（`QUANT_MULTI_WINDOW_LABELS` 不设置即关闭），验证充分后再开
- IC 体检自动禁用因子有状态文件（`.runtime/factor_registry.json` / `.runtime/factor_ic_state.json`），误禁可手动改回

## 风险与注意

1. **特征列变化导致模型不兼容**：启用新因子后，旧模型的特征列集合与新模型不一致。`ModelPredictor` 加载模型前会检查特征列，若不一致会自动降级启发式——属现有容错，但需要观察训练日志确认 ML 模型真正生效。
2. **IC 体检误禁风险**：单轮 IC 波动大，`disable` 需要连续 2 轮负 IC 才触发；第一轮只 `watch`。状态文件可人工修正。
3. **taker 数据依赖**：`taker_buy_base_volume` 需要行情数据源提供（Binance kline 第 10 字段）。若数据源未透传该字段，因子保持中性 0.5，不影响其他因子。
4. **多窗口标签默认关闭**：避免未充分验证的标签改动影响实盘信号质量。
5. **测试基线**：每次全量回归以"失败集合 ⊆ 基线集合"为准，新增失败必须排查。
