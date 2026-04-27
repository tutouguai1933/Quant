"""配置中心服务。

统一管理分散在 api.env、JSON 文件、docker-compose 中的配置。
提供配置读取、更新、历史追踪和验证功能。
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# 项目根目录
REPO_ROOT = Path(__file__).resolve().parents[4]

# 配置文件路径
API_ENV_PATH = REPO_ROOT / "infra" / "deploy" / "api.env"
FREQTRADE_CONFIG_DIR = REPO_ROOT / "infra" / "freqtrade" / "user_data"
CONFIG_HISTORY_PATH = REPO_ROOT / ".runtime" / "config_history.json"

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
            # 预留告警配置
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
        sensitive_keys = {
            "BINANCE_API_KEY",
            "BINANCE_API_SECRET",
            "QUANT_ADMIN_PASSWORD",
            "QUANT_FREQTRADE_API_PASSWORD",
        }

        if not include_secrets:
            for key in sensitive_keys:
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
        sensitive_keys = {
            "BINANCE_API_KEY",
            "BINANCE_API_SECRET",
            "QUANT_ADMIN_PASSWORD",
            "QUANT_FREQTRADE_API_PASSWORD",
        }

        if not include_secrets:
            for key in sensitive_keys:
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

        # 检查敏感配置是否为空
        sensitive_empty = []
        sensitive_keys = ["BINANCE_API_KEY", "BINANCE_API_SECRET"]
        for key in sensitive_keys:
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
            "sensitive_keys": [
                "BINANCE_API_KEY",
                "BINANCE_API_SECRET",
                "QUANT_ADMIN_PASSWORD",
                "QUANT_FREQTRADE_API_PASSWORD",
            ],
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


# 单例实例
config_center_service = ConfigCenterService()