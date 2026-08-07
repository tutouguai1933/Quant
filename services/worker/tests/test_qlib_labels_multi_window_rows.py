"""多窗口标签行生成。"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_labels import build_multi_window_label_rows  # noqa: E402


def _make_candles(n: int, close_start: int = 100, step: float = 1.0):
    candles = []
    for i in range(n):
        close = close_start + i * step
        candles.append({
            "open_time": 1000 * (i + 1),
            "close_time": 1000 * (i + 2),
            "open": str(close),
            "high": str(close),
            "low": str(close),
            "close": str(close),
            "volume": "10",
        })
    return candles


def test_multi_window_rows_format_matches_build_label_rows():
    candles = _make_candles(40)
    rows = build_multi_window_label_rows("TESTUSDT", candles, target_return_pct=Decimal("5"), stop_return_pct=Decimal("-5"))
    assert rows
    required = {"generated_at", "future_return_pct", "label", "holding_window", "is_trainable"}
    assert required.issubset(rows[0].keys())
    for row in rows:
        assert row["label"] in ("buy", "sell", "watch")
        assert isinstance(row["is_trainable"], bool)


def test_multi_window_rows_uptrend_labels_buy():
    # 单调上涨：早期 K 线在未来 6 根内涨幅 ≥5% → buy
    candles = _make_candles(30, close_start=100, step=2.0)  # 100,102,...158
    rows = build_multi_window_label_rows("TESTUSDT", candles, target_return_pct=Decimal("5"), stop_return_pct=Decimal("-5"))
    buy_rows = [r for r in rows if r["label"] == "buy"]
    assert buy_rows, "单调上涨应产生 buy 样本"


def test_multi_window_rows_last_rows_watch():
    # 末尾 K 线没有足够未来数据 → watch 或 is_trainable=False
    candles = _make_candles(12)
    rows = build_multi_window_label_rows("TESTUSDT", candles, target_return_pct=Decimal("5"), stop_return_pct=Decimal("-5"))
    assert rows
    assert rows[-1]["label"] == "watch"
