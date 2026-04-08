"""Qlib 最小标签定义。

这个文件负责把 K 线样本转成稳定的训练标签结构。
"""

from __future__ import annotations

from statistics import median
from decimal import Decimal, InvalidOperation


DAY_MS = 24 * 60 * 60 * 1000
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 3

LABEL_COLUMNS = (
    "symbol",
    "generated_at",
    "future_return_pct",
    "label",
    "holding_window",
    "is_trainable",
)


def build_label_rows(
    symbol: str,
    candles: list[dict[str, object]],
    *,
    label_mode: str = "earliest_hit",
    trigger_basis: str = "close",
    target_return_pct: Decimal = Decimal("1"),
    stop_return_pct: Decimal = Decimal("-1"),
    min_window_days: int = MIN_WINDOW_DAYS,
    max_window_days: int = MAX_WINDOW_DAYS,
    holding_window_label: str = "1-3d",
) -> list[dict[str, object]]:
    """把 K 线样本转成标签行。"""

    normalized_target = target_return_pct if isinstance(target_return_pct, Decimal) else Decimal(str(target_return_pct or "1"))
    normalized_stop = stop_return_pct if isinstance(stop_return_pct, Decimal) else Decimal(str(stop_return_pct or "-1"))
    normalized = [_normalize_candle(item) for item in candles]
    valid_candles = [item for item in normalized if item is not None]
    if not valid_candles:
        return []

    bar_step_ms = _infer_bar_step_ms(candles)
    normalized_min_days = max(1, int(min_window_days))
    normalized_max_days = max(normalized_min_days, int(max_window_days))
    min_window_bars = _window_bars(bar_step_ms, normalized_min_days)
    max_window_bars = _window_bars(bar_step_ms, normalized_max_days)

    rows: list[dict[str, object]] = []
    for index, candle in enumerate(valid_candles):
        future_window = _slice_future_window(
            candles=valid_candles,
            index=index,
            min_window_bars=min_window_bars,
            max_window_bars=max_window_bars,
        )
        if not future_window or candle["close"] == 0:
            future_return = None
            label = "watch"
            is_trainable = False
        else:
            future_return, label = _classify_window_label(
                entry_close=candle["close"],
                future_window=future_window,
                label_mode=label_mode,
                trigger_basis=trigger_basis,
                target_return_pct=normalized_target,
                stop_return_pct=normalized_stop,
            )
            is_trainable = True

        rows.append(
            {
                "symbol": symbol.strip().upper(),
                "generated_at": int(candle["close_time"]),
                "future_return_pct": None if future_return is None else _format_decimal(future_return),
                "label": label,
                "holding_window": holding_window_label,
                "is_trainable": is_trainable,
            }
        )
    return rows


def _infer_bar_step_ms(candles: list[dict[str, object]]) -> int:
    """从 K 线时间推导单根 bar 的间隔。"""

    close_times: list[int] = []
    for candle in candles:
        try:
            close_times.append(int(candle["close_time"]))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue

    deltas = [current - previous for previous, current in zip(close_times, close_times[1:]) if current > previous]
    if not deltas:
        return 4 * 60 * 60 * 1000
    return int(median(deltas))


