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

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from logging import getLogger
from typing import Optional

from pandas import DataFrame
import pandas as pd
import numpy as np

try:
    import requests
except ImportError:
    requests = None  # pragma: no cover - fallback when requests not installed

from freqtrade.strategy import IStrategy, merge_informative_pair

# Fix import path for Docker container - user_data is mounted at /freqtrade/user_data
import sys
sys.path.insert(0, '/freqtrade/user_data')
from config_helper import get_config

# 交易告警集成
try:
    TRADE_ALERT_ENABLED = get_config("QUANT_TRADE_ALERT_ENABLED", default="true", as_type="str").lower() == "true"
except Exception:
    TRADE_ALERT_ENABLED = False

logger = getLogger(__name__)


# 策略配置参数（使用统一配置接口）
# 回测优化：降低入场阈值，更容易触发交易信号
MIN_ENTRY_SCORE = float(get_config("QUANT_STRATEGY_MIN_ENTRY_SCORE", default=Decimal("0.35"), as_type="decimal"))
TRAILING_STOP_TRIGGER = float(get_config("QUANT_STRATEGY_TRAILING_STOP_TRIGGER", default=Decimal("0.02"), as_type="decimal"))
TRAILING_STOP_DISTANCE = float(get_config("QUANT_STRATEGY_TRAILING_STOP_DISTANCE", default=Decimal("0.01"), as_type="decimal"))
PROFIT_EXIT_RATIO = float(get_config("QUANT_STRATEGY_PROFIT_EXIT_RATIO", default=Decimal("0.05"), as_type="decimal"))
MAX_HOLDING_HOURS = get_config("QUANT_STRATEGY_MAX_HOLDING_HOURS", default=48, as_type="int")

# 技术指标参数
RSI_PERIOD = get_config("QUANT_RSI_PERIOD", default=14, as_type="int")
RSI_OVERBUY_THRESHOLD = float(get_config("QUANT_RSI_OVERBUY_THRESHOLD", default=Decimal("70"), as_type="decimal"))
RSI_OVERSELL_THRESHOLD = float(get_config("QUANT_RSI_OVERSELL_THRESHOLD", default=Decimal("30"), as_type="decimal"))
MACD_FAST_PERIOD = get_config("QUANT_MACD_FAST_PERIOD", default=12, as_type="int")
MACD_SLOW_PERIOD = get_config("QUANT_MACD_SLOW_PERIOD", default=26, as_type="int")
MACD_SIGNAL_PERIOD = get_config("QUANT_MACD_SIGNAL_PERIOD", default=9, as_type="int")
EMA_FAST_PERIOD = get_config("QUANT_EMA_FAST_PERIOD", default=20, as_type="int")
EMA_SLOW_PERIOD = get_config("QUANT_EMA_SLOW_PERIOD", default=55, as_type="int")
VOLUME_TREND_PERIOD = get_config("QUANT_VOLUME_TREND_PERIOD", default=20, as_type="int")

# 权重配置（用于本地计算的综合评分）
TREND_CONFIRM_WEIGHT = 0.20  # 趋势确认权重
INDICATOR_WEIGHT = 0.20  # 技术指标权重

