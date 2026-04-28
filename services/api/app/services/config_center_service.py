"""配置中心服务。

统一管理分散在 api.env、JSON 文件、docker-compose 中的配置。
提供配置读取、更新、历史追踪和验证功能。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

# 项目根目录
REPO_ROOT = Path(__file__).resolve().parents[4]

# 配置文件路径
API_ENV_PATH = REPO_ROOT / "infra" / "deploy" / "api.env"
FREQTRADE_CONFIG_DIR = REPO_ROOT / "infra" / "freqtrade" / "user_data"
CONFIG_HISTORY_PATH = REPO_ROOT / ".runtime" / "config_history.json"
FREQTRADE_CONFIG_PATH = REPO_ROOT / "infra" / "freqtrade" / "user_data" / "config.deploy.json"

# 交易对配置默认值
DEFAULT_PAIR_WHITELIST = ["DOGE/USDT", "BTC/USDT", "ETH/USDT"]
DEFAULT_PAIR_BLACKLIST: list[str] = []
DEFAULT_MAX_PAIRS = 5
DEFAULT_STAKE_PER_PAIR = "equal"  # equal, volatility, score

# 币种波动率参数配置（用于策略引擎）
PAIR_VOLATILITY_PARAMS = {
    "BTC/USDT": {
        "volatility_multiplier": Decimal("0.8"),  # BTC 波动较小
        "stop_loss_multiplier": Decimal("1.0"),
        "position_multiplier": Decimal("1.2"),  # 允许更大仓位
    },
    "ETH/USDT": {
        "volatility_multiplier": Decimal("0.9"),
        "stop_loss_multiplier": Decimal("1.0"),
        "position_multiplier": Decimal("1.1"),
    },
    "DOGE/USDT": {
        "volatility_multiplier": Decimal("1.3"),  # DOGE 波动较大
        "stop_loss_multiplier": Decimal("1.2"),
        "position_multiplier": Decimal("0.8"),  # 减小仓位
    },
    "SOL/USDT": {
        "volatility_multiplier": Decimal("1.1"),
        "stop_loss_multiplier": Decimal("1.1"),
        "position_multiplier": Decimal("0.9"),
    },
}

# 配置分组定义
CONFIG_SECTIONS = {
    "network": {
        "description": "网络相关配置（VPN、代理等）",
        "keys": [
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
            "QUANT_BINANCE_MARKET_BASE_URL",
            "QUANT_BINANCE_ACCOUNT_BASE_URL",
            "QUANT_BINANCE_TIMEOUT_SECONDS",
        ],
    },
    "trading": {
        "description": "交易相关配置",
        "keys": [
            "QUANT_RUNTIME_MODE",
            "QUANT_MARKET_SYMBOLS",
            "QUANT_ALLOW_LIVE_EXECUTION",
            "QUANT_LIVE_ALLOWED_SYMBOLS",
            "QUANT_LIVE_MAX_STAKE_USDT",
            "QUANT_LIVE_MAX_OPEN_TRADES",
            "QUANT_FREQTRADE_API_URL",
            "QUANT_FREQTRADE_API_USERNAME",
            "QUANT_FREQTRADE_API_PASSWORD",
            "QUANT_FREQTRADE_API_TIMEOUT_SECONDS",
        ],
    },
    "risk": {
        "description": "风控相关配置",
        "keys": [
            "QUANT_RISK_DAILY_MAX_LOSS_PCT",
            "QUANT_RISK_MAX_TRADES_PER_DAY",
            "QUANT_RISK_CRASH_THRESHOLD_PCT",
            "QUANT_QLIB_DRY_RUN_MIN_SHARPE",
            "QUANT_QLIB_DRY_RUN_MIN_WIN_RATE",
            "QUANT_QLIB_DRY_RUN_MAX_DRAWDOWN_PCT",
            "QUANT_QLIB_DRY_RUN_MAX_LOSS_STREAK",
            "QUANT_QLIB_DRY_RUN_MIN_SCORE",
            "QUANT_QLIB_FORCE_TOP_CANDIDATE",
        ],
    },
    "alert": {
        "description": "告警推送相关配置",
        "keys": [
            "QUANT_ALERT_TELEGRAM_TOKEN",
            "QUANT_ALERT_TELEGRAM_CHAT_ID",
            "QUANT_ALERT_WEBHOOK_URL",
            "QUANT_ALERT_ENABLED",
        ],
    },
    "vpn": {
        "description": "VPN/代理切换相关配置",
        "keys": [
            "QUANT_MIHOMO_API_URL",
            "QUANT_MIHOMO_PROXY_URL",
            "QUANT_VPN_HEALTH_CHECK_URL",
            "QUANT_VPN_HEALTH_CHECK_TIMEOUT",
            "QUANT_VPN_HEALTH_CHECK_INTERVAL",
            "QUANT_VPN_WHITELIST_IPS",
            "QUANT_VPN_AVAILABLE_NODES",
        ],
    },
    "strategy": {
        "description": "策略引擎相关配置",
        "keys": [
            "QUANT_STRATEGY_MIN_ENTRY_SCORE",
            "QUANT_STRATEGY_TRAILING_STOP_TRIGGER",
            "QUANT_STRATEGY_TRAILING_STOP_DISTANCE",
            "QUANT_STRATEGY_PROFIT_EXIT_RATIO",
            "QUANT_STRATEGY_MAX_HOLDING_HOURS",
            "QUANT_STRATEGY_BASE_POSITION_RATIO",
            "QUANT_STRATEGY_MAX_POSITION_RATIO",
            "QUANT_STRATEGY_VOLATILITY_SCALE_FACTOR",
            "QUANT_RSI_OVERBUY_THRESHOLD",
            "QUANT_RSI_OVERSELL_THRESHOLD",
            "QUANT_RSI_PERIOD",
            "QUANT_MACD_FAST_PERIOD",
            "QUANT_MACD_SLOW_PERIOD",
            "QUANT_MACD_SIGNAL_PERIOD",
            "QUANT_VOLUME_TREND_PERIOD",
        ],
    },
    "analytics": {
        "description": "数据分析相关配置",
        "keys": [
            "QUANT_ANALYTICS_HISTORY_DAYS",
        ],
    },
    "model_suggestion": {
        "description": "模型建议相关配置",
        "keys": [
            "QUANT_MODEL_SUGGESTION_ENABLED",
            "QUANT_MODEL_API_KEY",
            "QUANT_MODEL_THRESHOLD_RANGE",
            "QUANT_MODEL_PROVIDER",
            "QUANT_MODEL_TIMEOUT_SECONDS",
            "QUANT_MODEL_MAX_TOKENS",
        ],
    },
    "performance": {
        "description": "性能监控相关配置",
        "keys": [
            "QUANT_API_LATENCY_THRESHOLD_MS",
            "QUANT_TRADE_LATENCY_THRESHOLD_MS",
            "QUANT_PERFORMANCE_LOG_INTERVAL",
            "QUANT_PERFORMANCE_MAX_RECORDS",
            "QUANT_PERFORMANCE_ENABLE_ALERTS",
        ],
    },
    "auto_dispatch": {
        "description": "自动派发相关配置",
        "keys": [
            "QUANT_AUTO_DISPATCH_ENABLED",
            "QUANT_AUTO_DISPATCH_INTERVAL",
            "QUANT_AUTO_DISPATCH_MIN_SCORE",
            "QUANT_AUTO_DISPATCH_MAX_DAILY",
            "QUANT_AUTO_DISPATCH_REQUIRE_DRY_RUN_GATE",
            "QUANT_AUTO_DISPATCH_REQUIRE_LIVE_GATE",
        ],
    },
    "research": {
        "description": "研究相关配置",
        "keys": [
            "QUANT_QLIB_SESSION_ID",
            "QUANT_QLIB_DRY_RUN_MIN_SHARPE",
            "QUANT_QLIB_DRY_RUN_MIN_WIN_RATE",
            "QUANT_QLIB_DRY_RUN_MAX_DRAWDOWN_PCT",
            "QUANT_QLIB_DRY_RUN_MAX_LOSS_STREAK",
            "QUANT_QLIB_DRY_RUN_MIN_SCORE",
            "QUANT_QLIB_FORCE_TOP_CANDIDATE",
        ],
    },
    "auth": {
        "description": "认证相关配置",
        "keys": [
            "QUANT_ADMIN_USERNAME",
            "QUANT_ADMIN_PASSWORD",
            "QUANT_SESSION_TTL_SECONDS",
        ],
    },
    "binance": {
        "description": "币安交易所配置",
        "keys": [
            "BINANCE_API_KEY",
            "BINANCE_API_SECRET",
            "QUANT_BINANCE_MARKET_BASE_URL",
            "QUANT_BINANCE_ACCOUNT_BASE_URL",
            "QUANT_BINANCE_TIMEOUT_SECONDS",
        ],
    },
    "pairs": {
        "description": "交易对白名单配置",
        "keys": [
            "QUANT_PAIR_WHITELIST",
            "QUANT_PAIR_BLACKLIST",
            "QUANT_MAX_PAIRS",
            "QUANT_STAKE_PER_PAIR",
        ],
    },
}

# 敏感字段列表（用于脱敏）
SENSITIVE_KEYS = {
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "QUANT_ADMIN_PASSWORD",
    "QUANT_FREQTRADE_API_PASSWORD",
    "QUANT_ALERT_TELEGRAM_TOKEN",
    "QUANT_MODEL_API_KEY",
}

# 默认值配置（用于配置缺失时的fallback）
CONFIG_DEFAULTS: dict[str, str | int | float | Decimal] = {
    # 网络配置
    "QUANT_BINANCE_MARKET_BASE_URL": "https://api.binance.com",
    "QUANT_BINANCE_ACCOUNT_BASE_URL": "https://api.binance.com",
    "QUANT_BINANCE_TIMEOUT_SECONDS": 10,
    # 交易配置
    "QUANT_RUNTIME_MODE": "dry-run",
    "QUANT_ALLOW_LIVE_EXECUTION": "false",
    "QUANT_LIVE_MAX_STAKE_USDT": 6,
    "QUANT_LIVE_MAX_OPEN_TRADES": 1,
    "QUANT_FREQTRADE_API_TIMEOUT_SECONDS": 10,
    # 风控配置
    "QUANT_RISK_DAILY_MAX_LOSS_PCT": 3,
    "QUANT_RISK_MAX_TRADES_PER_DAY": 5,
    "QUANT_RISK_CRASH_THRESHOLD_PCT": 5,
    # VPN配置
    "QUANT_MIHOMO_API_URL": "http://mihomo:9090",
    "QUANT_MIHOMO_PROXY_URL": "http://mihomo:7890",
    "QUANT_VPN_HEALTH_CHECK_URL": "https://api.binance.com/api/v3/ping",
    "QUANT_VPN_HEALTH_CHECK_TIMEOUT": 10.0,
    "QUANT_VPN_HEALTH_CHECK_INTERVAL": 60,
    # 策略配置
    "QUANT_STRATEGY_MIN_ENTRY_SCORE": Decimal("0.7"),
    "QUANT_STRATEGY_TRAILING_STOP_TRIGGER": Decimal("0.02"),
    "QUANT_STRATEGY_TRAILING_STOP_DISTANCE": Decimal("0.01"),
    "QUANT_STRATEGY_PROFIT_EXIT_RATIO": Decimal("0.05"),
    "QUANT_STRATEGY_MAX_HOLDING_HOURS": 48,
    "QUANT_STRATEGY_BASE_POSITION_RATIO": Decimal("0.25"),
    "QUANT_STRATEGY_MAX_POSITION_RATIO": Decimal("0.50"),
    "QUANT_STRATEGY_VOLATILITY_SCALE_FACTOR": Decimal("0.5"),
    "QUANT_RSI_OVERBUY_THRESHOLD": Decimal("70"),
    "QUANT_RSI_OVERSELL_THRESHOLD": Decimal("30"),
    "QUANT_RSI_PERIOD": 14,
    "QUANT_MACD_FAST_PERIOD": 12,
    "QUANT_MACD_SLOW_PERIOD": 26,
    "QUANT_MACD_SIGNAL_PERIOD": 9,
    "QUANT_VOLUME_TREND_PERIOD": 20,
    # Analytics配置
    "QUANT_ANALYTICS_HISTORY_DAYS": 30,
    # 模型建议配置
    "QUANT_MODEL_SUGGESTION_ENABLED": "false",
    "QUANT_MODEL_THRESHOLD_RANGE": Decimal("0.05"),
    "QUANT_MODEL_PROVIDER": "anthropic",
    "QUANT_MODEL_TIMEOUT_SECONDS": 30,
    "QUANT_MODEL_MAX_TOKENS": 1024,
    # 性能监控配置
    "QUANT_API_LATENCY_THRESHOLD_MS": 500,
    "QUANT_TRADE_LATENCY_THRESHOLD_MS": 2000,
    "QUANT_PERFORMANCE_LOG_INTERVAL": 60,
    "QUANT_PERFORMANCE_MAX_RECORDS": 1000,
    "QUANT_PERFORMANCE_ENABLE_ALERTS": "true",
    # 自动派发配置
    "QUANT_AUTO_DISPATCH_ENABLED": "false",
    "QUANT_AUTO_DISPATCH_INTERVAL": 300,
    "QUANT_AUTO_DISPATCH_MIN_SCORE": Decimal("0.7"),
    "QUANT_AUTO_DISPATCH_MAX_DAILY": 5,
    "QUANT_AUTO_DISPATCH_REQUIRE_DRY_RUN_GATE": "true",
    "QUANT_AUTO_DISPATCH_REQUIRE_LIVE_GATE": "false",
    # 认证配置
    "QUANT_ADMIN_USERNAME": "admin",
    "QUANT_SESSION_TTL_SECONDS": 604800,
    # 告警配置
    "QUANT_ALERT_ENABLED": "true",
    # 交易对配置
    "QUANT_MAX_PAIRS": 5,
    "QUANT_STAKE_PER_PAIR": "equal",
}


class ConfigCenterService:
    """配置中心服务类。"""

    def __init__(self) -> None:
        """初始化配置中心服务。"""
        self._ensure_history_file()

    def _ensure_history_file(self) -> None:
        """确保配置历史文件存在。"""
        CONFIG_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not CONFIG_HISTORY_PATH.exists():
            CONFIG_HISTORY_PATH.write_text("[]", encoding="utf-8")

    def _read_env_file(self, path: Path) -> dict[str, str]:
        """读取环境变量文件。

        Args:
            path: 环境变量文件路径

        Returns:
            解析后的键值对字典
        """
        if not path.exists():
            return {}

        result: dict[str, str] = {}
        content = path.read_text(encoding="utf-8")

        for line in content.splitlines():
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue

            # 解析 KEY=VALUE 格式
            if "=" in line:
                key, _, value = line.partition("=")
                result[key.strip()] = value.strip()

        return result

    def _write_env_file(self, path: Path, config: dict[str, str]) -> None:
        """写入环境变量文件。

        Args:
            path: 环境变量文件路径
            config: 配置键值对
        """
        # 读取现有内容以保留注释和格式
        existing_lines: list[str] = []
        if path.exists():
            existing_lines = path.read_text(encoding="utf-8").splitlines()

        # 构建更新后的内容
        updated_keys: set[str] = set()
        new_lines: list[str] = []

        for line in existing_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                new_lines.append(line)
                continue

            if "=" in stripped:
                key, _, _ = stripped.partition("=")
                key = key.strip()
                if key in config:
                    new_lines.append(f"{key}={config[key]}")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # 添加新配置
        for key, value in config.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}")

        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def _read_json_config(self, path: Path) -> dict[str, Any]:
        """读取 JSON 配置文件。

        Args:
            path: JSON 配置文件路径

        Returns:
            解析后的配置字典
        """
        if not path.exists():
            return {}

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _record_history(
        self,
        action: str,
        key: str,
        old_value: str | None,
        new_value: str | None,
        source: str,
        operator: str = "system",
    ) -> None:
        """记录配置变更历史。

        Args:
            action: 操作类型 (create/update/delete)
            key: 配置键名
            old_value: 旧值
            new_value: 新值
            source: 配置来源
            operator: 操作者
        """
        try:
            history: list[dict[str, Any]] = []
            if CONFIG_HISTORY_PATH.exists():
                history = json.loads(CONFIG_HISTORY_PATH.read_text(encoding="utf-8"))

            entry = {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "key": key,
                "old_value": old_value,
                "new_value": new_value,
                "source": source,
                "operator": operator,
            }

            history.append(entry)

            # 只保留最近 1000 条记录
            if len(history) > 1000:
                history = history[-1000:]

            CONFIG_HISTORY_PATH.write_text(
                json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            # 历史记录失败不影响主流程
            pass

    def get_all_config(self, include_secrets: bool = False) -> dict[str, Any]:
        """获取所有配置（合并 env 和 JSON）。

        Args:
            include_secrets: 是否包含敏感信息

        Returns:
            包含所有配置的字典
        """
        result: dict[str, Any] = {
            "env": {},
            "json": {},
            "sections": {},
            "sources": {},
        }

        # 读取 api.env
        env_config = self._read_env_file(API_ENV_PATH)
        result["env"]["api.env"] = env_config
        result["sources"]["api.env"] = str(API_ENV_PATH)

        # 敏感字段脱敏
        if not include_secrets:
            for key in SENSITIVE_KEYS:
                if key in env_config:
                    env_config[key] = "***REDACTED***"

        # 读取 Freqtrade JSON 配置
        json_files = [
            "config.base.json",
            "config.deploy.json",
            "config.live.base.json",
            "config.private.json",
            "config.proxy.mihomo.json",
            "config.proxy.noop.json",
        ]

        for filename in json_files:
            path = FREQTRADE_CONFIG_DIR / filename
            if path.exists():
                json_config = self._read_json_config(path)
                result["json"][filename] = json_config
                result["sources"][filename] = str(path)

        # 按分组组织配置
        for section_name, section_info in CONFIG_SECTIONS.items():
            result["sections"][section_name] = {
                "description": section_info["description"],
                "config": {},
            }
            for key in section_info["keys"]:
                # 从环境变量中查找
                if key in env_config:
                    result["sections"][section_name]["config"][key] = env_config[key]

        return result

    def get_config_section(self, section: str, include_secrets: bool = False) -> dict[str, Any]:
        """获取特定配置段。

        Args:
            section: 配置段名称
            include_secrets: 是否包含敏感信息

        Returns:
            配置段内容

        Raises:
            ValueError: 配置段不存在
        """
        if section not in CONFIG_SECTIONS:
            raise ValueError(f"配置段 '{section}' 不存在，可用配置段: {list(CONFIG_SECTIONS.keys())}")

        section_info = CONFIG_SECTIONS[section]
        env_config = self._read_env_file(API_ENV_PATH)

        # 敏感字段脱敏
        if not include_secrets:
            for key in SENSITIVE_KEYS:
                if key in env_config:
                    env_config[key] = "***REDACTED***"

        result: dict[str, Any] = {
            "section": section,
            "description": section_info["description"],
            "config": {},
            "source": str(API_ENV_PATH),
        }

        for key in section_info["keys"]:
            if key in env_config:
                result["config"][key] = env_config[key]

        return result

    def update_config(
        self,
        key: str,
        value: str,
        operator: str = "system",
        comment: str = "",
    ) -> dict[str, Any]:
        """更新配置项。

        Args:
            key: 配置键名
            value: 新值
            operator: 操作者
            comment: 变更说明

        Returns:
            更新结果

        Raises:
            ValueError: 配置键名无效
        """
        # 验证配置键名
        if not re.match(r"^[A-Z_][A-Z0-9_]*$", key):
            raise ValueError(f"配置键名格式无效: {key}")

        # 读取现有配置
        env_config = self._read_env_file(API_ENV_PATH)
        old_value = env_config.get(key)

        # 更新配置
        env_config[key] = value
        self._write_env_file(API_ENV_PATH, env_config)

        # 记录历史
        action = "create" if old_value is None else "update"
        self._record_history(
            action=action,
            key=key,
            old_value=old_value,
            new_value=value,
            source="api.env",
            operator=operator,
        )

        return {
            "key": key,
            "old_value": old_value,
            "new_value": value,
            "action": action,
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
        }

    def batch_update_config(
        self,
        updates: dict[str, str],
        operator: str = "system",
        comment: str = "",
    ) -> dict[str, Any]:
        """批量更新配置项。

        Args:
            updates: 配置键值对
            operator: 操作者
            comment: 变更说明

        Returns:
            更新结果
        """
        results: list[dict[str, Any]] = []

        for key, value in updates.items():
            try:
                result = self.update_config(key, value, operator, comment)
                results.append(result)
            except ValueError as e:
                results.append({
                    "key": key,
                    "error": str(e),
                    "success": False,
                })

        return {
            "updates": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat(),
        }

    def delete_config(self, key: str, operator: str = "system") -> dict[str, Any]:
        """删除配置项。

        Args:
            key: 配置键名
            operator: 操作者

        Returns:
            删除结果

        Raises:
            ValueError: 配置不存在
        """
        env_config = self._read_env_file(API_ENV_PATH)

        if key not in env_config:
            raise ValueError(f"配置项 '{key}' 不存在")

        old_value = env_config.pop(key)
        self._write_env_file(API_ENV_PATH, env_config)

        # 记录历史
        self._record_history(
            action="delete",
            key=key,
            old_value=old_value,
            new_value=None,
            source="api.env",
            operator=operator,
        )

        return {
            "key": key,
            "old_value": old_value,
            "action": "delete",
            "timestamp": datetime.now().isoformat(),
        }

    def get_config_history(
        self,
        key: str | None = None,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """获取配置变更历史。

        Args:
            key: 过滤特定配置键
            action: 过滤操作类型
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            配置历史记录
        """
        if not CONFIG_HISTORY_PATH.exists():
            return {
                "items": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
            }

        try:
            history: list[dict[str, Any]] = json.loads(
                CONFIG_HISTORY_PATH.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            history = []

        # 过滤
        filtered = history
        if key:
            filtered = [h for h in filtered if h.get("key") == key]
        if action:
            filtered = [h for h in filtered if h.get("action") == action]

        # 排序（最新的在前）
        filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        total = len(filtered)
        items = filtered[offset:offset + limit]

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def validate_config(self) -> dict[str, Any]:
        """验证配置完整性。

        Returns:
            验证结果，包含缺失和无效配置
        """
        result: dict[str, Any] = {
            "valid": True,
            "missing": [],
            "invalid": [],
            "warnings": [],
            "sections": {},
        }

        # 读取环境变量配置
        env_config = self._read_env_file(API_ENV_PATH)

        # 必需配置项
        required_keys = [
            "QUANT_RUNTIME_MODE",
            "QUANT_MARKET_SYMBOLS",
            "QUANT_BINANCE_MARKET_BASE_URL",
        ]

        # 检查缺失配置
        for key in required_keys:
            if key not in env_config or not env_config[key]:
                result["missing"].append({
                    "key": key,
                    "section": self._find_section(key),
                })
                result["valid"] = False

        # 验证特定配置值
        validations = [
            ("QUANT_RUNTIME_MODE", ["dry-run", "live", "paper"]),
            ("QUANT_RISK_DAILY_MAX_LOSS_PCT", None, lambda v: self._is_numeric(v) and 0 < float(v) <= 100),
            ("QUANT_RISK_CRASH_THRESHOLD_PCT", None, lambda v: self._is_numeric(v) and 0 < float(v) <= 100),
        ]

        for validation in validations:
            key = validation[0]
            if key in env_config:
                value = env_config[key]

                # 枚举验证
                if len(validation) > 1 and isinstance(validation[1], list):
                    allowed = validation[1]
                    if value not in allowed:
                        result["invalid"].append({
                            "key": key,
                            "value": value,
                            "reason": f"值不在允许列表中: {allowed}",
                        })
                        result["valid"] = False

                # 自定义验证
                if len(validation) > 2 and callable(validation[2]):
                    validator = validation[2]
                    try:
                        if not validator(value):
                            result["invalid"].append({
                                "key": key,
                                "value": value,
                                "reason": "值验证失败",
                            })
                            result["valid"] = False
                    except Exception as e:
                        result["invalid"].append({
                            "key": key,
                            "value": value,
                            "reason": str(e),
                        })
                        result["valid"] = False

        # 检查敏感配置是否为空（只检查交易相关的敏感配置）
        sensitive_empty = []
        trade_sensitive_keys = ["BINANCE_API_KEY", "BINANCE_API_SECRET"]
        for key in trade_sensitive_keys:
            if key not in env_config or not env_config[key]:
                sensitive_empty.append(key)

        if sensitive_empty:
            result["warnings"].append({
                "type": "empty_sensitive",
                "keys": sensitive_empty,
                "message": "敏感配置项为空，某些功能可能无法正常工作",
            })

        # 分组验证结果
        for section_name, section_info in CONFIG_SECTIONS.items():
            section_result = {
                "description": section_info["description"],
                "keys": {},
            }

            for key in section_info["keys"]:
                key_status = {
                    "present": key in env_config,
                    "value": env_config.get(key),
                }
                section_result["keys"][key] = key_status

            result["sections"][section_name] = section_result

        return result

    def _find_section(self, key: str) -> str | None:
        """查找配置项所属的分组。

        Args:
            key: 配置键名

        Returns:
            分组名称或 None
        """
        for section_name, section_info in CONFIG_SECTIONS.items():
            if key in section_info["keys"]:
                return section_name
        return None

    def _is_numeric(self, value: str) -> bool:
        """检查值是否为数字。

        Args:
            value: 字符串值

        Returns:
            是否为数字
        """
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False

    def get_config_schema(self) -> dict[str, Any]:
        """获取配置模式定义。

        Returns:
            配置模式定义
        """
        return {
            "sections": CONFIG_SECTIONS,
            "sources": {
                "api.env": {
                    "path": str(API_ENV_PATH),
                    "type": "env",
                    "description": "主配置文件",
                },
                "freqtrade_configs": {
                    "path": str(FREQTRADE_CONFIG_DIR),
                    "type": "directory",
                    "files": [
                        "config.base.json",
                        "config.deploy.json",
                        "config.live.base.json",
                        "config.private.json",
                        "config.proxy.mihomo.json",
                        "config.proxy.noop.json",
                    ],
                },
            },
            "sensitive_keys": list(SENSITIVE_KEYS),
        }

    def reload_config(self) -> dict[str, Any]:
        """重新加载配置（提示需要重启服务）。

        Returns:
            重载结果
        """
        # 实际的配置重载需要重启服务
        # 这里只是返回当前配置状态
        return {
            "status": "pending_restart",
            "message": "配置已更新，需要重启服务才能生效",
            "config_valid": self.validate_config()["valid"],
            "timestamp": datetime.now().isoformat(),
        }

    # ========== 交易对白名单管理 ==========

    def get_pair_whitelist(self) -> dict[str, Any]:
        """获取交易对白名单配置。

        Returns:
            交易对白名单配置信息
        """
        env_config = self._read_env_file(API_ENV_PATH)

        # 从环境变量读取白名单
        whitelist_str = env_config.get("QUANT_PAIR_WHITELIST", "")
        if whitelist_str:
            whitelist = [p.strip() for p in whitelist_str.split(",") if p.strip()]
        else:
            # 从 Freqtrade 配置读取
            freqtrade_config = self._read_json_config(FREQTRADE_CONFIG_PATH)
            whitelist = freqtrade_config.get("exchange", {}).get("pair_whitelist", DEFAULT_PAIR_WHITELIST)

        # 从环境变量读取黑名单
        blacklist_str = env_config.get("QUANT_PAIR_BLACKLIST", "")
        if blacklist_str:
            blacklist = [p.strip() for p in blacklist_str.split(",") if p.strip()]
        else:
            freqtrade_config = self._read_json_config(FREQTRADE_CONFIG_PATH)
            blacklist = freqtrade_config.get("exchange", {}).get("pair_blacklist", DEFAULT_PAIR_BLACKLIST)

        # 其他配置
        max_pairs = int(env_config.get("QUANT_MAX_PAIRS", str(DEFAULT_MAX_PAIRS)))
        stake_per_pair = env_config.get("QUANT_STAKE_PER_PAIR", DEFAULT_STAKE_PER_PAIR)

        return {
            "whitelist": whitelist,
            "blacklist": blacklist,
            "max_pairs": max_pairs,
            "stake_per_pair": stake_per_pair,
            "volatility_params": PAIR_VOLATILITY_PARAMS,
            "effective_whitelist": [p for p in whitelist if p not in blacklist][:max_pairs],
            "sources": {
                "env": str(API_ENV_PATH),
                "freqtrade": str(FREQTRADE_CONFIG_PATH),
            },
            "timestamp": datetime.now().isoformat(),
        }

    def update_pair_whitelist(
        self,
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
        max_pairs: int | None = None,
        stake_per_pair: str | None = None,
        operator: str = "system",
        comment: str = "",
    ) -> dict[str, Any]:
        """更新交易对白名单配置。

        Args:
            whitelist: 新的白名单列表
            blacklist: 新的黑名单列表
            max_pairs: 最大交易对数量
            stake_per_pair: 仓位分配策略
            operator: 操作者
            comment: 变更说明

        Returns:
            更新结果
        """
        env_config = self._read_env_file(API_ENV_PATH)
        updates: dict[str, str] = {}
        changes: list[dict[str, Any]] = []

        # 更新白名单
        if whitelist is not None:
            # 验证交易对格式
            validated_pairs = []
            for pair in whitelist:
                pair = pair.strip().upper()
                # 标准化格式：BTCUSDT -> BTC/USDT
                if "/" not in pair:
                    if pair.endswith("USDT"):
                        base = pair[:-4]
                        pair = f"{base}/USDT"
                validated_pairs.append(pair)

            new_whitelist_str = ",".join(validated_pairs)
            old_whitelist_str = env_config.get("QUANT_PAIR_WHITELIST", "")
            updates["QUANT_PAIR_WHITELIST"] = new_whitelist_str
            changes.append({
                "key": "whitelist",
                "old_value": old_whitelist_str.split(",") if old_whitelist_str else [],
                "new_value": validated_pairs,
            })

            # 同步更新 Freqtrade 配置
            self._update_freqtrade_pair_whitelist(validated_pairs)

        # 更新黑名单
        if blacklist is not None:
            validated_blacklist = []
            for pair in blacklist:
                pair = pair.strip().upper()
                if "/" not in pair:
                    if pair.endswith("USDT"):
                        base = pair[:-4]
                        pair = f"{base}/USDT"
                validated_blacklist.append(pair)

            new_blacklist_str = ",".join(validated_blacklist)
            old_blacklist_str = env_config.get("QUANT_PAIR_BLACKLIST", "")
            updates["QUANT_PAIR_BLACKLIST"] = new_blacklist_str
            changes.append({
                "key": "blacklist",
                "old_value": old_blacklist_str.split(",") if old_blacklist_str else [],
                "new_value": validated_blacklist,
            })

        # 更新其他配置
        if max_pairs is not None:
            old_max_pairs = env_config.get("QUANT_MAX_PAIRS", str(DEFAULT_MAX_PAIRS))
            updates["QUANT_MAX_PAIRS"] = str(max_pairs)
            changes.append({
                "key": "max_pairs",
                "old_value": int(old_max_pairs) if old_max_pairs else DEFAULT_MAX_PAIRS,
                "new_value": max_pairs,
            })

        if stake_per_pair is not None:
            old_stake = env_config.get("QUANT_STAKE_PER_PAIR", DEFAULT_STAKE_PER_PAIR)
            updates["QUANT_STAKE_PER_PAIR"] = stake_per_pair
            changes.append({
                "key": "stake_per_pair",
                "old_value": old_stake,
                "new_value": stake_per_pair,
            })

        # 写入环境变量
        if updates:
            self._write_env_file(API_ENV_PATH, updates)

            # 记录历史
            for change in changes:
                self._record_history(
                    action="update",
                    key=f"pairs.{change['key']}",
                    old_value=str(change["old_value"]),
                    new_value=str(change["new_value"]),
                    source="api.env",
                    operator=operator,
                )

        return {
            "updates": changes,
            "current_config": self.get_pair_whitelist(),
            "comment": comment,
            "timestamp": datetime.now().isoformat(),
        }

    def _update_freqtrade_pair_whitelist(self, whitelist: list[str]) -> None:
        """同步更新 Freqtrade 配置文件中的交易对白名单。

        Args:
            whitelist: 新的白名单列表
        """
        if not FREQTRADE_CONFIG_PATH.exists():
            return

        try:
            config = self._read_json_config(FREQTRADE_CONFIG_PATH)
            if "exchange" not in config:
                config["exchange"] = {}
            config["exchange"]["pair_whitelist"] = whitelist

            # 写回配置文件
            FREQTRADE_CONFIG_PATH.write_text(
                json.dumps(config, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            # 配置文件更新失败不影响主流程
            pass

    def get_pair_volatility_params(self, pair: str) -> dict[str, Any]:
        """获取特定交易对的波动率参数。

        Args:
            pair: 交易对名称

        Returns:
            该交易对的波动率参数
        """
        normalized_pair = pair.strip().upper()
        if "/" not in normalized_pair:
            if normalized_pair.endswith("USDT"):
                base = normalized_pair[:-4]
                normalized_pair = f"{base}/USDT"

        params = PAIR_VOLATILITY_PARAMS.get(normalized_pair, {
            "volatility_multiplier": Decimal("1.0"),
            "stop_loss_multiplier": Decimal("1.0"),
            "position_multiplier": Decimal("1.0"),
        })

        return {
            "pair": normalized_pair,
            "params": {
                "volatility_multiplier": float(params["volatility_multiplier"]),
                "stop_loss_multiplier": float(params["stop_loss_multiplier"]),
                "position_multiplier": float(params["position_multiplier"]),
            },
            "is_custom": normalized_pair in PAIR_VOLATILITY_PARAMS,
        }

    def validate_pair_whitelist(self) -> dict[str, Any]:
        """验证交易对白名单配置。

        Returns:
            验证结果
        """
        result: dict[str, Any] = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "pairs_status": [],
        }

        pair_config = self.get_pair_whitelist()
        whitelist = pair_config["whitelist"]
        blacklist = pair_config["blacklist"]
        max_pairs = pair_config["max_pairs"]

        # 检查白名单数量
        if len(whitelist) < 3:
            result["warnings"].append({
                "type": "insufficient_pairs",
                "message": f"白名单交易对数量 ({len(whitelist)}) 较少，建议至少3个",
                "current": len(whitelist),
                "recommended": 3,
            })

        # 检查是否超过最大限制
        if len(whitelist) > max_pairs:
            result["warnings"].append({
                "type": "exceed_max_pairs",
                "message": f"白名单交易对数量 ({len(whitelist)}) 超过最大限制 ({max_pairs})",
                "current": len(whitelist),
                "max": max_pairs,
            })

        # 检查每个交易对的状态
        for pair in whitelist:
            pair_status = {
                "pair": pair,
                "in_blacklist": pair in blacklist,
                "has_volatility_params": pair in PAIR_VOLATILITY_PARAMS,
                "format_valid": "/" in pair and pair.endswith("/USDT"),
            }
            result["pairs_status"].append(pair_status)

            if pair_status["in_blacklist"]:
                result["warnings"].append({
                    "type": "pair_in_blacklist",
                    "message": f"交易对 {pair} 同时在白名单和黑名单中",
                    "pair": pair,
                })

            if not pair_status["format_valid"]:
                result["errors"].append({
                    "type": "invalid_format",
                    "message": f"交易对 {pair} 格式无效，应为 BASE/USDT 格式",
                    "pair": pair,
                })
                result["valid"] = False

        result["effective_count"] = len(pair_config["effective_whitelist"])
        result["timestamp"] = datetime.now().isoformat()

        return result


# 单例实例
config_center_service = ConfigCenterService()


# ========== 统一配置访问接口 ==========


def detect_environment() -> str:
    """检测当前运行环境。

    Returns:
        "server" - 在 Docker 容器或服务器环境运行
        "local" - 在本地开发环境运行
    """
    # 检查是否在 Docker 容器中运行
    if Path("/.dockerenv").exists():
        return "server"

    # 检查环境变量标识
    env_mode = os.environ.get("QUANT_RUNTIME_ENV", "").strip().lower()
    if env_mode in ("server", "production", "docker"):
        return "server"
    if env_mode in ("local", "development", "dev"):
        return "local"

    # 检查典型服务器路径特征
    server_indicators = [
        Path("/app").exists(),
        Path("/freqtrade").exists(),
        os.environ.get("QUANT_RUNTIME_MODE") == "live",
    ]
    if any(server_indicators):
        return "server"

    return "local"


def get_config(
    key: str,
    default: str | int | float | Decimal | None = None,
    *,
    as_type: str = "str",
) -> str | int | float | Decimal | bool | None:
    """统一配置读取接口。

    从以下优先级顺序读取配置：
    1. 环境变量 os.environ (运行时最高优先级)
    2. api.env 文件
    3. CONFIG_DEFAULTS 默认值
    4. 传入的 default 参数

    Args:
        key: 配置键名（如 QUANT_STRATEGY_MIN_ENTRY_SCORE）
        default: 默认值
        as_type: 返回类型 ("str", "int", "float", "decimal", "bool", "list")

    Returns:
        配置值，类型根据 as_type 参数决定
    """
    # 优先从环境变量读取（运行时最高优先级）
    raw_value = os.environ.get(key, "")

    # 如果环境变量为空，从 api.env 文件读取
    if raw_value.strip() == "":
        env_config = config_center_service._read_env_file(API_ENV_PATH)
        raw_value = env_config.get(key, "")

    # 如果还是空，使用 CONFIG_DEFAULTS
    if raw_value.strip() == "":
        default_value = CONFIG_DEFAULTS.get(key)
        if default_value is not None:
            raw_value = str(default_value)

    # 最后使用传入的 default
    if raw_value.strip() == "":
        if default is not None:
            raw_value = str(default)
        else:
            return None

    # 类型转换
    try:
        if as_type == "str":
            return raw_value.strip()
        elif as_type == "int":
            return int(raw_value.strip())
        elif as_type == "float":
            return float(raw_value.strip())
        elif as_type == "decimal":
            return Decimal(raw_value.strip())
        elif as_type == "bool":
            return raw_value.strip().lower() in ("true", "1", "yes", "on")
        elif as_type == "list":
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        else:
            return raw_value.strip()
    except (ValueError, InvalidOperation):
        # 类型转换失败，返回 default 或 None
        if default is not None:
            return default
        return None


def get_config_section_values(section: str) -> dict[str, Any]:
    """获取配置段的所有值（已解析类型）。

    Args:
        section: 配置段名称（如 "strategy", "vpn", "risk" 等）

    Returns:
        配置段的键值对字典
    """
    if section not in CONFIG_SECTIONS:
        raise ValueError(f"配置段 '{section}' 不存在")

    result: dict[str, Any] = {}
    section_info = CONFIG_SECTIONS[section]

    for key in section_info["keys"]:
        # 根据键名推断类型
        if key.endswith("_ENABLED") or key.endswith("_GATE"):
            result[key] = get_config(key, as_type="bool")
        elif key.endswith("_INTERVAL") or key.endswith("_SECONDS") or key.endswith("_MS") or key.endswith("_PERIOD") or key.endswith("_MAX_DAILY") or key.endswith("_MAX_RECORDS") or key.endswith("_HOURS") or key.endswith("_TTL_SECONDS") or key.endswith("_MAX_OPEN_TRADES") or key.endswith("_MAX_PAIRS") or key.endswith("_TOKENS"):
            result[key] = get_config(key, as_type="int")
        elif key.endswith("_PCT") or key.endswith("_RATIO") or key.endswith("_SCORE") or key.endswith("_THRESHOLD") or key.endswith("_RANGE") or key.endswith("_FACTOR") or key.endswith("_MULTIPLIER"):
            result[key] = get_config(key, as_type="decimal")
        elif key.endswith("_TIMEOUT"):
            # _TIMEOUT 可能是整数或浮点数
            raw = get_config(key)
            if raw is not None:
                try:
                    if "." in str(raw):
                        result[key] = float(raw)
                    else:
                        result[key] = int(raw)
                except ValueError:
                    result[key] = raw
            else:
                result[key] = None
        elif key.endswith("_IPS") or key.endswith("_NODES") or key.endswith("_SYMBOLS") or key.endswith("_WHITELIST") or key.endswith("_BLACKLIST"):
            result[key] = get_config(key, as_type="list")
        else:
            result[key] = get_config(key, as_type="str")

    return result


def is_sensitive_key(key: str) -> bool:
    """检查配置键是否为敏感字段。

    Args:
        key: 配置键名

    Returns:
        是否为敏感字段
    """
    return key in SENSITIVE_KEYS


def mask_sensitive_value(key: str, value: str | None) -> str | None:
    """脱敏敏感配置值。

    Args:
        key: 配置键名
        value: 配置值

    Returns:
        脱敏后的值或原值
    """
    if is_sensitive_key(key) and value:
        return "***REDACTED***"
    return value