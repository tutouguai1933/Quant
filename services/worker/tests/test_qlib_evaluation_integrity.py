"""验证 ML 评估只消费模型预测、真实价格和隔离后的时间样本。"""
from decimal import Decimal
import pytest

from services.worker.qlib_backtest import run_backtest
from services.worker.qlib_dataset import _split_rows
from services.worker.qlib_walk_forward import WalkForwardConfig, WalkForwardValidator


def bars(symbol="BTCUSDT", prices=(100, 100, 110), score=0.9):
    """构造信号收盘后才能交易的真实价格路径。"""
    return [dict(symbol=symbol, generated_at=i * 1000 + 999,
                 open_time=i * 1000, close_time=i * 1000 + 999,
                 open=p, high=p, low=p, close=p, prediction_score=score,
                 label="buy", future_return_pct="999")
            for i, p in enumerate(prices)]


def test_missing_predictions_is_unavailable_and_has_no_fake_metrics():
    rows = bars()
    for row in rows:
        row.pop("prediction_score")
    result = run_backtest(rows=rows, holding_window="1-3d")
    assert result["evaluation_status"] == "unavailable"
    assert result["metrics"] == {}


def test_future_labels_do_not_change_price_replay():
    rows = bars(score=0.1)
    first = run_backtest(rows=rows, holding_window="1-3d")
    for row in rows:
        row.update(label="sell", future_return_pct="-999")
    second = run_backtest(rows=rows, holding_window="1-3d")
    assert first["metrics"] == second["metrics"]
    assert first["metrics"]["trades_count"] == "0"


def test_trade_enters_next_open_and_returns_nav_not_label_sum():
    result = run_backtest(rows=bars(), holding_window="1-3d")
    assert result["evaluation_version"] == "ml_price_replay_v2"
    assert result["metrics"]["total_return_pct"] == "8.0000"
    assert result["series"]["performance"][-1]["strategy_nav"] == pytest.approx(1.08)


def test_multicoin_shared_budget_and_independent_prices():
    rows = bars("BTCUSDT", (100, 100, 104)) + bars("ETHUSDT", (100, 100, 96))
    result = run_backtest(rows=rows, holding_window="1-3d")
    assert float(result["metrics"]["total_return_pct"]) == pytest.approx(0)
    assert result["metrics"]["trades_count"] == "2"


def test_auc_ties_receive_half_credit_and_are_order_invariant():
    compute = WalkForwardValidator._compute_auc
    assert compute([0.5, 0.5], [1, 0]) == 0.5
    assert compute([0.5, 0.5], [0, 1]) == 0.5
    with pytest.raises(ValueError):
        compute([0.5], [0, 1])


def test_walk_forward_gap_counts_shared_timestamps_and_purges_labels():
    rows = [dict(symbol=s, generated_at=i, label_end_at=i + 4,
                 future_return_pct=1) for i in range(100) for s in ("BTC", "ETH")]
    config = WalkForwardConfig(n_folds=2, min_train_bars=10, gap_bars=3)
    folds = WalkForwardValidator().split(rows, config)
    assert folds
    for fold in folds:
        assert max(r["label_end_at"] for r in fold.train) < fold.test_start_ts
        assert fold.test_start_ts - max(r["generated_at"] for r in fold.train) > 3
        assert all(sum(r["generated_at"] == t for r in fold.test) == 2
                   for t in {r["generated_at"] for r in fold.test})


def test_dataset_split_groups_timestamps_and_purges_label_maturity():
    rows = [dict(symbol=s, generated_at=i, label_end_at=i + 3)
            for i in range(20) for s in ("BTC", "ETH", "SOL")]
    train, valid, test = _split_rows(rows, split_ratios=(Decimal(".6"), Decimal(".2"), Decimal(".2")))
    assert max(r["label_end_at"] for r in train) < min(r["generated_at"] for r in valid)
    assert max(r["label_end_at"] for r in valid) < min(r["generated_at"] for r in test)
    assert all(sum(r["generated_at"] == t for r in segment) == 3
               for segment in (train, valid, test) for t in {r["generated_at"] for r in segment})


def test_walk_forward_uses_model_positive_threshold():
    rows = [dict(generated_at=i, label_end_at=i, future_return_pct=1 if i % 2 else 3) for i in range(100)]
    report = WalkForwardValidator().run(
        lambda train, test: [0.1 if r["future_return_pct"] == 1 else .9 for r in test],
        rows, WalkForwardConfig(n_folds=2, min_train_bars=10, gap_bars=0, label_threshold=2))
    assert report.summary["mean"]["auc"] == 1


def test_oos_final_test_is_only_predicted(monkeypatch):
    import numpy as np
    from types import SimpleNamespace
    from scripts import run_oos_benchmark as benchmark
    from services.worker.ml.trainer import ModelTrainer
    calls = []
    train, valid, test = ([dict(future_return_pct=1, close_return_pct=1)],
                          [dict(future_return_pct=-1, close_return_pct=2)],
                          [dict(future_return_pct=-1, close_return_pct=3),
                           dict(future_return_pct=3, close_return_pct=4)])
    def fake_train(self, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(metrics={"val_auc": .6, "train_auc": .7},
                               model=SimpleNamespace(predict_proba=lambda X: np.array([[.9, .1], [.1, .9]])))
    monkeypatch.setattr(ModelTrainer, "train", fake_train)
    result = benchmark.evaluate_oos(train, valid, test)
    assert len(calls) == 1
    assert calls[0]["training_rows"] is train
    assert calls[0]["validation_rows"] is valid
    assert result["test_auc"] == 1


def test_single_walk_forward_fold_still_has_unseen_test_rows():
    rows = [dict(generated_at=i, label_end_at=i) for i in range(40)]
    folds = WalkForwardValidator().split(rows, WalkForwardConfig(n_folds=1, min_train_bars=10, gap_bars=3))
    assert len(folds) == 1
    assert folds[0].test_start_ts - max(r["generated_at"] for r in folds[0].train) > 3


def test_negative_gap_is_rejected_instead_of_extending_train_into_test():
    rows = [dict(generated_at=i, label_end_at=i) for i in range(40)]
    with pytest.raises(ValueError):
        WalkForwardValidator().split(rows, WalkForwardConfig(min_train_bars=10, gap_bars=-1))


def test_single_position_chooses_top_model_score_at_shared_timestamp():
    rows = bars("BTCUSDT", (100, 100, 96), score=.6) + bars("ETHUSDT", (100, 100, 104), score=.9)
    result = run_backtest(rows=rows, holding_window="1-3d", max_positions=1)
    assert float(result["metrics"]["total_return_pct"]) == pytest.approx(4)
    assert result["trades"][0]["symbol"] == "ETHUSDT"


def test_dataset_keeps_unpurged_rows_for_one_global_multicoin_split():
    from services.worker.qlib_dataset import build_dataset_bundle, serialize_dataset_bundle, deserialize_dataset_bundle
    from services.worker.tests.test_qlib_dataset import _sample_candles
    bundle = build_dataset_bundle(symbol="BTCUSDT", candles_1h=[], candles_4h=_sample_candles(180, step_hours=4))
    assert len(bundle.all_rows) == 162
    assert len(bundle.all_rows) > len(bundle.training_rows) + len(bundle.validation_rows) + len(bundle.testing_rows)
    assert deserialize_dataset_bundle(serialize_dataset_bundle(bundle)).all_rows == bundle.all_rows
