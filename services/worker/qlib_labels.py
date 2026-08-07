"""Qlib 最小标签定义。

这个文件负责把 K 线样本转成稳定的训练标签结构。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from statistics import median


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


# ---------------------------------------------------------------------------
# 新数据模型
# ---------------------------------------------------------------------------


@dataclass
class LabelSpec:
    """标签构建参数。

    LabelSpec() 默认值与现有 build_label_rows 行为对齐：
    target_pct=1.0, stop_pct=-1.0, window_bars=18（4h×18≈3天），
    mode="earliest_hit", neutral_threshold_pct=0.0（无过滤）。
    """

    target_pct: float = 1.0
    stop_pct: float = -1.0
    window_bars: int = 18  # 4h x 18 = 72h ≈ 3天
    mode: str = "earliest_hit"
    neutral_threshold_pct: float = 0.0


@dataclass
class LabeledRow:
    """单条标签结果。"""

    open_time: int
    future_return_pct: float
    label: str  # buy / sell / watch
    is_trainable: bool


@dataclass
class LabelQuality:
    """标签质量报告。"""

    total: int
    buy_ratio: float
    sell_ratio: float
    watch_ratio: float
    trainable_ratio: float


# ---------------------------------------------------------------------------
# LabelEngine
# ---------------------------------------------------------------------------


class LabelEngine:
    """把 K 线样本转成标签的引擎。

    支持三种模式：earliest_hit（默认）、close_only、window_majority。
    新增 neutral_threshold_pct 过滤和 window_bars 参数。
    """

    _SUPPORTED_MODES = ("earliest_hit", "close_only", "window_majority")

    def build(self, candles: list[dict], spec: LabelSpec) -> list[LabeledRow]:
        """根据 spec 从 K 线构建标签行。

        window_bars 决定向前看多少根 bar（从 index+1 开始）。
        neutral_threshold_pct > 0 时，|收益| <= 该值的样本标为 watch。
        """
        target_dec = Decimal(str(spec.target_pct))
        stop_dec = Decimal(str(spec.stop_pct))
        neutral_dec = Decimal(str(spec.neutral_threshold_pct))
        window_bars = max(1, int(spec.window_bars))
        mode = spec.mode if spec.mode in self._SUPPORTED_MODES else "earliest_hit"

        normalized = [_normalize_candle(item) for item in candles]
        valid_candles = [item for item in normalized if item is not None]
        if not valid_candles:
            return []

        rows: list[LabeledRow] = []
        for index, candle in enumerate(valid_candles):
            future_window = _slice_future_window_single(
                candles=valid_candles,
                index=index,
                window_bars=window_bars,
            )
            if not future_window or candle["close"] == 0:
                future_return = Decimal("0")
                label = "watch"
                is_trainable = False
            else:
                future_return, label = _classify_window_label(
                    entry_close=candle["close"],
                    future_window=future_window,
                    label_mode=mode,
                    trigger_basis="close",
                    target_return_pct=target_dec,
                    stop_return_pct=stop_dec,
                )
                is_trainable = True

            # neutral 过滤：|收益| <= neutral_threshold_pct 归为 watch
            if is_trainable and neutral_dec > 0:
                if abs(future_return) <= neutral_dec:
                    label = "watch"

            rows.append(
                LabeledRow(
                    open_time=int(candle["close_time"]),
                    future_return_pct=float(future_return) if is_trainable else 0.0,
                    label=label,
                    is_trainable=is_trainable,
                )
            )
        return rows

    def quality_report(self, rows: list[LabeledRow]) -> LabelQuality:
        """从标签行生成质量报告。"""
        if not rows:
            return LabelQuality(total=0, buy_ratio=0.0, sell_ratio=0.0, watch_ratio=0.0, trainable_ratio=0.0)
        total = len(rows)
        buy_count = sum(1 for r in rows if r.label == "buy")
        sell_count = sum(1 for r in rows if r.label == "sell")
        watch_count = sum(1 for r in rows if r.label == "watch")
        trainable_count = sum(1 for r in rows if r.is_trainable)
        return LabelQuality(
            total=total,
            buy_ratio=buy_count / total,
            sell_ratio=sell_count / total,
            watch_ratio=watch_count / total,
            trainable_ratio=trainable_count / total,
        )


# ---------------------------------------------------------------------------
# build_label_rows（兼容旧签名，内部保留 range-window 语义）
# ---------------------------------------------------------------------------


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
    """把 K 线样本转成标签行。

    签名完全兼容旧版，输出格式不变。
    内部保留 range-window 语义（min/max window days -> bar range）。
    """

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
        future_window = _slice_future_window_range(
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


# ---------------------------------------------------------------------------
# 多窗口标签（用于多窗口加权训练）
# ---------------------------------------------------------------------------


def _classify_single_window(
    close_now: Decimal,
    closes_ahead: list[Decimal],
    target_pct: Decimal,
    stop_pct: Decimal,
) -> str:
    """按单窗口判定 buy/sell/watch。

    窗口内每根 close 视为潜在入场价，当前 close 为出场价，
    按时间顺序先触达 target（盈利）为 buy，先触达 stop（亏损）为 sell。
    """

    for close in closes_ahead:
        if not close:
            continue
        change = (close_now - close) / close * 100
        if change >= target_pct:
            return "buy"
        if change <= stop_pct:
            return "sell"
    return "watch"


def build_multi_window_labels(
    candles: list[dict[str, object]],
    *,
    windows: tuple[int, ...] = (6, 12, 18),
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
        # 观察窗口 = 最后一根往前 window 根（不含最后一根本身）
        ahead = closes[-window - 1 : -1]
        result[window] = _classify_single_window(now, ahead, target, stop)
    return result


def build_multi_window_label_rows(
    symbol: str,
    candles: list[dict[str, object]],
    *,
    windows: tuple[int, ...] = (6, 12, 18),
    target_return_pct: Decimal = Decimal("1"),
    stop_return_pct: Decimal = Decimal("-1"),
    holding_window_label: str = "multi-window",
) -> list[dict[str, object]]:
    """对每根 K 线按多个未来窗口分别判定标签，多数票合并。

    与 build_label_rows 输出格式一致。标签无泄漏：每个窗口都是未来窗口。
    多数票规则：buy 票最多→buy；否则 sell 票最多→sell；否则 watch。
    平票时取较长窗口的结果。
    """

    normalized_target = target_return_pct if isinstance(target_return_pct, Decimal) else Decimal(str(target_return_pct or "1"))
    normalized_stop = stop_return_pct if isinstance(stop_return_pct, Decimal) else Decimal(str(stop_return_pct or "-1"))
    normalized = [_normalize_candle(item) for item in candles]
    valid_candles = [item for item in normalized if item is not None]
    if not valid_candles:
        return []

    rows: list[dict[str, object]] = []
    for index, candle in enumerate(valid_candles):
        if candle["close"] == 0:
            rows.append(
                {
                    "symbol": symbol.strip().upper(),
                    "generated_at": int(candle["close_time"]),
                    "future_return_pct": None,
                    "label": "watch",
                    "holding_window": holding_window_label,
                    "is_trainable": False,
                }
            )
            continue

        window_results: list[tuple[int, Decimal, str]] = []
        for window in windows:
            future_window = _slice_future_window_single(
                candles=valid_candles,
                index=index,
                window_bars=int(window),
            )
            if not future_window:
                continue
            future_return, label = _classify_window_label(
                entry_close=candle["close"],
                future_window=future_window,
                label_mode="earliest_hit",
                trigger_basis="close",
                target_return_pct=normalized_target,
                stop_return_pct=normalized_stop,
            )
            window_results.append((int(window), future_return, label))

        if not window_results:
            rows.append(
                {
                    "symbol": symbol.strip().upper(),
                    "generated_at": int(candle["close_time"]),
                    "future_return_pct": None,
                    "label": "watch",
                    "holding_window": holding_window_label,
                    "is_trainable": False,
                }
            )
            continue

        buy_votes = [item for item in window_results if item[2] == "buy"]
        sell_votes = [item for item in window_results if item[2] == "sell"]
        buy_count = len(buy_votes)
        sell_count = len(sell_votes)
        watch_count = len(window_results) - buy_count - sell_count
        largest_window = max(item[0] for item in window_results)
        largest_result = next(item for item in window_results if item[0] == largest_window)

        # 多数票合并：buy/sell 严格最多优先，平票（buy==sell）取较长窗口的结果
        if buy_count > sell_count and buy_count > watch_count:
            chosen_label = "buy"
        elif sell_count > buy_count and sell_count > watch_count:
            chosen_label = "sell"
        elif buy_count == sell_count:
            chosen_label = largest_result[2]
        else:
            chosen_label = "watch"

        # 票选结果对应的未来收益：buy 取最早 buy 窗口，sell 取最早 sell 窗口，watch 取最大窗口
        if chosen_label == "buy":
            chosen_return = min(buy_votes, key=lambda item: item[0])[1]
        elif chosen_label == "sell":
            chosen_return = min(sell_votes, key=lambda item: item[0])[1]
        else:
            chosen_return = largest_result[1]

        rows.append(
            {
                "symbol": symbol.strip().upper(),
                "generated_at": int(candle["close_time"]),
                "future_return_pct": _format_decimal(chosen_return),
                "label": chosen_label,
                "holding_window": holding_window_label,
                "is_trainable": True,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# 波动率调整收益
# ---------------------------------------------------------------------------


def volatility_adjusted_return(return_pct: float, atr_pct: float) -> float:
    """波动率调整收益：return_pct / atr_pct。

    用于标签构造：把收益按波动率归一，低波动期的小波动不会被放大成假信号。
    atr_pct <= 0 时返回 0（无法归一，放弃该样本）。
    """
    if atr_pct is None or float(atr_pct) <= 0:
        return 0.0
    return float(return_pct) / float(atr_pct)


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------


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


def _slice_future_window_range(
    *,
    candles: list[dict[str, Decimal | int]],
    index: int,
    min_window_bars: int,
    max_window_bars: int,
) -> list[dict[str, Decimal | int]]:
    """截取未来 1-3 天观察窗口（range 语义，兼容旧版）。"""

    start_index = index + min_window_bars
    end_index = index + max_window_bars
    if start_index >= len(candles) or end_index >= len(candles):
        return []
    return candles[start_index : end_index + 1]


def _slice_future_window_single(
    *,
    candles: list[dict[str, Decimal | int]],
    index: int,
    window_bars: int,
) -> list[dict[str, Decimal | int]]:
    """截取未来观察窗口（单一 window_bars 语义，从 index+1 开始）。"""

    start_index = index + 1
    end_index = index + window_bars
    if start_index >= len(candles):
        return []
    if end_index >= len(candles):
        end_index = len(candles) - 1
    if start_index > end_index:
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
    """按观察窗口内的命中结果生成标签。"""

    future_returns = [_return_pct(entry_close=entry_close, value=candle["close"]) for candle in future_window]
    trigger_high_returns = [_return_pct(entry_close=entry_close, value=candle["high"]) for candle in future_window]
    trigger_low_returns = [_return_pct(entry_close=entry_close, value=candle["low"]) for candle in future_window]

    def _buy_hit_index(values: list[Decimal]) -> int | None:
        return next((idx for idx, value in enumerate(values) if value >= target_return_pct), None)

    def _sell_hit_index(values: list[Decimal]) -> int | None:
        return next((idx for idx, value in enumerate(values) if value <= stop_return_pct), None)

    def _pick_buy_trigger(idx: int) -> Decimal:
        return trigger_high_returns[idx] if trigger_basis == "high_low" else future_returns[idx]

    def _pick_sell_trigger(idx: int) -> Decimal:
        return trigger_low_returns[idx] if trigger_basis == "high_low" else future_returns[idx]

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
