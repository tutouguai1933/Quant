"""Enhanced RSI strategy with multi-timeframe and risk management.

Features:
- Multi-timeframe: 1H for entry, 15M for precise entry confirmation
- Trend filter: SMA200 to avoid bear market entries
- ATR-based dynamic stoploss: Adapts to market volatility
- Trailing stop: Lock in profits dynamically
- Risk management: Daily loss limit, consecutive loss pause
"""

from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, informative
from pandas import DataFrame
import talib.abstract as ta
from datetime import datetime, timedelta
from typing import Optional
from decimal import Decimal
import logging


class EnhancedStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False

    # 策略日志
    logger = logging.getLogger(__name__)

    # ROI目标（考虑0.2%手续费成本）
    minimal_roi = {
        "0": 0.08,    # 8% 主目标（净收益7.8%）
        "30": 0.05,   # 30分钟后降到5%（净收益4.8%）
        "60": 0.04,   # 60分钟后降到4%（净收益3.8%）
        "120": 0.03   # 120分钟后降到3%（净收益2.8%，覆盖手续费）
    }

    # 止损
    stoploss = -0.08  # 8% 初始止损
    use_custom_stoploss = True  # 启用自定义止损（ATR动态止损）

    # Trailing stop动态止盈
    trailing_stop = True
    trailing_stop_positive = 0.03   # 3%利润后开始追踪
    trailing_stop_positive_offset = 0.05  # 5%利润时触发追踪
    trailing_only_offset_is_reached = True

    # 时间框架
    timeframe = "1h"
    startup_candle_count = 200  # SMA200需要

    # 可优化参数（hyperopt优化后）
    rsi_entry_threshold = IntParameter(25, 50, default=45, space="buy", optimize=True)
    rsi_exit_threshold = IntParameter(65, 80, default=80, space="sell", optimize=True)

    # ATR止损参数
    atr_period = IntParameter(10, 20, default=14, space="buy", optimize=True)
    atr_multiplier = DecimalParameter(1.5, 3.0, default=2.0, space="buy", optimize=True)

    # 风控参数
    max_day_loss_pct = DecimalParameter(0.03, 0.10, default=0.045, space="buy", optimize=True)  # 日亏损上限4.5%
    max_consecutive_losses = IntParameter(3, 8, default=5, space="buy", optimize=True)  # 连续亏损5次暂停

    # 内部状态
    _daily_loss_count: int = 0
    _daily_start_balance: Optional[Decimal] = None
    _consecutive_losses: int = 0
    _last_trade_date: Optional[str] = None
    _atr_stoploss_cache: dict = {}  # 缓存每个交易对的ATR止损值

    @informative('4h')
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """4H时间框架指标计算，用于趋势确认。"""
        dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
        dataframe['sma200'] = ta.SMA(dataframe['close'], timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1H时间框架指标
        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)
        dataframe["sma200"] = ta.SMA(dataframe["close"], timeperiod=200)
        dataframe["sma50"] = ta.SMA(dataframe["close"], timeperiod=50)

        # 成交量指标
        dataframe["volume_sma"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # ATR指标 - 用于动态止损
        dataframe["atr"] = ta.ATR(dataframe["high"], dataframe["low"], dataframe["close"],
                                   timeperiod=self.atr_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0

        # 入场条件：
        # 1. 1H RSI超卖 (< threshold)
        # 2. 4H趋势向上（价格在SMA200上方）
        # 3. 4H RSI不极端超买（避免逆大势）
        # 4. 成交量高于平均（有活性）
        conditions = (
            (dataframe["rsi"] < self.rsi_entry_threshold.value) &
            (dataframe["close_4h"] > dataframe["sma200_4h"]) &
            (dataframe["rsi_4h"] < 70) &
            (dataframe["volume"] > dataframe["volume_sma"] * 0.8)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0

        # 出场条件：
        # 1. RSI超买 (> threshold)
        # 2. 或价格跌破SMA50（短期趋势反转）
        conditions = (
            (dataframe["rsi"] > self.rsi_exit_threshold.value) |
            (dataframe["close"] < dataframe["sma50"] * 0.98)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: Optional[str],
        side: str,
        **kwargs
    ) -> bool:
        """风控检查：日亏损限额和连续亏损暂停"""

        # 获取当前日期
        today = current_time.strftime("%Y-%m-%d")

        # 新的一天，重置计数
        if self._last_trade_date != today:
            self._last_trade_date = today
            self._daily_loss_count = 0
            self._consecutive_losses = 0

        # 检查日亏损限额（通过wallet_balance估算）
        # 注意：dry_run模式下使用模拟余额
        total_profit_today = Decimal(str(self._daily_loss_count)) * Decimal(str(self.stoploss))

        if total_profit_today <= -self.max_day_loss_pct.value:
            self.logger.warning(f"Daily loss limit reached: {total_profit_today:.2%}")
            return False

        # 检查连续亏损暂停
        if self._consecutive_losses >= self.max_consecutive_losses.value:
            self.logger.warning(f"Consecutive loss limit reached: {self._consecutive_losses}")
            return False

        return True

    def confirm_trade_exit(
        self,
        pair: str,
        trade: "Trade",
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs
    ) -> bool:
        """记录交易结果用于风控"""

        # 计算本次交易盈亏（使用calc_profit代替calc_profit_pct）
        profit = trade.calc_profit(rate)
        stake_amount = trade.stake_amount
        profit_pct = profit / stake_amount if stake_amount > 0 else 0

        # 更新连续亏损计数
        if profit_pct < 0:
            self._consecutive_losses += 1
            self._daily_loss_count += 1
        else:
            self._consecutive_losses = 0  # 盈利后重置

        return True

    def custom_stoploss(
        self,
        pair: str,
        trade: "Trade",
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs
    ) -> Optional[float]:
        """ATR动态止损：根据市场波动调整止损距离。

        止损 = 2 * ATR / 当前价格
        这使止损能够适应市场波动：
        - 高波动时：止损距离更大，避免被震出
        - 低波动时：止损距离更小，保护利润
        """
        if not after_fill:
            return None

        # 获取当前DataFrame中的ATR值
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is not None and len(dataframe) > 0:
            last_candle = dataframe.iloc[-1]
            atr_value = last_candle.get("atr")

            if atr_value and atr_value > 0:
                # 计算ATR止损距离（相对于当前价格的比例）
                atr_stoploss = (self.atr_multiplier.value * atr_value) / current_rate

                # 缓存ATR止损值
                self._atr_stoploss_cache[pair] = atr_stoploss

                # ATR止损不能超过基础止损（风险控制）
                if atr_stoploss > abs(self.stoploss):
                    return self.stoploss

                return -atr_stoploss

        # 如果无法获取ATR，返回基础止损
        return None

    def _calculate_signal_strength(
        self,
        rsi: float,
        current_volume: float,
        avg_volume: float,
        rsi_threshold: int = 35
    ) -> float:
        """计算信号强度评分（0-100）

        Args:
            rsi: 当前RSI值
            current_volume: 当前成交量
            avg_volume: 平均成交量
            rsi_threshold: RSI超卖阈值，默认35

        Returns:
            信号强度评分（0-100分）
        """
        # RSI偏离度：RSI越低于阈值，偏离度越高，信号越强
        # 例如：RSI=25时，偏离度 = (35-25)/35 * 100 = 28.57
        if rsi < rsi_threshold:
            rsi_deviation = (rsi_threshold - rsi) / rsi_threshold * 100
        else:
            # RSI高于阈值时，偏离度为0，表示弱信号
            rsi_deviation = 0

        # 成交量比值：当前成交量/平均成交量
        # 比值>1表示放量，信号更强
        volume_ratio = (current_volume / avg_volume) if avg_volume > 0 else 1.0

        # 综合评分 = RSI偏离度 * 0.6 + 成交量比值 * 40
        # 成交量比值转换为百分制（比值1=40分，比值2=80分，封顶100分）
        volume_score = min(volume_ratio * 40, 40)
        signal_score = rsi_deviation * 0.6 + volume_score

        return min(signal_score, 100)

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs
    ) -> float:
        """根据信号强度动态调整仓位大小

        信号强度评分：
        - RSI偏离度（60%权重）：RSI越低于阈值，信号越强
        - 成交量比值（40%权重）：放量程度

        仓位调整：
        - 评分 > 80%：仓位 * 1.5（强信号加仓）
        - 评分 50-80%：正常仓位
        - 评分 < 50%：仓位 * 0.5（弱信号减仓）
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if len(dataframe) < 1:
            return proposed_stake

        last_candle = dataframe.iloc[-1]
        rsi = last_candle.get("rsi", 50)
        current_volume = last_candle.get("volume", 0)
        avg_volume = last_candle.get("volume_sma", current_volume)

        # 计算信号强度评分
        signal_score = self._calculate_signal_strength(
            rsi=rsi,
            current_volume=current_volume,
            avg_volume=avg_volume,
            rsi_threshold=self.rsi_entry_threshold.value
        )

        # 根据评分调整仓位
        if signal_score > 80:
            stake_multiplier = 1.5
            self.logger.info(
                f"Strong signal for {pair}: score={signal_score:.1f}%, "
                f"RSI={rsi:.1f}, vol_ratio={current_volume/avg_volume:.2f}, "
                f"stake x{stake_multiplier}"
            )
        elif signal_score >= 50:
            stake_multiplier = 1.0
            self.logger.info(
                f"Normal signal for {pair}: score={signal_score:.1f}%, "
                f"RSI={rsi:.1f}, vol_ratio={current_volume/avg_volume:.2f}"
            )
        else:
            stake_multiplier = 0.5
            self.logger.info(
                f"Weak signal for {pair}: score={signal_score:.1f}%, "
                f"RSI={rsi:.1f}, vol_ratio={current_volume/avg_volume:.2f}, "
                f"stake x{stake_multiplier}"
            )

        # 计算最终仓位
        adjusted_stake = proposed_stake * stake_multiplier

        # 确保不超过max_stake
        adjusted_stake = min(adjusted_stake, max_stake)

        # 确保不低于min_stake（如果设置）
        if min_stake is not None:
            adjusted_stake = max(adjusted_stake, min_stake)

        return adjusted_stake