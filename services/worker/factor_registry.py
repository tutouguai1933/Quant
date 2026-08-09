"""运行时因子启停注册表。

把 FACTOR_DEFINITIONS 里的 enabled 硬编码升级为运行时状态，
支持按因子 IC 体检结果自动启停，状态持久化到 JSON 文件。
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from services.worker.qlib_features import FACTOR_DEFINITIONS, FACTOR_METADATA

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path(".runtime/factor_registry.json")


class FactorRegistry:
    """因子启停注册表（进程内单例 + JSON 持久化）。"""

    def __init__(self, state_path: Path | str | None = None) -> None:
        self._state_path = Path(state_path) if state_path else DEFAULT_STATE_PATH
        self._overrides: dict[str, bool] = {}
        self._lock = threading.Lock()
        self._load()

    def _default_enabled(self, name: str) -> bool:
        metadata = FACTOR_METADATA.get(name) or {}
        return bool(metadata.get("enabled", True))

    def is_enabled(self, name: str) -> bool:
        with self._lock:
            if name in self._overrides:
                return self._overrides[name]
            return self._default_enabled(name)

    def set_enabled(self, name: str, enabled: bool) -> None:
        with self._lock:
            self._overrides[name] = enabled
            self._save_locked()

    def enabled_columns(self, role: str = "primary") -> list[str]:
        items = [i for i in FACTOR_DEFINITIONS if i.get("role") == role]
        return [i["name"] for i in items if self.is_enabled(i["name"])]

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._overrides = {str(k): bool(v) for k, v in dict(data.get("overrides", {})).items()}
        except (json.JSONDecodeError, OSError, IOError) as exc:
            logger.warning("加载因子注册表状态失败（回退默认）: %s", exc)
            self._overrides = {}

    def _save_locked(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            # 原子写：先写临时文件再替换，避免写一半被读取
            temp_path = self._state_path.with_name(f".{self._state_path.name}.tmp")
            with open(temp_path, "w", encoding="utf-8") as fh:
                json.dump({"overrides": self._overrides}, fh, ensure_ascii=False, indent=2)
            temp_path.replace(self._state_path)
        except (OSError, IOError) as exc:
            logger.warning("保存因子注册表状态失败: %s", exc)


factor_registry = FactorRegistry()
