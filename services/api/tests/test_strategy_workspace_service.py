from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.strategy_workspace_service import StrategyWorkspaceService  # noqa: E402


class StrategyWorkspaceServiceTests(unittest.TestCase):
    def test_workspace_contains_catalog_cards_whitelist_and_history_lists(self) -> None:
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
            },
            clear=False,
        ), patch(
            "services.api.app.services.strategy_workspace_service.workbench_config_service.get_config",
            return_value={"data": {"selected_symbols": []}},
        ):
            service = StrategyWorkspaceService(
                catalog_service=_FakeCatalogService(),
                signal_store=_FakeSignalStore(),
                execution_sync=_FakeExecutionSync(),
                market_reader=_FakeMarketReader(),
                research_reader=_FakeResearchService(),
                account_sync=_FakeAccountSyncService(),
            )

            workspace = service.get_workspace(signal_limit=5, order_limit=5)

        self.assertEqual(workspace["overview"]["strategy_count"], 2)
        self.assertEqual(workspace["overview"]["whitelist_count"], 2)
        self.assertEqual(workspace["whitelist"], ["BTCUSDT", "ETHUSDT"])
        self.assertEqual(workspace["executor_runtime"]["backend"], "memory")
        self.assertEqual(len(workspace["strategies"]), 2)
        self.assertEqual(workspace["recent_signals"][0]["strategy_id"], 1)
        self.assertEqual(workspace["recent_orders"][0]["status"], "filled")
        self.assertEqual(workspace["research"]["status"], "ready")
        self.assertEqual(workspace["account_state"]["source"], "binance-account-sync")
        self.assertEqual(workspace["account_state"]["truth_source"], "binance")
        self.assertEqual(workspace["account_state"]["summary"]["dust_count"], 1)
        self.assertIn("configuration", workspace)
        self.assertIn("research_scope", workspace["configuration"])
        self.assertIn("automation_policy", workspace["configuration"])
        self.assertIn("candidate_pool_preset", workspace["configuration"])
        self.assertIn("live_subset_preset", workspace["configuration"])

    def test_workspace_cards_include_runtime_status_signal_and_evaluation(self) -> None:
        with patch.dict(os.environ, {"QUANT_RUNTIME_MODE": "dry-run"}, clear=False), patch(
            "services.api.app.services.strategy_workspace_service.workbench_config_service.get_config",
            return_value={"data": {"selected_symbols": []}},
        ):
            service = StrategyWorkspaceService(
                catalog_service=_FakeCatalogService(),
                signal_store=_FakeSignalStore(),
                execution_sync=_FakeExecutionSync(),
                market_reader=_FakeMarketReader(),
                research_reader=_FakeResearchService(),
                account_sync=_FakeAccountSyncService(),
            )

            workspace = service.get_workspace()
        breakout_card = workspace["strategies"][0]
        pullback_card = workspace["strategies"][1]

        self.assertEqual(breakout_card["runtime_status"], "running")
        self.assertEqual(breakout_card["latest_signal"]["strategy_id"], 1)
        self.assertEqual(breakout_card["current_evaluation"]["decision"], "signal")
        self.assertEqual(breakout_card["current_evaluation"]["confidence"], "high")
        self.assertEqual(breakout_card["current_evaluation"]["research_gate"]["status"], "confirmed_by_research")
        self.assertEqual(breakout_card["research_cockpit"]["research_bias"], "bullish")
        self.assertEqual(breakout_card["research_cockpit"]["confidence"], "high")
        self.assertEqual(breakout_card["research_cockpit"]["research_gate"]["status"], "confirmed_by_research")
        self.assertEqual(breakout_card["research_summary"]["model_version"], "qlib-minimal-20260402093000")
        self.assertEqual(breakout_card["research_summary"]["score"], "0.7100")
        self.assertEqual(pullback_card["current_evaluation"]["strategy_id"], "trend_pullback")
        self.assertIn(
            pullback_card["current_evaluation"]["decision"],
            {"watch", "signal", "block", "evaluation_unavailable"},
        )

    def test_workspace_uses_single_research_snapshot_for_summary_and_gate(self) -> None:
        with patch.dict(os.environ, {"QUANT_RUNTIME_MODE": "dry-run"}, clear=False), patch(
            "services.api.app.services.strategy_workspace_service.workbench_config_service.get_config",
            return_value={"data": {"selected_symbols": []}},
        ):
            service = StrategyWorkspaceService(
                catalog_service=_FakeCatalogService(),
                signal_store=_FakeSignalStore(),
                execution_sync=_FakeExecutionSync(),
                market_reader=_FakeMarketReader(),
                research_reader=_SnapshotOnlyResearchService(),
                account_sync=_FakeAccountSyncService(),
            )

            workspace = service.get_workspace()
        breakout_card = workspace["strategies"][0]

        self.assertEqual(breakout_card["research_summary"]["explanation"], "暂无研究结果")
        self.assertEqual(breakout_card["current_evaluation"]["research_gate"]["status"], "unavailable")
        self.assertEqual(breakout_card["research_cockpit"]["research_bias"], "unavailable")
        self.assertEqual(breakout_card["research_cockpit"]["research_explanation"], "该币种暂无研究结论")

    def test_workspace_surfaces_account_snapshot_for_phase_b_follow_up_chain(self) -> None:
        with patch.dict(
            os.environ,
            {
                "QUANT_RUNTIME_MODE": "live",
                "BINANCE_API_KEY": "k",
                "BINANCE_API_SECRET": "s",
            },
            clear=False,
        ), patch(
            "services.api.app.services.strategy_workspace_service.workbench_config_service.get_config",
            return_value={"data": {"selected_symbols": []}},
        ):
            service = StrategyWorkspaceService(
                catalog_service=_FakeCatalogService(),
                signal_store=_FakeSignalStore(),
                execution_sync=_FakeExecutionSync(),
                market_reader=_FakeMarketReader(),
                research_reader=_FakeResearchService(),
                account_sync=_FakeAccountSyncService(),
            )

            workspace = service.get_workspace()

        self.assertEqual(workspace["account_state"]["latest_balance"]["asset"], "DOGE")
        self.assertEqual(workspace["account_state"]["latest_order"]["symbol"], "DOGEUSDT")
        self.assertEqual(workspace["account_state"]["latest_position"]["symbol"], "DOGE")

    def test_workspace_prefers_ready_research_candidate(self) -> None:
        with patch.dict(os.environ, {"QUANT_RUNTIME_MODE": "dry-run"}, clear=False), patch(
            "services.api.app.services.strategy_workspace_service.workbench_config_service.get_config",
            return_value={"data": {"selected_symbols": []}},
        ):
            service = StrategyWorkspaceService(
                catalog_service=_FakeCatalogService(),
                signal_store=_FakeSignalStore(),
                execution_sync=_FakeExecutionSync(),
                market_reader=_FakeMarketReader(),
                research_reader=_FakeResearchService(),
                account_sync=_FakeAccountSyncService(),
            )

            workspace = service.get_workspace()

        self.assertEqual(workspace["research_recommendation"]["symbol"], "BTCUSDT")
        self.assertEqual(workspace["research_recommendation"]["allowed_to_dry_run"], True)
        self.assertEqual(workspace["research_recommendation"]["next_action"], "enter_dry_run")

    def test_workspace_prefers_configured_candidate_pool_over_catalog_whitelist(self) -> None:
        from services.api.app.services.workbench_config_service import WorkbenchConfigService

        with tempfile.TemporaryDirectory() as temp_dir:
            config_service = WorkbenchConfigService(config_path=Path(temp_dir) / "workbench.json")
            config_service.update_section(
                "data",
                {
                    "selected_symbols": ["ETHUSDT", "XRPUSDT", "DOGEUSDT"],
                },
            )
            with patch(
                "services.api.app.services.strategy_workspace_service.workbench_config_service",
                config_service,
            ), patch.dict(os.environ, {"QUANT_RUNTIME_MODE": "dry-run"}, clear=False):
                service = StrategyWorkspaceService(
                    catalog_service=_FakeCatalogService(),
                    signal_store=_FakeSignalStore(),
                    execution_sync=_FakeExecutionSync(),
                    market_reader=_FakeMarketReader(),
                    research_reader=_FakeResearchService(),
                    account_sync=_FakeAccountSyncService(),
                )

                workspace = service.get_workspace()

        self.assertEqual(workspace["whitelist"], ["ETHUSDT", "XRPUSDT", "DOGEUSDT"])
        self.assertEqual(workspace["overview"]["whitelist_count"], 3)
        self.assertEqual(workspace["strategies"][0]["symbols"], ["ETHUSDT", "XRPUSDT", "DOGEUSDT"])
        self.assertIn("候选池预设", workspace["configuration"]["candidate_pool_preset"])


