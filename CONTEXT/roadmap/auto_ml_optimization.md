# 自反馈 ML 优化系统设计

> 目标：建立闭环自动优化机制，持续提升模型性能

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    自反馈优化系统架构                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│   │  监控层      │────▶│  决策层      │────▶│  执行层      │   │
│   │              │     │              │     │              │   │
│   │ - 性能监控   │     │ - 触发判断   │     │ - 超参搜索   │   │
│   │ - 漂移检测   │     │ - 策略选择   │     │ - 模型训练   │   │
│   │ - 预测追踪   │     │ - 优先级排序 │     │ - 效果验证   │   │
│   └──────────────┘     └──────────────┘     └──────────────┘   │
│          │                    │                    │           │
│          └────────────────────┴────────────────────┘           │
│                         反馈循环                                │
│                                                                 │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │                    优化策略库                             │ │
│   │  ├─ 策略1: 超参数优化 (Optuna)                            │ │
│   │  ├─ 策略2: 特征筛选 (重要性 > 阈值)                       │ │
│   │  ├─ 策略3: 标签阈值调整 (正样本率平衡)                    │ │
│   │  ├─ 策略4: 样本权重调整 (类别平衡)                        │ │
│   │  ├─ 策略5: 模型集成 (LightGBM + XGBoost)                  │ │
│   │  └─ 策略6: 训练数据增强 (滚动窗口扩展)                    │ │
│   └──────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、监控层

### 2.1 性能指标监控

```python
@dataclass
class ModelPerformanceMetrics:
    """模型性能指标"""

    # 训练指标
    train_auc: float
    val_auc: float
    overfitting_gap: float  # train_auc - val_auc

    # 实盘追踪指标
    brier_score: float  # 预测校准度
    precision_at_k: float  # Top-K 预测准确率
    actual_return: float  # 实际收益

    # 样本指标
    training_samples: int
    positive_rate: float

    # 健康度评分
    health_score: float  # 综合健康度 0-100
```

### 2.2 性能下降触发条件

| 指标 | 阈值 | 触发动作 |
|------|------|----------|
| val_auc < 0.55 | 连续 3 次 | 触发超参优化 |
| overfitting_gap > 0.15 | 单次 | 增强正则化 |
| brier_score > 0.25 | 单次 | 标签阈值调整 |
| positive_rate < 0.30 | 单次 | 降低 label_threshold |
| positive_rate > 0.60 | 单次 | 提高 label_threshold |

---

## 三、决策层

### 3.1 优化策略优先级

```python
class OptimizationStrategy(Enum):
    """优化策略枚举"""

    # P0: 快速修复（立即执行）
    LABEL_THRESHOLD_ADJUST = "label_threshold_adjust"  # 调整标签阈值
    SAMPLE_WEIGHT_BALANCE = "sample_weight_balance"  # 样本权重平衡

    # P1: 标准优化（定时执行）
    HYPERPARAM_SEARCH = "hyperparam_search"  # 超参数搜索
    FEATURE_SELECTION = "feature_selection"  # 特征筛选

    # P2: 高级优化（周期执行）
    MODEL_ENSEMBLE = "model_ensemble"  # 模型集成
    DATA_AUGMENTATION = "data_augmentation"  # 数据增强


def select_strategy(metrics: ModelPerformanceMetrics) -> OptimizationStrategy:
    """根据指标选择优化策略"""

    # 正样本率异常 -> 调整标签阈值
    if metrics.positive_rate < 0.30 or metrics.positive_rate > 0.60:
        return OptimizationStrategy.LABEL_THRESHOLD_ADJUST

    # 过拟合严重 -> 增强正则化或特征筛选
    if metrics.overfitting_gap > 0.15:
        return OptimizationStrategy.FEATURE_SELECTION

    # 欠拟合 -> 超参搜索
    if metrics.train_auc < 0.60:
        return OptimizationStrategy.HYPERPARAM_SEARCH

    # 性能停滞 -> 模型集成
    if metrics.val_auc < 0.55:
        return OptimizationStrategy.MODEL_ENSEMBLE

    return OptimizationStrategy.HYPERPARAM_SEARCH
```

### 3.2 执行频率

| 策略 | 触发条件 | 执行频率 | 超时 |
|------|----------|----------|------|
| 标签阈值调整 | 自动检测 | 立即 | 1 分钟 |
| 超参搜索 | 定时/触发 | 每 6 小时 | 30 分钟 |
| 特征筛选 | 触发 | 需要时 | 5 分钟 |
| 模型集成 | 定时 | 每天 | 10 分钟 |

---

## 四、执行层

### 4.1 标签阈值自适应调整

```python
class LabelThresholdOptimizer:
    """标签阈值自适应优化器"""

    TARGET_POSITIVE_RATE = 0.40  # 目标正样本率
    MIN_THRESHOLD = 0.5
    MAX_THRESHOLD = 3.0
    STEP = 0.1

    def optimize(self, current_threshold: float, positive_rate: float) -> float:
        """根据正样本率调整阈值"""

        if positive_rate < 0.30:
            # 正样本太少，降低阈值
            new_threshold = max(
                self.MIN_THRESHOLD,
                current_threshold - self.STEP
            )
        elif positive_rate > 0.50:
            # 正样本太多，提高阈值
            new_threshold = min(
                self.MAX_THRESHOLD,
                current_threshold + self.STEP
            )
        else:
            new_threshold = current_threshold

        return new_threshold
```

