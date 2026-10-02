"""RSI 入场可卖约束及真实成交风险回归，隔离本地缺失的交易框架。"""
import importlib.util
import sys
import types
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_DOWN
from pathlib import Path
from types import SimpleNamespace
import pytest

@pytest.fixture
def strategy(monkeypatch):
    # 仅模拟不可用框架，实际执行仓库策略代码。
    class Parameter:
        def __init__(self, *args, default=None, **kwargs):
            self.value = default
    modules = {name: types.ModuleType(name) for name in (
        "freqtrade", "freqtrade.strategy", "freqtrade.persistence", "pandas", "talib", "talib.abstract")}
    modules["freqtrade.strategy"].IStrategy = object
    modules["freqtrade.strategy"].IntParameter = Parameter
    modules["freqtrade.strategy"].DecimalParameter = Parameter
    modules["freqtrade.strategy"].informative = lambda *args: lambda f: f
    modules["pandas"].DataFrame = object
    closed = []
    modules["freqtrade.persistence"].Trade = SimpleNamespace(get_trades_proxy=lambda **kwargs: closed)
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    path = Path(__file__).resolve().parents[3] / "infra/freqtrade/user_data/strategies/EnhancedStrategy.py"
    spec = importlib.util.spec_from_file_location("rsi_strategy_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    obj = module.EnhancedStrategy()
    obj.config = {"trading_mode": "spot"}
    market = {"active": True, "spot": True, "taker": .001, "maker": .001,
              "limits": {"cost": {"min": 5}, "amount": {"min": .001}}, "precision": {"amount": .001}}
    def precision(pair, amount):
        # 模拟交易所按数量步长向下截断。
        return float((Decimal(str(amount)) / Decimal(".001")).to_integral_value(rounding=ROUND_DOWN) * Decimal(".001"))
    exchange = SimpleNamespace(amount_to_precision=precision)
    row = {"rsi": 25, "volume": 100, "volume_sma_hourly": 100}
    class Frame:
        def __len__(self):
            return 1
        @property
        def iloc(self):
            return [row]
    obj.dp = SimpleNamespace(market=lambda pair: market, _exchange=exchange, get_analyzed_dataframe=lambda *args: (Frame(), None))
    obj.wallets = SimpleNamespace(get_total_stake_amount=lambda: 100)
    return obj, closed, market

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)

def enter(obj, amount=.009, rate=807.29):
    # 调用策略真实入场回调。
    return obj.confirm_trade_entry("BNB/USDT", "limit", amount, rate, "GTC", NOW, None, "long")

def trade(id, profit, when=NOW):
    # 建立具有净成交收益的平仓事实。
    return SimpleNamespace(id=id, is_open=False, close_date_utc=when, close_profit_abs=profit, strategy="EnhancedStrategy")

def test_fee_step_and_stop_price_reject_dust_entry(strategy):
    obj, _, _ = strategy
    assert enter(obj, .007) is False

def test_exit_feasible_entry_allowed(strategy):
    obj, _, _ = strategy
    assert enter(obj, .009) is True

def test_missing_market_rules_fail_closed(strategy):
    obj, _, market = strategy
    market["limits"] = {}
    assert enter(obj) is False

def test_insufficient_budget_is_not_overridden(strategy):
    obj, _, _ = strategy
    assert obj.custom_stake_amount("BNB/USDT", NOW, 807.29, 4, 5, 4, 1, None, "long") == 0

def test_no_minimum_topup_of_weak_signal_budget(strategy):
    obj, _, _ = strategy
    assert obj.custom_stake_amount("BNB/USDT", NOW, 807.29, 6, 5, 6, 1, None, "long") == 0

def test_failed_repeated_exit_does_not_count_losses(strategy):
    obj, _, _ = strategy
    item = SimpleNamespace(calc_profit=lambda rate: -.2, stake_amount=6)
    assert enter(obj)
    for _ in range(8):
        assert obj.confirm_trade_exit("BNB/USDT", item, "limit", .006, 780, "GTC", "stop_loss", NOW)
    assert enter(obj)

def test_small_actual_loss_not_fixed_eight_percent(strategy):
    obj, closed, _ = strategy
    closed.append(trade(1, -.2))
    assert enter(obj)

def test_daily_net_account_loss_blocks_after_restart(strategy):
    obj, closed, _ = strategy
    closed.extend([trade(1, -3), trade(2, -3)])
    assert enter(obj) is False

def test_profit_offsets_daily_net_loss(strategy):
    obj, closed, _ = strategy
    closed.extend([trade(1, -6), trade(2, 6)])
    assert enter(obj)

def test_duplicate_closed_fact_does_not_count_twice(strategy):
    obj, closed, _ = strategy
    closed.extend([trade(1, -3), trade(1, -3)])
    assert enter(obj)

def test_consecutive_losses_reset_on_new_utc_day(strategy):
    obj, closed, _ = strategy
    closed.extend(trade(i, -.01, NOW - timedelta(days=1, minutes=i)) for i in range(5))
    assert enter(obj)

def test_other_strategy_history_does_not_pollute_rsi_risk(strategy):
    obj, closed, _ = strategy
    item = trade(1, -50)
    item.strategy = "OtherStrategy"
    closed.append(item)
    assert enter(obj)

def test_stop_price_not_only_entry_notional(strategy):
    obj, _, market = strategy
    market["taker"] = market["maker"] = 0
    assert enter(obj, .007, 750) is False

def test_missing_fee_rejects_entry(strategy):
    obj, _, market = strategy
    market.pop("maker")
    market.pop("taker")
    assert enter(obj) is False

def test_larger_configured_fee_is_used(strategy):
    obj, _, _ = strategy
    obj.config["fee"] = .15
    assert enter(obj, .008) is False

def test_market_lot_step_applies_to_stop_exit(strategy):
    obj, _, market = strategy
    market["info"] = {"filters": [{"filterType": "MARKET_LOT_SIZE", "minQty": "0.01", "maxQty": "1000", "stepSize": "0.01"}]}
    assert enter(obj, .009) is False

def test_no_candle_path_still_checks_budget(strategy):
    obj, _, _ = strategy
    obj.dp.get_analyzed_dataframe = lambda *args: (None, None)
    assert obj.custom_stake_amount("BNB/USDT", NOW, 807.29, 4, 5, 4, 1, None, "long") == 0

def test_account_equity_changes_loss_limit(strategy):
    obj, closed, _ = strategy
    obj.wallets.get_total_stake_amount = lambda: 5
    closed.append(trade(1, -.3))
    assert enter(obj) is False

def test_history_unavailable_fails_closed(strategy, monkeypatch):
    obj, _, _ = strategy
    def unavailable(**kwargs):
        # 模拟框架成交记录读取失败。
        raise RuntimeError("unavailable")
    monkeypatch.setattr(sys.modules["freqtrade.persistence"].Trade, "get_trades_proxy", unavailable)
    assert enter(obj) is False

def test_consecutive_losses_survive_same_day_restart(strategy):
    obj, closed, _ = strategy
    closed.extend(trade(i, -.01, NOW - timedelta(minutes=i)) for i in range(5))
    assert enter(obj) is False
