"""交易所管理服务。

提供交易所切换、配置管理和统一的交易所访问接口。
"""

from __future__ import annotations

import logging
import os
from typing import Any

from services.api.app.services.exchange.base import (
    ExchangeBase,
    ExchangeConfig,
)
from services.api.app.services.exchange.okx import OKXExchange
from services.api.app.services.exchange.bybit import BybitExchange

logger = logging.getLogger(__name__)


# 支持的交易所列表
SUPPORTED_EXCHANGES: dict[str, dict[str, Any]] = {
    "okx": {
        "name": "okx",
        "display_name": "OKX",
        "description": "OKX 交易所，支持现货和合约交易",
        "class": OKXExchange,
        "requires_password": True,  # OKX 需要 passphrase
    },
    "bybit": {
        "name": "bybit",
        "display_name": "Bybit",
        "description": "Bybit 交易所，支持现货和合约交易",
        "class": BybitExchange,
        "requires_password": False,
    },
}


class ExchangeService:
    """交易所管理服务。

    提供：
    - 交易所实例管理
    - 交易所切换
    - 配置管理
    """

    def __init__(self) -> None:
        self._current_exchange: str = "okx"
        self._exchanges: dict[str, ExchangeBase] = {}
        self._configs: dict[str, ExchangeConfig] = {}

    def get_supported_exchanges(self) -> list[dict[str, Any]]:
        """获取支持的交易所列表。"""
        result = []
        for name, info in SUPPORTED_EXCHANGES.items():
            result.append({
                "name": info["name"],
                "display_name": info["display_name"],
                "description": info["description"],
                "requires_password": info["requires_password"],
                "is_active": name in self._exchanges,
            })
        return result

    def get_current_exchange_name(self) -> str:
        """获取当前交易所名称。"""
        return self._current_exchange

    def get_current_exchange(self) -> ExchangeBase | None:
        """获取当前交易所实例。"""
        return self._exchanges.get(self._current_exchange)

    async def initialize_exchange(
        self,
        name: str,
        api_key: str,
        api_secret: str,
        password: str | None = None,
        sandbox: bool = False,
        default_type: str = "swap",
    ) -> dict[str, Any]:
        """初始化交易所。

        Args:
            name: 交易所名称
            api_key: API Key
            api_secret: API Secret
            password: 密码（OKX 需要）
            sandbox: 是否使用沙盒模式
            default_type: 默认交易类型

        Returns:
            初始化结果
        """
        if name not in SUPPORTED_EXCHANGES:
            return {
                "success": False,
                "message": f"不支持的交易所: {name}",
            }

        exchange_info = SUPPORTED_EXCHANGES[name]

        if exchange_info["requires_password"] and not password:
            return {
                "success": False,
                "message": f"{name} 交易所需要 password 参数",
            }

        config = ExchangeConfig(
            api_key=api_key,
            api_secret=api_secret,
            password=password,
            sandbox=sandbox,
            default_type=default_type,
        )

        exchange_class = exchange_info["class"]
        exchange = exchange_class(config)

        try:
            success = await exchange.initialize()
            if success:
                self._exchanges[name] = exchange
                self._configs[name] = config
                logger.info("交易所初始化成功: %s", name)
                return {
                    "success": True,
                    "message": f"{name} 交易所初始化成功",
                    "exchange": exchange.to_dict(),
                }
            else:
                return {
                    "success": False,
                    "message": f"{name} 交易所初始化失败",
                }
        except Exception as e:
            logger.error("交易所初始化异常: %s - %s", name, e)
            return {
                "success": False,
                "message": f"初始化异常: {str(e)}",
            }

    async def switch_exchange(self, name: str) -> dict[str, Any]:
        """切换当前交易所。

        Args:
            name: 目标交易所名称

        Returns:
            切换结果
        """
        if name not in SUPPORTED_EXCHANGES:
            return {
                "success": False,
                "message": f"不支持的交易所: {name}",
            }

        if name not in self._exchanges:
            return {
                "success": False,
                "message": f"交易所 {name} 未初始化，请先初始化",
            }

        self._current_exchange = name
        logger.info("切换交易所: %s", name)

        return {
            "success": True,
            "message": f"已切换到 {name} 交易所",
            "current_exchange": name,
        }

    async def close_exchange(self, name: str) -> dict[str, Any]:
        """关闭交易所连接。

        Args:
            name: 交易所名称

        Returns:
            关闭结果
        """
        if name not in self._exchanges:
            return {
                "success": False,
                "message": f"交易所 {name} 不存在",
            }

        exchange = self._exchanges[name]
        await exchange.close()

        del self._exchanges[name]
        if name in self._configs:
            del self._configs[name]

        if self._current_exchange == name:
            self._current_exchange = ""

        logger.info("交易所已关闭: %s", name)

        return {
            "success": True,
            "message": f"{name} 交易所已关闭",
        }

    async def close_all(self) -> None:
        """关闭所有交易所连接。"""
        for name in list(self._exchanges.keys()):
            await self.close_exchange(name)

    def get_exchange_config(self, name: str) -> dict[str, Any] | None:
        """获取交易所配置。"""
        if name not in self._configs:
            return None
        return self._configs[name].to_dict()

    def update_exchange_config(
        self,
        name: str,
        api_key: str | None = None,
        api_secret: str | None = None,
        password: str | None = None,
        sandbox: bool | None = None,
        default_type: str | None = None,
    ) -> dict[str, Any]:
        """更新交易所配置。

        注意：更新配置后需要重新初始化交易所才能生效。

        Args:
            name: 交易所名称
            api_key: 新的 API Key
            api_secret: 新的 API Secret
            password: 新的密码
            sandbox: 是否沙盒模式
            default_type: 默认交易类型

        Returns:
            更新结果
        """
        if name not in self._configs:
            return {
                "success": False,
                "message": f"交易所 {name} 配置不存在",
            }

        config = self._configs[name]

        if api_key is not None:
            config.api_key = api_key
        if api_secret is not None:
            config.api_secret = api_secret
        if password is not None:
            config.password = password
        if sandbox is not None:
            config.sandbox = sandbox
        if default_type is not None:
            config.default_type = default_type

        logger.info("交易所配置已更新: %s（需要重新初始化）", name)

        return {
            "success": True,
            "message": f"{name} 配置已更新，请重新初始化交易所",
            "config": config.to_dict(),
        }

    def load_config_from_env(self, name: str) -> ExchangeConfig | None:
        """从环境变量加载交易所配置。

        环境变量格式：
        - QUANT_{NAME}_API_KEY
        - QUANT_{NAME}_API_SECRET
        - QUANT_{NAME}_PASSWORD
        - QUANT_{NAME}_SANDBOX
        - QUANT_{NAME}_DEFAULT_TYPE

        Args:
            name: 交易所名称（大写）

        Returns:
            配置对象，如果环境变量不存在则返回 None
        """
        prefix = f"QUANT_{name.upper()}_"

        api_key = os.getenv(f"{prefix}API_KEY", "")
        api_secret = os.getenv(f"{prefix}API_SECRET", "")

        if not api_key or not api_secret:
            return None

        password = os.getenv(f"{prefix}PASSWORD", "")
        sandbox = os.getenv(f"{prefix}SANDBOX", "false").lower() == "true"
        default_type = os.getenv(f"{prefix}DEFAULT_TYPE", "swap")

        return ExchangeConfig(
            api_key=api_key,
            api_secret=api_secret,
            password=password,
            sandbox=sandbox,
            default_type=default_type,
        )


# 全局交易所服务实例
exchange_service = ExchangeService()