"""因子 IC 体检器。

训练后评估每个主因子最近 IC：
- IC >= 0.05: keep（保持）
- 0.0 <= IC < 0.05: downgrade（建议降权）
- IC < 0 且连续 2 轮: disable（自动禁用）
- IC < 0 第一轮: watch（警告观察）
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

from services.worker.qlib_features import PRIMARY_FEATURE_COLUMNS

KEEP_IC = 0.05
DOWNGRADE_IC = 0.0
WATCH_ROUNDS = 1
DISABLE_ROUNDS = 2

DEFAULT_STATE_PATH = Path(".runtime/factor_ic_state.json")

logger = logging.getLogger(__name__)


class FactorIcDoctor:
    """基于 IC 序列做因子启停与降权决策。"""

    def __init__(self, state_path: Path | str | None = None) -> None:
        self._state_path = Path(state_path) if state_path else DEFAULT_STATE_PATH
        self._negative_rounds: dict[str, int] = {}
        self._lock = threading.Lock()
        self._load()

    def assess(self, report: dict[str, object]) -> dict[str, object]:
        """输入训练报告，返回每个主因子的体检动作。"""
        evaluation = dict(report.get("factor_evaluation") or {})
        ic_series = list(evaluation.get("ic_series") or [])
        latest_ic: dict[str, float] = {}
        for entry in ic_series:
            factor = str(entry.get("factor", ""))
            ic = entry.get("ic")
            if factor and isinstance(ic, (int, float)):
                latest_ic[factor] = float(ic)

        actions: dict[str, str] = {}
        with self._lock:
            for factor in PRIMARY_FEATURE_COLUMNS:
                if factor not in latest_ic:
                    actions[factor] = "unknown"
                    continue
                ic = latest_ic[factor]
                if ic >= KEEP_IC:
                    self._negative_rounds[factor] = 0
                    actions[factor] = "keep"
                elif ic >= DOWNGRADE_IC:
                    self._negative_rounds[factor] = 0
                    actions[factor] = "downgrade"
                else:
                    rounds = self._negative_rounds.get(factor, 0) + 1
                    self._negative_rounds[factor] = rounds
                    actions[factor] = "disable" if rounds >= DISABLE_ROUNDS else "watch"
            self._save_locked()

        return {
            "actions": actions,
            "negative_rounds": dict(self._negative_rounds),
            "assessed_at": time.time(),
        }

    def _load(self) -> None:
        if not self._state_path.exists():
            return
        try:
            with open(self._state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._negative_rounds = {str(k): int(v) for k, v in dict(data.get("negative_rounds", {})).items()}
        except (json.JSONDecodeError, OSError, IOError) as exc:
            logger.warning("加载 IC 体检状态失败（回退默认）: %s", exc)
            self._negative_rounds = {}

    def _save_locked(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w", encoding="utf-8") as fh:
                json.dump({"negative_rounds": self._negative_rounds}, fh, ensure_ascii=False, indent=2)
        except (OSError, IOError) as exc:
            logger.warning("保存 IC 体检状态失败: %s", exc)
