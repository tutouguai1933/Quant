"""Sync service that treats Freqtrade adapter state as the source of truth."""

from __future__ import annotations

from services.api.app.adapters.freqtrade.client import freqtrade_client


class SyncService:
    """Returns the latest adapter snapshot without maintaining a second truth source."""

    def sync_execution_state(self) -> dict[str, object]:
        return freqtrade_client.get_snapshot().to_dict()

    def get_runtime_snapshot(self) -> dict[str, object]:
        """返回执行器当前运行快照。"""

        snapshot = self.sync_execution_state()
        runtime = dict(freqtrade_client.get_runtime_snapshot())
        runtime.update(
            {
                "strategy_count": len(list(snapshot.get("strategies", []))),
                "order_count": len(list(snapshot.get("orders", []))),
                "position_count": len(list(snapshot.get("positions", []))),
            }
        )
        return runtime

    def list_orders(self, limit: int = 100) -> list[dict[str, object]]:
        snapshot = self.sync_execution_state()
        return list(snapshot["orders"])[:limit]

    def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
        snapshot = self.sync_execution_state()
        return list(snapshot["positions"])[:limit]

    def list_strategies(self, limit: int = 50) -> list[dict[str, object]]:
        snapshot = self.sync_execution_state()
        return list(snapshot["strategies"])[:limit]

    def get_strategy(self, strategy_id: int) -> dict[str, object] | None:
        strategies = self.list_strategies(limit=200)
        for strategy in strategies:
            if strategy["id"] == strategy_id:
                return strategy
        return None


sync_service = SyncService()
