"""Qlib 研究数据集整理。

这个文件负责把 1h / 4h K 线整理成带时间切分的数据包。
"""

from __future__ import annotations

from dataclasses import dataclass, field


DATA_STATE_NAMES = ("raw", "cleaned", "feature-ready")

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

    last_error: RuntimeError | None = None
    for timeframe, candles in candidates:
        try:
            return _build_dataset_bundle_for_candles(
                symbol=standardized_symbol,
                timeframe=timeframe,
                candles=candles,
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
) -> DatasetBundle:
    """把单个周期的 K 线整理成可切分的数据包。"""

    feature_rows = build_feature_rows(symbol, candles)
    label_rows = build_label_rows(symbol, candles)
    merged_rows = _merge_feature_and_label_rows(feature_rows, label_rows)
    if len(merged_rows) < 3:
        raise RuntimeError("样本不足以切成训练/验证/测试三段")
    training_rows, validation_rows, testing_rows = _split_rows(merged_rows)
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


def _split_rows(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    """把样本按时间顺序切成训练、验证和测试三段。"""

    if not rows:
        raise RuntimeError("研究数据集中没有可切分的样本")
    if len(rows) < 3:
        raise RuntimeError("样本不足以切成训练/验证/测试三段")

    train_end = max(1, int(len(rows) * 0.6))
    valid_end = max(train_end + 1, int(len(rows) * 0.8))
    if valid_end >= len(rows):
        valid_end = len(rows) - 1
    return rows[:train_end], rows[train_end:valid_end], rows[valid_end:]


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
