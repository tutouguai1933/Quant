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

    def get_latest_result(self) -> dict[str, object]:
        """返回最近一次研究结果。"""

        config = self._config_loader()
        if getattr(config, "status", "") != "ready":
            return self._build_unavailable_result(config)

        try:
            training_payload = self._read_json(config.paths.latest_training_path)
            inference_payload = self._read_json(config.paths.latest_inference_path)
        except RuntimeError as exc:
            return {
                "status": "unavailable",
                "backend": config.backend,
                "qlib_available": config.qlib_available,
                "detail": str(exc),
                "latest_training": None,
                "latest_inference": None,
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
            "symbols": symbols,
        }

    def run_training(self) -> dict[str, object]:
        """触发一次训练。"""

        config = self._config_loader()
        runner = QlibRunner(config=config)
        return runner.train(self._prepare_dataset())

    def run_inference(self) -> dict[str, object]:
        """触发一次推理。"""

        config = self._config_loader()
        runner = QlibRunner(config=config)
        return runner.infer(self._prepare_dataset())

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

    def _prepare_dataset(self) -> dict[str, list[dict[str, object]]]:
        """准备最小研究输入。"""

        dataset: dict[str, list[dict[str, object]]] = {}
        whitelist = list(self._whitelist_provider())
        for symbol in whitelist:
            chart = self._market_reader.get_symbol_chart(
                symbol=symbol,
                interval="1h",
                limit=120,
                allowed_symbols=tuple(whitelist),
            )
            items = list(chart.get("items", []))
            if items:
                dataset[symbol] = items
        if not dataset:
            raise QlibConfigurationError("研究层没有拿到可用市场样本")
        return dataset

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
            "symbols": {},
        }


research_service = ResearchService()