class _FakeCatalogService:
    def get_whitelist(self) -> list[str]:
        return ["BTCUSDT", "ETHUSDT"]

    def list_strategies(self) -> list[dict[str, object]]:
        return [
            {
                "key": "trend_breakout",
                "display_name": "趋势突破",
                "description": "顺势突破",
                "default_params": {
                    "timeframe": "1h",
                    "lookback_bars": 3,
                    "breakout_buffer_pct": "1.0",
                },
            },
            {
                "key": "trend_pullback",
                "display_name": "趋势回调",
                "description": "顺势回踩",
                "default_params": {
                    "timeframe": "1h",
                    "lookback_bars": 3,
                    "pullback_depth_pct": "2.0",
                },
            },
        ]


class _FakeSignalStore:
    def list_signals(self, limit: int = 100) -> list[dict[str, object]]:
        return [
            {
                "signal_id": 11,
                "strategy_id": 1,
                "symbol": "BTCUSDT",
                "status": "received",
                "generated_at": "2026-04-02T00:00:00+00:00",
                "source": "trend_breakout",
            }
        ][:limit]


class _FakeExecutionSync:
    def get_runtime_snapshot(self) -> dict[str, object]:
        return {
            "executor": "freqtrade",
            "backend": "memory",
            "mode": "dry-run",
            "connection_status": "not_configured",
        }

    def get_strategy(self, strategy_id: int) -> dict[str, object] | None:
        data = {
            1: {"id": 1, "name": "趋势突破", "status": "running"},
            2: {"id": 2, "name": "趋势回调", "status": "stopped"},
        }
        return data.get(strategy_id)

    def list_orders(self, limit: int = 100) -> list[dict[str, object]]:
        return [
            {
                "id": "order-1",
                "symbol": "BTC/USDT",
                "side": "buy",
                "orderType": "market",
                "status": "filled",
            }
        ][:limit]

    def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
        return [
            {
                "id": "position-1",
                "symbol": "BTCUSDT",
                "side": "long",
                "quantity": "0.0100000000",
                "unrealizedPnl": "0.0000000000",
            }
        ][:limit]


