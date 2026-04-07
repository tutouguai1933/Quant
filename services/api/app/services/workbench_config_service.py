"""工作台配置服务，统一暴露优先级、模型、回测与自动化阈值。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from services.worker.workbench_config import WorkbenchConfig, load_workbench_config


DEFAULT_CONFIG_PATH = Path(".runtime/workbench_config.json")


class WorkbenchConfigService:
    """读取并持久化工作台配置。"""

    def __init__(self, *, config_path: Path | None = None, env: dict[str, str] | None = None) -> None:
        self._config_path = Path(
            config_path
            or os.getenv("QUANT_WORKBENCH_CONFIG_PATH")
            or DEFAULT_CONFIG_PATH
        )
        self._env = env or dict(os.environ)

    def get_config(self) -> dict[str, object]:
        """返回当前可读的工作台配置。"""

        config = load_workbench_config(env=self._env, config_path=self._config_path)
        return config.to_dict()

    def persist_config(self, updates: dict[str, Any]) -> dict[str, object]:
        """合并更新并写入配置文件。"""

        payload = self._read_payload()
        merged = self._deep_merge(payload, updates)
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.get_config()

    def _read_payload(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in base.items():
            if isinstance(value, dict):
                result[key] = dict(value)
            else:
                result[key] = value
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = WorkbenchConfigService._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


workbench_config_service = WorkbenchConfigService()
