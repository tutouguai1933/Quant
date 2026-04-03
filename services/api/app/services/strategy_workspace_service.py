"""策略中心聚合服务。

这个文件负责把策略目录、运行状态、最近信号和最近执行结果整理成策略中心页面可直接消费的结构。
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from services.api.app.core.settings import Settings
from services.api.app.services.account_sync_service import account_sync_service
from services.api.app.services.market_service import MarketService
from services.api.app.services.research_cockpit_service import build_market_research_brief
from services.api.app.services.research_service import ResearchService, research_service
from services.api.app.services.signal_service import SignalService, signal_service
from services.api.app.services.strategy_catalog import StrategyCatalogService, strategy_catalog_service
from services.api.app.services.strategy_engine import apply_research_soft_gate, evaluate_trend_breakout, evaluate_trend_pullback
from services.api.app.services.sync_service import SyncService, sync_service


class StrategyWorkspaceService:
    """聚合策略中心所需的最小工作台数据。"""

    def __init__(
        self,
        *,
        catalog_service: StrategyCatalogService | None = None,
        signal_store: SignalService | None = None,
        execution_sync: SyncService | None = None,
        market_reader: MarketService | None = None,
        research_reader: ResearchService | None = None,
        account_sync: object | None = None,
    ) -> None:
        self._catalog_service = catalog_service or strategy_catalog_service
        self._signal_store = signal_store or signal_service
        self._execution_sync = execution_sync or sync_service
        self._market_reader = market_reader or MarketService()
        self._research_reader = research_reader or research_service
        self._account_sync = account_sync or account_sync_service

    def get_workspace(self, signal_limit: int = 5, order_limit: int = 5) -> dict[str, object]:
        """返回策略中心页面的一次完整聚合视图。"""

        whitelist = self._catalog_service.get_whitelist()
        catalog = self._catalog_service.list_strategies()
        recent_signals = self._signal_store.list_signals(limit=signal_limit)
        account_state = self._build_account_state(order_limit=order_limit)
        recent_orders = list(account_state["orders"]) if account_state["source"] == "binance-account-sync" else self._execution_sync.list_orders(limit=order_limit)
        latest_research = self._research_reader.get_latest_result()
        strategy_cards = self._build_strategy_cards(catalog, whitelist, latest_research)

        return {
            "overview": {
                "strategy_count": len(strategy_cards),
                "whitelist_count": len(whitelist),
                "signal_count": len(recent_signals),
                "order_count": len(recent_orders),
                "running_count": sum(1 for item in strategy_cards if item["runtime_status"] == "running"),
            },
            "executor_runtime": self._execution_sync.get_runtime_snapshot(),
            "research": self._build_research_overview(latest_research),
            "research_recommendation": self._build_research_recommendation(),
            "whitelist": whitelist,
            "strategies": strategy_cards,
            "recent_signals": recent_signals,
            "recent_orders": recent_orders,
            "account_state": account_state,
        }

    def _build_account_state(self, order_limit: int = 5) -> dict[str, object]:
        """把账户真实状态整理成策略中心可以直接展示的摘要。"""

        runtime_mode = Settings.from_env().runtime_mode
        if runtime_mode == "live":
            balances = self._call_account_sync("list_balances", limit=order_limit)
            orders = self._call_account_sync("list_orders", limit=order_limit)
            positions = self._call_account_sync("list_positions", limit=order_limit)
            source = "binance-account-sync"
            truth_source = "binance"
        else:
            balances = []
            orders = self._execution_sync.list_orders(limit=order_limit)
            positions = self._execution_sync.list_positions(limit=order_limit)
            source = "freqtrade-sync"
            truth_source = "freqtrade"

        latest_balance = balances[0] if balances else None
        latest_order = orders[0] if orders else None
        latest_position = positions[0] if positions else None
        summary = {
            "balance_count": len(balances),
            "tradable_balance_count": sum(1 for item in balances if str(item.get("tradeStatus", "")).lower() == "tradable"),
            "dust_count": sum(1 for item in balances if str(item.get("tradeStatus", "")).lower() == "dust"),
            "order_count": len(orders),
            "position_count": len(positions),
        }

        return {
            "source": source,
            "truth_source": truth_source,
            "summary": summary,
            "balances": balances,
            "orders": orders,
            "positions": positions,
            "latest_balance": latest_balance,
            "latest_order": latest_order,
            "latest_position": latest_position,
        }

    def _call_account_sync(self, method_name: str, **kwargs) -> list[dict[str, object]]:
        """安全调用账户同步对象，避免页面因为接口缺失直接报错。"""

        method = getattr(self._account_sync, method_name, None)
        if method is None:
            return []
        items = method(**kwargs)
        if items is None:
            return []
        return list(items)

    def _build_strategy_cards(
        self,
        catalog: list[dict[str, object]],
        whitelist: list[str],
        latest_research: dict[str, object],
    ) -> list[dict[str, object]]:
        """把策略目录变成页面卡片所需结构。"""

        cards: list[dict[str, object]] = []
        for index, strategy in enumerate(catalog, start=1):
            runtime_item = self._execution_sync.get_strategy(index) or {}
            default_params = dict(strategy.get("default_params") or {})
            symbols = list(whitelist)
            primary_symbol = symbols[0] if symbols else ""
            research_summary = self._get_symbol_research_from_snapshot(latest_research, primary_symbol)
            latest_signal = self._get_latest_signal(index)
            cards.append(
                {
                    "strategy_id": index,
                    "key": str(strategy.get("key", "")),
                    "display_name": str(strategy.get("display_name", "")),
                    "description": str(strategy.get("description", "")),
                    "symbols": symbols,
                    "default_params": default_params,
                    "runtime_status": str(runtime_item.get("status", "stopped")),
                    "runtime_name": str(runtime_item.get("name", strategy.get("display_name", ""))),
                    "latest_signal": latest_signal,
                    "research_summary": self._build_research_summary(primary_symbol, research_summary),
                    "current_evaluation": self._evaluate_strategy(
                        strategy_key=str(strategy.get("key", "")),
                        default_params=default_params,
                        symbols=symbols,
                        research_summary=research_summary,
                    ),
                }
            )
            cards[-1]["research_cockpit"] = build_market_research_brief(
                symbol=primary_symbol,
                recommended_strategy=str(strategy.get("key", "")),
                evaluation=dict(cards[-1]["current_evaluation"] or {}),
                research_summary=research_summary,
            )
        return cards

    def _get_latest_signal(self, strategy_id: int) -> dict[str, object] | None:
        """返回指定策略最近一条已持久化信号。"""

        signals = self._signal_store.list_signals(limit=100)
        for signal in signals:
            if signal.get("strategy_id") == strategy_id:
                return {
                    "signal_id": signal.get("signal_id"),
                    "strategy_id": signal.get("strategy_id"),
                    "symbol": signal.get("symbol"),
                    "status": signal.get("status"),
                    "generated_at": signal.get("generated_at"),
                    "source": signal.get("source"),
                }
        return None

    def _build_research_overview(self, latest_research: dict[str, object]) -> dict[str, object]:
        """把研究层结果收敛成页面总览。"""

        latest_training = dict(latest_research.get("latest_training") or {})
        latest_inference = dict(latest_research.get("latest_inference") or {})
        inference_summary = dict(latest_inference.get("summary") or {})
        return {
            "status": str(latest_research.get("status", "unavailable")),
            "detail": str(latest_research.get("detail", "n/a")),
            "model_version": str(latest_training.get("model_version", "")),
            "signal_count": int(inference_summary.get("signal_count", 0) or 0),
        }

    def _build_research_recommendation(self) -> dict[str, object] | None:
        """返回当前最值得继续进入执行页的研究候选。"""

        getter = getattr(self._research_reader, "get_research_recommendation", None)
        if getter is None:
            return None
        recommendation = getter()
        if recommendation is None:
            return None
        return dict(recommendation)

    def _build_research_summary(
        self,
        primary_symbol: str,
        research_summary: dict[str, object] | None,
    ) -> dict[str, object]:
        """读取策略卡片对应的研究摘要。"""

        summary = research_summary or {}
        if summary:
            return {
                "symbol": str(summary.get("symbol", primary_symbol)),
                "score": str(summary.get("score", "")),
                "signal": str(summary.get("signal", "")),
                "model_version": str(summary.get("model_version", "")),
                "explanation": str(summary.get("explanation", "")),
                "generated_at": str(summary.get("generated_at", "")),
            }
        return {
            "symbol": primary_symbol,
            "score": "",
            "signal": "",
            "model_version": "",
            "explanation": "暂无研究结果",
            "generated_at": "",
        }

    def _evaluate_strategy(
        self,
        *,
        strategy_key: str,
        default_params: dict[str, object],
        symbols: list[str],
        research_summary: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """基于当前真实行情给出每套策略的即时判断。"""

        timeframe = self._require_text(default_params.get("timeframe"))
        lookback_bars = self._parse_positive_int(default_params.get("lookback_bars"))
        primary_symbol = symbols[0] if symbols else ""

        if timeframe is None or lookback_bars is None or not primary_symbol:
            return _build_strategy_unavailable_result(
                strategy_id=strategy_key,
                symbol=primary_symbol,
                timeframe=timeframe or "",
                lookback_bars=lookback_bars,
                extra_param_key=self._resolve_extra_param_key(strategy_key),
                extra_param_value=None,
                reason="invalid_catalog_defaults",
            )

        extra_param_key = self._resolve_extra_param_key(strategy_key)
        extra_param_value = self._parse_decimal(default_params.get(extra_param_key))
        if extra_param_value is None:
            return _build_strategy_unavailable_result(
                strategy_id=strategy_key,
                symbol=primary_symbol,
                timeframe=timeframe,
                lookback_bars=lookback_bars,
                extra_param_key=extra_param_key,
                extra_param_value=None,
                reason=f"invalid_{extra_param_key}",
            )

        try:
            chart = self._market_reader.get_symbol_chart(
                symbol=primary_symbol,
                interval=timeframe,
                limit=lookback_bars + 1,
                allowed_symbols=tuple(symbols),
            )
        except Exception:
            return _build_strategy_unavailable_result(
                strategy_id=strategy_key,
                symbol=primary_symbol,
                timeframe=timeframe,
                lookback_bars=lookback_bars,
                extra_param_key=extra_param_key,
                extra_param_value=extra_param_value,
                reason="chart_unavailable",
            )
        items = list(chart.get("items", []))
        if not items:
            return _build_strategy_unavailable_result(
                strategy_id=strategy_key,
                symbol=primary_symbol,
                timeframe=timeframe,
                lookback_bars=lookback_bars,
                extra_param_key=extra_param_key,
                extra_param_value=extra_param_value,
                reason="empty_chart",
                overlays=chart.get("overlays", {}),
            )

        if strategy_key == "trend_breakout":
            return apply_research_soft_gate(
                evaluate_trend_breakout(
                    primary_symbol,
                    items,
                    timeframe=timeframe,
                    lookback_bars=lookback_bars,
                    breakout_buffer_pct=extra_param_value,
                ),
                research_summary,
            )

        if strategy_key == "trend_pullback":
            return apply_research_soft_gate(
                evaluate_trend_pullback(
                    primary_symbol,
                    items,
                    timeframe=timeframe,
                    lookback_bars=lookback_bars,
                    pullback_depth_pct=extra_param_value,
                ),
                research_summary,
            )

        return _build_strategy_unavailable_result(
            strategy_id=strategy_key,
            symbol=primary_symbol,
            timeframe=timeframe,
            lookback_bars=lookback_bars,
            extra_param_key=extra_param_key,
            extra_param_value=extra_param_value,
            reason="unsupported_strategy",
        )

    @staticmethod
    def _get_symbol_research_from_snapshot(
        latest_research: dict[str, object],
        symbol: str,
    ) -> dict[str, object] | None:
        """从当前研究快照里读取单个币种摘要。"""

        if not symbol:
            return None
        symbols = dict(latest_research.get("symbols") or {})
        summary = symbols.get(symbol)
        if isinstance(summary, dict):
            return dict(summary)
        return None

    @staticmethod
    def _resolve_extra_param_key(strategy_key: str) -> str:
        """返回不同策略的专属参数名。"""

        if strategy_key == "trend_breakout":
            return "breakout_buffer_pct"
        if strategy_key == "trend_pullback":
            return "pullback_depth_pct"
        return "extra_param"

    @staticmethod
    def _require_text(value: object) -> str | None:
        """读取非空文本。"""

        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    @staticmethod
    def _parse_positive_int(value: object) -> int | None:
        """读取正整数参数。"""

        try:
            parsed = Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            return None
        if parsed != parsed.to_integral_value():
            return None
        normalized = int(parsed)
        if normalized <= 0:
            return None
        return normalized

    @staticmethod
    def _parse_decimal(value: object) -> Decimal | None:
        """读取数值型参数。"""

        try:
            return Decimal(str(value))
        except (TypeError, ValueError, InvalidOperation):
            return None


strategy_workspace_service = StrategyWorkspaceService(
    catalog_service=strategy_catalog_service,
    signal_store=signal_service,
    execution_sync=sync_service,
    market_reader=MarketService(),
    research_reader=research_service,
)


def _build_strategy_unavailable_result(
    *,
    strategy_id: str,
    symbol: str,
    timeframe: str,
    lookback_bars: object,
    extra_param_key: str,
    extra_param_value: object,
    reason: str,
    overlays: dict[str, object] | None = None,
) -> dict[str, object]:
    """构造策略暂不可评估时的统一结果。"""

    return {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "lookback_bars": lookback_bars,
        extra_param_key: extra_param_value,
        "decision": "evaluation_unavailable",
        "reason": reason,
        "overlays": overlays or {"sample_size": 0},
    }
