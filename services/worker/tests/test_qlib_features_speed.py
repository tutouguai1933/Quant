"""滚动窗口优化正确性回归。"""
from __future__ import annotations

import sys
import time
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_features import _atr, _rsi  # noqa: E402


def _make_candles(n: int):
    candles = []
    price = Decimal("100")
    for i in range(n):
        high = price + Decimal("1")
        low = price - Decimal("1")
        candles.append({"open": price, "high": high, "low": low, "close": price, "volume": Decimal("10")})
        price += Decimal("0.5")
    return candles


def _make_candles_full(n: int, step_hours: int = 4):
    """构造带时间字段的完整 K 线（4h 周期对应 atr/rsi period=14）。"""
    candles = []
    price = Decimal("100")
    base_open_time = 1712016000000
    step_ms = step_hours * 60 * 60 * 1000
    for i in range(n):
        high = price + Decimal("2")
        low = price - Decimal("1.5")
        candles.append({
            "open_time": base_open_time + i * step_ms,
            "open": price,
            "high": high,
            "low": low,
            "close": price,
            "volume": Decimal("10"),
            "close_time": base_open_time + (i + 1) * step_ms - 1,
        })
        price += Decimal("0.5")
    return candles


def _atr_original(candles, period):
    """原始 O(n²) 语义参照：从第 1 根到第 i 根逐步计算。"""
    from services.worker.qlib_features import _mean
    true_ranges = []
    prev_close = None
    for c in candles:
        if prev_close is None:
            true_ranges.append(c["high"] - c["low"])
        else:
            true_ranges.append(max(c["high"] - c["low"], abs(c["high"] - prev_close), abs(c["low"] - prev_close)))
        prev_close = c["close"]
    if not true_ranges:
        return Decimal("0")
    return _mean(true_ranges[-period:])


def _rsi_original(candles, period):
    """原始 RSI 语义参照（简化平均法，与现有 _rsi 一致）。"""
    from services.worker.qlib_features import _mean
    if len(candles) < 2:
        return Decimal("50")
    gains = []
    losses = []
    for prev, cur in zip(candles, candles[1:]):
        change = cur["close"] - prev["close"]
        if change > 0:
            gains.append(change)
        elif change < 0:
            losses.append(-change)
    avg_gain = _mean(gains[-period:])
    avg_loss = _mean(losses[-period:])
    if avg_gain == 0 and avg_loss == 0:
        return Decimal("50")
    if avg_loss == 0:
        return Decimal("100")
    rs = avg_gain / avg_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + rs))


def test_rolling_atr_matches_original():
    candles = _make_candles(100)
    for i in range(1, len(candles) + 1):
        window = candles[:i]
        if len(window) < 2:
            continue
        assert _atr(window, 14) == _atr_original(window, 14), f"ATR 不一致 at i={i}"


def test_rolling_rsi_matches_original():
    candles = _make_candles(100)
    for i in range(2, len(candles) + 1):
        window = candles[:i]
        assert _rsi(window, 14) == _rsi_original(window, 14), f"RSI 不一致 at i={i}"


def test_rolling_matches_original_with_random_data():
    """随机波动数据下滚动实现与原实现仍完全一致（防止窗口截错也能通过）。"""
    import random

    random.seed(42)
    candles = []
    price = Decimal("100")
    for i in range(120):
        # 随机振幅的 K 线，制造波动
        move = Decimal(str(random.uniform(-3, 3)))
        high = price + Decimal(str(abs(random.uniform(0.5, 2))))
        low = price - Decimal(str(abs(random.uniform(0.5, 2))))
        candles.append({"open": price, "high": high, "low": low, "close": price + move, "volume": Decimal("10")})
        price += move
    for i in range(1, len(candles) + 1):
        window = candles[:i]
        if len(window) >= 2:
            assert _atr(window, 14) == _atr_original(window, 14), f"ATR 不一致 at i={i}"
        if len(window) >= 2:
            assert _rsi(window, 14) == _rsi_original(window, 14), f"RSI 不一致 at i={i}"


def test_rolling_atr_speed_smoke():
    """性能冒烟：1000 根 K 线逐根算 ATR 应在 1 秒内。"""
    candles = _make_candles(1000)
    start = time.monotonic()
    for i in range(1, len(candles) + 1):
        _atr(candles[:i], 14)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"ATR 逐根计算耗时 {elapsed:.2f}s，超过 1s 上限"


def test_build_feature_rows_matches_per_call_reference():
    """整条流水线输出与逐根调用公共函数的旧实现完全一致（4h 周期：atr/rsi period=14）。"""
    from services.worker.qlib_features import (
        _format_decimal,
        _normalize_feature_decimal,
        _volatility_contraction,
        build_feature_rows,
    )

    candles = _make_candles_full(150)
    rows = build_feature_rows("TEST", candles)
    assert len(rows) == 150
    for index, row in enumerate(rows):
        prefix = candles[: index + 1]
        rsi_old = _rsi(prefix, 14)
        vc_old = _volatility_contraction(prefix, 14)
        assert row["rsi14"] == _format_decimal(
            _normalize_feature_decimal("rsi14", rsi_old, outlier_policy="clip")
        ), f"rsi14 不一致 at row={index}"
        assert row["volatility_contraction"] == _format_decimal(
            _normalize_feature_decimal("volatility_contraction", vc_old, outlier_policy="clip")
        ), f"volatility_contraction 不一致 at row={index}"


def test_build_feature_rows_speed_smoke():
    """整条流水线性能冒烟：1000 根 K 线应在 10 秒内（优化前约 111 秒）。"""
    from services.worker.qlib_features import build_feature_rows

    candles = _make_candles_full(1000)
    start = time.monotonic()
    rows = build_feature_rows("TEST", candles)
    elapsed = time.monotonic() - start
    assert elapsed < 10.0, f"build_feature_rows 1000 根耗时 {elapsed:.2f}s，超过 10s 上限"