# 研究评分 API 配置
QUANT_API_BASE_URL = get_config("QUANT_API_BASE_URL", default="http://127.0.0.1:9011", as_type="str")
RESEARCH_API_TIMEOUT = get_config("QUANT_RESEARCH_API_TIMEOUT", default=5, as_type="int")
# 综合评分权重：研究评分权重 0.4，本地评分权重 0.6（当 API 可用时）
RESEARCH_SCORE_FALLBACK_WEIGHT = 0.40


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

    # 研究评分缓存（避免重复调用 API）
    _research_score_cache: dict[str, dict] = {}
    _cache_timestamp: Optional[datetime] = None
    _cache_ttl_seconds: int = 300  # 5分钟缓存

    # 交易告警追踪
    _trade_alert_tracker: dict[str, dict] = {}
    _daily_pnl_tracker: dict[str, float] = {}
    _consecutive_losses: dict[str, int] = {}
    _last_alert_reset_date: Optional[str] = None

    def _check_trade_alerts(self, pair: str, profit_ratio: float, entry_price: float, exit_price: float) -> None:
        """检查交易告警条件并发送告警。

        Args:
            pair: 币种对
            profit_ratio: 盈亏比例
            entry_price: 入场价格
            exit_price: 出场价格
        """
        if not TRADE_ALERT_ENABLED:
            return

        try:
            import requests

            # 告警配置阈值
            large_loss_threshold = 0.05  # 5%
            consecutive_loss_threshold = 3
            daily_loss_threshold = 0.10  # 10%

            symbol = pair.replace("/", "").replace(":", "")
            is_loss = profit_ratio < 0

            # 检查单笔大额亏损
            if is_loss and abs(profit_ratio) > large_loss_threshold:
                self._send_trade_alert(
                    alert_type="large_loss",
                    symbol=symbol,
                    message=f"单笔亏损 {abs(profit_ratio):.2%} 超过阈值 {large_loss_threshold:.2%}",
                    details={
                        "loss_percent": f"{abs(profit_ratio):.2%}",
                        "entry_price": str(entry_price),
                        "exit_price": str(exit_price),
                    }
                )

            # 检查连续亏损
            if is_loss:
                self._consecutive_losses[symbol] = self._consecutive_losses.get(symbol, 0) + 1
                if self._consecutive_losses[symbol] >= consecutive_loss_threshold:
                    self._send_trade_alert(
                        alert_type="consecutive_loss",
                        symbol=symbol,
                        message=f"连续亏损 {self._consecutive_losses[symbol]} 笔",
                        details={
                            "consecutive_count": str(self._consecutive_losses[symbol]),
                        }
                    )
                    # 重置计数
                    self._consecutive_losses[symbol] = 0
            else:
                self._consecutive_losses[symbol] = 0

            # 更新日盈亏追踪
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if self._last_alert_reset_date != today:
                self._daily_pnl_tracker.clear()
                self._last_alert_reset_date = today

            self._daily_pnl_tracker[symbol] = self._daily_pnl_tracker.get(symbol, 0.0) + profit_ratio

            # 检查日亏损限制
            daily_pnl = self._daily_pnl_tracker.get(symbol, 0.0)
            if daily_pnl < -daily_loss_threshold:
                self._send_trade_alert(
                    alert_type="daily_loss_limit",
                    symbol=symbol,
                    message=f"日亏损 {abs(daily_pnl):.2%} 超过阈值 {daily_loss_threshold:.2%}",
                    details={
                        "daily_loss": f"{abs(daily_pnl):.2%}",
                        "date": today,
                    }
                )

        except Exception as e:
            logger.warning("交易告警检查失败: %s", e)

    def _send_trade_alert(self, alert_type: str, symbol: str, message: str, details: dict) -> None:
        """发送交易告警到飞书。

        Args:
            alert_type: 告警类型
            symbol: 币种符号
            message: 告警消息
            details: 告警详情
        """
        try:
            import requests

            # 飞书告警 API
            alert_url = f"{QUANT_API_BASE_URL}/api/v1/alert/trade"
            payload = {
                "alert_type": alert_type,
                "symbol": symbol,
                "message": message,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            response = requests.post(alert_url, json=payload, timeout=5)
            if response.status_code == 200:
                logger.info("交易告警发送成功: %s - %s", alert_type, symbol)
            else:
                logger.warning("交易告警发送失败: HTTP %d", response.status_code)

        except requests.exceptions.Timeout:
            logger.warning("交易告警发送超时")
        except Exception as e:
            logger.warning("交易告警发送异常: %s", e)

    def confirm_trade_exit(
        self,
        pair: str,
        order: dict,
        trade: object,
        current_time: datetime,
        proposed_rate: float,
        current_profit: float,
        exit_reason: str,
        **kwargs,
    ) -> bool:
        """交易退出确认回调 - 检查告警条件。

        Args:
            pair: 币种对
            order: 订单信息
            trade: 交易对象
            current_time: 当前时间
            proposed_rate: 提议的退出价格
            current_profit: 当前盈利比例
            exit_reason: 退出原因

        Returns:
            是否确认退出（始终返回 True）
        """
        # 检查交易告警
        entry_price = float(trade.open_rate) if hasattr(trade, 'open_rate') else proposed_rate
        self._check_trade_alerts(
            pair=pair,
            profit_ratio=current_profit,
            entry_price=entry_price,
            exit_price=proposed_rate,
        )

        logger.info(
            "交易退出确认: %s, 盈亏=%.2f%%, 原因=%s",
            pair,
            current_profit * 100,
            exit_reason,
        )

        return True

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        """Bot循环开始回调 - 每日开始时重置统计数据。

        Args:
            current_time: 当前时间
        """
        today = current_time.strftime("%Y-%m-%d")

        # 检查是否需要重置日统计
        if self._last_alert_reset_date != today:
            self._daily_pnl_tracker.clear()
            self._last_alert_reset_date = today
            logger.info("交易日统计数据已重置: %s", today)

    def _fetch_research_score(self, symbol: str) -> Optional[float]:
        """从研究 API 获取币种评分。

        Args:
            symbol: 币种符号（如 ETHUSDT）

        Returns:
            评分（0.0-1.0），API 不可用时返回 None
        """
        if requests is None:
            logger.debug("requests 库未安装，跳过研究评分获取")
            return None

        # 检查缓存是否有效
        now = datetime.now(timezone.utc)
        if (
            self._cache_timestamp
            and (now - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds
            and symbol in self._research_score_cache
        ):
            return self._research_score_cache[symbol].get("score")

        try:
            api_url = f"{QUANT_API_BASE_URL}/api/v1/evaluation/workspace"
            logger.debug("调用研究评分 API: %s", api_url)

            response = requests.get(api_url, timeout=RESEARCH_API_TIMEOUT)
            response.raise_for_status()

            data = response.json()
            if not data or data.get("error"):
                logger.warning("研究 API 返回错误: %s", data.get("error"))
                return None

            workspace = data.get("data", {}).get("item", {})
            if workspace.get("status") != "ready":
                logger.debug("研究评估状态非 ready: %s", workspace.get("status"))
                return None

            # 更新缓存
            self._cache_timestamp = now
            leaderboard = workspace.get("leaderboard", [])

            for entry in leaderboard:
                entry_symbol = entry.get("symbol", "")
                # 处理可能的符号格式差异（ETHUSDT vs ETH/USDT）
                normalized_symbol = entry_symbol.replace("/", "")
                self._research_score_cache[normalized_symbol] = {
                    "score": float(entry.get("score", 0)),
                    "next_action": entry.get("next_action", ""),
                    "recommendation_reason": entry.get("recommendation_reason", ""),
                }

            # 返回请求的币种评分
            normalized_request = symbol.replace("/", "")
            if normalized_request in self._research_score_cache:
                cached = self._research_score_cache[normalized_request]
                logger.info(
                    "研究评分获取成功: %s, score=%.4f, action=%s",
                    symbol,
                    cached.get("score", 0),
                    cached.get("next_action", ""),
                )
                return cached.get("score")

            logger.debug("币种 %s 未在研究排行榜中", symbol)
            return None

        except requests.exceptions.Timeout:
            logger.warning("研究 API 请求超时 (%d秒)", RESEARCH_API_TIMEOUT)
            return None
        except requests.exceptions.RequestException as e:
            logger.warning("研究 API 请求失败: %s", str(e))
            return None
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("研究 API 响应解析失败: %s", str(e))
            return None

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

        # 计算综合评分（传入 metadata 以获取币种信息）
        dataframe["entry_score"] = self._calculate_entry_score(dataframe, metadata)

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

    def _calculate_entry_score(self, dataframe: DataFrame, metadata: dict = None) -> pd.Series:
        """计算综合入场评分。

        评分公式：
        - 有研究评分时：基础评分 * 0.6 + 研究评分 * 0.4
        - 无研究评分时：使用纯本地计算（fallback）
        """
        if len(dataframe) < 2:
            return pd.Series(0.0, index=dataframe.index)

        # 获取研究评分（从 metadata 中获取币种信息）
        research_score = None
        if metadata:
            pair = metadata.get("pair", "")
            # 标准化币种符号（去掉斜杠）
            symbol = pair.replace("/", "").replace(":", "")
            research_score = self._fetch_research_score(symbol)

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

        # 本地计算的基础评分
        base_score = 0.50
        local_score = base_score + trend_score + indicator_score

        # 综合评分：有研究评分时加权融合
        if research_score is not None:
            # 研究评分权重 0.4，本地权重 0.6
            total_score = local_score * 0.6 + research_score * RESEARCH_SCORE_FALLBACK_WEIGHT
            logger.info(
                "综合评分计算: %s, 本地=%.4f, 研究=%.4f, 综合=%.4f",
                metadata.get("pair", "unknown") if metadata else "unknown",
                local_score.iloc[-1] if len(local_score) > 0 else 0,
                research_score,
                total_score.iloc[-1] if len(total_score) > 0 else 0,
            )
        else:
            # API 不可用时使用纯本地计算
            total_score = local_score
            logger.debug(
                "研究评分不可用，使用本地评分: %s, score=%.4f",
                metadata.get("pair", "unknown") if metadata else "unknown",
                total_score.iloc[-1] if len(total_score) > 0 else 0,
            )

        # 限制在 0-1 之间
        return total_score.clip(0.0, 1.0)


# 保持向后兼容：类名使用 SampleStrategy
# 真实策略逻辑在 QuantStrategy 实现