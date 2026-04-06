"""数据工作台聚合服务。

这个文件负责把研究层快照和市场原始样本整理成“数据工作台”可直接展示的结构。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from services.api.app.services.market_service import MarketService
from services.api.app.services.market_timeframe_service import get_supported_market_intervals
from services.api.app.services.market_timeframe_service import normalize_market_interval
from services.api.app.services.research_service import research_service
from services.api.app.services.strategy_catalog import strategy_catalog_service
from services.api.app.services.workbench_config_service import workbench_config_service


class DataWorkspaceService:
    """聚合研究数据快照与市场样本预览。"""

    def __init__(
        self,
        *,
        research_reader: object | None = None,
        market_reader: MarketService | None = None,
        whitelist_provider: Callable[[], list[str]] | None = None,
        controls_builder: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        self._research_reader = research_reader or research_service
        self._market_reader = market_reader or MarketService()
        self._whitelist_provider = whitelist_provider or strategy_catalog_service.get_whitelist
        self._controls_builder = controls_builder or workbench_config_service.build_workspace_controls

    def get_workspace(self, *, symbol: str, interval: str, limit: int) -> dict[str, object]:
        """返回数据工作台统一模型。"""

        whitelist = [item.strip().upper() for item in self._whitelist_provider() if item.strip()]
        workbench_controls = self._controls_builder()
        configured_data = dict((workbench_controls.get("config") or {}).get("data") or {})
        requested_symbol = symbol.strip().upper()
        configured_primary_symbol = str(configured_data.get("primary_symbol", "")).strip().upper()
        if requested_symbol:
            selected_symbol = requested_symbol if requested_symbol in whitelist else ""
        else:
            selected_symbol = configured_primary_symbol
        if selected_symbol not in whitelist:
            selected_symbol = whitelist[0] if whitelist else requested_symbol
        requested_interval = interval.strip()
        configured_intervals = [str(item) for item in list(configured_data.get("timeframes") or [])]
        normalized_interval = normalize_market_interval(requested_interval or (configured_intervals[0] if configured_intervals else "4h"))
        normalized_limit = max(int(limit or configured_data.get("sample_limit", 200) or 200), 1)

        research_report = self._read_factory_report()
        training_snapshot = self._extract_training_snapshot(research_report)
        preview = self._build_preview(
            symbol=selected_symbol,
            interval=normalized_interval,
            limit=normalized_limit,
            whitelist=tuple(whitelist),
        )
        research_status = str(research_report.get("status", "unavailable") or "unavailable")
        status = research_status
        if research_status == "ready" and str(preview.get("status", "ready")) != "ready":
            status = "degraded"

        return {
            "status": status,
            "backend": str(research_report.get("backend", "qlib-fallback")),
            "filters": {
                "selected_symbol": selected_symbol,
                "selected_interval": normalized_interval,
                "limit": normalized_limit,
                "available_symbols": whitelist,
                "available_intervals": list(get_supported_market_intervals()),
            },
            "sources": {
                "research": str(research_report.get("backend", "qlib-fallback")),
                "market": "binance",
            },
            "controls": {
                "selected_symbols": list(configured_data.get("selected_symbols") or []),
                "primary_symbol": str(configured_data.get("primary_symbol", "")),
                "timeframes": list(configured_data.get("timeframes") or []),
                "sample_limit": int(configured_data.get("sample_limit", normalized_limit) or normalized_limit),
                "available_symbols": whitelist,
                "available_timeframes": list(get_supported_market_intervals()),
            },
            "snapshot": training_snapshot,
            "preview": preview,
            "training_window": self._extract_training_window(research_report),
            "symbols": self._build_symbol_rows(whitelist=whitelist, selected_symbol=selected_symbol),
        }

    def _read_factory_report(self) -> dict[str, object]:
        """读取统一研究报告。"""

        reader = getattr(self._research_reader, "get_factory_report", None)
        if callable(reader):
            payload = reader()
            if isinstance(payload, dict):
                return payload
        return {"status": "unavailable", "backend": "qlib-fallback"}

    @staticmethod
    def _extract_training_snapshot(report: dict[str, object]) -> dict[str, object]:
        """抽取训练阶段的数据快照。"""

        snapshots = dict(report.get("snapshots") or {})
        training = dict(snapshots.get("training") or {})
        data_states = dict(training.get("data_states") or {})
        current_state = str(data_states.get("current") or training.get("active_data_state") or "")
        if current_state and "current" not in data_states:
            data_states["current"] = current_state
        return {
            "snapshot_id": str(training.get("snapshot_id", "")),
            "cache_signature": str(training.get("cache_signature", "")),
            "active_data_state": str(training.get("active_data_state", "")) or current_state,
            "data_states": data_states,
            "dataset_snapshot_path": str(training.get("dataset_snapshot_path", "")),
        }

    @staticmethod
    def _extract_training_window(report: dict[str, object]) -> dict[str, object]:
        """抽取训练窗口摘要。"""

        latest_training = dict(report.get("latest_training") or {})
        training_context = dict(latest_training.get("training_context") or {})
        return {
            "holding_window": str(training_context.get("holding_window", "")),
            "sample_window": dict(training_context.get("sample_window") or {}),
        }

    def _build_preview(
        self,
        *,
        symbol: str,
        interval: str,
        limit: int,
        whitelist: tuple[str, ...],
    ) -> dict[str, object]:
        """构造图表样本预览。"""

        try:
            chart = self._market_reader.get_symbol_chart(
                symbol=symbol,
                interval=interval,
                limit=limit,
                allowed_symbols=whitelist,
            )
        except Exception as exc:
            return {
                "symbol": symbol,
                "interval": interval,
                "effective_interval": interval,
                "source": "binance",
                "total_rows": 0,
                "first_open_time": "",
                "last_close_time": "",
                "status": "unavailable",
                "detail": str(exc),
            }
        items = list(chart.get("items") or [])
        first_item = items[0] if items else {}
        last_item = items[-1] if items else {}
        return {
            "symbol": symbol,
            "interval": interval,
            "effective_interval": interval,
            "source": "binance",
            "total_rows": len(items),
            "first_open_time": _format_timestamp(first_item.get("open_time")),
            "last_close_time": _format_timestamp(last_item.get("close_time")),
            "status": "ready",
            "detail": "",
        }

    @staticmethod
    def _build_symbol_rows(*, whitelist: list[str], selected_symbol: str) -> list[dict[str, object]]:
        """构造标的选项摘要。"""

        return [
            {
                "symbol": symbol,
                "selected": symbol == selected_symbol,
            }
            for symbol in whitelist
        ]


def _format_timestamp(value: object) -> str:
    """把毫秒时间戳格式化成 UTC 字符串。"""

    try:
        numeric = int(value or 0)
    except (TypeError, ValueError):
        return ""
    if numeric <= 0:
        return ""
    return datetime.fromtimestamp(numeric / 1000, tz=timezone.utc).isoformat()


data_workspace_service = DataWorkspaceService()