def _window_bars(bar_step_ms: int, days: int) -> int:
    """把天数换算成对应的 bar 数。"""

    if bar_step_ms <= 0:
        return 0
    return max(1, (days * DAY_MS) // bar_step_ms)


def _slice_future_window(
    *,
    candles: list[dict[str, Decimal | int]],
    index: int,
    min_window_bars: int,
    max_window_bars: int,
) -> list[dict[str, Decimal | int]]:
    """截取未来 1-3 天观察窗口。"""

    start_index = index + min_window_bars
    end_index = index + max_window_bars
    if start_index >= len(candles) or end_index >= len(candles):
        return []
    return candles[start_index : end_index + 1]


def _classify_window_label(
    *,
    entry_close: Decimal,
    future_window: list[dict[str, Decimal | int]],
    label_mode: str,
    trigger_basis: str,
    target_return_pct: Decimal,
    stop_return_pct: Decimal,
) -> tuple[Decimal, str]:
    """按 1-3 天窗口内的最早命中结果生成标签。"""

    future_returns = [_return_pct(entry_close=entry_close, value=candle["close"]) for candle in future_window]
    trigger_high_returns = [_return_pct(entry_close=entry_close, value=candle["high"]) for candle in future_window]
    trigger_low_returns = [_return_pct(entry_close=entry_close, value=candle["low"]) for candle in future_window]

    def _buy_hit_index(values: list[Decimal]) -> int | None:
        return next((index for index, value in enumerate(values) if value >= target_return_pct), None)

    def _sell_hit_index(values: list[Decimal]) -> int | None:
        return next((index for index, value in enumerate(values) if value <= stop_return_pct), None)

    def _pick_buy_trigger(index: int) -> Decimal:
        return trigger_high_returns[index] if trigger_basis == "high_low" else future_returns[index]

    def _pick_sell_trigger(index: int) -> Decimal:
        return trigger_low_returns[index] if trigger_basis == "high_low" else future_returns[index]

    if label_mode == "window_majority":
        checkpoints = []
        total_bars = len(future_window)
        for step in range(1, total_bars + 1):
            candidate_returns = future_returns[:step]
            candidate_high_returns = trigger_high_returns[:step]
            candidate_low_returns = trigger_low_returns[:step]
            buy_hit = _buy_hit_index(candidate_high_returns if trigger_basis == "high_low" else candidate_returns)
            sell_hit = _sell_hit_index(candidate_low_returns if trigger_basis == "high_low" else candidate_returns)
            if buy_hit is not None and (sell_hit is None or buy_hit <= sell_hit):
                checkpoints.append(("buy", _pick_buy_trigger(buy_hit)))
                continue
            if sell_hit is not None:
                checkpoints.append(("sell", _pick_sell_trigger(sell_hit)))
                continue
            checkpoints.append(("watch", candidate_returns[-1]))
        buy_votes = [value for label, value in checkpoints if label == "buy"]
        sell_votes = [value for label, value in checkpoints if label == "sell"]
        watch_votes = [value for label, value in checkpoints if label == "watch"]
        if len(buy_votes) > len(sell_votes) and len(buy_votes) >= len(watch_votes):
            return buy_votes[0], "buy"
        if len(sell_votes) > len(buy_votes) and len(sell_votes) >= len(watch_votes):
            return sell_votes[0], "sell"
        if watch_votes:
            return watch_votes[-1], "watch"
        final_return = future_returns[-1]
        if final_return >= target_return_pct:
            return final_return, "buy"
        if final_return <= stop_return_pct:
            return final_return, "sell"
        return final_return, "watch"
    if label_mode == "close_only":
        final_return = future_returns[-1]
        if final_return >= target_return_pct:
            return final_return, "buy"
        if final_return <= stop_return_pct:
            return final_return, "sell"
        return final_return, "watch"
    first_buy_index = _buy_hit_index(trigger_high_returns if trigger_basis == "high_low" else future_returns)
    first_sell_index = _sell_hit_index(trigger_low_returns if trigger_basis == "high_low" else future_returns)

    if first_buy_index is not None and (first_sell_index is None or first_buy_index <= first_sell_index):
        return _pick_buy_trigger(first_buy_index), "buy"
    if first_sell_index is not None:
        return _pick_sell_trigger(first_sell_index), "sell"
    return future_returns[-1], "watch"


def _return_pct(*, entry_close: Decimal, value: Decimal) -> Decimal:
    """按入场价计算未来收益百分比。"""

    return ((value - entry_close) / entry_close) * Decimal("100")


def _normalize_candle(candle: dict[str, object]) -> dict[str, Decimal | int] | None:
    """把输入 K 线整理成可计算结构。

    这里刻意要求和特征层相同的关键字段，避免脏 K 线只在一侧被过滤后造成训练标签错位。
    """

    try:
        return {
            "open": Decimal(str(candle["open"])),
            "high": Decimal(str(candle["high"])),
            "low": Decimal(str(candle["low"])),
            "close": Decimal(str(candle["close"])),
            "volume": Decimal(str(candle["volume"])),
            "close_time": int(candle["close_time"]),
        }
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def _classify_label(value: Decimal) -> str:
    """把未来收益转成择时标签。"""

    if value >= Decimal("1"):
        return "buy"
    if value <= Decimal("-1"):
        return "sell"
    return "watch"


def _format_decimal(value: Decimal) -> str:
    """把数值统一成字符串。"""

    normalized = value.quantize(Decimal("0.0001"))
    return format(normalized, "f")
