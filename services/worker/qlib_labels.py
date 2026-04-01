"""Qlib 最小标签定义。

这个文件负责把 K 线样本转成稳定的训练标签结构。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


LABEL_COLUMNS = (
    "symbol",
    "generated_at",
    "future_return_pct",
    "direction",
    "is_trainable",
)


def build_label_rows(symbol: str, candles: list[dict[str, object]]) -> list[dict[str, object]]:
    """把 K 线样本转成标签行。"""

    normalized = [_normalize_candle(item) for item in candles]
    valid_candles = [item for item in normalized if item is not None]
    if not valid_candles:
        return []

    rows: list[dict[str, object]] = []
    for index, candle in enumerate(valid_candles):
        next_close = valid_candles[index + 1]["close"] if index + 1 < len(valid_candles) else None
        if next_close is None or candle["close"] == 0:
            future_return = None
            direction = "unknown"
            is_trainable = False
        else:
            future_return = ((next_close - candle["close"]) / candle["close"]) * Decimal("100")
            direction = _classify_direction(future_return)
            is_trainable = True

        rows.append(
            {
                "symbol": symbol.strip().upper(),
                "generated_at": int(candle["close_time"]),
                "future_return_pct": None if future_return is None else _format_decimal(future_return),
                "direction": direction,
                "is_trainable": is_trainable,
            }
        )
    return rows


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


def _classify_direction(value: Decimal) -> str:
    """把未来收益转成方向枚举。"""

    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _format_decimal(value: Decimal) -> str:
    """把数值统一成字符串。"""

    normalized = value.quantize(Decimal("0.0001"))
    return format(normalized, "f")
