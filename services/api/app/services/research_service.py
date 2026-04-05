"""研究层聚合服务。

这个文件负责触发训练、推理，并把研究结果转换成控制平面可读结构。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from services.api.app.services.market_service import MarketService
from services.api.app.services.strategy_catalog import strategy_catalog_service
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
    ) -> None:
        self._config_loader = config_loader or load_qlib_config
        self._market_reader = market_reader or MarketService()
        self._whitelist_provider = whitelist_provider or strategy_catalog_service.get_whitelist
        self._market_cache: dict[tuple[str, str, int, tuple[str, ...]], list[dict[str, object]]] = {}

    def get_latest_result(self) -> dict[str, object]:
        """返回最近一次研究结果。"""

        config = self._config_loader()
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
            }
        symbols = {
            str(item.get("symbol", "")): item
            for item in list((inference_payload or {}).get("signals", []))
            if str(item.get("symbol", "")).strip()
        }
        return {
            "status": "ready",
            "backend": config.backend,
            "qlib_available": config.qlib_available,
            "detail": config.detail,
            "latest_training": training_payload,
            "latest_inference": inference_payload,
            "recent_runs": list((experiment_index or {}).get("items") or []),
            "symbols": symbols,
        }

    def run_training(self) -> dict[str, object]:
        """触发一次训练。"""

        config = self._config_loader()
        runner = QlibRunner(config=config)
        dataset, market_cache = self._prepare_dataset()
        result = runner.train(dataset)
        result["market_cache"] = market_cache
        return result

    def run_inference(self) -> dict[str, object]:
        """触发一次推理。"""

        config = self._config_loader()
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
            "forced_for_validation": bool(recommendation.get("forced_for_validation")),
            "forced_reason": str(recommendation.get("forced_reason", "")),
            "strategy_template": str(recommendation.get("strategy_template", "")),
            "dry_run_gate": dry_run_gate,
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
        cache_summary = {
            "request_count": 0,
            "reused_count": 0,
            "fresh_count": 0,
            "scope": "service-instance",
            "refresh_rule": "service_restart",
        }
        for symbol in whitelist:
            chart_1h, reused_1h = self._read_market_chart_cached(
                symbol=symbol,
                interval="1h",
                limit=120,
                allowed_symbols=tuple(whitelist),
            )
            chart_4h, reused_4h = self._read_market_chart_cached(
                symbol=symbol,
                interval="4h",
                limit=120,
                allowed_symbols=tuple(whitelist),
            )
            cache_summary["request_count"] += 2
            cache_summary["reused_count"] += int(reused_1h) + int(reused_4h)
            cache_summary["fresh_count"] += int(not reused_1h) + int(not reused_4h)
            candles_1h = list(chart_1h.get("items", []))
            candles_4h = list(chart_4h.get("items", []))
            if candles_1h or candles_4h:
                dataset[symbol] = {
                    "candles_1h": candles_1h,
                    "candles_4h": candles_4h,
                }
        if not dataset:
            raise QlibConfigurationError("研究层没有拿到可用市场样本")
        return dataset, cache_summary

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
        }

    @staticmethod
    def _build_missing_result_detail(*, has_training: bool, has_inference: bool) -> str:
        """构造研究结果缺失时的状态说明。"""

        if has_training and not has_inference:
            return "研究层已有训练结果，但还没有推理结果"
        if has_inference and not has_training:
            return "研究层已有推理结果，但训练结果缺失"
        return "研究层还没有可用训练和推理结果"


research_service = ResearchService()


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
