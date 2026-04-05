"""集中式策略目录服务。

这个文件只负责返回首批固定策略、默认白名单和统一目录视图，不承担执行逻辑。
"""

from __future__ import annotations

from copy import deepcopy


class StrategyCatalogService:
    """提供固定的策略目录和默认交易白名单。"""

    def __init__(self) -> None:
        self._whitelist: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
        self._strategies: tuple[dict[str, object], ...] = (
            {
                "key": "trend_breakout",
                "display_name": "趋势突破",
                "description": "顺着趋势等待关键区间突破后入场。",
                "default_params": {
                    "timeframe": "1h",
                    "lookback_bars": 20,
                    "breakout_buffer_pct": 0.5,
                },
            },
            {
                "key": "trend_pullback",
                "display_name": "趋势回调",
                "description": "在趋势中等待回调完成后顺势入场。",
                "default_params": {
                    "timeframe": "1h",
                    "lookback_bars": 20,
                    "pullback_depth_pct": 1.0,
                },
            },
        )
        self._strategy_template_aliases: dict[str, str] = {
            "trend_breakout_timing": "trend_breakout",
            "trend_pullback_timing": "trend_pullback",
        }

    def get_whitelist(self) -> list[str]:
        """返回默认允许交易的币种白名单。"""

        return list(self._whitelist)

    def list_strategies(self) -> list[dict[str, object]]:
        """返回首批固定策略目录。"""

        return [deepcopy(strategy) for strategy in self._strategies]

    def get_catalog(self) -> dict[str, object]:
        """返回目录总览，供只读路由直接输出。"""

        return {
            "whitelist": self.get_whitelist(),
            "strategies": self.list_strategies(),
        }

    def resolve_strategy_id(self, key_or_template: str) -> int | None:
        """把策略 key 或研究模板名映射成当前策略实例编号。"""

        normalized = str(key_or_template or "").strip()
        if not normalized:
            return None
        strategy_key = self._strategy_template_aliases.get(normalized, normalized)
        for index, strategy in enumerate(self._strategies, start=1):
            if str(strategy.get("key", "")) == strategy_key:
                return index
        return None

    def resolve_strategy_key(self, strategy_id: int) -> str:
        """把策略实例编号映射回策略 key。"""

        if strategy_id <= 0 or strategy_id > len(self._strategies):
            return ""
        return str(self._strategies[strategy_id - 1].get("key", ""))


strategy_catalog_service = StrategyCatalogService()
