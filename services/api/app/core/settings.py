"""运行配置读取。

这个文件负责统一读取运行模式、Binance 凭据、Freqtrade REST 配置和市场白名单。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


DEFAULT_MARKET_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
ALLOWED_RUNTIME_MODES = {"demo", "dry-run", "live"}


@dataclass(frozen=True)
class Settings:
    """控制平面运行配置。"""

    runtime_mode: str
    market_symbols: tuple[str, ...]
    binance_api_key: str = field(repr=False)
    binance_api_secret: str = field(repr=False)
    freqtrade_api_url: str = field(default="", repr=False)
    freqtrade_api_username: str = field(default="", repr=False)
    freqtrade_api_password: str = field(default="", repr=False)
    freqtrade_api_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "Settings":
        """从环境变量读取运行配置。"""

        runtime_mode = os.getenv("QUANT_RUNTIME_MODE", "demo").strip().lower() or "demo"
        if runtime_mode not in ALLOWED_RUNTIME_MODES:
            raise ValueError("QUANT_RUNTIME_MODE 只能是 demo、dry-run 或 live")

        binance_api_key = os.getenv("BINANCE_API_KEY", "").strip()
        binance_api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
        freqtrade_api_url = (
            os.getenv("QUANT_FREQTRADE_URL")
            or os.getenv("QUANT_FREQTRADE_API_URL")
            or ""
        ).strip().rstrip("/")
        freqtrade_api_username = (
            os.getenv("QUANT_FREQTRADE_USERNAME")
            or os.getenv("QUANT_FREQTRADE_API_USERNAME")
            or ""
        ).strip()
        freqtrade_api_password = (
            os.getenv("QUANT_FREQTRADE_PASSWORD")
            or os.getenv("QUANT_FREQTRADE_API_PASSWORD")
            or ""
        ).strip()
        raw_timeout = os.getenv("QUANT_FREQTRADE_API_TIMEOUT_SECONDS", "10").strip() or "10"
        try:
            freqtrade_api_timeout_seconds = float(raw_timeout)
        except ValueError as exc:
            raise ValueError("QUANT_FREQTRADE_API_TIMEOUT_SECONDS 必须是数字") from exc
        if freqtrade_api_timeout_seconds <= 0:
            raise ValueError("QUANT_FREQTRADE_API_TIMEOUT_SECONDS 必须大于 0")

        raw_symbols = os.getenv("QUANT_MARKET_SYMBOLS")
        if raw_symbols is None:
            market_symbols = DEFAULT_MARKET_SYMBOLS
        else:
            normalized_symbols: list[str] = []
            seen_symbols: set[str] = set()
            for item in raw_symbols.split(","):
                symbol = item.strip().upper()
                if not symbol:
                    raise ValueError("QUANT_MARKET_SYMBOLS 不能为空")
                if not re.fullmatch(r"[A-Z0-9]+", symbol):
                    raise ValueError("QUANT_MARKET_SYMBOLS 只能包含大写字母和数字")
                if symbol in seen_symbols:
                    continue
                seen_symbols.add(symbol)
                normalized_symbols.append(symbol)

            market_symbols = tuple(normalized_symbols)
            if not market_symbols:
                raise ValueError("QUANT_MARKET_SYMBOLS 不能为空")

        freqtrade_config_values = (freqtrade_api_url, freqtrade_api_username, freqtrade_api_password)
        has_freqtrade_config = any(freqtrade_config_values)
        if has_freqtrade_config and not all(freqtrade_config_values):
            raise ValueError(
                "配置 Freqtrade REST 时必须同时提供 QUANT_FREQTRADE_API_URL、QUANT_FREQTRADE_API_USERNAME 和 QUANT_FREQTRADE_API_PASSWORD"
            )

        if runtime_mode == "live" and (not binance_api_key or not binance_api_secret):
            raise ValueError("live 模式需要提供 BINANCE_API_KEY 和 BINANCE_API_SECRET")

        return cls(
            runtime_mode=runtime_mode,
            binance_api_key=binance_api_key,
            binance_api_secret=binance_api_secret,
            market_symbols=market_symbols,
            freqtrade_api_url=freqtrade_api_url,
            freqtrade_api_username=freqtrade_api_username,
            freqtrade_api_password=freqtrade_api_password,
            freqtrade_api_timeout_seconds=freqtrade_api_timeout_seconds,
        )

    def has_freqtrade_rest_config(self) -> bool:
        """判断是否启用了 Freqtrade REST 配置。"""

        return bool(self.freqtrade_api_url and self.freqtrade_api_username and self.freqtrade_api_password)

    def should_use_freqtrade_rest(self) -> bool:
        """判断当前阶段是否允许切到真实 Freqtrade REST 后端。"""

        return self.runtime_mode == "dry-run" and self.has_freqtrade_rest_config()

    @property
    def freqtrade_url(self) -> str:
        """返回兼容短字段名的 Freqtrade URL。"""

        return self.freqtrade_api_url

    @property
    def freqtrade_username(self) -> str:
        """返回兼容短字段名的 Freqtrade 用户名。"""

        return self.freqtrade_api_username

    @property
    def freqtrade_password(self) -> str:
        """返回兼容短字段名的 Freqtrade 密码。"""

        return self.freqtrade_api_password

    @property
    def freqtrade_rest_enabled(self) -> bool:
        """返回是否启用了真实 REST 后端。"""

        return self.should_use_freqtrade_rest()
