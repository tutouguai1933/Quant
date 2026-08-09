"""标签对比实验核心函数测试。"""

import json
import tempfile
from pathlib import Path

from scripts.run_label_sweep import load_dataset_rows, split_time_ordered


def test_load_dataset_rows_merges_three_row_kinds() -> None:
    """加载 dataset cache 时合并 training/validation/testing 三类行。"""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = {
            "training_rows": [{"symbol": "BTCUSDT", "generated_at": 1}],
            "validation_rows": [{"symbol": "BTCUSDT", "generated_at": 2}],
            "testing_rows": [{"symbol": "BTCUSDT", "generated_at": 3}],
        }
        (Path(tmp) / "cache_1.json").write_text(json.dumps(bundle), encoding="utf-8")
        rows = load_dataset_rows(tmp)
        assert len(rows) == 3


def test_split_time_ordered_respects_timestamp() -> None:
    """切分严格按时间：训练全部早于验证。"""
    rows = [{"symbol": "A", "generated_at": i * 10} for i in range(10)]
    train, valid = split_time_ordered(rows, train_ratio=0.75)
    assert len(train) == 7 and len(valid) == 3
    assert all(int(r["generated_at"]) < int(v["generated_at"]) for r in train for v in valid)


def test_build_labeled_rows_merges_features_and_labels() -> None:
    """K 线→特征+标签合并：行数与 K 线对齐、含 future_return_pct。"""
    import json as _json
    from decimal import Decimal

    from scripts.run_label_sweep import build_labeled_rows

    with tempfile.TemporaryDirectory() as tmp:
        # 构造 300 根 4h K 线（带简单趋势，保证有标签）
        bars = []
        base_open = 1712016000000
        step = 4 * 3600 * 1000
        price = 100.0
        for i in range(300):
            close = price + 0.5 + (i % 5) * 0.1
            bars.append({
                "open_time": base_open + i * step,
                "close_time": base_open + i * step + step - 1,
                "open": f"{price:.2f}",
                "high": f"{max(price, close) + 1.0:.2f}",
                "low": f"{min(price, close) - 1.0:.2f}",
                "close": f"{close:.2f}",
                "volume": f"{1000 + i * 10:.2f}",
            })
            price = close
        (Path(tmp) / "BTCUSDT_4h.jsonl").write_text(
            "\n".join(_json.dumps(b) for b in bars), encoding="utf-8"
        )

        rows = build_labeled_rows(
            kline_dir=tmp,
            symbols=["BTCUSDT"],
            interval="4h",
            label_config={"name": "t", "label_mode": "earliest_hit", "target": "1", "stop": "-1", "min_days": 1, "max_days": 3},
        )
        assert len(rows) > 100
        assert all("future_return_pct" in r for r in rows)
        assert all(float(r["future_return_pct"]) != 0 for r in rows if r["future_return_pct"] is not None)
