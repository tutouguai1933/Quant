"""验证自动化模型的实时特征、生产准入与概率语义，不改变 RSI 策略。"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from services.worker.qlib_config import load_qlib_config
from services.worker.qlib_runner import QlibRunner
from services.worker.qlib_runner import _prune_directory


NOW = datetime(2026, 10, 2, 4, tzinfo=timezone.utc)


def candles(end=NOW, count=140):
    """构造结束于指定时刻的完整四小时行情。"""
    rows = []
    for i in range(count):
        close_time = int((end - timedelta(hours=4 * (count - 1 - i))).timestamp() * 1000) - 1
        price = 100 + i * .1
        rows.append({"open_time": close_time - 14400000 + 1, "close_time": close_time,
                     "open": str(price), "high": str(price + 1), "low": str(price - 1),
                     "close": str(price + .1), "volume": "100"})
    return rows


def runner(tmp_path):
    """准备研究结果，避免测试实际训练或调用网络。"""
    config = load_qlib_config(env={"QUANT_QLIB_RUNTIME_ROOT": str(tmp_path), "QUANT_QLIB_HOLDING_WINDOW_MIN_DAYS": "2", "QUANT_QLIB_HOLDING_WINDOW_MAX_DAYS": "5"})
    instance = QlibRunner(config=config)
    instance._ensure_runtime_directories()
    instance._write_json(config.paths.latest_training_path, {"model_version": "experiment", "metrics": {"model_type": "heuristic"}})
    return instance


def test_live_features_do_not_wait_for_future_labels(tmp_path):
    """报告必须使用最新收盘特征，不能使用五天前的测试行。"""
    instance = runner(tmp_path)
    rows = candles() + candles(end=NOW + timedelta(hours=4), count=1)
    with mock.patch("services.worker.qlib_runner._utc_now", return_value=NOW):
        result = instance.infer({"BTCUSDT": rows})
    assert result["signals"][0]["feature_asof"] == datetime.fromtimestamp(candles()[-1]["close_time"] / 1000, timezone.utc).isoformat()


def test_stale_market_is_excluded_from_live_signals(tmp_path):
    """过期市场不能生成当下方向或参与平均分。"""
    instance = runner(tmp_path)
    with mock.patch("services.worker.qlib_runner._utc_now", return_value=NOW):
        result = instance.infer({"MATICUSDT": candles(end=NOW - timedelta(days=750))})
    assert result["signals"] == []
    assert any("MATICUSDT" in str(w) for w in result["warnings"])


def test_rolling_training_does_not_mix_stale_market(tmp_path):
    """当下滚动训练不能混入已经多年未更新的资产。"""
    instance = runner(tmp_path)
    with mock.patch("services.worker.qlib_runner._utc_now", return_value=NOW):
        bundle = instance._build_training_bundle({"BTCUSDT": candles(count=300), "MATICUSDT": candles(end=NOW - timedelta(days=750), count=300)})
    assert set(bundle.symbol_bundles) == {"BTCUSDT"}


def test_first_bad_model_is_not_promoted(tmp_path):
    """没有生产模型时，也不能自动提升验证低于随机的模型。"""
    instance = runner(tmp_path)
    registry = mock.Mock()
    registry.get_production_model.return_value = None
    decision = instance._evaluate_and_promote(registry, "bad", {"val_auc": .447, "val_f1": 0})
    assert decision["promoted"] is False
    registry.promote.assert_not_called()


def test_low_upside_probability_is_not_short_signal(tmp_path):
    """不上涨超过阈值的概率不能直接变成下跌概率。"""
    assert runner(tmp_path)._classify_signal(.32) == "flat"


def test_unapproved_experiment_cannot_enter_execution(tmp_path):
    """没有合格生产模型时可研究，但候选不能通过执行准入。"""
    instance = runner(tmp_path)
    with mock.patch("services.worker.qlib_runner._utc_now", return_value=NOW):
        result = instance.infer({"BTCUSDT": candles()})
    assert result["model_admission"]["passed"] is False
    for candidate in result["candidates"]["items"]:
        assert candidate["allowed_to_live"] is False
        assert candidate["allowed_to_dry_run"] is False


def test_production_artifact_is_not_pruned_with_old_experiments(tmp_path):
    """新实验不能清理仍由生产模型引用的文件。"""
    import os
    production = tmp_path / "production.txt"
    production.write_text("production", encoding="utf-8")
    os.utime(production, (1, 1))
    for i in range(3):
        (tmp_path / f"experiment-{i}.txt").write_text("experiment", encoding="utf-8")
    _prune_directory(tmp_path, keep=2, label="测试产物", protected_paths={production})
    assert production.is_file()


def test_probability_target_is_part_of_production_protocol(tmp_path):
    """持有窗口和标签变化必须改变协议，不能把旧概率用于新目标。"""
    from dataclasses import replace
    instance = runner(tmp_path)
    original = instance._model_input_protocol(timeframes=["4h"])
    changed = QlibRunner(config=replace(instance._config, holding_window_max_days=3, label_mode="earliest_hit"))
    from types import SimpleNamespace
    record = SimpleNamespace(stage="production", version_id="prod", metrics={"val_auc": .7, "val_f1": .6},
                             training_context={"input_protocol": original, "evaluation_version": "ml_price_replay_v2", "evaluation_available": True})
    with mock.patch("services.worker.model_registry.get_model_registry") as registry:
        registry.return_value.get_production_model.return_value = record
        assert instance._resolve_production_model()[1]["passed"] is True
        assert changed._resolve_production_model()[1]["passed"] is False


def test_legacy_backtest_is_unavailable_without_rewriting_history():
    """读旧报告不能继续展示未来信息造成的收益，也不能改写原始历史文件。"""
    import services.worker.qlib_live_policy as policy
    artifact = {"model_version": "old", "backtest": {"metrics": {"net_return_pct": "12715.8965"}, "series": {"performance": [1, 2]}}}
    result = policy.hide_legacy_evaluation(artifact)
    assert result["backtest"]["evaluation_status"] == "unavailable"
    assert result["backtest"]["metrics"] == {}
    assert artifact["backtest"]["metrics"]["net_return_pct"] == "12715.8965"


def test_live_fixed_window_matches_training_history(tmp_path):
    """固定日期实时特征必须按训练相同规则裁历史，不能使用窗外价格。"""
    from dataclasses import replace
    from services.worker.qlib_dataset import _filter_candles_by_fixed_window
    instance = runner(tmp_path)
    instance._config = replace(instance._config, window_mode="fixed", start_date="2026-09-20", end_date="2026-09-28")
    rows = candles()
    with mock.patch("services.worker.qlib_runner._utc_now", return_value=NOW):
        actual = instance._prepare_research_candles(rows)
    expected = _filter_candles_by_fixed_window(rows, start_date="2026-09-20", end_date="2026-09-28")
    assert actual == expected


def test_feature_engine_and_history_window_are_versioned(tmp_path):
    """预处理实现及历史起点变化必须失效旧模型与数据集缓存。"""
    from dataclasses import replace
    from services.worker.qlib_features import FEATURE_ENGINE_VERSION
    instance = runner(tmp_path)
    protocol = instance._model_input_protocol()
    assert protocol["feature_engine_version"] == FEATURE_ENGINE_VERSION
    assert protocol["lookback_days"] == instance._config.lookback_days
    before = instance._build_dataset_cache_key(symbol="BTCUSDT", candles_1h=[], candles_4h=[], candles_15m=[])
    with mock.patch("services.worker.qlib_runner.FEATURE_ENGINE_VERSION", "future_protocol"):
        after = instance._build_dataset_cache_key(symbol="BTCUSDT", candles_1h=[], candles_4h=[], candles_15m=[])
    assert before != after
