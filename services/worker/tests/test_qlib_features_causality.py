"""特征因果性：未来追加行情不能改变过去特征，BTC 只能读取同步已见价格。"""
from decimal import Decimal
from statistics import mean, pstdev
import pytest
from services.worker.qlib_features import build_feature_rows, compute_btc_correlation, _zscore_series


def _candles(closes):
    """构造有足够历史且波动不恒定的同步 OHLC 样本。"""
    rows = []
    prior = closes[0]
    for index, close in enumerate(closes):
        rows.append(dict(open_time=index * 14400000, close_time=(index + 1) * 14400000 - 1,
                         open=prior, high=max(prior, close) * 1.02,
                         low=min(prior, close) * .98, close=close,
                         volume=1000 + index * 7))
        prior = close
    return rows


@pytest.mark.parametrize("normalization", ["fixed_4dp", "zscore_by_symbol"])
def test_appending_future_prices_does_not_change_historical_features(normalization):
    candles = _candles([100 + i * .6 + (i % 7 - 3) for i in range(90)])
    prefix = build_feature_rows("ETHUSDT", candles[:60], normalization_policy=normalization)
    full = build_feature_rows("ETHUSDT", candles, normalization_policy=normalization)
    assert prefix == full[:len(prefix)]


def test_online_zscore_matches_population_statistics_for_each_visible_prefix():
    values = [Decimal(v) for v in (1, 3, 8, 4, 17)]
    scores = _zscore_series(values)
    assert scores[0] == 0
    for index in range(1, len(values)):
        visible = [float(value) for value in values[:index + 1]]
        expected = (visible[-1] - mean(visible)) / pstdev(visible)
        assert float(scores[index]) == pytest.approx(expected)
    assert _zscore_series([Decimal(7)] * 5) == [Decimal(0)] * 5


def test_btc_features_only_use_current_visible_aligned_prices():
    coin = [100 + i + (i % 4) ** 2 for i in range(70)]
    btc = [200 + i * 3 + (i % 4) ** 2 for i in range(35)] + [1000 - i * 8 for i in range(35)]
    full = build_feature_rows("ETHUSDT", _candles(coin), btc_closes=btc)
    for stop in (1, 2, 3, 20, 35, 50, 70):
        visible = build_feature_rows("ETHUSDT", _candles(coin[:stop]), btc_closes=btc[:stop])
        assert visible == full[:stop]
        assert float(full[stop - 1]["btc_correlation"]) == pytest.approx(compute_btc_correlation(coin[:stop], btc[:stop]), abs=.00005)


def test_missing_current_btc_price_is_neutral_instead_of_reusing_old_alignment():
    closes = [100, 105, 102, 109, 104]
    rows = build_feature_rows("ETHUSDT", _candles(closes), btc_closes=[200, 210, 204])
    assert float(rows[2]["btc_correlation"]) == pytest.approx(1)
    assert rows[3]["btc_correlation"] == "0.0000"
    assert rows[4]["btc_correlation"] == "0.0000"
    assert compute_btc_correlation(closes, [200, 210, 204]) == 0


def test_dirty_coin_candle_does_not_shift_btc_alignment():
    closes = [100, 105, 102, 109, 104, 113]
    candles = _candles(closes)
    candles[1].pop("open")
    btc = [close * 2 for close in closes]
    rows = build_feature_rows("ETHUSDT", candles, btc_closes=btc)
    assert float(rows[-1]["btc_correlation"]) == pytest.approx(1)


def test_feature_engine_exposes_causality_version():
    from services.worker import qlib_features
    assert qlib_features.FEATURE_ENGINE_VERSION == "causal_features_v2"
