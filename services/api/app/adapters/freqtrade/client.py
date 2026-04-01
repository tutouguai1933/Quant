"""Freqtrade 统一门面。

这个文件负责在内存态和真实 REST 后端之间切换，外部只需要调用同一组控制接口。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from services.api.app.core.settings import Settings


def utc_now() -> datetime:
    """返回当前 UTC 时间。"""

    return datetime.now(timezone.utc)


@dataclass(slots=True)
class FreqtradeSnapshot:
    """Freqtrade 当前快照。"""

    balances: list[dict[str, object]]
    positions: list[dict[str, object]]
    orders: list[dict[str, object]]
    strategies: list[dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        """把快照转成普通字典。"""

        return {
            "balances": self.balances,
            "positions": self.positions,
            "orders": self.orders,
            "strategies": self.strategies,
        }


class _MemoryFreqtradeBackend:
    """当前阶段使用的内存态 Freqtrade 后端。"""

    def __init__(self) -> None:
        self._strategies: dict[int, dict[str, object]] = {
            1: {
                "id": 1,
                "name": "BTC Trend",
                "producerType": "qlib",
                "status": "stopped",
                "executor": "freqtrade",
                "exchange": "binance",
                "updatedAt": utc_now().isoformat(),
            }
        }
        self._balances: list[dict[str, object]] = [
            {
                "asset": "USDT",
                "total": "10000.0000000000",
                "available": "10000.0000000000",
                "locked": "0.0000000000",
                "snapshotTime": utc_now().isoformat(),
            }
        ]
        self._positions: dict[str, dict[str, object]] = {}
        self._orders: dict[str, dict[str, object]] = {}
        self._next_order_id = 1

    def control_strategy(self, strategy_id: int, action: str) -> dict[str, object]:
        """切换策略状态。"""

        strategy = self._strategies.setdefault(
            strategy_id,
            {
                "id": strategy_id,
                "name": f"Strategy {strategy_id}",
                "producerType": "mock",
                "status": "draft",
                "executor": "freqtrade",
                "exchange": "binance",
                "updatedAt": utc_now().isoformat(),
            },
        )
        next_status = {"start": "running", "pause": "paused", "stop": "stopped"}[action]
        strategy["status"] = next_status
        strategy["updatedAt"] = utc_now().isoformat()
        return dict(strategy)

    def submit_execution_action(self, action: dict[str, object]) -> dict[str, object]:
        """把执行动作写入内存态快照。"""

        runtime_mode = self._runtime_mode()
        order_id = f"ft-{runtime_mode}-order-{self._next_order_id}"
        self._next_order_id += 1

        side = "buy" if action["side"] == "long" else "sell"
        quantity = Decimal(str(action["quantity"]))
        symbol = str(action["symbol"])
        avg_price = Decimal("86000.0000000000")
        timestamp = utc_now().isoformat()

        order = {
            "id": order_id,
            "venueOrderId": order_id,
            "runtimeMode": runtime_mode,
            "symbol": symbol,
            "side": side,
            "orderType": "market",
            "status": "filled",
            "quantity": f"{quantity:.10f}",
            "executedQty": f"{quantity:.10f}",
            "avgPrice": f"{avg_price:.10f}",
            "sourceSignalId": action["source_signal_id"],
            "strategyId": action.get("strategy_id"),
            "updatedAt": timestamp,
        }
        self._orders[order_id] = order

        if action["side"] == "flat":
            self._positions.pop(symbol, None)
        else:
            self._positions[symbol] = {
                "id": f"position-{symbol}",
                "symbol": symbol,
                "side": action["side"],
                "quantity": f"{quantity:.10f}",
                "entryPrice": f"{avg_price:.10f}",
                "markPrice": f"{avg_price:.10f}",
                "unrealizedPnl": "0.0000000000",
                "updatedAt": timestamp,
                "strategyId": action.get("strategy_id"),
            }

        return dict(order)

    def get_snapshot(self) -> FreqtradeSnapshot:
        """读取内存态快照。"""

        return FreqtradeSnapshot(
            balances=[dict(item) for item in self._balances],
            positions=[dict(item) for item in self._positions.values()],
            orders=[dict(item) for item in self._orders.values()],
            strategies=[dict(item) for item in self._strategies.values()],
        )

    def get_runtime_snapshot(self) -> dict[str, object]:
        """返回内存态运行视图。"""

        return {
            "executor": "freqtrade",
            "backend": "memory",
            "mode": self._runtime_mode(),
            "connection_status": "not_configured",
            "base_url": "",
        }

    def _runtime_mode(self) -> str:
        """读取当前运行模式。"""

        return Settings.from_env().runtime_mode


class FreqtradeClient:
    """统一门面，自动选择内存态或 REST 后端。"""

    def __init__(self, settings: Settings | None = None, rest_client: object | None = None) -> None:
        self._settings = settings or Settings.from_env()
        self._backend = self._build_backend(rest_client)

    def control_strategy(self, strategy_id: int, action: str) -> dict[str, object]:
        """对外暴露策略控制接口。"""

        return self._backend.control_strategy(strategy_id, action)

    def submit_execution_action(self, action: dict[str, object]) -> dict[str, object]:
        """对外暴露执行动作提交接口。"""

        return self._backend.submit_execution_action(action)

    def get_snapshot(self) -> FreqtradeSnapshot:
        """对外暴露快照读取接口。"""

        return self._backend.get_snapshot()

    def get_runtime_snapshot(self) -> dict[str, object]:
        """对外暴露运行视图。"""

        return self._backend.get_runtime_snapshot()

    def _build_backend(self, rest_client: object | None) -> object:
        """根据运行配置选择后端。"""

        if self._settings.should_use_freqtrade_rest():
            if rest_client is not None:
                return rest_client
            from services.api.app.adapters.freqtrade.rest_client import FreqtradeRestClient

            return FreqtradeRestClient.from_settings(self._settings)
        return _MemoryFreqtradeBackend()


freqtrade_client = FreqtradeClient()
