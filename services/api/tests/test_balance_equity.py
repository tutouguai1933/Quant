"""验证完整账户权益，避免零头截断及把部分账户当总额。"""
from unittest.mock import Mock
from decimal import Decimal
import pytest

from services.api.app.services.account_sync_service import AccountSyncService


def test_nonzero_assets_are_filtered_before_limit():
    """先过滤无余额资产，再应用显示数量限制。"""
    client = Mock()
    client.get_balances.return_value = [{"asset": f"ZERO{i}", "free": "0", "locked": "0"} for i in range(105)] + [{"asset": "DOGE", "free": ".855", "locked": "0"}]
    service = AccountSyncService(client=client, market_client=Mock())
    service._annotate_balances = lambda rows, settings: rows
    assert service.list_balances(limit=100)[0]["asset"] == "DOGE"


def service():
    """构造两个账户及价格快照，不调用外部网络。"""
    from services.api.app.services.balance_equity_service import BalanceEquityService
    account = Mock()
    account.get_spot_account.return_value = {"balances": [
        {"asset": "USDT", "free": "4", "locked": "1"},
        {"asset": "BNB", "free": ".01", "locked": "0"},
        {"asset": "DOGE", "free": ".855", "locked": "0"},
        {"asset": "SHIB", "free": ".1", "locked": "0"}]}
    account.get_futures_account.return_value = {"totalWalletBalance": "9", "totalUnrealizedProfit": ".4", "totalMarginBalance": "9.4"}
    market = Mock()
    market.get_prices.return_value = [{"symbol": "BNBUSDT", "price": "700"}, {"symbol": "DOGEUSDT", "price": ".1"}, {"symbol": "SHIBUSDT", "price": ".00001"}]
    return BalanceEquityService(account_client=account, market_client=market), account, market


def test_equity_includes_locked_dust_and_futures_pnl():
    """总额含冻结余额、零头及合约浮盈，不能重复加入浮盈。"""
    instance, _, _ = service()
    result = instance.get_summary()
    assert result["status"] == "available"
    assert Decimal(result["spot_equity"]) == Decimal("12.085501")
    assert Decimal(result["futures_equity"]) == Decimal("9.4")
    assert Decimal(result["total_equity"]) == Decimal("21.485501")
    assert len(result["assets"]) == 4


def test_unpriced_asset_does_not_produce_partial_total():
    """未取得价格时不把持有资产估作0。"""
    instance, _, market = service()
    market.get_prices.return_value = []
    result = instance.get_summary()
    assert result["total_equity"] is None
    assert result["spot_equity"] is None
    assert result["futures_equity"] == "9.4"
    assert result["status"] == "unavailable"


@pytest.mark.parametrize("failed", ["get_spot_account", "get_futures_account"])
def test_failed_wallet_never_becomes_zero_total(failed):
    """账户读取失败不显示另一账户为合计，错误提示不暴露请求详情。"""
    instance, account, _ = service()
    getattr(account, failed).side_effect = RuntimeError("secret_signed_url")
    result = instance.get_summary()
    assert result["total_equity"] is None
    assert "secret_signed_url" not in str(result)


def test_empty_or_invalid_account_response_is_unavailable():
    """缺合约字段或未返回现货字段不冒充空钱包。"""
    instance, account, _ = service()
    account.get_spot_account.return_value = {}
    account.get_futures_account.return_value = {}
    assert instance.get_summary()["total_equity"] is None


def test_single_snapshot_is_cached():
    """同一快照被多个页面请求复用。"""
    instance, account, market = service()
    assert instance.get_summary() == instance.get_summary()
    account.get_spot_account.assert_called_once()
    account.get_futures_account.assert_called_once()
    market.get_prices.assert_called_once()


def test_summary_requires_authentication_before_reading_accounts():
    """未登录不能取得完整账户权益，也不能触发外部读取。"""
    from services.api.app.routes import balances
    result = balances.get_balance_summary()
    assert result["error"]["code"] == "unauthorized"


@pytest.mark.parametrize("bad_value", ["NaN", "Infinity", None])
def test_nonfinite_or_missing_futures_equity_cannot_be_total(bad_value):
    """非有限或缺失金额不能进入前端和账户合计。"""
    instance, account, _ = service()
    account.get_futures_account.return_value["totalMarginBalance"] = bad_value
    assert instance.get_summary()["total_equity"] is None


def test_cached_snapshot_cannot_be_modified_by_caller():
    """修改某次返回的列表不能污染其他页面的账户余额。"""
    instance, _, _ = service()
    result = instance.get_summary()
    result["assets"][0]["available"] = "99999"
    assert instance.get_summary()["assets"][0]["available"] == "4"


def test_summary_non_live_never_reads_real_accounts(monkeypatch):
    """模拟环境即使已登录也不读取实盘账户。"""
    from types import SimpleNamespace
    from services.api.app.routes import balances
    monkeypatch.setattr(balances.auth_service, "require_control_plane_access", lambda token: {})
    monkeypatch.setattr(balances.Settings, "from_env", lambda: SimpleNamespace(runtime_mode="dry-run"))
    result = balances.get_balance_summary(authorization="Bearer test")
    assert result["data"]["total_equity"] is None
    assert result["data"]["status"] == "unavailable"


def test_default_lazy_account_client_exposes_equity_reads(monkeypatch):
    """默认惰性客户端必须把两类账户读取转接到真实客户端。"""
    from services.api.app.adapters.binance import account_client
    from services.api.app.services.balance_equity_service import BalanceEquityService
    client = Mock()
    client.get_spot_account.return_value = {"balances": [{"asset": "USDT", "free": "5", "locked": "0"}]}
    client.get_futures_account.return_value = {"totalMarginBalance": "9.4", "totalUnrealizedProfit": "0"}
    monkeypatch.setattr(account_client, "create_binance_account_client", lambda: client)
    result = BalanceEquityService(market_client=Mock()).get_summary()
    assert result["total_equity"] == "14.4"
    client.get_spot_account.assert_called_once()
    client.get_futures_account.assert_called_once()
