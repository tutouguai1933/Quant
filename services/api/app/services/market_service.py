"""市场数据聚合服务。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from services.api.app.adapters.binance.market_client import BinanceMarketClient
from services.api.app.services.indicator_service import build_empty_marker_groups
from services.api.app.services.indicator_service import build_indicator_summary
from services.api.app.services.market_timeframe_service import build_multi_timeframe_summary
from services.api.app.services.market_timeframe_service import get_supported_market_intervals
from services.api.app.services.market_timeframe_service import normalize_market_interval
from services.api.app.services.research_cockpit_service import build_market_research_brief
from services.api.app.services.research_cockpit_service import build_symbol_research_cockpit
from services.api.app.services.strategy_catalog import StrategyCatalogService, strategy_catalog_service
from services.api.app.services.strategy_engine import apply_research_soft_gate, evaluate_trend_breakout, evaluate_trend_pullback


ChartCache = dict[tuple[str, tuple[str, ...] | None], dict[str, object]]


def normalize_market_snapshot(item: dict[str, object]) -> dict[str, object]:
    """把 Binance 24h ticker 统一成控制平面的市场快照结构。"""

    return {
        "symbol": str(item.get("symbol", "")),
        "last_price": str(item.get("lastPrice", "")),
        "change_percent": str(item.get("priceChangePercent", "")),
        "quote_volume": str(item.get("quoteVolume", "")),
    }


def normalize_kline_series(rows: list[list[object]]) -> list[dict[str, object]]:
    """把 Binance K 线数组统一成控制平面的图表结构。"""

    normalized_rows, _ = _normalize_kline_rows(rows)
    return normalized_rows


class MarketService:
    """市场数据读取与整理服务。"""

    def __init__(
        self,
        client: BinanceMarketClient | None = None,
        catalog_service: StrategyCatalogService | None = None,
        research_reader: object | None = None,
    ) -> None:
        self._client = client or BinanceMarketClient()
        self._catalog_service = catalog_service or strategy_catalog_service
        self._research_reader = research_reader or _NullResearchReader()

    def list_market_snapshots(self, symbols: tuple[str, ...]) -> list[dict[str, object]]:
        """只返回配置白名单里的市场快照。"""

        allowed_symbols = {symbol.strip().upper() for symbol in symbols if symbol.strip()}
        catalog_whitelist = tuple(self._catalog_service.get_whitelist())
        effective_symbols = allowed_symbols & {symbol.strip().upper() for symbol in catalog_whitelist if symbol.strip()}
        rows = self._client.get_tickers()
        snapshots: list[dict[str, object]] = []
        for row in rows:
            normalized_symbol = str(row.get("symbol", "")).strip().upper()
            if normalized_symbol not in effective_symbols:
                continue
            snapshot = normalize_market_snapshot(row)
            snapshot.update(self._build_market_strategy_summary(normalized_symbol, catalog_whitelist))
            snapshot["research_brief"] = build_market_research_brief(
                symbol=normalized_symbol,
                recommended_strategy=str(snapshot.get("recommended_strategy", "none")),
                evaluation=_resolve_primary_evaluation(
                    str(snapshot.get("recommended_strategy", "none")),
                    dict(snapshot.get("strategy_summary") or {}),
                ),
                research_summary=self._get_symbol_research(normalized_symbol),
            )
            snapshots.append(snapshot)
        return snapshots

    def get_symbol_chart(
        self,
        symbol: str,
        interval: str = "4h",
        limit: int = 200,
        allowed_symbols: tuple[str, ...] | None = None,
    ) -> dict[str, object]:
        """返回指定币种的标准化图表数据。"""

        normalized_symbol = symbol.strip().upper()
        active_interval = normalize_market_interval(interval)
        catalog_whitelist = tuple(self._catalog_service.get_whitelist())

        if allowed_symbols is not None:
            allowed_set = {item.strip().upper() for item in allowed_symbols if item.strip()}
            if normalized_symbol not in allowed_set:
                chart = self._read_base_chart(
                    symbol=symbol,
                    interval=active_interval,
                    limit=limit,
                    allowed_symbols=allowed_symbols,
                )
                strategy_context = _build_empty_strategy_context(normalized_symbol, "symbol_not_in_market_whitelist")
                markers = build_empty_marker_groups()
                return {
                    "items": [],
                    "overlays": dict(chart.get("overlays") or {}),
                    "markers": markers,
                    "active_interval": active_interval,
                    "supported_intervals": get_supported_market_intervals(),
                    "multi_timeframe_summary": [],
                    "strategy_context": strategy_context,
                    "research_cockpit": build_symbol_research_cockpit(
                        symbol=normalized_symbol,
                        recommended_strategy=str(strategy_context.get("recommended_strategy", "none")),
                        evaluation=_resolve_primary_evaluation(
                            str(strategy_context.get("recommended_strategy", "none")),
                            dict(strategy_context.get("evaluations") or {}),
                        ),
                        research_summary=None,
                        markers=markers,
                    ),
                }
        chart = self._read_base_chart(
            symbol=symbol,
            interval=active_interval,
            limit=limit,
            allowed_symbols=allowed_symbols,
        )
        items = list(chart.get("items", []))
        normalized_catalog_whitelist = tuple(item.strip().upper() for item in catalog_whitelist if item.strip())
        strategy_chart_cache: ChartCache = {}
        if normalized_symbol in normalized_catalog_whitelist:
            strategy_chart_cache[_build_chart_cache_key(active_interval, normalized_catalog_whitelist)] = {
                "limit": limit,
                "chart": {
                    "items": items,
                    "overlays": dict(chart.get("overlays") or {}),
                },
            }
        summary_cache: dict[str, dict[str, object]] = {}

        def resolve_interval_summary(candidate_interval: str) -> dict[str, object]:
            normalized_interval = normalize_market_interval(candidate_interval)
            if normalized_interval not in summary_cache:
                summary_cache[normalized_interval] = self._build_market_strategy_summary(
                    normalized_symbol,
                    catalog_whitelist,
                    interval=normalized_interval,
                    chart_cache=strategy_chart_cache,
                )
            return summary_cache[normalized_interval]

        multi_timeframe_summary = build_multi_timeframe_summary(
            symbol=normalized_symbol,
            intervals=("1d", "4h", "1h", "15m"),
            evaluate_interval=resolve_interval_summary,
        )
        summary = summary_cache.get(active_interval) or self._build_market_strategy_summary(
            normalized_symbol,
            catalog_whitelist,
            interval=active_interval,
            chart_cache=strategy_chart_cache,
        )
        strategy_context = _build_strategy_context(
            symbol=normalized_symbol,
            recommended_strategy=str(summary.get("recommended_strategy", "none")),
            trend_state=str(summary.get("trend_state", "neutral")),
            strategy_summary=dict(summary.get("strategy_summary") or {}),
        )
        markers = _build_strategy_markers(items, strategy_context)
        research_summary = self._get_symbol_research(normalized_symbol)
        return {
            "items": items,
            "overlays": dict(chart.get("overlays") or {}),
            "markers": markers,
            "active_interval": active_interval,
            "supported_intervals": get_supported_market_intervals(),
            "multi_timeframe_summary": multi_timeframe_summary,
            "strategy_context": strategy_context,
            "research_cockpit": build_symbol_research_cockpit(
                symbol=normalized_symbol,
                recommended_strategy=str(strategy_context.get("recommended_strategy", "none")),
                evaluation=_resolve_primary_evaluation(
                    str(strategy_context.get("recommended_strategy", "none")),
                    dict(strategy_context.get("evaluations") or {}),
                ),
                research_summary=research_summary,
                markers=markers,
            ),
        }

    def _read_base_chart(
        self,
        *,
        symbol: str,
        interval: str,
        limit: int,
        allowed_symbols: tuple[str, ...] | None,
    ) -> dict[str, object]:
        """读取不带策略上下文的原始图表数据。"""

        if allowed_symbols is not None:
            normalized_allowed_symbols = {item.strip().upper() for item in allowed_symbols if item.strip()}
            normalized_symbol = symbol.strip().upper()
            if normalized_symbol not in normalized_allowed_symbols:
                warnings = [f"symbol_not_in_market_whitelist:{normalized_symbol}"]
                return {
                    "items": [],
                    "overlays": build_indicator_summary([], warnings=warnings),
                }

        rows = self._client.get_klines(symbol=symbol, interval=interval, limit=limit)
        items, warnings = _normalize_kline_rows(rows)
        return {
            "items": items,
            "overlays": build_indicator_summary(items, warnings=warnings),
        }

    def _build_market_strategy_summary(
        self,
        symbol: str,
        catalog_whitelist: tuple[str, ...],
        interval: str | None = None,
        chart_cache: ChartCache | None = None,
    ) -> dict[str, object]:
        """给市场快照补上最小策略视角。"""

        normalized_whitelist = {item.strip().upper() for item in catalog_whitelist if item.strip()}
        research_summary = self._get_symbol_research(symbol)
        breakout_result = self._evaluate_catalog_strategy(
            symbol,
            "trend_breakout",
            tuple(normalized_whitelist),
            interval=interval,
            chart_cache=chart_cache,
            research_summary=research_summary,
        )
        pullback_result = self._evaluate_catalog_strategy(
            symbol,
            "trend_pullback",
            tuple(normalized_whitelist),
            interval=interval,
            chart_cache=chart_cache,
            research_summary=research_summary,
        )
        preferred_strategy, trend_state = _classify_market_state(breakout_result, pullback_result)

        return {
            "is_whitelisted": symbol in normalized_whitelist,
            "recommended_strategy": preferred_strategy,
            "trend_state": trend_state,
            "strategy_summary": {
                "trend_breakout": breakout_result,
                "trend_pullback": pullback_result,
            },
        }

    def _evaluate_catalog_strategy(
        self,
        symbol: str,
        strategy_key: str,
        allowed_symbols: tuple[str, ...],
        interval: str | None = None,
        chart_cache: ChartCache | None = None,
        research_summary: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """按策略目录默认参数评估当前 symbol。"""

        strategy = self._find_catalog_strategy(strategy_key)
        if strategy is None:
            return {
                "strategy_id": strategy_key,
                "symbol": symbol,
                "decision": "evaluation_unavailable",
                "reason": "strategy_not_in_catalog",
            }

        default_params = dict(strategy.get("default_params") or {})
        timeframe = normalize_market_interval(interval) if interval is not None else _parse_text_param(default_params.get("timeframe"))
        lookback_bars = _parse_positive_int(default_params.get("lookback_bars"))
        extra_param_key = "breakout_buffer_pct" if strategy_key == "trend_breakout" else "pullback_depth_pct"
        extra_param_value = _parse_decimal(default_params.get(extra_param_key))

        if timeframe is None or lookback_bars is None or extra_param_value is None:
            return {
                "strategy_id": strategy_key,
                "symbol": symbol,
                "decision": "evaluation_unavailable",
                "reason": "invalid_catalog_defaults",
            }

        chart = self._read_strategy_chart(
            symbol=symbol,
            interval=timeframe,
            limit=lookback_bars + 1,
            allowed_symbols=allowed_symbols,
            chart_cache=chart_cache,
        )
        items = list(chart.get("items", []))
        if not items:
            return {
                "strategy_id": strategy_key,
                "symbol": symbol,
                "decision": "evaluation_unavailable",
                "reason": "empty_chart",
            }

        if strategy_key == "trend_breakout":
            return apply_research_soft_gate(
                evaluate_trend_breakout(
                    symbol,
                    items,
                    timeframe=timeframe,
                    lookback_bars=lookback_bars,
                    breakout_buffer_pct=extra_param_value,
                ),
                research_summary,
            )

        return apply_research_soft_gate(
            evaluate_trend_pullback(
                symbol,
                items,
                timeframe=timeframe,
                lookback_bars=lookback_bars,
                pullback_depth_pct=extra_param_value,
            ),
            research_summary,
        )

    def _read_strategy_chart(
        self,
        *,
        symbol: str,
        interval: str,
        limit: int,
        allowed_symbols: tuple[str, ...],
        chart_cache: ChartCache | None,
    ) -> dict[str, object]:
        """读取策略评估图表，并在单次请求内复用。"""

        if chart_cache is None:
            return self._read_base_chart(
                symbol=symbol,
                interval=interval,
                limit=limit,
                allowed_symbols=allowed_symbols,
            )

        cache_key = _build_chart_cache_key(interval, allowed_symbols)
        cached = chart_cache.get(cache_key)
        if cached is not None and int(cached.get("limit", 0) or 0) >= limit:
            return dict(cached.get("chart") or {})

        chart = self._read_base_chart(
            symbol=symbol,
            interval=interval,
            limit=limit,
            allowed_symbols=allowed_symbols,
        )
        chart_cache[cache_key] = {
            "limit": limit,
            "chart": {
                "items": list(chart.get("items", [])),
                "overlays": dict(chart.get("overlays") or {}),
            },
        }
        return chart

    def _find_catalog_strategy(self, strategy_key: str) -> dict[str, object] | None:
        """读取策略目录项。"""

        catalog = self._catalog_service.get_catalog()
        for strategy in catalog.get("strategies", []):
            if strategy.get("key") == strategy_key:
                return strategy
        return None

    def _get_symbol_research(self, symbol: str) -> dict[str, object] | None:
        """读取单个币种研究摘要。"""

        getter = getattr(self._research_reader, "get_symbol_research", None)
        if callable(getter):
            return getter(symbol)
        return None


class _NullResearchReader:
    """研究层未注入时的空读取器。"""

    @staticmethod
    def get_symbol_research(symbol: str) -> dict[str, object] | None:
        return None


def _build_chart_cache_key(interval: str, allowed_symbols: tuple[str, ...] | None) -> tuple[str, tuple[str, ...] | None]:
    """生成请求内图表缓存键。"""

    if allowed_symbols is None:
        return interval, None
    normalized_symbols = sorted({item.strip().upper() for item in allowed_symbols if item.strip()})
    return interval, tuple(normalized_symbols)


def _classify_market_state(
    breakout_result: dict[str, object],
    pullback_result: dict[str, object],
) -> tuple[str, str]:
    """把两套策略的最小结果收敛成市场页可读状态。"""

    breakout_decision = str(breakout_result.get("decision", "evaluation_unavailable"))
    pullback_decision = str(pullback_result.get("decision", "evaluation_unavailable"))

    if breakout_decision == "signal":
        return "trend_breakout", "uptrend"
    if pullback_decision == "signal":
        return "trend_pullback", "pullback"
    if pullback_decision == "watch":
        return "trend_pullback", "pullback"
    if breakout_decision == "watch":
        return "trend_breakout", "uptrend"
    return "none", "neutral"


def _resolve_primary_evaluation(
    recommended_strategy: str,
    strategy_summary: dict[str, dict[str, object]],
) -> dict[str, object]:
    """返回当前页面最该展示的主评估结果。"""

    if recommended_strategy in strategy_summary:
        return dict(strategy_summary[recommended_strategy] or {})
    for strategy_key in ("trend_breakout", "trend_pullback"):
        if strategy_key in strategy_summary:
            return dict(strategy_summary[strategy_key] or {})
    return {}


def _build_empty_strategy_context(symbol: str, reason: str) -> dict[str, object]:
    """返回空图表或白名单外时的策略上下文。"""

    unavailable = {
        "strategy_id": "unavailable",
        "symbol": symbol,
        "decision": "evaluation_unavailable",
        "reason": reason,
        "overlays": {"sample_size": 0},
    }
    return {
        "recommended_strategy": "none",
        "trend_state": "neutral",
        "next_step": "当前 symbol 还不在可观察范围，先回市场页检查白名单。",
        "evaluations": {
            "trend_breakout": dict(unavailable),
            "trend_pullback": dict(unavailable),
        },
    }


def _build_strategy_context(
    *,
    symbol: str,
    recommended_strategy: str,
    trend_state: str,
    strategy_summary: dict[str, dict[str, object]],
) -> dict[str, object]:
    """把策略摘要整理成图表页可直接消费的解释结构。"""

    if recommended_strategy == "trend_breakout":
        next_step = "优先看突破参考线，若继续走强，再进入策略中心执行 dry-run。"
    elif recommended_strategy == "trend_pullback":
        next_step = "优先盯住回踩位和失效位，回踩确认后再进入策略中心。"
    else:
        next_step = "当前没有明确优势策略，先观察，不急着派发。"
    return {
        "recommended_strategy": recommended_strategy if recommended_strategy in {"trend_breakout", "trend_pullback"} else "none",
        "trend_state": trend_state if trend_state in {"uptrend", "pullback"} else "neutral",
        "next_step": next_step,
        "evaluations": strategy_summary,
        "primary_reason": _resolve_primary_reason(recommended_strategy, strategy_summary),
    }


def _resolve_primary_reason(recommended_strategy: str, strategy_summary: dict[str, dict[str, object]]) -> str:
    """返回当前最值得看的理由。"""

    if recommended_strategy in strategy_summary:
        return str(strategy_summary[recommended_strategy].get("reason", "n/a"))
    for strategy_key in ("trend_breakout", "trend_pullback"):
        if strategy_key in strategy_summary:
            return str(strategy_summary[strategy_key].get("reason", "n/a"))
    return "n/a"


def _build_strategy_markers(items: list[dict[str, object]], strategy_context: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    """根据当前策略判断生成图表页要展示的信号点和止损参考。"""

    if not items:
        return build_empty_marker_groups()

    latest = items[-1]
    latest_time = int(latest.get("close_time") or latest.get("open_time") or 0)
    latest_price = str(latest.get("close") or "")
    evaluations = dict(strategy_context.get("evaluations") or {})
    markers = build_empty_marker_groups()

    for strategy_key, raw_evaluation in evaluations.items():
        evaluation = dict(raw_evaluation or {})
        overlays = dict(evaluation.get("overlays") or {})
        decision = str(evaluation.get("decision", "evaluation_unavailable"))
        reason = str(evaluation.get("reason", "n/a"))
        entry_price = (
            overlays.get("breakout_threshold")
            or overlays.get("pullback_level")
            or overlays.get("latest_close")
            or latest_price
        )
        stop_price = overlays.get("recent_low") or overlays.get("invalidation_level")

        if decision == "signal":
            markers["signals"].append(
                {
                    "strategy_id": strategy_key,
                    "time": latest_time,
                    "price": str(overlays.get("latest_close") or latest_price),
                    "label": "signal",
                    "reason": reason,
                }
            )
        if decision in {"signal", "watch"} and entry_price:
            markers["entries"].append(
                {
                    "strategy_id": strategy_key,
                    "time": latest_time,
                    "price": str(entry_price),
                    "label": "entry",
                    "reason": reason,
                }
            )
        if stop_price:
            markers["stops"].append(
                {
                    "strategy_id": strategy_key,
                    "time": latest_time,
                    "price": str(stop_price),
                    "label": "stop",
                    "reason": reason,
                }
            )
    return markers


def _parse_text_param(value: object) -> str | None:
    """读取非空文本参数。"""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


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


def _parse_decimal(value: object) -> Decimal | None:
    """读取数值参数。"""

    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None


def _normalize_kline_rows(rows: list[list[object]]) -> tuple[list[dict[str, object]], list[str]]:
    """把 Binance K 线数组统一成控制平面的图表结构，并跳过坏行。"""

    normalized_rows: list[dict[str, object]] = []
    warnings: list[str] = []
    for index, row in enumerate(rows):
        try:
            if len(row) < 7:
                raise ValueError("kline row has insufficient columns")
            normalized_rows.append(
                {
                    "open_time": int(row[0]),
                    "open": str(row[1]),
                    "high": str(row[2]),
                    "low": str(row[3]),
                    "close": str(row[4]),
                    "volume": str(row[5]),
                    "close_time": int(row[6]),
                }
            )
        except (TypeError, ValueError, IndexError):
            warnings.append(f"invalid_kline_row:{index}")
    return normalized_rows, warnings
