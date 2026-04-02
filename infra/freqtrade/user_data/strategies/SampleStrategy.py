"""最小 Freqtrade 策略。

这个文件只负责让 Spot dry-run 容器稳定启动。
当前不依赖它主动开仓，控制平面主要通过 REST 动作来验证执行链路。
"""

from __future__ import annotations

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class SampleStrategy(IStrategy):
    """最小可启动策略。"""

    INTERFACE_VERSION = 3
    can_short = False
    minimal_roi = {"0": 0.02}
    stoploss = -0.1
    timeframe = "1h"
    startup_candle_count = 30
    process_only_new_candles = True
    use_exit_signal = True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """当前阶段不额外计算指标。"""

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """默认不主动产生入场信号。"""

        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """默认不主动产生离场信号。"""

        dataframe["exit_long"] = 0
        return dataframe
