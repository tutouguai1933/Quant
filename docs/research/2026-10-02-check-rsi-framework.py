"""服务器现有 Freqtrade 镜像兼容检查；只用合成数据，不连接交易所或生产数据库。"""
import importlib.util
import inspect
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ccxt import TICK_SIZE
from freqtrade.data.dataprovider import DataProvider
from freqtrade.exchange import Exchange
from freqtrade.enums import CandleType, RunMode
from freqtrade.persistence import LocalTrade, Trade
from freqtrade.wallets import Wallets


def check_framework(strategy_path):
    """检查实际框架签名、数量精度和策略回调的合成路径。"""
    assert "is_open" in inspect.signature(Trade.get_trades_proxy).parameters
    assert "pair" in inspect.signature(DataProvider.market).parameters
    assert "amount" in inspect.signature(Exchange.amount_to_precision).parameters
    assert callable(Wallets.get_total_stake_amount)
    spec = importlib.util.spec_from_file_location("rsi_framework_check", strategy_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # informative 装饰器初始化必需 candle_type_def；这里只构造公开合成配置。
    obj = module.EnhancedStrategy({
        "trading_mode": "spot", "stake_currency": "USDT", "timeframe": "1h",
        "dry_run": True, "runmode": RunMode.DRY_RUN, "candle_type_def": CandleType.SPOT,
    })
    market = {"active": True, "taker": .001, "maker": .001,
              "limits": {"cost": {"min": 5}, "amount": {"min": .001}},
              "precision": {"amount": .001}}
    precision_context = SimpleNamespace(get_precision_amount=lambda pair: .001, precisionMode=TICK_SIZE)
    def precision(pair, amount):
        # 执行真实框架精度函数，不构造交易所连接。
        return Exchange.amount_to_precision(precision_context, pair, amount)
    obj.dp = SimpleNamespace(market=lambda pair: market, _exchange=SimpleNamespace(amount_to_precision=precision))
    obj.wallets = SimpleNamespace(get_total_stake_amount=lambda: 100)
    now = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
    assert not obj._entry_can_exit("BNB/USDT", .007, 807.29)
    assert obj._entry_can_exit("BNB/USDT", .009, 807.29)
    closed = LocalTrade(id=1, is_open=False, strategy="EnhancedStrategy",
                        close_date=now, close_profit_abs=-.2)
    with patch.object(Trade, "get_trades_proxy", return_value=[closed, closed]):
        assert obj._realized_risk_allows_entry(now)
    closed.close_profit_abs = -6
    with patch.object(Trade, "get_trades_proxy", return_value=[closed]):
        assert not obj._realized_risk_allows_entry(now)
    print("框架兼容检查：5通过/0失败（仅合成数据）")


if __name__ == "__main__":
    # 脚本从标准输入执行时，使用服务器容器已有策略挂载路径。
    check_framework(Path("/freqtrade/user_data/strategies/EnhancedStrategy.py"))
