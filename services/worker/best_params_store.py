"""最优超参数存储。

提供超参数优化结果的持久化存储，供训练时加载使用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class BestParams:
    """最优参数数据类。"""

    params: dict[str, Any]
    auc: float
    generated_at: datetime
    n_trials: int
    model_type: str


class BestParamsStore:
    """最优超参数存储。

    将优化后的最佳参数持久化，供后续训练使用。
    """

    def __init__(self, store_path: Path) -> None:
        """初始化存储。

        Args:
            store_path: 存储文件路径
        """
        self._store_path = Path(store_path)
        self._ensure_directory()

    def _ensure_directory(self) -> None:
        """确保存储目录存在。"""
        self._store_path.parent.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        params: dict[str, Any],
        auc: float,
        n_trials: int,
        model_type: str = "lightgbm",
    ) -> None:
        """保存最优参数。

        Args:
            params: 最优参数字典
            auc: 最优 AUC 值
            n_trials: 优化轮数
            model_type: 模型类型
        """
        data = {
            "params": params,
            "auc": auc,
            "n_trials": n_trials,
            "model_type": model_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._store_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self) -> BestParams | None:
        """加载最优参数。

        Returns:
            BestParams | None: 最优参数，不存在则返回 None
        """
        if not self._store_path.exists():
            return None

        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
            return BestParams(
                params=data["params"],
                auc=float(data["auc"]),
                generated_at=datetime.fromisoformat(data["generated_at"]),
                n_trials=int(data["n_trials"]),
                model_type=data.get("model_type", "lightgbm"),
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def clear(self) -> None:
        """清除存储。"""
        if self._store_path.exists():
            self._store_path.unlink()

    def exists(self) -> bool:
        """检查是否存在存储。"""
        return self._store_path.exists()

    def get_info(self) -> dict[str, Any]:
        """获取存储信息。

        Returns:
            dict: 存储信息
        """
        best_params = self.load()
        if best_params is None:
            return {
                "exists": False,
                "path": str(self._store_path),
            }

        return {
            "exists": True,
            "path": str(self._store_path),
            "auc": best_params.auc,
            "n_trials": best_params.n_trials,
            "model_type": best_params.model_type,
            "generated_at": best_params.generated_at.isoformat(),
            "params": best_params.params,
        }


# 默认存储路径
DEFAULT_BEST_PARAMS_PATH = Path("/app/.runtime/best_params.json")


def get_best_params_store(store_path: Path | None = None) -> BestParamsStore:
    """获取最优参数存储实例。

    Args:
        store_path: 存储路径

    Returns:
        BestParamsStore: 存储实例
    """
    if store_path is None:
        # 优先使用 Docker 挂载的持久化目录
        if DEFAULT_BEST_PARAMS_PATH.parent.exists():
            store_path = DEFAULT_BEST_PARAMS_PATH
        else:
            from services.worker.qlib_config import DEFAULT_RUNTIME_ROOT
            store_path = Path(DEFAULT_RUNTIME_ROOT) / "best_params.json"
    return BestParamsStore(store_path)
