"""Qlib 研究层配置。

这个文件负责统一读取研究层运行目录，并给出清晰的可执行状态。
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_RUNTIME_ROOT = Path("/tmp/quant-qlib-runtime")


class QlibConfigurationError(RuntimeError):
    """研究层配置不可执行时抛出的错误。"""


@dataclass(frozen=True)
class QlibRuntimePaths:
    """研究层运行目录集合。"""

    runtime_root: Path
    dataset_dir: Path
    artifacts_dir: Path
    runs_dir: Path
    latest_training_path: Path
    latest_inference_path: Path


@dataclass(frozen=True)
class QlibRuntimeConfig:
    """研究层配置快照。"""

    status: str
    detail: str
    backend: str
    qlib_available: bool
    paths: QlibRuntimePaths

    def ensure_ready(self) -> None:
        """确认研究层目录已经可执行。"""

        if self.status != "ready":
            raise QlibConfigurationError(self.detail)
        if not self.paths.runtime_root.exists():
            raise QlibConfigurationError(f"研究层运行目录不存在：{self.paths.runtime_root}")


def load_qlib_config(
    env: dict[str, str] | None = None,
    *,
    require_explicit: bool = False,
) -> QlibRuntimeConfig:
    """读取研究层配置。"""

    values = env if env is not None else dict(os.environ)
    runtime_root_raw = values.get("QUANT_QLIB_RUNTIME_ROOT", "").strip()
    session_id = values.get("QUANT_QLIB_SESSION_ID", "").strip()

    if require_explicit and not runtime_root_raw and not session_id:
        return _build_config(
            runtime_root=DEFAULT_RUNTIME_ROOT,
            status="unconfigured",
            detail="未设置 QUANT_QLIB_RUNTIME_ROOT 或 QUANT_QLIB_SESSION_ID，研究层当前只能返回明确状态，不能直接执行训练。",
        )

    if runtime_root_raw:
        runtime_root = Path(runtime_root_raw).expanduser()
    elif session_id:
        runtime_root = DEFAULT_RUNTIME_ROOT / session_id
    else:
        runtime_root = DEFAULT_RUNTIME_ROOT
    return _build_config(
        runtime_root=runtime_root,
        status="ready",
        detail=f"研究层目录已指向 {runtime_root}",
    )


def _build_config(runtime_root: Path, *, status: str, detail: str) -> QlibRuntimeConfig:
    """构造配置对象。"""

    qlib_available = importlib.util.find_spec("qlib") is not None
    backend = "qlib" if qlib_available else "qlib-fallback"
    paths = QlibRuntimePaths(
        runtime_root=runtime_root,
        dataset_dir=runtime_root / "dataset",
        artifacts_dir=runtime_root / "artifacts",
        runs_dir=runtime_root / "runs",
        latest_training_path=runtime_root / "latest_training.json",
        latest_inference_path=runtime_root / "latest_inference.json",
    )
    return QlibRuntimeConfig(
        status=status,
        detail=detail,
        backend=backend,
        qlib_available=qlib_available,
        paths=paths,
    )