class _FakeMarketReader:
    def get_symbol_chart(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 200,
        allowed_symbols: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        if symbol == "BTCUSDT":
            items = [
                {"open": "98", "high": "100", "low": "95", "close": "99"},
                {"open": "99", "high": "102", "low": "96", "close": "101"},
                {"open": "101", "high": "103", "low": "97", "close": "102"},
                {"open": "102", "high": "106", "low": "101", "close": "105"},
            ]
        else:
            items = [
                {"open": "100", "high": "108", "low": "99", "close": "107"},
                {"open": "107", "high": "109", "low": "103", "close": "104"},
                {"open": "104", "high": "106", "low": "101", "close": "102"},
                {"open": "102", "high": "105", "low": "102", "close": "103"},
            ]
        return {
            "items": items,
            "overlays": {"sample_size": len(items)},
            "markers": {"signals": [], "entries": [], "stops": []},
        }


class _FakeAccountSyncService:
    def list_balances(self, limit: int = 100) -> list[dict[str, object]]:
        return [
            {
                "id": "balance-doge",
                "asset": "DOGE",
                "available": "0.97600000",
                "locked": "0.00000000",
                "tradeStatus": "dust",
                "tradeHint": "这部分余额低于当前可卖门槛，属于交易所零头资产",
                "sellableQuantity": "0",
                "dustQuantity": "0.976",
            },
            {
                "id": "balance-usdt",
                "asset": "USDT",
                "available": "20.00771436",
                "locked": "0.00000000",
                "tradeStatus": "tradable",
                "tradeHint": "这是基础计价资产，可以直接用于下单",
                "sellableQuantity": "20.00771436",
                "dustQuantity": "0",
            },
        ][:limit]

    def list_orders(self, limit: int = 100, symbols: tuple[str, ...] | None = None) -> list[dict[str, object]]:
        return [
            {
                "id": "order-doge-1",
                "symbol": "DOGEUSDT",
                "side": "sell",
                "orderType": "MARKET",
                "status": "filled",
            }
        ][:limit]

    def list_positions(self, limit: int = 100) -> list[dict[str, object]]:
        return [
            {
                "id": "position-doge",
                "symbol": "DOGE",
                "side": "long",
                "quantity": "0.97600000",
                "unrealizedPnl": "0.00000000",
            }
        ][:limit]


class _FakeResearchService:
    def get_latest_result(self) -> dict[str, object]:
        return {
            "status": "ready",
            "detail": "ok",
            "latest_training": {"model_version": "qlib-minimal-20260402093000"},
            "latest_inference": {
                "summary": {"signal_count": 2},
                "candidates": {
                    "items": [
                        {
                            "rank": 1,
                            "symbol": "BTCUSDT",
                            "score": "0.7100",
                            "allowed_to_dry_run": True,
                            "dry_run_gate": {"status": "passed", "reasons": []},
                            "strategy_template": "trend_breakout_timing",
                        }
                    ]
                },
            },
            "symbols": {
                "BTCUSDT": {
                    "symbol": "BTCUSDT",
                    "score": "0.7100",
                    "signal": "long",
                    "model_version": "qlib-minimal-20260402093000",
                    "explanation": "close_return=1.5000%, trend_gap=2.2000%, volume_ratio=1.1000",
                    "generated_at": "2026-04-02T09:30:00+00:00",
                }
            },
        }

    def get_symbol_research(self, symbol: str) -> dict[str, object] | None:
        return dict(self.get_latest_result()["symbols"]).get(symbol)

    def get_research_recommendation(self) -> dict[str, object] | None:
        return {
            "symbol": "BTCUSDT",
            "score": "0.7100",
            "allowed_to_dry_run": True,
            "strategy_template": "trend_breakout_timing",
            "dry_run_gate": {"status": "passed", "reasons": []},
            "next_action": "enter_dry_run",
        }


class _SnapshotOnlyResearchService:
    def get_latest_result(self) -> dict[str, object]:
        return {
            "status": "ready",
            "detail": "ok",
            "latest_training": {"model_version": "qlib-minimal-20260402103000"},
            "latest_inference": {"summary": {"signal_count": 1}},
            "symbols": {
                "ETHUSDT": {
                    "symbol": "ETHUSDT",
                    "score": "0.6800",
                    "signal": "long",
                    "model_version": "qlib-minimal-20260402103000",
                    "explanation": "eth-only",
                    "generated_at": "2026-04-02T10:30:00+00:00",
                }
            },
        }

    def get_symbol_research(self, symbol: str) -> dict[str, object] | None:
        raise AssertionError("workspace should use the fetched research snapshot instead of re-reading")


if __name__ == "__main__":
    unittest.main()
