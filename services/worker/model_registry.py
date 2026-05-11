"""模型版本管理注册表。

提供模型注册、版本管理、对比、提升功能。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class ModelRecord:
    """模型记录数据类。"""

    version_id: str
    model_type: str
    model_path: Path
    metrics: dict[str, float]
    training_context: dict[str, Any]
    tags: list[str]
    stage: str  # "staging", "production", "archived"
    created_at: datetime
    updated_at: datetime
    description: str = ""


@dataclass(slots=True)
class ModelComparison:
    """模型对比结果数据类。"""

    version_a: str
    version_b: str
    metrics_diff: dict[str, float]
    winner: str | None  # "a", "b", or None (tie)
    recommendation: str


class ModelRegistry:
    """模型版本管理注册表。

    提供模型的完整生命周期管理。
    """

    def __init__(self, registry_dir: Path) -> None:
        """初始化注册表。

        Args:
            registry_dir: 注册表存储目录
        """
        self._registry_dir = Path(registry_dir)
        self._models_dir = self._registry_dir / "models"
        self._index_path = self._registry_dir / "model_index.json"
        self._production_path = self._registry_dir / "production_model.json"

        self._ensure_directories()
        self._index: dict[str, dict[str, Any]] = self._load_index()

    def _ensure_directories(self) -> None:
        """确保目录存在。"""
        self._registry_dir.mkdir(parents=True, exist_ok=True)
        self._models_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """加载索引。"""
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_index(self) -> None:
        """保存索引。"""
        self._index_path.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def register(
        self,
        model_path: Path,
        model_type: str,
        metrics: dict[str, float],
        training_context: dict[str, Any],
        tags: list[str] | None = None,
        description: str = "",
    ) -> str:
        """注册新模型版本。

        Args:
            model_path: 模型文件路径
            model_type: 模型类型
            metrics: 评估指标
            training_context: 训练上下文
            tags: 标签列表
            description: 描述

        Returns:
            str: 版本 ID
        """
        version_id = f"v_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"

        now = datetime.now(timezone.utc)
        record = {
            "version_id": version_id,
            "model_type": model_type,
            "model_path": str(model_path),
            "metrics": metrics,
            "training_context": training_context,
            "tags": tags or [],
            "stage": "staging",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "description": description,
        }

        self._index[version_id] = record
        self._save_index()

        return version_id

    def get_model(self, version_id: str) -> ModelRecord | None:
        """获取指定版本模型。

        Args:
            version_id: 版本 ID

        Returns:
            ModelRecord | None: 模型记录
        """
        record = self._index.get(version_id)
        if not record:
            return None

        return ModelRecord(
            version_id=record["version_id"],
            model_type=record["model_type"],
            model_path=Path(record["model_path"]),
            metrics=record["metrics"],
            training_context=record["training_context"],
            tags=record["tags"],
            stage=record["stage"],
            created_at=datetime.fromisoformat(record["created_at"]),
            updated_at=datetime.fromisoformat(record["updated_at"]),
            description=record.get("description", ""),
        )

    def list_models(
        self,
        limit: int = 20,
        tags: list[str] | None = None,
        stage: str | None = None,
        model_type: str | None = None,
    ) -> list[ModelRecord]:
        """列出模型版本。

        Args:
            limit: 最大返回数量
            tags: 过滤标签
            stage: 过滤阶段
            model_type: 过滤模型类型

        Returns:
            list[ModelRecord]: 模型记录列表
        """
        records = []
        for version_id, record in self._index.items():
            # 过滤标签
            if tags and not all(t in record["tags"] for t in tags):
                continue
            # 过滤阶段
            if stage and record["stage"] != stage:
                continue
            # 过滤模型类型
            if model_type and record["model_type"] != model_type:
                continue

            records.append(ModelRecord(
                version_id=record["version_id"],
                model_type=record["model_type"],
                model_path=Path(record["model_path"]),
                metrics=record["metrics"],
                training_context=record["training_context"],
                tags=record["tags"],
                stage=record["stage"],
                created_at=datetime.fromisoformat(record["created_at"]),
                updated_at=datetime.fromisoformat(record["updated_at"]),
                description=record.get("description", ""),
            ))

        # 按创建时间降序排序
        records.sort(key=lambda x: x.created_at, reverse=True)
        return records[:limit]

    def promote(self, version_id: str, stage: str) -> bool:
        """提升模型到指定阶段。

        Args:
            version_id: 版本 ID
            stage: 目标阶段 ("staging", "production", "archived")

        Returns:
            bool: 是否成功
        """
        if version_id not in self._index:
            return False

        if stage not in ("staging", "production", "archived"):
            return False

        # 如果提升到 production，先将当前 production 模型降级
        if stage == "production":
            for vid, record in self._index.items():
                if record["stage"] == "production":
                    record["stage"] = "archived"
                    record["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._index[version_id]["stage"] = stage
        self._index[version_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_index()

        # 更新 production 指针
        if stage == "production":
            self._production_path.write_text(
                json.dumps({"version_id": version_id}, ensure_ascii=False),
                encoding="utf-8",
            )

        return True

    def compare(
        self,
        version_id_a: str,
        version_id_b: str,
    ) -> ModelComparison | None:
        """比较两个模型版本。

        Args:
            version_id_a: 版本 A 的 ID
            version_id_b: 版本 B 的 ID

        Returns:
            ModelComparison | None: 对比结果
        """
        record_a = self._index.get(version_id_a)
        record_b = self._index.get(version_id_b)

        if not record_a or not record_b:
            return None

        metrics_a = record_a["metrics"]
        metrics_b = record_b["metrics"]

        # 计算指标差异
        metrics_diff: dict[str, float] = {}
        for key in set(metrics_a.keys()) | set(metrics_b.keys()):
            val_a = metrics_a.get(key, 0.0)
            val_b = metrics_b.get(key, 0.0)
            metrics_diff[key] = val_b - val_a

        # 确定胜者（基于 val_auc）
        auc_a = metrics_a.get("val_auc", 0.0)
        auc_b = metrics_b.get("val_auc", 0.0)

        if auc_b > auc_a + 0.01:  # B 至少好 1%
            winner = "b"
            recommendation = f"建议使用 {version_id_b}，AUC 提升 {auc_b - auc_a:.4f}"
        elif auc_a > auc_b + 0.01:  # A 至少好 1%
            winner = "a"
            recommendation = f"建议使用 {version_id_a}，AUC 提升 {auc_a - auc_b:.4f}"
        else:
            winner = None
            recommendation = "两个模型性能接近，建议选择更简单或更新的版本"

        return ModelComparison(
            version_a=version_id_a,
            version_b=version_id_b,
            metrics_diff=metrics_diff,
            winner=winner,
            recommendation=recommendation,
        )

    def get_production_model(self) -> ModelRecord | None:
        """获取当前生产模型。

        Returns:
            ModelRecord | None: 生产模型记录
        """
        for record in self._index.values():
            if record["stage"] == "production":
                return ModelRecord(
                    version_id=record["version_id"],
                    model_type=record["model_type"],
                    model_path=Path(record["model_path"]),
                    metrics=record["metrics"],
                    training_context=record["training_context"],
                    tags=record["tags"],
                    stage=record["stage"],
                    created_at=datetime.fromisoformat(record["created_at"]),
                    updated_at=datetime.fromisoformat(record["updated_at"]),
                    description=record.get("description", ""),
                )
        return None

    def delete(self, version_id: str) -> bool:
        """删除模型版本。

        Args:
            version_id: 版本 ID

        Returns:
            bool: 是否成功
        """
        if version_id not in self._index:
            return False

        # 不允许删除生产模型
        if self._index[version_id]["stage"] == "production":
            return False

        del self._index[version_id]
        self._save_index()
        return True

    def add_tags(self, version_id: str, tags: list[str]) -> bool:
        """添加标签。

        Args:
            version_id: 版本 ID
            tags: 要添加的标签

        Returns:
            bool: 是否成功
        """
        if version_id not in self._index:
            return False

        current_tags = set(self._index[version_id]["tags"])
        current_tags.update(tags)
        self._index[version_id]["tags"] = list(current_tags)
        self._index[version_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_index()
        return True

    def update_description(self, version_id: str, description: str) -> bool:
        """更新描述。

        Args:
            version_id: 版本 ID
            description: 新描述

        Returns:
            bool: 是否成功
        """
        if version_id not in self._index:
            return False

        self._index[version_id]["description"] = description
        self._index[version_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_index()
        return True


# 全局注册表实例
_registry: ModelRegistry | None = None

# 默认 registry 路径：优先使用 /app/.runtime（Docker 挂载），否则使用 /tmp
DEFAULT_REGISTRY_ROOT = Path("/app/.runtime")


def get_model_registry(registry_dir: Path | None = None) -> ModelRegistry:
    """获取模型注册表实例。

    Args:
        registry_dir: 注册表目录

    Returns:
        ModelRegistry: 注册表实例
    """
    global _registry
    if _registry is None or registry_dir is not None:
        # 优先使用 Docker 挂载的持久化目录
        if DEFAULT_REGISTRY_ROOT.exists():
            dir_path = registry_dir or DEFAULT_REGISTRY_ROOT / "registry"
        else:
            from services.worker.qlib_config import DEFAULT_RUNTIME_ROOT
            dir_path = registry_dir or Path(DEFAULT_RUNTIME_ROOT) / "registry"
        _registry = ModelRegistry(dir_path)
    return _registry
