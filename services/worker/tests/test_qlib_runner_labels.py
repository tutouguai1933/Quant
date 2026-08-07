"""训练管线多窗口标签开关。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.worker.qlib_config import load_qlib_config  # noqa: E402


def test_config_defaults_multi_window_disabled():
    """默认关闭多窗口（保持现状，避免未验证改动上线）。"""
    config = load_qlib_config(env={})
    assert config.multi_window_labels_enabled is False
    assert config.label_windows == [6, 12, 18]


def test_config_reads_env_override():
    """环境变量可开启多窗口并覆盖窗口列表。"""
    config = load_qlib_config(
        env={
            "QUANT_MULTI_WINDOW_LABELS": "true",
            "QUANT_LABEL_WINDOWS": "3,6,12",
        }
    )
    assert config.multi_window_labels_enabled is True
    assert config.label_windows == [3, 6, 12]
