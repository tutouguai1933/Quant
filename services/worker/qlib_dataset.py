"""Qlib 研究数据集整理。

这个文件负责把 1h / 4h K 线整理成带时间切分的数据包。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


DATA_STATE_NAMES = ("raw", "cleaned", "feature-ready")

from services.worker.qlib_config import get_runtime_hint
from services.worker.qlib_features import build_feature_rows
from services.worker.qlib_labels import build_label_rows


@dataclass(slots=True)
class DatasetBundle:
    """研究数据集包。"""

    symbol: str
    timeframe: str
    training_rows: list[dict[str, object]]
    validation_rows: list[dict[str, object]]
    testing_rows: list[dict[str, object]]
    data_states: dict[str, dict[str, object]] = field(default_factory=dict)
    cache: dict[str, object] = field(default_factory=dict)


def build_dataset_bundle(
    *,
    symbol: str,
    candles_1h: list[dict[str, object]],
    candles_4h: list[dict[str, object]],
    label_mode: str = "earliest_hit",
    outlier_policy: str = "clip",
    normalization_policy: str = "fixed_4dp",
    missing_policy: str = "neutral_fill",
    label_target_pct=None,
    label_stop_pct=None,
    min_window_days: int = 1,
    max_window_days: int = 3,
    holding_window_label: str = "1-3d",
    lookback_days: int | None = None,
    window_mode: str = "rolling",
    start_date: str = "",
    end_date: str = "",
    train_split_ratio: object | None = None,
    validation_split_ratio: object | None = None,
    test_split_ratio: object | None = None,
) -> DatasetBundle:
    """把输入 K 线整理成训练、验证、测试三段数据。"""

    standardized_symbol = _normalize_symbol(symbol)
    candidates = []
    if candles_4h:
        candidates.append(("4h", candles_4h))
    if candles_1h:
        candidates.append(("1h", candles_1h))
    if not candidates:
        raise RuntimeError("没有可用的研究 K 线样本")
    split_ratios = _resolve_split_ratios(
        train_split_ratio=train_split_ratio,
        validation_split_ratio=validation_split_ratio,
        test_split_ratio=test_split_ratio,
    )
    normalized_lookback_days = _resolve_lookback_days(lookback_days)

    last_error: RuntimeError | None = None
    for timeframe, candles in candidates:
        filtered_candles = _filter_candles(
            candles,
            lookback_days=normalized_lookback_days,
            window_mode=window_mode,
            start_date=start_date,
            end_date=end_date,
        )
        try:
            return _build_dataset_bundle_for_candles(
                symbol=standardized_symbol,
                timeframe=timeframe,
                candles=filtered_candles,
                label_mode=label_mode,
                outlier_policy=outlier_policy,
                normalization_policy=normalization_policy,
                missing_policy=missing_policy,
                label_target_pct=label_target_pct,
                label_stop_pct=label_stop_pct,
                min_window_days=min_window_days,
                max_window_days=max_window_days,
                holding_window_label=holding_window_label,
                split_ratios=split_ratios,
            )
        except RuntimeError as exc:
            if str(exc) != "样本不足以切成训练/验证/测试三段":
                raise
            last_error = exc

    if last_error is not None:
        raise last_error
    raise RuntimeError("样本不足以切成训练/验证/测试三段")


def _build_dataset_bundle_for_candles(
    *,
    symbol: str,
    timeframe: str,
    candles: list[dict[str, object]],
    label_mode: str = "earliest_hit",
    outlier_policy: str = "clip",
    normalization_policy: str = "fixed_4dp",
    missing_policy: str = "neutral_fill",
    label_target_pct=None,
    label_stop_pct=None,
    min_window_days: int = 1,
    max_window_days: int = 3,
    holding_window_label: str = "1-3d",
    split_ratios: tuple[Decimal, Decimal, Decimal] = (Decimal("0.6"), Decimal("0.2"), Decimal("0.2")),
) -> DatasetBundle:
    """把单个周期的 K 线整理成可切分的数据包。"""

    feature_rows = build_feature_rows(
        symbol,
        candles,
        outlier_policy=outlier_policy,
        normalization_policy=normalization_policy,
        missing_policy=missing_policy,
    )
    label_rows = build_label_rows(
        symbol,
        candles,
        label_mode=label_mode,
        target_return_pct=label_target_pct,
        stop_return_pct=label_stop_pct,
        min_window_days=min_window_days,
        max_window_days=max_window_days,
        holding_window_label=holding_window_label,
    )
    merged_rows = _merge_feature_and_label_rows(feature_rows, label_rows)
    if len(merged_rows) < 3:
        raise RuntimeError("样本不足以切成训练/验证/测试三段")
    training_rows, validation_rows, testing_rows = _split_rows(merged_rows, split_ratios=split_ratios)
    return DatasetBundle(
        symbol=symbol,
        timeframe=timeframe,
        training_rows=training_rows,
        validation_rows=validation_rows,
        testing_rows=testing_rows,
        data_states=_build_data_states(
            raw_count=len(candles),
            cleaned_count=min(len(feature_rows), len(label_rows)),
            feature_ready_count=len(merged_rows),
        ),
    )


def _merge_feature_and_label_rows(
    feature_rows: list[dict[str, object]],
    label_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """按时间把特征和标签合并。"""

    label_rows_by_time = {
        int(label_row["generated_at"]): label_row
        for label_row in label_rows
        if label_row.get("generated_at") is not None
    }
    merged_rows: list[dict[str, object]] = []
    for feature_row in feature_rows:
        label_row = label_rows_by_time.get(int(feature_row["generated_at"]))
        if label_row is None:
            continue
        if not label_row["is_trainable"]:
            continue
        merged_rows.append({**feature_row, **label_row})
    merged_rows.sort(key=lambda item: int(item["generated_at"]))
    return merged_rows


def _split_rows(
    rows: list[dict[str, object]],
    *,
    split_ratios: tuple[Decimal, Decimal, Decimal],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """把样本按时间顺序切成训练、验证和测试三段。"""

    if not rows:
        raise RuntimeError("研究数据集中没有可切分的样本")
    if len(rows) < 3:
        raise RuntimeError("样本不足以切成训练/验证/测试三段")

    train_ratio, validation_ratio, _ = split_ratios
    train_end = max(1, int(len(rows) * float(train_ratio)))
    valid_end = max(train_end + 1, int(len(rows) * float(train_ratio + validation_ratio)))
    if valid_end >= len(rows):
        valid_end = len(rows) - 1
    return rows[:train_end], rows[train_end:valid_end], rows[valid_end:]


def _resolve_split_ratios(
    *,
    train_split_ratio: object | None,
    validation_split_ratio: object | None,
    test_split_ratio: object | None,
) -> tuple[Decimal, Decimal, Decimal]:
    """解析训练/验证/测试切分比例，并统一归一化。"""

    default_train = Decimal("0.6")
    default_validation = Decimal("0.2")
    default_test = Decimal("0.2")
    train_ratio = _read_split_ratio(
        direct_value=train_split_ratio,
        runtime_name="train_split_ratio",
        default=default_train,
    )
    validation_ratio = _read_split_ratio(
        direct_value=validation_split_ratio,
        runtime_name="validation_split_ratio",
        default=default_validation,
    )
    test_ratio = _read_split_ratio(
        direct_value=test_split_ratio,
        runtime_name="test_split_ratio",
        default=default_test,
    )
    total = train_ratio + validation_ratio + test_ratio
    if total <= Decimal("0"):
        return default_train, default_validation, default_test
    return (
        train_ratio / total,
        validation_ratio / total,
        test_ratio / total,
    )


def _resolve_lookback_days(direct_value: object | None) -> int:
    """读取数据窗口天数。"""

    raw_value: object | None = direct_value
    if raw_value is None:
        raw_value = get_runtime_hint("lookback_days", consume=True)
    try:
        parsed = int(str(raw_value))
    except (TypeError, ValueError):
        parsed = 30
    return max(parsed, 7)


def _filter_candles(
    candles: list[dict[str, object]],
    *,
    lookback_days: int,
    window_mode: str,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    """按当前窗口模式裁剪 K 线样本。"""

    if window_mode == "fixed" and (start_date or end_date):
        return _filter_candles_by_fixed_window(candles, start_date=start_date, end_date=end_date)
    return _filter_candles_by_lookback_days(candles, lookback_days=lookback_days)


def _filter_candles_by_lookback_days(candles: list[dict[str, object]], *, lookback_days: int) -> list[dict[str, object]]:
    """按回看天数过滤 K 线样本。"""

    if not candles:
        return []
    latest_close_time = _read_candle_timestamp(candles[-1], "close_time")
    if latest_close_time <= 0:
        return list(candles)
    earliest_allowed_open = latest_close_time - (lookback_days * 24 * 60 * 60 * 1000)
    filtered = [
        candle
        for candle in candles
        if _read_candle_timestamp(candle, "open_time") >= earliest_allowed_open
    ]
    return filtered or list(candles)


def _filter_candles_by_fixed_window(
    candles: list[dict[str, object]],
    *,
    start_date: str,
    end_date: str,
) -> list[dict[str, object]]:
    """按固定日期窗口裁剪 K 线样本。"""

    if not candles:
        return []
    start_ms = _date_to_timestamp(start_date, end_of_day=False)
    end_ms = _date_to_timestamp(end_date, end_of_day=True)
    filtered = []
    for candle in candles:
        open_time = _read_candle_timestamp(candle, "open_time")
        close_time = _read_candle_timestamp(candle, "close_time")
        if start_ms and close_time < start_ms:
            continue
        if end_ms and open_time > end_ms:
            continue
        filtered.append(candle)
    return filtered or list(candles)


def _date_to_timestamp(value: str, *, end_of_day: bool) -> int:
    """把 YYYY-MM-DD 转成毫秒时间戳。"""

    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        base = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    if end_of_day:
        base = base + timedelta(days=1) - timedelta(milliseconds=1)
    return int(base.timestamp() * 1000)


def _read_candle_timestamp(candle: dict[str, object], key: str) -> int:
    """读取 K 线时间戳。"""

    try:
        return int(candle.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _read_split_ratio(*, direct_value: object | None, runtime_name: str, default: Decimal) -> Decimal:
    """读取单个切分比例。"""

    raw_value: object | None = direct_value
    if raw_value is None:
        raw_value = get_runtime_hint(runtime_name, consume=True)
    try:
        parsed = Decimal(str(raw_value))
    except (InvalidOperation, TypeError, ValueError):
        parsed = default
    if parsed <= Decimal("0"):
        return default
    return parsed


def _normalize_symbol(symbol: str) -> str:
    """把币种代码统一成标准格式。"""

    return symbol.strip().upper()


def _build_data_states(*, raw_count: int, cleaned_count: int, feature_ready_count: int) -> dict[str, dict[str, object]]:
    """构造统一数据状态说明。"""

    symbol_count = 1
    return {
        "raw": {
            "state": "ready" if raw_count > 0 else "empty",
            "symbol_count": symbol_count,
            "row_count": raw_count,
            "dropped_count": max(raw_count - cleaned_count, 0),
        },
        "cleaned": {
            "state": "ready" if cleaned_count > 0 else "empty",
            "symbol_count": symbol_count,
            "row_count": cleaned_count,
            "dropped_count": max(cleaned_count - feature_ready_count, 0),
        },
        "feature-ready": {
            "state": "ready" if feature_ready_count > 0 else "empty",
            "symbol_count": symbol_count,
            "row_count": feature_ready_count,
            "dropped_count": 0,
        },
    }


def serialize_dataset_bundle(bundle: DatasetBundle) -> dict[str, object]:
    """把数据集包序列化成可缓存结构。"""

    return {
        "symbol": bundle.symbol,
        "timeframe": bundle.timeframe,
        "training_rows": bundle.training_rows,
        "validation_rows": bundle.validation_rows,
        "testing_rows": bundle.testing_rows,
        "data_states": bundle.data_states,
        "cache": bundle.cache,
    }


def deserialize_dataset_bundle(payload: dict[str, object]) -> DatasetBundle:
    """从缓存结构恢复数据集包。"""

    return DatasetBundle(
        symbol=str(payload.get("symbol", "")),
        timeframe=str(payload.get("timeframe", "")),
        training_rows=list(payload.get("training_rows") or []),
        validation_rows=list(payload.get("validation_rows") or []),
        testing_rows=list(payload.get("testing_rows") or []),
        data_states=dict(payload.get("data_states") or {}),
        cache=dict(payload.get("cache") or {}),
    )
