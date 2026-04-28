"""基于研究结论的真实交易策略。

策略核心：
1. 入场：综合评分 >= MIN_ENTRY_SCORE (0.60)，结合 RSI/MACD/成交量趋势确认
2. 止损追踪：盈利超过 TRAILING_STOP_TRIGGER (2%) 后启用移动止损
3. 退出：盈利达到 PROFIT_EXIT_RATIO (5%) 或持仓超过 MAX_HOLDING_HOURS (48h)

参数配置：
- QUANT_STRATEGY_MIN_ENTRY_SCORE = 0.60
- QUANT_STRATEGY_TRAILING_STOP_TRIGGER = 0.02
- QUANT_STRATEGY_TRAILING_STOP_DISTANCE = 0.01
- QUANT_STRATEGY_PROFIT_EXIT_RATIO = 0.05
- QUANT_STRATEGY_MAX_HOLDING_HOURS = 48
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from logging import getLogger
from typing import Optional

from pandas import DataFrame
import pandas as pd
import numpy as np

from freqtrade.strategy import IStrategy, merge_informative_pair

logger = getLogger(__name__)


def _read_env_decimal(key: str, default: float) -> float:
    """从环境变量读取浮点配置。"""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(Decimal(raw.strip()))
    except (InvalidOperation, ValueError):
        logger.warning("配置 %s=%s 解析失败，使用默认值 %s", key, raw, default)
        return default


def _read_env_int(key: str, default: int) -> int:
    """从环境变量读取整数配置。"""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        logger.warning("配置 %s=%s 解析失败，使用默认值 %s", key, raw, default)
        return default


# 策略配置参数（从环境变量读取）
MIN_ENTRY_SCORE = _read_env_decimal("QUANT_STRATEGY_MIN_ENTRY_SCORE", 0.60)
TRAILING_STOP_TRIGGER = _read_env_decimal("QUANT_STRATEGY_TRAILING_STOP_TRIGGER", 0.02)
TRAILING_STOP_DISTANCE = _read_env_decimal("QUANT_STRATEGY_TRAILING_STOP_DISTANCE", 0.01)
PROFIT_EXIT_RATIO = _read_env_decimal("QUANT_STRATEGY_PROFIT_EXIT_RATIO", 0.05)
MAX_HOLDING_HOURS = _read_env_int("QUANT_STRATEGY_MAX_HOLDING_HOURS", 48)

# 技术指标参数
RSI_PERIOD = _read_env_int("QUANT_RSI_PERIOD", 14)
RSI_OVERBUY_THRESHOLD = _read_env_decimal("QUANT_RSI_OVERBUY_THRESHOLD", 70)
RSI_OVERSELL_THRESHOLD = _read_env_decimal("QUANT_RSI_OVERSELL_THRESHOLD", 30)
MACD_FAST_PERIOD = _read_env_int("QUANT_MACD_FAST_PERIOD", 12)
MACD_SLOW_PERIOD = _read_env_int("QUANT_MACD_SLOW_PERIOD", 26)
MACD_SIGNAL_PERIOD = _read_env_int("QUANT_MACD_SIGNAL_PERIOD", 9)
EMA_FAST_PERIOD = _read_env_int("QUANT_EMA_FAST_PERIOD", 20)
EMA_SLOW_PERIOD = _read_env_int("QUANT_EMA_SLOW_PERIOD", 55)
VOLUME_TREND_PERIOD = _read_env_int("QUANT_VOLUME_TREND_PERIOD", 20)

# 权重配置
RESEARCH_SCORE_WEIGHT = 0.60
TREND_CONFIRM_WEIGHT = 0.20
INDICATOR_WEIGHT = 0.20


class SampleStrategy(IStrategy):
    """基于研究结论的真实交易策略。"""

    INTERFACE_VERSION = 3
    can_short = False
    minimal_roi = {"0": PROFIT_EXIT_RATIO}  # 使用配置的盈利目标
    stoploss = -0.10  # 基础止损 10%
    timeframe = "1h"
    startup_candle_count = 100  # 需要足够数据计算 MACD
    process_only_new_candles = True
    use_exit_signal = True
    use_custom_stoploss = True

    # 持仓追踪（用于移动止损和时间限制）
    _position_tracker: dict[str, dict] = {}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """计算技术指标：RSI、MACD、EMA、成交量趋势。"""

        if dataframe is None or len(dataframe) < 30:
            logger.warning("数据不足，无法计算指标")
            return dataframe

        # 计算 EMA 快线（20周期）
        dataframe["ema_fast"] = self._calculate_ema(
            dataframe["close"], EMA_FAST_PERIOD
        )

        # 计算 EMA 慢线（55周期）
        dataframe["ema_slow"] = self._calculate_ema(
            dataframe["close"], EMA_SLOW_PERIOD
        )

        # 计算 RSI
        dataframe["rsi"] = self._calculate_rsi(dataframe["close"], RSI_PERIOD)

        # 计算 MACD
        macd_result = self._calculate_macd(
            dataframe["close"],
            MACD_FAST_PERIOD,
            MACD_SLOW_PERIOD,
            MACD_SIGNAL_PERIOD,
        )
        dataframe["macd_line"] = macd_result["macd_line"]
        dataframe["macd_signal"] = macd_result["signal_line"]
        dataframe["macd_histogram"] = macd_result["histogram"]

        # 计算成交量趋势
        dataframe["volume_sma"] = dataframe["volume"].rolling(
            window=VOLUME_TREND_PERIOD, min_periods=1
        ).mean()
        dataframe["volume_ratio"] = (
            dataframe["volume"] / dataframe["volume_sma"]
        ).replace([np.inf, -np.inf], 1.0).fillna(1.0)

        # 量价配合分析
        dataframe["price_change"] = dataframe["close"].pct_change()
        dataframe["volume_signal"] = self._calculate_volume_signal(
            dataframe["volume_ratio"],
            dataframe["price_change"],
        )

        # 计算综合评分
        dataframe["entry_score"] = self._calculate_entry_score(dataframe)

        # RSI 信号
        dataframe["rsi_signal"] = self._calculate_rsi_signal(dataframe["rsi"])

        # MACD 趋势信号
        dataframe["macd_trend"] = self._calculate_macd_trend(dataframe["macd_histogram"])

        # 趋势确认
        dataframe["trend_confirmed"] = self._check_trend_confirmation(dataframe)

        logger.debug(
            "指标计算完成: %s, 最新评分=%.4f, RSI=%.2f, MACD趋势=%s",
            metadata.get("pair", "unknown"),
            dataframe["entry_score"].iloc[-1] if len(dataframe) > 0 else 0,
            dataframe["rsi"].iloc[-1] if len(dataframe) > 0 else 50,
            dataframe["macd_trend"].iloc[-1] if len(dataframe) > 0 else "neutral",
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """入场信号：综合评分 >= MIN_ENTRY_SCORE 且趋势确认。"""

        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""

        if len(dataframe) < 2:
            return dataframe

        # 入场条件：
        # 1. 综合评分 >= MIN_ENTRY_SCORE
        # 2. 趋势确认（EMA、RSI、MACD、成交量）
        # 3. RSI 不在超买区域（避免追高）
        # 4. MACD 趋势向上或中性

        latest = dataframe.iloc[-1]
        entry_score = latest.get("entry_score", 0)
        trend_confirmed = latest.get("trend_confirmed", False)
        rsi_signal = latest.get("rsi_signal", "neutral")
        macd_trend = latest.get("macd_trend", "neutral")

        # 检查入场条件
        score_met = entry_score >= MIN_ENTRY_SCORE
        trend_ok = trend_confirmed
        rsi_ok = rsi_signal != "overbought_risk"  # 不在超买风险区
        macd_ok = macd_trend in ("bullish", "neutral")  # MACD向上或中性

        if score_met and trend_ok and rsi_ok and macd_ok:
            dataframe.loc[dataframe.index[-1], "enter_long"] = 1
            dataframe.loc[dataframe.index[-1], "enter_tag"] = (
                f"score={entry_score:.2f}|rsi={rsi_signal}|macd={macd_trend}"
            )

            logger.info(
                "入场信号触发: %s, 评分=%.4f, 趋势确认=%s, RSI信号=%s, MACD趋势=%s",
                metadata.get("pair", "unknown"),
                entry_score,
                trend_confirmed,
                rsi_signal,
                macd_trend,
            )

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """退出信号：反向信号检测。"""

        dataframe["exit_long"] = 0

        if len(dataframe) < 2:
            return dataframe

        latest = dataframe.iloc[-1]

        # 退出条件：
        # 1. RSI 进入超买区域且价格开始下跌
        # 2. MACD 趋势转为向下
        # 3. 成交量萎缩且价格下跌

        rsi_signal = latest.get("rsi_signal", "neutral")
        macd_trend = latest.get("macd_trend", "neutral")
        volume_signal = latest.get("volume_signal", "neutral")
        price_change = latest.get("price_change", 0)

        should_exit = False
        exit_reason = ""

        # RSI 超买警告
        if rsi_signal == "overbought_risk" and price_change < 0:
            should_exit = True
            exit_reason = "rsi_overbought"

        # MACD 趋势反转
        if macd_trend == "bearish" and latest.get("macd_histogram", 0) < 0:
            should_exit = True
            exit_reason = "macd_bearish"

        # 成交量萎缩下跌
        if volume_signal == "low_volume_fall":
            should_exit = True
            exit_reason = "volume_fall"

        if should_exit:
            dataframe.loc[dataframe.index[-1], "exit_long"] = 1
            logger.info(
                "退出信号触发: %s, 原因=%s, RSI=%s, MACD=%s, VOL=%s",
                metadata.get("pair", "unknown"),
                exit_reason,
                rsi_signal,
                macd_trend,
                volume_signal,
            )

        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade: object,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> Optional[float]:
        """实现追踪止损。

        当盈利超过 TRAILING_STOP_TRIGGER (2%) 后，启用移动止损。
        止损距离为 TRAILING_STOP_DISTANCE (1%)。
        """

        if not after_fill:
            return None

        # 初始化持仓追踪
        if pair not in self._position_tracker:
            self._position_tracker[pair] = {
                "entry_time": current_time,
                "peak_profit": current_profit,
                "trailing_active": False,
            }

        tracker = self._position_tracker[pair]

        # 更峰值盈利
        if current_profit > tracker["peak_profit"]:
            tracker["peak_profit"] = current_profit

        # 检查是否触发追踪止损
        if not tracker["trailing_active"]:
            if current_profit >= TRAILING_STOP_TRIGGER:
                tracker["trailing_active"] = True
                logger.info(
                    "追踪止损激活: %s, 当前盈利=%.2f%%, 触发阈值=%.2f%%",
                    pair,
                    current_profit * 100,
                    TRAILING_STOP_TRIGGER * 100,
                )

        # 计算止损水平
        if tracker["trailing_active"]:
            # 追踪止损：峰值盈利 - 止损距离
            stop_profit = tracker["peak_profit"] - TRAILING_STOP_DISTANCE
            stoploss = stop_profit / current_profit if current_profit > 0 else -self.stoploss

            # 止损不能低于基础止损
            if stoploss < -self.stoploss:
                stoploss = -self.stoploss

            logger.debug(
                "追踪止损: %s, 峰值=%.2f%%, 止损位=%.2f%%, 当前=%.2f%%",
                pair,
                tracker["peak_profit"] * 100,
                stop_profit * 100,
                current_profit * 100,
            )

            return stoploss

        # 未激活时返回基础止损
        return None

    def custom_exit(
        self,
        pair: str,
        trade: object,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        """检查退出条件：盈利目标和持仓时间限制。"""

        # 初始化追踪
        if pair not in self._position_tracker:
            self._position_tracker[pair] = {
                "entry_time": trade.open_date_utc or current_time,
                "peak_profit": current_profit,
                "trailing_active": False,
            }

        tracker = self._position_tracker[pair]
        entry_time = tracker["entry_time"]

        # 检查盈利目标
        if current_profit >= PROFIT_EXIT_RATIO:
            logger.info(
                "盈利目标达成退出: %s, 盈利=%.2f%% >= 目标=%.2f%%",
                pair,
                current_profit * 100,
                PROFIT_EXIT_RATIO * 100,
            )
            self._position_tracker.pop(pair, None)
            return f"profit_target_{PROFIT_EXIT_RATIO:.0%}"

        # 检查持仓时间限制
        if entry_time:
            holding_duration = current_time - entry_time
            holding_hours = holding_duration.total_seconds() / 3600

            if holding_hours >= MAX_HOLDING_HOURS:
                logger.info(
                    "持仓时间超限退出: %s, 持仓=%.1f小时 >= 上限=%d小时",
                    pair,
                    holding_hours,
                    MAX_HOLDING_HOURS,
                )
                self._position_tracker.pop(pair, None)
                return f"time_limit_{MAX_HOLDING_HOURS}h"

        return None

    def _calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        """计算指数移动平均。"""
        return series.ewm(span=period, adjust=False).mean()

    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        """计算相对强弱指标。"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=period, min_periods=1).mean()
        avg_loss = loss.rolling(window=period, min_periods=1).mean()

        rs = avg_gain / avg_loss.replace(0, np.inf)
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50)

    def _calculate_macd(
        self,
        series: pd.Series,
        fast_period: int,
        slow_period: int,
        signal_period: int,
    ) -> dict:
        """计算 MACD 指标。"""
        ema_fast = self._calculate_ema(series, fast_period)
        ema_slow = self._calculate_ema(series, slow_period)

        macd_line = ema_fast - ema_slow
        signal_line = self._calculate_ema(macd_line, signal_period)
        histogram = macd_line - signal_line

        return {
            "macd_line": macd_line,
            "signal_line": signal_line,
            "histogram": histogram,
        }

    def _calculate_volume_signal(
        self,
        volume_ratio: pd.Series,
        price_change: pd.Series,
    ) -> pd.Series:
        """计算成交量信号。"""
        result = pd.Series("neutral", index=volume_ratio.index)

        # 成交量放大
        high_volume = volume_ratio > 1.2
        # 成交量萎缩
        low_volume = volume_ratio < 0.8

        # 量价齐升
        result.loc[high_volume & (price_change > 0)] = "bullish_volume"
        # 量价齐跌
        result.loc[high_volume & (price_change < 0)] = "bearish_volume"
        # 缩量上涨
        result.loc[low_volume & (price_change > 0)] = "low_volume_rise"
        # 缩量下跌
        result.loc[low_volume & (price_change < 0)] = "low_volume_fall"
        # 放量横盘
        result.loc[high_volume & (price_change == 0)] = "high_volume_neutral"

        return result

    def _calculate_rsi_signal(self, rsi: pd.Series) -> pd.Series:
        """计算 RSI 信号。"""
        result = pd.Series("neutral", index=rsi.index)

        # 超买区域（卖出机会，但做多时是风险）
        result.loc[rsi > RSI_OVERBUY_THRESHOLD] = "overbought_risk"
        # 超卖区域（买入机会）
        result.loc[rsi < RSI_OVERSELL_THRESHOLD] = "oversold_buy"

        return result

    def _calculate_macd_trend(self, histogram: pd.Series) -> pd.Series:
        """计算 MACD 趋势。"""
        result = pd.Series("neutral", index=histogram.index)

        result.loc[histogram > 0] = "bullish"
        result.loc[histogram < 0] = "bearish"

        return result

    def _check_trend_confirmation(self, dataframe: DataFrame) -> pd.Series:
        """检查趋势确认（综合 EMA、RSI、MACD、成交量）。"""
        if len(dataframe) < 2:
            return pd.Series(False, index=dataframe.index)

        # EMA 趋势：价格在 EMA 快线之上
        ema_trend = dataframe["close"] > dataframe["ema_fast"]

        # RSI 趋势：不在超买区域
        rsi_trend = dataframe["rsi"] < RSI_OVERBUY_THRESHOLD

        # MACD 趋势：向上或中性
        macd_trend = dataframe["macd_histogram"] >= 0

        # 成交量趋势：放大或正常
        volume_trend = dataframe["volume_ratio"] >= 0.8

        # 计算确认得分（需要至少3项满足）
        confirmation_score = (
            ema_trend.astype(int) +
            rsi_trend.astype(int) +
            macd_trend.astype(int) +
            volume_trend.astype(int)
        )

        # 需要至少3项确认
        return confirmation_score >= 3

    def _calculate_entry_score(self, dataframe: DataFrame) -> pd.Series:
        """计算综合入场评分。"""
        if len(dataframe) < 2:
            return pd.Series(0.0, index=dataframe.index)

        # 基础评分（假设研究评分，这里用技术指标模拟）
        # 实际应该从 API 获取研究评分

        # 趋势评分：EMA 金叉
        trend_score = 0.0
        ema_cross = dataframe["ema_fast"] > dataframe["ema_slow"]
        trend_score = ema_cross.astype(float) * TREND_CONFIRM_WEIGHT

        # 指标评分
        indicator_score = 0.0

        # RSI 评分：超卖加分，超买减分
        rsi_score = pd.Series(0.0, index=dataframe.index)
        rsi_score.loc[dataframe["rsi"] < RSI_OVERSELL_THRESHOLD] = 0.08
        rsi_score.loc[dataframe["rsi"] > RSI_OVERBUY_THRESHOLD] = -0.05
        rsi_score.loc[(dataframe["rsi"] >= RSI_OVERSELL_THRESHOLD) &
                      (dataframe["rsi"] <= RSI_OVERBUY_THRESHOLD)] = 0.04

        # MACD 评分：向上加分
        macd_score = pd.Series(0.0, index=dataframe.index)
        macd_score.loc[dataframe["macd_histogram"] > 0] = 0.08
        macd_score.loc[dataframe["macd_histogram"] == 0] = 0.02

        # 成交量评分：放量加分
        volume_score = pd.Series(0.0, index=dataframe.index)
        volume_score.loc[dataframe["volume_ratio"] > 1.2] = 0.04

        indicator_score = (rsi_score + macd_score + volume_score) / 3 * INDICATOR_WEIGHT

        # 综合评分
        base_score = 0.50  # 基础评分
        total_score = base_score + trend_score + indicator_score

        # 限制在 0-1 之间
        return total_score.clip(0.0, 1.0)


# 保持向后兼容：类名使用 SampleStrategy
# 真实策略逻辑在 QuantStrategy 实现