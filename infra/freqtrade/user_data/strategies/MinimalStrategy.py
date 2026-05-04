"""Minimal strategy for backtesting - RSI + Trend filter."""

from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class MinimalStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False
    minimal_roi = {"0": 0.08}  # 8% ROI target
    stoploss = -0.08  # 8% initial stop loss
    trailing_stop = True
    trailing_stop_positive = 0.03  # Start trailing when 3% profit
    trailing_stop_positive_offset = 0.05  # Trail at 5% below peak when triggered
    trailing_only_offset_is_reached = True  # Only trail after 5% profit reached
    timeframe = "1h"
    startup_candle_count = 200  # Need 200 candles for SMA200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)
        dataframe["sma200"] = ta.SMA(dataframe["close"], timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        # Only enter when: RSI oversold AND price above SMA200 (bullish trend)
        dataframe.loc[
            (dataframe["rsi"] < 35) &
            (dataframe["close"] > dataframe["sma200"]),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe.loc[dataframe["rsi"] > 70, "exit_long"] = 1
        return dataframe