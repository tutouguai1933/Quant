"""研究层聚合服务。

这个文件负责触发训练、推理，并把研究结果转换成控制平面可读结构。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from services.api.app.services.market_service import MarketService
from services.api.app.services.strategy_catalog import strategy_catalog_service
from services.api.app.services.workbench_config_service import workbench_config_service
from services.worker.qlib_config import QlibConfigurationError, load_qlib_config
from services.worker.qlib_runner import QlibRunner


class ResearchService:
    """负责研究层读写和最小结果转换。"""

    def __init__(
        self,
        *,
        config_loader: Callable[[], object] | None = None,
        market_reader: MarketService | None = None,
        whitelist_provider: Callable[[], list[str]] | None = None,
        workbench_config_reader: Callable[[], dict[str, object]] | None = None,
        runtime_override_provider: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        self._config_loader = config_loader
        self._market_reader = market_reader or MarketService()
        self._whitelist_provider = whitelist_provider or strategy_catalog_service.get_whitelist
        self._workbench_config_reader = workbench_config_reader or workbench_config_service.get_config
        self._runtime_override_provider = runtime_override_provider or workbench_config_service.get_research_runtime_overrides
        self._market_cache: dict[tuple[str, str, int, tuple[str, ...]], list[dict[str, object]]] = {}

    def get_latest_result(self) -> dict[str, object]:
        """返回最近一次研究结果。"""

        config = self._load_runtime_config()
        if getattr(config, "status", "") != "ready":
            return self._build_unavailable_result(config)

        try:
            training_payload = self._read_json(config.paths.latest_training_path)
            inference_payload = self._read_json(config.paths.latest_inference_path)
            experiment_index = self._read_json(config.paths.experiment_index_path)
        except RuntimeError as exc:
            return {
                "status": "unavailable",
                "backend": config.backend,
                "qlib_available": config.qlib_available,
                "detail": str(exc),
                "latest_training": None,
                "latest_inference": None,
                "recent_runs": [],
                "symbols": {},
                "config_alignment": {"status": "unavailable", "stale_fields": [], "note": "研究结果文件暂不可读，无法校验当前配置是否对齐。"},
            }
        if not training_payload or not inference_payload:
            return {
                "status": "unavailable",
                "backend": config.backend,
                "qlib_available": config.qlib_available,
                "detail": self._build_missing_result_detail(
                    has_training=bool(training_payload),
                    has_inference=bool(inference_payload),
                ),
                "latest_training": training_payload,
                "latest_inference": inference_payload,
                "recent_runs": list((experiment_index or {}).get("items") or []),
                "symbols": {},
                "config_alignment": {"status": "unavailable", "stale_fields": [], "note": "研究结果还不完整，暂时无法对齐当前配置。"},
            }
        symbols = {
            str(item.get("symbol", "")): item
            for item in list((inference_payload or {}).get("signals", []))
            if str(item.get("symbol", "")).strip()
        }
        config_alignment = self._build_config_alignment(
            workbench_config=self._workbench_config_reader(),
            training_payload=training_payload,
            inference_payload=inference_payload,
        )
        return {
            "status": "ready",
            "backend": config.backend,
            "qlib_available": config.qlib_available,
            "detail": config.detail,
            "latest_training": training_payload,
            "latest_inference": inference_payload,
            "recent_runs": list((experiment_index or {}).get("items") or []),
            "symbols": symbols,
            "config_alignment": config_alignment,
        }

    def run_training(self) -> dict[str, object]:
        """触发一次训练。"""

        config = self._load_runtime_config()
        runner = QlibRunner(config=config)
        dataset, market_cache = self._prepare_dataset()
        result = runner.train(dataset)
        result["market_cache"] = market_cache
        return result

    def run_inference(self) -> dict[str, object]:
        """触发一次推理。"""

        config = self._load_runtime_config()
        runner = QlibRunner(config=config)
        dataset, market_cache = self._prepare_dataset()
        result = runner.infer(dataset)
        result["market_cache"] = market_cache
        return result

    def get_symbol_research(self, symbol: str) -> dict[str, object] | None:
        """读取单个币种最近一次研究摘要。"""

        latest = self.get_latest_result()
        symbols = dict(latest.get("symbols") or {})
        return symbols.get(symbol.strip().upper())

    def get_factory_snapshot(self) -> dict[str, object]:
        """返回研究工厂候选总览。"""

        from services.api.app.services.research_factory_service import ResearchFactoryService

        return ResearchFactoryService(result_provider=self.get_latest_result).build_snapshot()

    def get_factory_symbol(self, symbol: str) -> dict[str, object] | None:
        """返回单个币种的研究候选摘要。"""

        from services.api.app.services.research_factory_service import ResearchFactoryService

        return ResearchFactoryService(result_provider=self.get_latest_result).get_symbol_snapshot(symbol)

    def get_factory_report(self) -> dict[str, object]:
        """返回统一研究报告。"""

        from services.api.app.services.research_factory_service import ResearchFactoryService

        return ResearchFactoryService(result_provider=self.get_latest_result).build_report()

    def get_research_recommendation(self) -> dict[str, object] | None:
        """返回当前最值得继续进入执行链的研究候选。"""

        report = self.get_factory_report()
        candidates = list(report.get("candidates") or [])
        if not candidates:
            return None
        ready_items = [item for item in candidates if bool(item.get("allowed_to_dry_run"))]
        source_items = ready_items or candidates
        recommendation = sorted(source_items, key=_candidate_sort_key)[0]
        dry_run_gate = dict(recommendation.get("dry_run_gate") or {})
        return {
            "symbol": str(recommendation.get("symbol", "")),
            "score": str(recommendation.get("score", "")),
            "allowed_to_dry_run": bool(recommendation.get("allowed_to_dry_run")),
            "allowed_to_live": bool(recommendation.get("allowed_to_live")),
            "forced_for_validation": bool(recommendation.get("forced_for_validation")),
            "forced_reason": str(recommendation.get("forced_reason", "")),
            "strategy_template": str(recommendation.get("strategy_template", "")),
            "dry_run_gate": dry_run_gate,
            "live_gate": dict(recommendation.get("live_gate") or {}),
            "next_action": str(recommendation.get("next_action", "")) or str(report.get("overview", {}).get("recommended_action", "")),
            "review_status": str(recommendation.get("review_status", "")),
            "execution_priority": int(recommendation.get("execution_priority", 999999) or 999999),
            "failure_reasons": list(dry_run_gate.get("reasons") or []),
            "recommended_for_execution": bool(recommendation.get("allowed_to_dry_run")),
        }

    def _prepare_dataset(self) -> tuple[dict[str, dict[str, list[dict[str, object]]]], dict[str, int]]:
        """准备最小研究输入。"""

        dataset: dict[str, dict[str, list[dict[str, object]]]] = {}
        whitelist = list(self._whitelist_provider())
        workbench_config = self._workbench_config_reader()
        data_config = dict(workbench_config.get("data") or {})
        selected_symbols = self._resolve_selected_symbols(data_config=data_config, whitelist=whitelist)
        selected_timeframes = self._resolve_selected_timeframes(data_config=data_config)
        sample_limit = int(data_config.get("sample_limit", 120) or 120)
        lookback_days = int(data_config.get("lookback_days", 30) or 30)
        cache_summary = {
            "request_count": 0,
            "reused_count": 0,
            "fresh_count": 0,
            "scope": "service-instance",
            "refresh_rule": "service_restart",
        }
        for symbol in selected_symbols:
            candles_1h: list[dict[str, object]] = []
            candles_4h: list[dict[str, object]] = []
            reused_1h = False
            reused_4h = False
            if "1h" in selected_timeframes:
                limit_1h = _resolve_research_fetch_limit(timeframe="1h", sample_limit=sample_limit, lookback_days=lookback_days)
                chart_1h, reused_1h = self._read_market_chart_cached(
                    symbol=symbol,
                    interval="1h",
                    limit=limit_1h,
                    allowed_symbols=tuple(whitelist),
                )
                candles_1h = list(chart_1h.get("items", []))
                cache_summary["request_count"] += 1
            if "4h" in selected_timeframes:
                limit_4h = _resolve_research_fetch_limit(timeframe="4h", sample_limit=sample_limit, lookback_days=lookback_days)
                chart_4h, reused_4h = self._read_market_chart_cached(
                    symbol=symbol,
                    interval="4h",
                    limit=limit_4h,
                    allowed_symbols=tuple(whitelist),
                )
                candles_4h = list(chart_4h.get("items", []))
                cache_summary["request_count"] += 1
            cache_summary["reused_count"] += int(reused_1h) + int(reused_4h)
            cache_summary["fresh_count"] += int(("1h" in selected_timeframes) and not reused_1h) + int(("4h" in selected_timeframes) and not reused_4h)
            if candles_1h or candles_4h:
                dataset[symbol] = {
                    "candles_1h": candles_1h,
                    "candles_4h": candles_4h,
                }
        if not dataset:
            raise QlibConfigurationError("研究层没有拿到可用市场样本")
        return dataset, cache_summary

    @staticmethod
    def _resolve_selected_symbols(*, data_config: dict[str, object], whitelist: list[str]) -> list[str]:
        """解析研究层要消费的标的列表。"""

        raw_symbols = data_config.get("selected_symbols")
        if raw_symbols is None:
            return whitelist
        selected_symbols = [
            item
            for item in [str(symbol).strip().upper() for symbol in list(raw_symbols or [])]
            if item in whitelist
        ]
        if not selected_symbols:
            raise QlibConfigurationError("数据工作台当前没有选中研究标的，请先至少勾选一个币种。")
        return selected_symbols

    @staticmethod
    def _resolve_selected_timeframes(*, data_config: dict[str, object]) -> list[str]:
        """解析研究层要消费的周期列表。"""

        raw_timeframes = data_config.get("timeframes")
        if raw_timeframes is None:
            return ["4h", "1h"]
        selected_timeframes = [
            item
            for item in [str(interval).strip() for interval in list(raw_timeframes or [])]
            if item in {"1h", "4h"}
        ]
        if not selected_timeframes:
            raise QlibConfigurationError("数据工作台当前没有选中研究周期，请先至少勾选一个周期。")
        return selected_timeframes

    def _load_runtime_config(self):
        """加载研究运行配置，并叠加工作台配置覆盖项。"""

        if self._config_loader is not None:
            return self._config_loader()
        env = dict(os.environ)
        env.update(self._runtime_override_provider())
        return load_qlib_config(env=env)

    def _read_market_chart_cached(
        self,
        *,
        symbol: str,
        interval: str,
        limit: int,
        allowed_symbols: tuple[str, ...],
    ) -> tuple[dict[str, object], bool]:
        """优先复用已读取的市场图表数据。"""

        cache_key = (
            symbol.strip().upper(),
            interval,
            limit,
            tuple(sorted(item.strip().upper() for item in allowed_symbols)),
        )
        cached = self._market_cache.get(cache_key)
        if cached is not None:
            return {"items": list(cached)}, True
        chart = self._market_reader.get_symbol_chart(
            symbol=symbol,
            interval=interval,
            limit=limit,
            allowed_symbols=allowed_symbols,
        )
        items = list(chart.get("items", []))
        self._market_cache[cache_key] = list(items)
        return {"items": items}, False

    @staticmethod
    def _read_json(path: Path) -> dict[str, object] | None:
        """读取 JSON 文件。"""

        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"研究结果文件暂不可读：{path}") from exc

    @staticmethod
    def _build_unavailable_result(config: object) -> dict[str, object]:
        """构造研究层不可执行状态。"""

        return {
            "status": "unavailable",
            "backend": getattr(config, "backend", "qlib-fallback"),
            "qlib_available": bool(getattr(config, "qlib_available", False)),
            "detail": str(getattr(config, "detail", "研究层未就绪")),
            "latest_training": None,
            "latest_inference": None,
            "recent_runs": [],
            "symbols": {},
            "config_alignment": {"status": "unavailable", "stale_fields": [], "note": "研究层未就绪，暂时无法校验配置对齐。"},
        }

    @staticmethod
    def _build_missing_result_detail(*, has_training: bool, has_inference: bool) -> str:
        """构造研究结果缺失时的状态说明。"""

        if has_training and not has_inference:
            return "研究层已有训练结果，但还没有推理结果"
        if has_inference and not has_training:
            return "研究层已有推理结果，但训练结果缺失"
        return "研究层还没有可用训练和推理结果"

    @staticmethod
    def _build_config_alignment(
        *,
        workbench_config: dict[str, object],
        training_payload: dict[str, object],
        inference_payload: dict[str, object],
    ) -> dict[str, object]:
        """比较当前工作台配置和最近一次研究结果是否还对齐。"""

        data_config = dict(workbench_config.get("data") or {})
        features_config = dict(workbench_config.get("features") or {})
        research_config = dict(workbench_config.get("research") or {})
        backtest_config = dict(workbench_config.get("backtest") or {})
        thresholds_config = dict(workbench_config.get("thresholds") or {})

        training_context = dict(training_payload.get("training_context") or {})
        training_parameters = dict(training_context.get("parameters") or {})
        inference_context = dict(inference_payload.get("inference_context") or {})
        input_summary = dict(inference_context.get("input_summary") or {})

        stale_fields: list[str] = []

        if sorted(str(item) for item in list(data_config.get("selected_symbols") or [])) != sorted(
            str(item) for item in list(training_context.get("symbols") or [])
        ):
            stale_fields.append("selected_symbols")
        if sorted(str(item) for item in list(data_config.get("timeframes") or [])) != sorted(
            str(item) for item in list(training_context.get("timeframes") or [])
        ):
            stale_fields.append("timeframes")
        if str(data_config.get("sample_limit", "")) != str(training_parameters.get("sample_limit", "")):
            stale_fields.append("sample_limit")
        if str(data_config.get("lookback_days", "")) != str(training_parameters.get("lookback_days", input_summary.get("lookback_days", ""))):
            stale_fields.append("lookback_days")

        current_pairs = {
            "research_template": str(research_config.get("research_template", "")),
            "model_key": str(research_config.get("model_key", "")),
            "label_mode": str(research_config.get("label_mode", "")),
            "label_target_pct": str(research_config.get("label_target_pct", "")),
            "label_stop_pct": str(research_config.get("label_stop_pct", "")),
            "holding_window_min_days": str(research_config.get("min_holding_days", "")),
            "holding_window_max_days": str(research_config.get("max_holding_days", "")),
            "outlier_policy": str(features_config.get("outlier_policy", "")),
            "normalization_policy": str(features_config.get("normalization_policy", "")),
            "sample_limit": str(data_config.get("sample_limit", "")),
            "lookback_days": str(data_config.get("lookback_days", "")),
            "backtest_fee_bps": str(backtest_config.get("fee_bps", "")),
            "backtest_slippage_bps": str(backtest_config.get("slippage_bps", "")),
            "dry_run_min_score": str(thresholds_config.get("dry_run_min_score", "")),
            "dry_run_min_positive_rate": str(thresholds_config.get("dry_run_min_positive_rate", "")),
            "dry_run_min_net_return_pct": str(thresholds_config.get("dry_run_min_net_return_pct", "")),
            "dry_run_min_sharpe": str(thresholds_config.get("dry_run_min_sharpe", "")),
            "dry_run_max_drawdown_pct": str(thresholds_config.get("dry_run_max_drawdown_pct", "")),
            "dry_run_max_loss_streak": str(thresholds_config.get("dry_run_max_loss_streak", "")),
            "live_min_score": str(thresholds_config.get("live_min_score", "")),
            "live_min_positive_rate": str(thresholds_config.get("live_min_positive_rate", "")),
            "live_min_net_return_pct": str(thresholds_config.get("live_min_net_return_pct", "")),
        }
        runtime_pairs = {
            "research_template": str(training_parameters.get("research_template", input_summary.get("research_template", ""))),
            "model_key": str(training_parameters.get("model_key", input_summary.get("model_key", ""))),
            "label_mode": str(training_parameters.get("label_mode", input_summary.get("label_mode", ""))),
            "label_target_pct": str(training_parameters.get("label_target_pct", "")),
            "label_stop_pct": str(training_parameters.get("label_stop_pct", "")),
            "holding_window_min_days": str(training_parameters.get("holding_window_min_days", "")),
            "holding_window_max_days": str(training_parameters.get("holding_window_max_days", "")),
            "outlier_policy": str(training_parameters.get("outlier_policy", input_summary.get("outlier_policy", ""))),
            "normalization_policy": str(training_parameters.get("normalization_policy", input_summary.get("normalization_policy", ""))),
            "sample_limit": str(training_parameters.get("sample_limit", input_summary.get("sample_limit", ""))),
            "lookback_days": str(training_parameters.get("lookback_days", input_summary.get("lookback_days", ""))),
            "backtest_fee_bps": str(training_parameters.get("backtest_fee_bps", "")),
            "backtest_slippage_bps": str(training_parameters.get("backtest_slippage_bps", "")),
            "dry_run_min_score": str(input_summary.get("dry_run_min_score", "")),
            "dry_run_min_positive_rate": str(input_summary.get("dry_run_min_positive_rate", "")),
            "dry_run_min_net_return_pct": str(input_summary.get("dry_run_min_net_return_pct", "")),
            "dry_run_min_sharpe": str(input_summary.get("dry_run_min_sharpe", "")),
            "dry_run_max_drawdown_pct": str(input_summary.get("dry_run_max_drawdown_pct", "")),
            "dry_run_max_loss_streak": str(input_summary.get("dry_run_max_loss_streak", "")),
            "live_min_score": str(input_summary.get("live_min_score", "")),
            "live_min_positive_rate": str(input_summary.get("live_min_positive_rate", "")),
            "live_min_net_return_pct": str(input_summary.get("live_min_net_return_pct", "")),
        }
        if sorted(str(item) for item in list(features_config.get("primary_factors") or [])) != sorted(
            str(item) for item in list(training_parameters.get("primary_factors") or [])
        ):
            stale_fields.append("primary_factors")
        if sorted(str(item) for item in list(features_config.get("auxiliary_factors") or [])) != sorted(
            str(item) for item in list(training_parameters.get("auxiliary_factors") or [])
        ):
            stale_fields.append("auxiliary_factors")

        for key, current_value in current_pairs.items():
            if current_value != runtime_pairs.get(key, ""):
                stale_fields.append(key)

        if stale_fields:
            return {
                "status": "stale",
                "stale_fields": sorted(set(stale_fields)),
                "note": "当前页面配置已经变化，现有研究结果仍然基于上一轮训练/推理配置。",
            }
        return {
            "status": "aligned",
            "stale_fields": [],
            "note": "当前页面配置和最近一次研究结果已经对齐。",
        }


research_service = ResearchService()


def _resolve_research_fetch_limit(*, timeframe: str, sample_limit: int, lookback_days: int) -> int:
    """按时间窗口换算研究拉数长度。"""

    normalized_limit = max(int(sample_limit or 0), 1)
    normalized_days = max(int(lookback_days or 0), 1)
    bars_per_day = 24 if timeframe == "1h" else 6 if timeframe == "4h" else 1
    required_bars = normalized_days * bars_per_day
    return max(normalized_limit, required_bars)


def _candidate_sort_key(item: dict[str, object]) -> tuple[int, str]:
    """把推荐候选按 rank 和 symbol 做稳定排序。"""

    execution_priority = item.get("execution_priority")
    try:
        parsed_priority = int(execution_priority)
    except (TypeError, ValueError):
        parsed_priority = 999999
    rank = item.get("rank")
    try:
        parsed_rank = int(rank)
    except (TypeError, ValueError):
        parsed_rank = 999999
    return parsed_priority, parsed_rank, str(item.get("symbol", ""))
