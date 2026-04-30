"""波动率计算服务，提供ATR和标准差波动率计算。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from services.api.app.adapters.binance.market_client import BinanceMarketClient
from services.api.app.core.settings import Settings


@dataclass(slots=True)
class VolatilityResult:
    """波动率计算结果。"""

    symbol: str
    atr: Decimal
    atr_percent: Decimal
    std: Decimal
    std_percent: Decimal
    volatility_factor: Decimal
    calculated_at: datetime
    period_atr: int
    period_std: int
    data_points: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "atr": str(self.atr),
            "atr_percent": str(self.atr_percent),
            "std": str(self.std),
            "std_percent": str(self.std_percent),
            "volatility_factor": str(self.volatility_factor),
            "calculated_at": self.calculated_at.isoformat(),
            "period_atr": self.period_atr,
            "period_std": self.period_std,
            "data_points": self.data_points,
        }


@dataclass(frozen=True)
class VolatilityConfig:
    """波动率计算配置。"""

    atr_period: int = 14
    std_period: int = 20
    lookback_multiplier: int = 2
    cache_ttl_seconds: int = 300

    @classmethod
    def from_env(cls) -> "VolatilityConfig":
        return cls(
            atr_period=14,
            std_period=20,
            lookback_multiplier=2,
            cache_ttl_seconds=300,
        )


class VolatilityService:
    """波动率计算服务，支持ATR和标准差方法。"""

    def __init__(
        self,
        config: VolatilityConfig | None = None,
        market_client: BinanceMarketClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._config = config or VolatilityConfig.from_env()
        self._market_client = market_client or BinanceMarketClient()
        self._settings = settings or Settings.from_env()
        self._cache: dict[str, tuple[VolatilityResult, datetime]] = {}

    def calculate_atr(self, ohlcv: list[dict[str, Any]], period: int = 14) -> Decimal:
        """计算ATR (Average True Range) 波动率。

        ATR = 平均真实波动范围，用于衡量市场波动性。
        True Range = max(High-Low, abs(High-PrevClose), abs(Low-PrevClose))
        """
        if len(ohlcv) < period + 1:
            return Decimal("0")

        true_ranges: list[Decimal] = []
        for i in range(1, len(ohlcv)):
            current = ohlcv[i]
            prev = ohlcv[i - 1]

            high = self._to_decimal(current.get("high", 0))
            low = self._to_decimal(current.get("low", 0))
            prev_close = self._to_decimal(prev.get("close", 0))

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)

            true_range = max(tr1, tr2, tr3)
            true_ranges.append(true_range)

        if len(true_ranges) < period:
            return Decimal("0")

        recent_tr = true_ranges[-period:]
        atr = sum(recent_tr) / Decimal(period)
        return atr

    def calculate_std(self, prices: list[Decimal], period: int = 20) -> Decimal:
        """计算标准差波动率。

        StdDev = sqrt(sum((price - mean)^2) / n)
        """
        if len(prices) < period:
            return Decimal("0")

        recent_prices = prices[-period:]
        mean = sum(recent_prices) / Decimal(period)

        squared_diffs = [(p - mean) ** 2 for p in recent_prices]
        variance = sum(squared_diffs) / Decimal(period)

        std = variance.sqrt() if variance > 0 else Decimal("0")
        return std

    def get_volatility_factor(self, symbol: str) -> Decimal:
        """获取波动率因子（相对历史波动率）。

        波动率因子 = 当前波动率 / 历史平均波动率
        用于判断当前市场状态相对于历史的波动程度。
        """
        result = self.get_volatility(symbol)
        return result.volatility_factor

    def get_volatility(self, symbol: str) -> VolatilityResult:
        """获取完整的波动率数据。"""
        now = datetime.now(timezone.utc)

        cache_key = symbol.upper()
        cached = self._cache.get(cache_key)
        if cached:
            cached_result, cached_at = cached
            age_seconds = (now - cached_at).total_seconds()
            if age_seconds < self._config.cache_ttl_seconds:
                return cached_result

        ohlcv = self._fetch_ohlcv(symbol)
        if not ohlcv:
            return self._empty_result(symbol, now)

        atr = self.calculate_atr(ohlcv, self._config.atr_period)
        prices = [self._to_decimal(c.get("close", 0)) for c in ohlcv]
        std = self.calculate_std(prices, self._config.std_period)

        latest_close = prices[-1] if prices else Decimal("0")
        atr_percent = (atr / latest_close * Decimal("100")) if latest_close > 0 else Decimal("0")
        std_percent = (std / latest_close * Decimal("100")) if latest_close > 0 else Decimal("0")

        volatility_factor = self._calculate_volatility_factor(ohlcv, atr, std)

        result = VolatilityResult(
            symbol=symbol.upper(),
            atr=atr,
            atr_percent=atr_percent,
            std=std,
            std_percent=std_percent,
            volatility_factor=volatility_factor,
            calculated_at=now,
            period_atr=self._config.atr_period,
            period_std=self._config.std_period,
            data_points=len(ohlcv),
        )

        self._cache[cache_key] = (result, now)
        return result

    def clear_cache(self) -> None:
        """清除缓存。"""
        self._cache.clear()

    def _fetch_ohlcv(self, symbol: str) -> list[dict[str, Any]]:
        """从Binance获取OHLCV数据。"""
        lookback = max(self._config.atr_period, self._config.std_period) * self._config.lookback_multiplier
        try:
            klines = self._market_client.get_klines(
                symbol=symbol,
                interval="4h",
                limit=lookback + 50,
            )
        except Exception:
            return []

        ohlcv: list[dict[str, Any]] = []
        for kline in klines:
            if not kline or len(kline) < 6:
                continue
            try:
                ohlcv.append({
                    "open": Decimal(str(kline[1])),
                    "high": Decimal(str(kline[2])),
                    "low": Decimal(str(kline[3])),
                    "close": Decimal(str(kline[4])),
                    "volume": Decimal(str(kline[5])),
                })
            except (InvalidOperation, ValueError):
                continue

        return ohlcv

    def _calculate_volatility_factor(
        self,
        ohlcv: list[dict[str, Any]],
        current_atr: Decimal,
        current_std: Decimal,
    ) -> Decimal:
        """计算相对历史波动率因子。"""
        if len(ohlcv) < 50 or current_atr == 0:
            return Decimal("1.0")

        historical_atrs: list[Decimal] = []
        window_size = 14
        step = 7

        for i in range(window_size, len(ohlcv) - step, step):
            segment = ohlcv[i - window_size:i]
            atr = self.calculate_atr(segment, window_size)
            if atr > 0:
                historical_atrs.append(atr)

        if not historical_atrs:
            return Decimal("1.0")

        avg_historical_atr = sum(historical_atrs) / Decimal(len(historical_atrs))
        if avg_historical_atr == 0:
            return Decimal("1.0")

        factor = current_atr / avg_historical_atr
        return factor.quantize(Decimal("0.01"))

    def _to_decimal(self, value: Any) -> Decimal:
        """将值转换为Decimal。"""
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    def _empty_result(self, symbol: str, now: datetime) -> VolatilityResult:
        """返回空结果。"""
        return VolatilityResult(
            symbol=symbol.upper(),
            atr=Decimal("0"),
            atr_percent=Decimal("0"),
            std=Decimal("0"),
            std_percent=Decimal("0"),
            volatility_factor=Decimal("1.0"),
            calculated_at=now,
            period_atr=self._config.atr_period,
            period_std=self._config.std_period,
            data_points=0,
        )


volatility_service = VolatilityService()