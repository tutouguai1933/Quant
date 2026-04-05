"""Qlib 研究层配置。

这个文件负责统一读取研究层运行目录，并给出清晰的可执行状态。
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


DEFAULT_RUNTIME_ROOT = Path("/tmp/quant-qlib-runtime")
DEFAULT_BACKTEST_FEE_BPS = Decimal("10")
DEFAULT_BACKTEST_SLIPPAGE_BPS = Decimal("5")


class QlibConfigurationError(RuntimeError):
    """研究层配置不可执行时抛出的错误。"""


@dataclass(frozen=True)
class QlibRuntimePaths:
    """研究层运行目录集合。"""

    runtime_root: Path
    dataset_dir: Path
    dataset_snapshots_dir: Path
    artifacts_dir: Path
    runs_dir: Path
    latest_training_path: Path
    latest_inference_path: Path
    latest_dataset_snapshot_path: Path
    experiment_index_path: Path


@dataclass(frozen=True)
class QlibRuntimeConfig:
    """研究层配置快照。"""

    status: str
    detail: str
    backend: str
    qlib_available: bool
    backtest_fee_bps: Decimal
    backtest_slippage_bps: Decimal
    force_validation_top_candidate: bool
    paths: QlibRuntimePaths

    def ensure_ready(self) -> None:
        """确认研究层目录已经可执行。"""

        if self.status != "ready":
            raise QlibConfigurationError(self.detail)
        try:
            self.paths.runtime_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise QlibConfigurationError(f"研究层运行目录不可写：{self.paths.runtime_root}") from exc


def load_qlib_config(
    env: dict[str, str] | None = None,
    *,
    require_explicit: bool = False,
) -> QlibRuntimeConfig:
    """读取研究层配置。"""

    values = env if env is not None else dict(os.environ)
    runtime_root_raw = values.get("QUANT_QLIB_RUNTIME_ROOT", "").strip()
    session_id = values.get("QUANT_QLIB_SESSION_ID", "").strip()
    backtest_fee_bps = _read_decimal(
        values.get("QUANT_QLIB_BACKTEST_FEE_BPS"),
        default=DEFAULT_BACKTEST_FEE_BPS,
        env_name="QUANT_QLIB_BACKTEST_FEE_BPS",
    )
    backtest_slippage_bps = _read_decimal(
        values.get("QUANT_QLIB_BACKTEST_SLIPPAGE_BPS"),
        default=DEFAULT_BACKTEST_SLIPPAGE_BPS,
        env_name="QUANT_QLIB_BACKTEST_SLIPPAGE_BPS",
    )
    force_validation_top_candidate = str(values.get("QUANT_QLIB_FORCE_TOP_CANDIDATE", "")).strip().lower() == "true"

    if require_explicit and not runtime_root_raw and not session_id:
        return _build_config(
            runtime_root=DEFAULT_RUNTIME_ROOT,
            status="unconfigured",
            detail="未设置 QUANT_QLIB_RUNTIME_ROOT 或 QUANT_QLIB_SESSION_ID，研究层当前只能返回明确状态，不能直接执行训练。",
            backtest_fee_bps=backtest_fee_bps,
            backtest_slippage_bps=backtest_slippage_bps,
            force_validation_top_candidate=force_validation_top_candidate,
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
        backtest_fee_bps=backtest_fee_bps,
        backtest_slippage_bps=backtest_slippage_bps,
        force_validation_top_candidate=force_validation_top_candidate,
    )


def _build_config(
    runtime_root: Path,
    *,
    status: str,
    detail: str,
    backtest_fee_bps: Decimal,
    backtest_slippage_bps: Decimal,
    force_validation_top_candidate: bool,
) -> QlibRuntimeConfig:
    """构造配置对象。"""

    qlib_available = importlib.util.find_spec("qlib") is not None
    backend = "qlib" if qlib_available else "qlib-fallback"
    paths = QlibRuntimePaths(
        runtime_root=runtime_root,
        dataset_dir=runtime_root / "dataset",
        dataset_snapshots_dir=runtime_root / "dataset" / "snapshots",
        artifacts_dir=runtime_root / "artifacts",
        runs_dir=runtime_root / "runs",
        latest_training_path=runtime_root / "latest_training.json",
        latest_inference_path=runtime_root / "latest_inference.json",
        latest_dataset_snapshot_path=runtime_root / "dataset" / "latest_dataset_snapshot.json",
        experiment_index_path=runtime_root / "runs" / "experiment_index.json",
    )
    return QlibRuntimeConfig(
        status=status,
        detail=detail,
        backend=backend,
        qlib_available=qlib_available,
        backtest_fee_bps=backtest_fee_bps,
        backtest_slippage_bps=backtest_slippage_bps,
        force_validation_top_candidate=force_validation_top_candidate,
        paths=paths,
    )


def _read_decimal(value: str | None, *, default: Decimal, env_name: str) -> Decimal:
    """读取回测配置里的十进制值。"""

    raw = str(value or "").strip()
    if not raw:
        return default
    try:
        parsed = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{env_name} 必须是数字") from exc
    if parsed < 0:
        raise ValueError(f"{env_name} 不能小于 0")
    return parsed
