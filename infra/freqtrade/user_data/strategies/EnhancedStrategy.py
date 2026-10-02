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
from datetime import datetime, timezone
from typing import Optional
from decimal import Decimal, ROUND_DOWN
from math import isfinite
from freqtrade.persistence import Trade
import logging


class EnhancedStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False

    # 策略日志
    logger = logging.getLogger(__name__)

    # ROI目标（考虑0.2%手续费成本）
    minimal_roi = {
        "0": 0.08,    # 8% 主目标
        "30": 0.05,   # 30分钟后降到5%
        "60": 0.03,   # 60分钟后降到3%
        "120": 0.02   # 120分钟后降到2%
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

    # ATR 只保存止损辅助数据；成交风险每次从框架持久化事实重建。
    _atr_stoploss_cache: dict = {}

    def _entry_can_exit(self, pair: str, amount: float, rate: float) -> bool:
        """验证费用和步长扣减后，在基础止损价仍满足交易所退出限制。"""
        try:
            market = self.dp.market(pair)
            if not market or market.get("active") is False:
                raise ValueError("交易对不存在或已停用")
            cost_limits = market.get("limits", {}).get("cost", {})
            amount_limits = market.get("limits", {}).get("amount", {})
            minimum_cost = cost_limits.get("min")
            if minimum_cost is None or float(minimum_cost) <= 0:
                raise ValueError("缺少交易所最小成交金额")
            if not isfinite(amount) or not isfinite(rate) or amount <= 0 or rate <= 0:
                raise ValueError("价格或数量无效")
            contract_size = float(market.get("contractSize") or 1)
            if not isfinite(contract_size) or contract_size <= 0:
                raise ValueError("合约单位无效")
            fees = [market.get("maker"), market.get("taker"), self.config.get("fee")]
            fees = [float(fee) for fee in fees if fee is not None]
            if not fees or any(not isfinite(fee) or fee < 0 or fee >= 1 for fee in fees):
                raise ValueError("缺少有效手续费率")
            fee = max(fees)
            exchange = self.dp._exchange
            # 合约精度按张数处理；现货假定最保守的基础币扣费方式。
            entry_amount = exchange.amount_to_precision(pair, amount / contract_size) * contract_size
            is_spot = self.config.get("trading_mode", "spot") == "spot"
            after_fee = entry_amount * (1 - fee) if is_spot else entry_amount
            exit_amount = exchange.amount_to_precision(pair, after_fee / contract_size) * contract_size
            min_amount = float(amount_limits.get("min") or 0) * contract_size
            max_amount = amount_limits.get("max")
            max_amount = float(max_amount) * contract_size if max_amount is not None else None
            max_cost = cost_limits.get("max")
            # CCXT 常规精度可能只含 LOT_SIZE，市场止损另须满足 MARKET_LOT_SIZE。
            for rule in (market.get("info") or {}).get("filters", []):
                if rule.get("filterType") not in ("LOT_SIZE", "MARKET_LOT_SIZE"):
                    continue
                min_amount = max(min_amount, float(rule.get("minQty") or 0) * contract_size)
                rule_max = float(rule.get("maxQty") or 0) * contract_size
                if rule_max > 0:
                    max_amount = min(max_amount, rule_max) if max_amount is not None else rule_max
                step = Decimal(str(rule.get("stepSize") or 0)) * Decimal(str(contract_size))
                if step > 0:
                    exit_amount = float((Decimal(str(exit_amount)) / step).to_integral_value(rounding=ROUND_DOWN) * step)
            stop_rate = rate * (1 - abs(self.stoploss))
            valid = (entry_amount > 0 and exit_amount > 0 and
                     entry_amount >= min_amount and exit_amount >= min_amount and
                     entry_amount * rate >= float(minimum_cost) and
                     exit_amount * stop_rate >= float(minimum_cost))
            if max_amount is not None:
                valid = valid and entry_amount <= max_amount
            if max_cost is not None:
                valid = valid and entry_amount * rate <= float(max_cost)
            if not valid:
                self.logger.warning("RSI拒绝入场 %s：扣费后止损退出数量=%s 金额=%s，最小金额=%s",
                                    pair, exit_amount, exit_amount * stop_rate, minimum_cost)
            return bool(valid)
        except Exception as exc:
            self.logger.warning("RSI拒绝入场 %s：退出约束检查不可用：%s", pair, exc)
            return False

    def _realized_risk_allows_entry(self, current_time: datetime) -> bool:
        """从已平仓净收益重建日亏损和连续亏损，失败退出与重启均不改变事实。"""
        try:
            now = current_time.replace(tzinfo=timezone.utc) if current_time.tzinfo is None else current_time.astimezone(timezone.utc)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            facts = {}
            for trade in Trade.get_trades_proxy(is_open=False):
                if trade.is_open or trade.strategy != self.__class__.__name__:
                    continue
                closed_at = trade.close_date_utc
                profit = trade.close_profit_abs
                if closed_at is None or profit is None:
                    raise ValueError("已平仓记录缺少成交时间或净收益")
                if closed_at.tzinfo is None:
                    closed_at = closed_at.replace(tzinfo=timezone.utc)
                profit = Decimal(str(profit))
                if not profit.is_finite():
                    raise ValueError("已平仓净收益无效")
                if day_start <= closed_at <= now:
                    facts[trade.id] = (closed_at, profit)
            ordered = sorted(facts.values(), key=lambda item: item[0])
            daily_profit = sum((profit for closed_at, profit in ordered if closed_at >= day_start), Decimal(0))
            balance = Decimal(str(self.wallets.get_total_stake_amount()))
            # 框架交易权益包含持仓成本；去除本日已实现收益得到日初风险分母。
            start_balance = balance - daily_profit
            if not start_balance.is_finite() or start_balance <= 0:
                raise ValueError("账户交易权益无效")
            if daily_profit / start_balance <= -Decimal(str(self.max_day_loss_pct.value)):
                self.logger.warning("RSI日已实现净亏损达到限制：%s / %s", daily_profit, start_balance)
                return False
            consecutive = 0
            # 保持原有 UTC 跨日恢复规则，同日重启仍由成交事实重建。
            for _, profit in reversed(ordered):
                if profit >= 0:
                    break
                consecutive += 1
            if consecutive >= self.max_consecutive_losses.value:
                self.logger.warning("RSI连续已成交亏损达到限制：%s", consecutive)
                return False
            return True
        except Exception as exc:
            self.logger.warning("RSI拒绝入场：成交风控事实不可用：%s", exc)
            return False

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

        # 成交量指标 - 同一时段对比（过去7天同一小时的均量）
        lookback_days = 7
        volume_sum = dataframe["volume"].copy()
        valid_count = dataframe["volume"].notna().astype(int)
        for day in range(1, lookback_days + 1):
            shifted = dataframe["volume"].shift(day * 24)
            volume_sum += shifted.fillna(0)
            valid_count += shifted.notna().astype(int)
        dataframe["volume_sma_hourly"] = volume_sum / valid_count.replace(0, 1)

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
        # 4. 成交量不低于过去7天同一时段的60%（过滤异常缩量）
        conditions = (
            (dataframe["rsi"] < self.rsi_entry_threshold.value) &
            (dataframe["close_4h"] > dataframe["sma200_4h"]) &
            (dataframe["rsi_4h"] < 70) &
            (dataframe["volume"] > dataframe["volume_sma_hourly"] * 0.6)
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
        """同时检查未来可卖约束及实际成交风险，不改变 RSI 信号。"""
        return (side == "long" and self._entry_can_exit(pair, amount, rate) and
                self._realized_risk_allows_entry(current_time))

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
        """允许退出请求；请求未必成交，成交风险由框架已平仓事实读取。"""
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

        if dataframe is None or len(dataframe) < 1:
            return self._validated_stake(pair, current_rate, proposed_stake, min_stake, max_stake, leverage)

        last_candle = dataframe.iloc[-1]
        rsi = last_candle.get("rsi", 50)
        current_volume = last_candle.get("volume", 0)
        avg_volume = last_candle.get("volume_sma_hourly", current_volume)

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

        # 信号仓位与最大预算是上限，交易所最小值不能覆盖风险预算。
        adjusted_stake = min(proposed_stake * stake_multiplier, max_stake)
        return self._validated_stake(pair, current_rate, adjusted_stake, min_stake, max_stake, leverage)

    def _validated_stake(self, pair: str, rate: float, stake: float,
                         min_stake: Optional[float], max_stake: float, leverage: float) -> float:
        """仓位不足以安全退出时拒绝交易，不自动增加资金。"""
        if not all(isfinite(value) and value > 0 for value in (rate, stake, max_stake, leverage)):
            return 0.0
        stake = min(stake, max_stake)
        if min_stake is not None and stake < min_stake:
            self.logger.warning("RSI拒绝入场 %s：预算 %s 低于框架最小仓位 %s", pair, stake, min_stake)
            return 0.0
        return stake if self._entry_can_exit(pair, stake * leverage / rate, rate) else 0.0
