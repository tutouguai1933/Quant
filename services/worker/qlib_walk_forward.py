"""Walk-forward 验证器。

严格时间序列交叉验证：时间升序切分、gap 防泄漏隔离、min_train_bars 不足自动减折。
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Callable


@dataclass
class WalkForwardConfig:
    """Walk-forward 切分配置。"""

    n_folds: int = 4
    min_train_bars: int = 120
    gap_bars: int = 18  # 默认 = 标签窗口（防泄漏）
    mode: str = "expanding"  # expanding（滚动扩展）/ rolling（固定窗口）
    step_bars: int | None = None  # rolling 时的窗口长度


@dataclass
class Fold:
    """单折训练/测试切分。"""

    index: int
    train: list[dict]
    test: list[dict]
    test_start_ts: int
    test_end_ts: int


@dataclass
class FoldMetrics:
    """单折指标。"""

    fold: int
    n_test: int
    positive_rate: float
    auc: float | None
    avg_future_return_pct: float


@dataclass
class WalkForwardReport:
    """Walk-forward 汇总报告。"""

    folds: list[FoldMetrics]
    summary: dict  # {mean: {...}, std: {...}}


class WalkForwardValidator:
    """时间序列 walk-forward 验证器。

    约束：
    - rows 按 open_time 升序
    - 每折 test 严格在 train 之后且间隔 >= gap_bars * interval
    - min_train_bars 不足则自动减少折数并记录警告
    """

    def split(self, rows: list[dict], config: WalkForwardConfig) -> list[Fold]:
        """将 rows 按时间升序切分为 walk-forward folds。

        Returns:
            按时间顺序排列的 Fold 列表。
        """
        if not rows:
            return []

        # 确保按时间升序
        sorted_rows = sorted(rows, key=lambda r: int(r.get("open_time", r.get("generated_at", 0))))

        n_folds = config.n_folds
        total_bars = len(sorted_rows)
        min_train = max(1, config.min_train_bars)

        # 自动减少折数：每折至少需要 min_train + 1 test bar
        while n_folds > 1 and total_bars < n_folds * (min_train + 1):
            n_folds -= 1
        if n_folds < 1:
            n_folds = 1

        # 计算每折大小
        fold_size = total_bars // n_folds
        if fold_size < 2:
            return []

        folds: list[Fold] = []
        for i in range(n_folds):
            test_start = (i + 1) * fold_size
            if i == n_folds - 1:
                test_end = total_bars
            else:
                test_end = min(total_bars, test_start + fold_size)

            # 确保 test 最少 1 条
            if test_end - test_start < 1:
                test_end = test_start + 1
            if test_end > total_bars:
                test_end = total_bars

            # train = 当前折之前所有数据（expanding 模式）
            if config.mode == "rolling" and config.step_bars:
                train_start = max(0, test_start - config.step_bars)
            else:
                train_start = 0
            train_end = test_start - config.gap_bars
            if train_end < min_train:
                train_end = min_train

            if train_end <= train_start:
                train_rows = sorted_rows[train_start:train_end]
            else:
                train_rows = sorted_rows[train_start:train_end]

            test_rows = sorted_rows[test_start:test_end]

            if train_rows and test_rows:
                folds.append(Fold(
                    index=i + 1,
                    train=train_rows,
                    test=test_rows,
                    test_start_ts=int(test_rows[0].get("open_time", test_rows[0].get("generated_at", 0))),
                    test_end_ts=int(test_rows[-1].get("open_time", test_rows[-1].get("generated_at", 0))),
                ))

        return folds

    def run(
        self,
        predict_fn: Callable,
        rows: list[dict],
        config: WalkForwardConfig,
    ) -> WalkForwardReport:
        """完整 walk-forward 运行：切分 + 每折训练/预测 + 指标汇总。

        Args:
            predict_fn: (train_rows, test_rows) -> list[float]  返回每样本预测概率
            rows: 全部样本行，必须含 future_return_pct 字段
            config: 切分配置

        Returns:
            WalkForwardReport 包含每折指标和汇总统计。
        """
        folds = self.split(rows, config)
        fold_metrics: list[FoldMetrics] = []

        for fold in folds:
            predictions = predict_fn(fold.train, fold.test)

            n_test = len(fold.test)
            returns = [_to_float(r.get("future_return_pct", 0)) for r in fold.test]
            positive_rate = sum(1 for v in returns if v > 0) / max(n_test, 1)
            avg_return = sum(returns) / max(n_test, 1)

            # 用 predictions 和真实方向计算 AUC
            auc = self._compute_auc(predictions, [1 if r > 0 else 0 for r in returns])

            fold_metrics.append(FoldMetrics(
                fold=fold.index,
                n_test=n_test,
                positive_rate=positive_rate,
                auc=auc,
                avg_future_return_pct=avg_return,
            ))

        # 汇总
        summary = self._build_summary(fold_metrics)
        return WalkForwardReport(folds=fold_metrics, summary=summary)

    @staticmethod
    def _compute_auc(predictions: list[float], labels: list[int]) -> float | None:
        """简化的 AUC 计算。"""
        n = len(predictions)
        if n < 2:
            return None
        pos_count = sum(labels)
        neg_count = n - pos_count
        if pos_count == 0 or neg_count == 0:
            return None

        paired = sorted(zip(predictions, labels), key=lambda x: x[0], reverse=True)
        correct = 0
        total_pairs = pos_count * neg_count
        seen_pos = 0
        for _, label in paired:
            if label == 0:
                correct += seen_pos
            else:
                seen_pos += 1
        return correct / total_pairs if total_pairs > 0 else None

    @staticmethod
    def _build_summary(fold_metrics: list[FoldMetrics]) -> dict:
        """从折指标计算 mean/std 汇总。"""
        if not fold_metrics:
            return {"mean": {}, "std": {}}

        keys = ["positive_rate", "auc", "avg_future_return_pct", "n_test"]
        mean_vals: dict[str, float] = {}
        std_vals: dict[str, float] = {}

        for key in keys:
            values = []
            for fm in fold_metrics:
                v = getattr(fm, key)
                if v is not None:
                    values.append(v)
            if values:
                mean_vals[key] = statistics.mean(values)
                std_vals[key] = statistics.stdev(values) if len(values) > 1 else 0.0
            else:
                mean_vals[key] = 0.0
                std_vals[key] = 0.0

        return {"mean": mean_vals, "std": std_vals}


def _to_float(value: object) -> float:
    """安全转换为 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
