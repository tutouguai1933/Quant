"""运行配置读取。

这个文件负责统一读取运行模式、Binance 凭据、Freqtrade REST 配置和市场白名单。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


DEFAULT_MARKET_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
ALLOWED_RUNTIME_MODES = {"demo", "dry-run", "live"}
DEFAULT_BINANCE_BASE_URL = "https://api.binance.com"
DEFAULT_BINANCE_MARKET_BASE_URL = DEFAULT_BINANCE_BASE_URL
DEFAULT_BINANCE_ACCOUNT_BASE_URL = DEFAULT_BINANCE_BASE_URL
DEFAULT_BINANCE_TIMEOUT_SECONDS = 10.0
DEFAULT_AUTOMATION_STATE_PATH = ".runtime/automation_state.json"


@dataclass(frozen=True)
class Settings:
    """控制平面运行配置。"""

    runtime_mode: str
    market_symbols: tuple[str, ...]
    binance_api_key: str = field(repr=False)
    binance_api_secret: str = field(repr=False)
    binance_market_base_url: str = DEFAULT_BINANCE_MARKET_BASE_URL
    binance_account_base_url: str = DEFAULT_BINANCE_ACCOUNT_BASE_URL
    binance_timeout_seconds: float = DEFAULT_BINANCE_TIMEOUT_SECONDS
    freqtrade_api_url: str = field(default="", repr=False)
    freqtrade_api_username: str = field(default="", repr=False)
    freqtrade_api_password: str = field(default="", repr=False)
    freqtrade_api_timeout_seconds: float = 10.0
    allow_live_execution: bool = False
    live_allowed_symbols: tuple[str, ...] = ()
    live_max_stake_usdt: Decimal | None = None
    live_max_open_trades: int | None = None
    automation_state_path: str = DEFAULT_AUTOMATION_STATE_PATH

    @classmethod
    def from_env(cls) -> "Settings":
        """从环境变量读取运行配置。"""

        runtime_mode = os.getenv("QUANT_RUNTIME_MODE", "demo").strip().lower() or "demo"
        if runtime_mode not in ALLOWED_RUNTIME_MODES:
            raise ValueError("QUANT_RUNTIME_MODE 只能是 demo、dry-run 或 live")

        binance_api_key = os.getenv("BINANCE_API_KEY", "").strip()
        binance_api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
        binance_market_base_url = (
            os.getenv("QUANT_BINANCE_MARKET_BASE_URL") or DEFAULT_BINANCE_MARKET_BASE_URL
        ).strip().rstrip("/")
        binance_account_base_url = (
            os.getenv("QUANT_BINANCE_ACCOUNT_BASE_URL") or DEFAULT_BINANCE_ACCOUNT_BASE_URL
        ).strip().rstrip("/")
        raw_binance_timeout = (
            os.getenv("QUANT_BINANCE_TIMEOUT_SECONDS", str(DEFAULT_BINANCE_TIMEOUT_SECONDS)).strip()
            or str(DEFAULT_BINANCE_TIMEOUT_SECONDS)
        )
        try:
            binance_timeout_seconds = float(raw_binance_timeout)
        except ValueError as exc:
            raise ValueError("QUANT_BINANCE_TIMEOUT_SECONDS 必须是数字") from exc
        if binance_timeout_seconds <= 0:
            raise ValueError("QUANT_BINANCE_TIMEOUT_SECONDS 必须大于 0")
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
        allow_live_execution = os.getenv("QUANT_ALLOW_LIVE_EXECUTION", "").strip().lower() == "true"

        raw_symbols = os.getenv("QUANT_MARKET_SYMBOLS")
        if raw_symbols is None:
            market_symbols = DEFAULT_MARKET_SYMBOLS
        else:
            market_symbols = cls._parse_symbol_list(raw_symbols, env_name="QUANT_MARKET_SYMBOLS")
            if not market_symbols:
                raise ValueError("QUANT_MARKET_SYMBOLS 不能为空")

        raw_live_symbols = os.getenv("QUANT_LIVE_ALLOWED_SYMBOLS")
        live_allowed_symbols = ()
        if raw_live_symbols is not None and raw_live_symbols.strip():
            live_allowed_symbols = cls._parse_symbol_list(raw_live_symbols, env_name="QUANT_LIVE_ALLOWED_SYMBOLS")

        raw_live_max_stake = os.getenv("QUANT_LIVE_MAX_STAKE_USDT", "").strip()
        live_max_stake_usdt: Decimal | None = None
        if raw_live_max_stake:
            try:
                live_max_stake_usdt = Decimal(raw_live_max_stake)
            except InvalidOperation as exc:
                raise ValueError("QUANT_LIVE_MAX_STAKE_USDT 必须是数字") from exc
            if live_max_stake_usdt <= 0:
                raise ValueError("QUANT_LIVE_MAX_STAKE_USDT 必须大于 0")

        raw_live_max_open_trades = os.getenv("QUANT_LIVE_MAX_OPEN_TRADES", "").strip()
        live_max_open_trades: int | None = None
        if raw_live_max_open_trades:
            try:
                live_max_open_trades = int(raw_live_max_open_trades)
            except ValueError as exc:
                raise ValueError("QUANT_LIVE_MAX_OPEN_TRADES 必须是整数") from exc
            if live_max_open_trades <= 0:
                raise ValueError("QUANT_LIVE_MAX_OPEN_TRADES 必须大于 0")
        automation_state_path = (os.getenv("QUANT_AUTOMATION_STATE_PATH") or DEFAULT_AUTOMATION_STATE_PATH).strip() or DEFAULT_AUTOMATION_STATE_PATH

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
            binance_market_base_url=binance_market_base_url,
            binance_account_base_url=binance_account_base_url,
            binance_timeout_seconds=binance_timeout_seconds,
            freqtrade_api_url=freqtrade_api_url,
            freqtrade_api_username=freqtrade_api_username,
            freqtrade_api_password=freqtrade_api_password,
            freqtrade_api_timeout_seconds=freqtrade_api_timeout_seconds,
            allow_live_execution=allow_live_execution,
            live_allowed_symbols=live_allowed_symbols,
            live_max_stake_usdt=live_max_stake_usdt,
            live_max_open_trades=live_max_open_trades,
            automation_state_path=automation_state_path,
        )

    @staticmethod
    def _parse_symbol_list(raw_value: str, env_name: str) -> tuple[str, ...]:
        """解析并标准化交易对列表。"""

        normalized_symbols: list[str] = []
        seen_symbols: set[str] = set()
        for item in raw_value.split(","):
            symbol = item.strip().upper()
            if not symbol:
                raise ValueError(f"{env_name} 不能为空")
            if not re.fullmatch(r"[A-Z0-9]+", symbol):
                raise ValueError(f"{env_name} 只能包含大写字母和数字")
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            normalized_symbols.append(symbol)
        return tuple(normalized_symbols)

    def has_freqtrade_rest_config(self) -> bool:
        """判断是否启用了 Freqtrade REST 配置。"""

        return bool(self.freqtrade_api_url and self.freqtrade_api_username and self.freqtrade_api_password)

    def should_use_freqtrade_rest(self) -> bool:
        """判断当前阶段是否允许切到真实 Freqtrade REST 后端。"""

        return self.runtime_mode in {"dry-run", "live"} and self.has_freqtrade_rest_config()

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

    @property
    def account_sync_order_symbols(self) -> tuple[str, ...]:
        """返回账户订单同步应覆盖的交易对范围。"""

        if self.runtime_mode == "live":
            return self.live_allowed_symbols
        return self.market_symbols
