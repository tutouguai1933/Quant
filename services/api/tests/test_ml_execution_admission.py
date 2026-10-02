"""验证自动化模型执行前的硬约束与合约平仓，保持 RSI 独立。"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest import mock

from services.api.app.adapters.freqtrade.rest_client import FreqtradeRestClient, FreqtradeRestConfig
from services.api.app.services.direction_short_service import DirectionShortService
from services.api.app.services.execution_service import ExecutionService
from services.worker.qlib_live_policy import EVALUATION_VERSION, inference_execution_guard

NOW = datetime(2026, 10, 2, 4, tzinfo=timezone.utc)


def approved_signal():
    """构造与生产模型一致的实时概率信号。"""
    return {"model_admission": {"passed": True, "stage": "production", "evaluation_version": EVALUATION_VERSION, "model_version": "production-v2", "reasons": []},
            "signals": [{"symbol": "BTCUSDT", "feature_asof": (NOW - timedelta(seconds=1)).isoformat(), "expires_at": (NOW + timedelta(hours=1)).isoformat(),
                         "model_version": "production-v2", "executable": True, "prediction_semantics": "return_above_threshold_probability"}]}


def test_fresh_production_signal_is_allowed():
    """模型与实时行情完整时允许自动化策略继续执行。"""
    assert inference_execution_guard(approved_signal(), now=NOW)["passed"] is True


def test_expired_feature_is_blocked():
    """实际行情过期时不能用新的报告生成时间掩盖。"""
    signal = approved_signal()
    signal["signals"][0]["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
    assert inference_execution_guard(signal, now=NOW)["passed"] is False


def test_upside_model_cannot_open_short():
    """即使模型合格，上涨概率的补集也不能打开合约空单。"""
    assert inference_execution_guard(approved_signal(), now=NOW, opening_short=True)["passed"] is False


def test_legacy_result_without_admission_is_blocked():
    """部署前的旧研究结果不满足新准入。"""
    assert inference_execution_guard({"signals": []}, now=NOW)["passed"] is False


def test_direction_service_does_not_open_from_unqualified_score(tmp_path, monkeypatch):
    """方向服务默认不允许仅凭低上涨分数开仓。"""
    monkeypatch.setenv("QUANT_DIRECTION_SHORT_STATE_PATH", str(tmp_path / "state.json"))
    assert DirectionShortService().decide(avg_score=.32)["action"] == "hold"


def test_full_exit_action_does_not_require_entry_quantity():
    """全平动作依据交易标识与真实数量，不能因入场字段缺失失败。"""
    client = FreqtradeRestClient(FreqtradeRestConfig(base_url="http://127.0.0.1:1", username="test", password="test"))
    trade = {"trade_id": 7, "pair": "BTC/USDT:USDT", "amount": .001, "is_open": True}
    with mock.patch.object(client, "_resolve_flat_trades", return_value=[trade]), mock.patch.object(client, "_request_json", return_value={}), mock.patch.object(client, "_find_trade_history", return_value=trade), mock.patch.object(client, "_push_trade_notification"):
        result = client.submit_execution_action({"symbol": "BTC/USDT:USDT", "side": "flat", "trade_id": 7})
    assert result


def test_ml_flat_signal_cannot_close_natural_rsi_position():
    """相同币种不代表相同策略，研究退出不能平掉自然 RSI 仓位。"""
    signal = {"source": "qlib", "side": "flat", "symbol": "BTCUSDT", "payload": {"ml_context": approved_signal()}}
    with mock.patch("services.api.app.services.execution_service.inference_execution_guard", return_value={"passed": True, "reasons": []}), mock.patch("services.api.app.services.execution_service.freqtrade_client") as client:
        client.list_open_trades.return_value = [{"trade_id": 1, "pair": "BTC/USDT", "is_open": True, "is_short": False, "enter_tag": ""}]
        import pytest
        with pytest.raises(PermissionError, match="归属"):
            ExecutionService._guard_ml_signal(signal, runtime_mode="live")


def test_ml_flat_selects_only_identified_ml_trade():
    """已有 ML 仓可退出，但必须携带实际交易 ID，不能按币种全平。"""
    signal = {"source": "qlib", "side": "flat", "symbol": "BTCUSDT", "payload": {"ml_context": approved_signal()}}
    with mock.patch("services.api.app.services.execution_service.inference_execution_guard", return_value={"passed": True, "reasons": []}), mock.patch("services.api.app.services.execution_service.freqtrade_client") as client:
        client.list_open_trades.return_value = [{"trade_id": 2, "pair": "BTC/USDT", "is_open": True, "is_short": False, "enter_tag": "quant-ml:production-v2:7"}]
        assert ExecutionService._guard_ml_signal(signal, runtime_mode="live") == 2
