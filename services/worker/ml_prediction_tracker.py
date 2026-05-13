"""ML 预测实盘表现追踪。

记录 ML 预测与实际收益的对比，支持校准分析和 A/B 对比。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TRACKING_DIR = Path("/tmp/quant-qlib-runtime/tracking")


@dataclass(slots=True)
class PredictionRecord:
    """单次 ML 预测记录。"""

    record_id: str
    symbol: str
    generated_at: str  # ISO 格式
    model_version: str
    probability: float
    score: float
    side: str  # buy/sell
    signal_source: str  # ml / heuristic
    feature_snapshot: dict[str, float] = field(default_factory=dict)

    # 事后填充
    outcome_return_pct: float | None = None
    outcome_at: str | None = None
    holding_hours: float | None = None


@dataclass(slots=True)
class CalibrationMetrics:
    """校准分析指标。"""

    total_predictions: int
    completed_predictions: int
    win_rate: float
    mean_return_pct: float
    brier_score: float
    probability_buckets: list[dict[str, object]]  # 按概率分桶统计


class MLPredictionTracker:
    """ML 预测实盘表现追踪器。"""

    def __init__(self, tracking_dir: Path | None = None) -> None:
        self._tracking_dir = Path(tracking_dir or DEFAULT_TRACKING_DIR)
        self._tracking_dir.mkdir(parents=True, exist_ok=True)
        self._records_path = self._tracking_dir / "prediction_records.json"
        self._records: list[dict[str, object]] = self._load_records()

    def _load_records(self) -> list[dict[str, object]]:
        if not self._records_path.exists():
            return []
        try:
            data = json.loads(self._records_path.read_text(encoding="utf-8"))
            return list(data) if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save_records(self) -> None:
        self._records_path.write_text(json.dumps(self._records, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_prediction(
        self,
        symbol: str,
        probability: float,
        score: float,
        model_version: str,
        side: str = "buy",
        signal_source: str = "ml",
        feature_snapshot: dict[str, float] | None = None,
    ) -> str:
        """记录一次 ML 预测，返回 record_id。"""
        record_id = f"{symbol}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        record: dict[str, object] = {
            "record_id": record_id,
            "symbol": symbol.strip().upper(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": model_version,
            "probability": float(probability),
            "score": float(score),
            "side": side,
            "signal_source": signal_source,
            "feature_snapshot": dict(feature_snapshot or {}),
            "outcome_return_pct": None,
            "outcome_at": None,
            "holding_hours": None,
        }
        self._records.append(record)
        self._save_records()
        logger.info("记录 ML 预测: %s prob=%.3f score=%.3f", symbol, probability, score)
        return record_id

    def record_outcome(
        self,
        record_id: str,
        return_pct: float,
        holding_hours: float | None = None,
    ) -> bool:
        """更新预测记录的实际结果。"""
        for record in self._records:
            if str(record.get("record_id", "")) == record_id:
                record["outcome_return_pct"] = float(return_pct)
                record["outcome_at"] = datetime.now(timezone.utc).isoformat()
                if holding_hours is not None:
                    record["holding_hours"] = float(holding_hours)
                self._save_records()
                logger.info("更新预测结果: %s return=%.2f%%", record_id, return_pct)
                return True
        return False

    def record_outcome_by_symbol(
        self,
        symbol: str,
        return_pct: float,
        holding_hours: float | None = None,
    ) -> bool:
        """按符号查找最近一条未更新的记录并更新结果。"""
        symbol_key = symbol.strip().upper()
        for record in reversed(self._records):
            if str(record.get("symbol", "")) == symbol_key and record.get("outcome_return_pct") is None:
                record["outcome_return_pct"] = float(return_pct)
                record["outcome_at"] = datetime.now(timezone.utc).isoformat()
                if holding_hours is not None:
                    record["holding_hours"] = float(holding_hours)
                self._save_records()
                return True
        return False

    def get_calibration(self, min_samples: int = 5) -> CalibrationMetrics:
        """计算校准指标。"""
        completed = [r for r in self._records if r.get("outcome_return_pct") is not None]
        total = len(self._records)

        if not completed:
            return CalibrationMetrics(
                total_predictions=total,
                completed_predictions=0,
                win_rate=0.0,
                mean_return_pct=0.0,
                brier_score=0.0,
                probability_buckets=[],
            )

        wins = sum(1 for r in completed if float(r.get("outcome_return_pct", 0)) > 0)
        win_rate = wins / len(completed) if completed else 0.0
        mean_return = sum(float(r["outcome_return_pct"]) for r in completed) / len(completed)

        # Brier Score: (1/n) * sum((p_i - o_i)^2) where o_i is 1 if positive return, 0 otherwise
        brier = sum(
            (float(r["probability"]) - (1.0 if float(r.get("outcome_return_pct", 0)) > 0 else 0.0)) ** 2
            for r in completed
        ) / len(completed)

        # 概率分桶
        buckets = self._build_probability_buckets(completed)

        return CalibrationMetrics(
            total_predictions=total,
            completed_predictions=len(completed),
            win_rate=win_rate,
            mean_return_pct=mean_return,
            brier_score=brier,
            probability_buckets=buckets,
        )

    def _build_probability_buckets(self, records: list[dict[str, object]]) -> list[dict[str, object]]:
        """按预测概率分桶统计实际表现。"""
        buckets: dict[str, list[float]] = {}
        for r in records:
            prob = float(r.get("probability", 0.5))
            bucket_key = f"{int(prob * 10) / 10:.1f}-{int(prob * 10) / 10 + 0.1:.1f}"
            if bucket_key not in buckets:
                buckets[bucket_key] = []
            buckets[bucket_key].append(float(r.get("outcome_return_pct", 0)))

        result: list[dict[str, object]] = []
        for key in sorted(buckets.keys()):
            returns = buckets[key]
            result.append({
                "bucket": key,
                "count": len(returns),
                "win_rate": sum(1 for r in returns if r > 0) / len(returns),
                "mean_return_pct": sum(returns) / len(returns),
            })
        return result

    def get_recent_records(self, limit: int = 50) -> list[dict[str, object]]:
        """返回最近的预测记录。"""
        return self._records[-limit:]

    def get_ab_comparison(self) -> dict[str, object]:
        """对比 ML 预测信号与启发式信号的表现。"""
        completed = [r for r in self._records if r.get("outcome_return_pct") is not None]
        ml_records = [r for r in completed if r.get("signal_source") == "ml"]
        heuristic_records = [r for r in completed if r.get("signal_source") != "ml"]

        def _stats(records: list[dict[str, object]]) -> dict[str, object]:
            if not records:
                return {"count": 0, "win_rate": 0.0, "mean_return_pct": 0.0, "sharpe": 0.0}
            returns = [float(r.get("outcome_return_pct", 0)) for r in records]
            wins = sum(1 for r in returns if r > 0)
            mean_r = sum(returns) / len(returns)
            variance = sum((r - mean_r) ** 2 for r in returns) / max(len(returns), 1)
            sharpe = mean_r / (variance ** 0.5) if variance > 0 else 0.0
            return {
                "count": len(records),
                "win_rate": wins / len(records),
                "mean_return_pct": mean_r,
                "sharpe": sharpe,
            }

        return {
            "ml": _stats(ml_records),
            "heuristic": _stats(heuristic_records),
        }

    def clear_old_records(self, keep_count: int = 200) -> int:
        """清理过旧的记录，返回删除条数。"""
        if len(self._records) <= keep_count:
            return 0
        removed = len(self._records) - keep_count
        self._records = self._records[-keep_count:]
        self._save_records()
        return removed


_global_tracker: MLPredictionTracker | None = None


def get_prediction_tracker(tracking_dir: Path | None = None) -> MLPredictionTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = MLPredictionTracker(tracking_dir)
    return _global_tracker
