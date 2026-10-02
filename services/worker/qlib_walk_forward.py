"""Walk-forward 验证器。

严格时间序列交叉验证：时间升序切分、gap 防泄漏隔离、min_train_bars 不足自动减折。
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass
from typing import Callable


logger = logging.getLogger(__name__)


@dataclass
class WalkForwardConfig:
    """Walk-forward 切分配置。"""

    n_folds: int = 4
    min_train_bars: int = 120
    gap_bars: int = 18  # 默认 = 标签窗口（防泄漏）
    mode: str = "expanding"  # expanding（滚动扩展）/ rolling（固定窗口）
    step_bars: int | None = None  # rolling 时的窗口长度
    label_threshold: float = 0.0
    label_column: str = "future_return_pct"


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
        if config.gap_bars < 0 or config.n_folds < 1 or config.min_train_bars < 1:
            raise ValueError("Walk-forward 折数、训练窗口或间隔无效")

        # 确保按时间升序
        sorted_rows = sorted(rows, key=_timestamp)
        timestamps = sorted({_timestamp(row) for row in sorted_rows})

        n_folds = config.n_folds
        total_bars = len(timestamps)
        min_train = max(1, config.min_train_bars)

        # 自动减少折数：每折至少需要 min_train 训练 + gap 间隔 + 1 根测试
        while n_folds > 1 and total_bars < n_folds * (min_train + config.gap_bars + 1):
            n_folds -= 1
        if n_folds < 1:
            n_folds = 1

        # 计算每折大小
        fold_size = total_bars // n_folds
        if n_folds == 1:
            # 单折仍需保留未来测试段，不能把全部数据都用作训练前缀。
            fold_size = max(min_train + config.gap_bars, total_bars // 2)
        if fold_size < 2:
            return []

        folds: list[Fold] = []
        prev_test_end = fold_size  # 第一折 test 从 fold_size 开始
        for i in range(n_folds):
            # test 段连续覆盖 [fold_size, total]：最后一折的起点紧接上一折终点，
            # 而不是 (i+1)*fold_size（那会把最后一折 test 挤到文件末尾只剩几行）
            if i == n_folds - 1:
                test_start = prev_test_end
                test_end = total_bars
            else:
                test_start = (i + 1) * fold_size
                test_end = min(total_bars, test_start + fold_size)
                prev_test_end = test_end

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

            # 样本不足时不扩张训练集越过 gap（会把标签泄漏进测试），整折跳过并记录日志
            if train_end < min_train:
                logger.warning(
                    "Walk-forward 第 %d 折训练样本不足（需要 %d 根，可用 %d 根），跳过该折",
                    i + 1,
                    min_train,
                    max(train_end, 0),
                )
                continue
            if train_end <= train_start:
                # rolling 固定窗口下训练区间为空，跳过该折
                continue

            train_times = set(timestamps[train_start:train_end])
            test_times = set(timestamps[test_start:test_end])
            if not test_times:
                continue
            boundary = min(test_times)
            # 以标签实际成熟时间清除边界重叠；元数据缺失不能证明无泄漏。
            unsafe_times = {_timestamp(row) for row in sorted_rows if _timestamp(row) in train_times
                            and (row.get("label_end_at") is None or int(row["label_end_at"]) >= boundary)}
            train_times -= unsafe_times
            train_rows = [row for row in sorted_rows if _timestamp(row) in train_times]
            test_rows = [row for row in sorted_rows if _timestamp(row) in test_times]
            if len({_timestamp(row) for row in train_rows}) < min_train:
                logger.warning("Walk-forward 第 %d 折成熟标签不足，跳过", i + 1)
                continue

            if train_rows and test_rows:
                folds.append(Fold(
                    index=i + 1,
                    train=train_rows,
                    test=test_rows,
                    test_start_ts=_timestamp(test_rows[0]),
                    test_end_ts=_timestamp(test_rows[-1]),
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
            labels = [1 if _to_float(row.get(config.label_column)) > config.label_threshold else 0 for row in fold.test]
            positive_rate = sum(labels) / max(n_test, 1)
            avg_return = sum(returns) / max(n_test, 1)

            # 用 predictions 和真实方向计算 AUC
            auc = self._compute_auc(predictions, labels)

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
        """按同分数组累计半分，保持 O(n log n) 且不依赖输入顺序。"""
        if len(predictions) != len(labels):
            raise ValueError("预测数量与标签数量不一致")
        if any(not math.isfinite(float(score)) for score in predictions) or any(label not in (0, 1) for label in labels):
            raise ValueError("AUC 预测或标签无效")
        n = len(predictions)
        if n < 2:
            return None
        pos_count = sum(labels)
        neg_count = n - pos_count
        if pos_count == 0 or neg_count == 0:
            return None

        paired = sorted(zip(predictions, labels), key=lambda x: x[0])
        correct = 0.0
        total_pairs = pos_count * neg_count
        seen_neg = 0
        index = 0
        while index < n:
            end = index + 1
            while end < n and paired[end][0] == paired[index][0]:
                end += 1
            positives = sum(label for _, label in paired[index:end])
            negatives = end - index - positives
            correct += positives * (seen_neg + 0.5 * negatives)
            seen_neg += negatives
            index = end
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


def _timestamp(row: dict) -> int:
    """以特征可用收盘时间为切分时间，兼容仅有 open_time 的外部样本。"""
    return int(row.get("generated_at", row.get("open_time", 0)))


def _to_float(value: object) -> float:
    """安全转换为 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
