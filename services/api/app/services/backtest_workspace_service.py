"""回测工作台聚合服务。

这个文件负责把研究报告里的回测摘要、成本假设和候选对比整理成前端可见结构。
"""

from __future__ import annotations

from services.api.app.services.research_service import research_service
from services.api.app.services.workbench_config_service import workbench_config_service


class BacktestWorkspaceService:
    """聚合当前回测上下文。"""

    def __init__(self, *, report_reader: object | None = None, controls_builder=None) -> None:
        self._report_reader = report_reader or research_service
        self._controls_builder = controls_builder or workbench_config_service.build_workspace_controls

    def get_workspace(self) -> dict[str, object]:
        """返回回测工作台统一模型。"""

        report = self._read_factory_report()
        latest_training = dict(report.get("latest_training") or {})
        training_context = dict(latest_training.get("training_context") or {})
        training_backtest = dict(latest_training.get("backtest") or {})
        assumptions = dict(training_backtest.get("assumptions") or {})
        metrics = dict(training_backtest.get("metrics") or {})
        controls = self._controls_builder()
        configured_backtest = dict((controls.get("config") or {}).get("backtest") or {})
        configured_thresholds = dict((controls.get("config") or {}).get("thresholds") or {})
        leaderboard = [
            {
                "symbol": str(item.get("symbol", "")),
                "strategy_template": str(item.get("strategy_template", "")),
                "backtest": dict(item.get("backtest") or {}),
            }
            for item in list(report.get("leaderboard") or [])
            if isinstance(item, dict)
        ]

        status = str(report.get("status", "unavailable") or "unavailable")
        if training_backtest or leaderboard:
            status = "ready"

        return {
            "status": status,
            "backend": str(report.get("backend", "qlib-fallback") or "qlib-fallback"),
            "overview": {
                "holding_window": str(training_context.get("holding_window", "")),
                "candidate_count": len(leaderboard),
                "recommended_symbol": str((report.get("overview") or {}).get("recommended_symbol", "")),
            },
            "assumptions": {
                str(name): str(value)
                for name, value in assumptions.items()
            },
            "controls": {
                "fee_bps": str(configured_backtest.get("fee_bps", "")),
                "slippage_bps": str(configured_backtest.get("slippage_bps", "")),
                "dry_run_min_win_rate": str(configured_thresholds.get("dry_run_min_win_rate", "0.5")),
                "dry_run_max_turnover": str(configured_thresholds.get("dry_run_max_turnover", "0.6")),
                "dry_run_min_sample_count": str(configured_thresholds.get("dry_run_min_sample_count", "20")),
                "live_min_win_rate": str(configured_thresholds.get("live_min_win_rate", "0.55")),
                "live_max_turnover": str(configured_thresholds.get("live_max_turnover", "0.45")),
                "live_min_sample_count": str(configured_thresholds.get("live_min_sample_count", "24")),
            },
            "training_backtest": {
                "metrics": {
                    str(name): str(value)
                    for name, value in metrics.items()
                }
            },
            "leaderboard": [
                {
                    "symbol": item["symbol"],
                    "strategy_template": item["strategy_template"],
                    "backtest": {
                        str(name): str(value)
                        for name, value in dict(item.get("backtest") or {}).items()
                    },
                }
                for item in leaderboard
            ],
        }

    def _read_factory_report(self) -> dict[str, object]:
        """读取统一研究报告。"""

        reader = getattr(self._report_reader, "get_factory_report", None)
        if callable(reader):
            payload = reader()
            if isinstance(payload, dict):
                return payload
        return {"status": "unavailable", "backend": "qlib-fallback"}


backtest_workspace_service = BacktestWorkspaceService()
