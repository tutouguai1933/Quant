"""集中式策略目录服务。

这个文件只负责返回首批固定策略、默认白名单和统一目录视图，不承担执行逻辑。
"""

from __future__ import annotations

from copy import deepcopy


class StrategyCatalogService:
    """提供固定的策略目录和默认交易白名单。"""

    def __init__(self) -> None:
        self._whitelist: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT")
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


strategy_catalog_service = StrategyCatalogService()