### 4.2 超参数搜索空间

```python
HYPERPARAM_SEARCH_SPACE = {
    "lightgbm": {
        "num_leaves": (4, 16),  # 减少复杂度
        "learning_rate": (0.01, 0.1),
        "min_child_samples": (20, 100),
        "reg_alpha": (0.1, 2.0),  # L1 正则化
        "reg_lambda": (0.1, 2.0),  # L2 正则化
        "feature_fraction": (0.5, 0.9),
        "bagging_fraction": (0.5, 0.9),
    },
    "label_threshold": (0.5, 2.0),  # 同时搜索标签阈值
}
```

### 4.3 Optuna 优化目标

```python
def objective(trial: optuna.Trial) -> float:
    """优化目标函数"""

    # 采样超参数
    params = {
        "num_leaves": trial.suggest_int("num_leaves", 4, 16),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 100),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.1, 2.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.1, 2.0),
        # ...
    }

    # 采样标签阈值
    label_threshold = trial.suggest_float("label_threshold", 0.5, 2.0)

    # 训练模型
    model, metrics = train_model(params, label_threshold)

    # 多目标优化：最大化 val_auc，最小化过拟合
    score = metrics.val_auc - 0.5 * abs(metrics.train_auc - metrics.val_auc)

    return score
```

---

## 五、反馈循环

### 5.1 预测追踪

```python
class PredictionTracker:
    """预测追踪器"""

    def record_prediction(
        self,
        symbol: str,
        predicted_prob: float,
        actual_return: float,
        threshold: float,
    ):
        """记录预测结果"""

        is_positive = actual_return > threshold
        predicted_positive = predicted_prob > 0.5

        # 计算 Brier Score
        brier_score = (predicted_prob - (1 if is_positive else 0)) ** 2

        # 存储记录
        self._records.append({
            "symbol": symbol,
            "predicted_prob": predicted_prob,
            "actual_return": actual_return,
            "is_positive": is_positive,
            "predicted_positive": predicted_positive,
            "brier_score": brier_score,
            "timestamp": datetime.now(timezone.utc),
        })

    def get_calibration_metrics(self) -> dict:
        """获取校准指标"""

        if not self._records:
            return {}

        # 按预测概率分组
        bins = defaultdict(list)
        for r in self._records:
            bin_key = int(r["predicted_prob"] * 10) / 10  # 0.1 粒度
            bins[bin_key].append(r)

        # 计算每个 bin 的实际正样本率
        calibration = {}
        for bin_key, records in bins.items():
            actual_positive_rate = sum(1 for r in records if r["is_positive"]) / len(records)
            calibration[bin_key] = {
                "predicted_prob": bin_key,
                "actual_rate": actual_positive_rate,
                "count": len(records),
            }

        return calibration
```

### 5.2 自动重训练触发器

```python
class AutoRetrainTrigger:
    """自动重训练触发器"""

    def check_retrain_needed(self) -> dict:
        """检查是否需要重训练"""

        # 1. 检查模型性能
        production_model = get_production_model()
        if production_model.val_auc < 0.55:
            return {
                "needed": True,
                "reason": "val_auc_below_threshold",
                "strategy": OptimizationStrategy.HYPERPARAM_SEARCH,
            }

        # 2. 检查预测校准度
        calibration = prediction_tracker.get_calibration_metrics()
        if self._is_miscalibrated(calibration):
            return {
                "needed": True,
                "reason": "prediction_miscalibrated",
                "strategy": OptimizationStrategy.LABEL_THRESHOLD_ADJUST,
            }

        # 3. 检查数据漂移
        if self._detect_data_drift():
            return {
                "needed": True,
                "reason": "data_drift_detected",
                "strategy": OptimizationStrategy.HYPERPARAM_SEARCH,
            }

        # 4. 定时触发
        last_train_time = get_last_train_time()
        if (datetime.now() - last_train_time) > timedelta(hours=6):
            return {
                "needed": True,
                "reason": "scheduled_retrain",
                "strategy": OptimizationStrategy.HYPERPARAM_SEARCH,
            }

        return {"needed": False}
```

---

## 六、实现计划

### Phase 1: 监控基础 (1 天)

- [ ] 实现 ModelPerformanceMetrics 数据结构
- [ ] 实现性能指标收集
- [ ] 实现 Brier Score 计算

### Phase 2: 自适应标签阈值 (1 天)

- [ ] 实现 LabelThresholdOptimizer
- [ ] 集成到训练流程
- [ ] 添加触发条件检测

### Phase 3: 超参搜索增强 (1 天)

- [ ] 扩展 Optuna 搜索空间（包含 label_threshold）
- [ ] 实现多目标优化
- [ ] 添加搜索结果验证

### Phase 4: 反馈循环 (1 天)

- [ ] 实现 PredictionTracker 增强
- [ ] 实现 AutoRetrainTrigger
- [ ] 集成到 OpenClaw 调度

---

## 七、预期效果

| 阶段 | val_auc 目标 | 过拟合 gap 目标 |
|------|-------------|----------------|
| 当前 | 0.526 | 0.08 |
| Phase 1-2 | 0.55 | 0.10 |
| Phase 3-4 | 0.60 | 0.08 |
| 稳定运行 | 0.65+ | < 0.10 |
