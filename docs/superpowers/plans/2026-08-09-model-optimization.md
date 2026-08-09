# 模型优化：标签质量实验 + 排序学习 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升验证 AUC（当前 0.532，接近抛硬币）。分两个阶段：①标签质量对比实验选出信噪比更高的标签配置；②把二分类模型升级为排序学习（更贴合"16 币选最优"的任务目标）。

**Architecture:** 当前管线：16 币 4h K 线 → 特征(17个) → 标签(earliest_hit, target 1%/stop -1%, 1-3天窗口) → lightgbm 二分类 → roc_auc 评估。阶段 A 不改代码架构，用实验脚本在同一数据集上对比 6 组标签配置的验证 AUC，选优后改默认配置。阶段 B 为模型层升级：lightgbm 支持 lambdarank（按同一时间点 16 个币分组，排序学习），评估增加 ndcg@5 / top-5 命中率，保留 AUC 参考；通过配置开关 `QUANT_QLIB_MODEL_MODE` 在 binary/ranking 间切换，便于 A/B 对比。

**Tech Stack:** Python + lightgbm（LGBMClassifier → LGBMRanker/lambdarank objective）+ pytest + 服务器 dataset cache 数据（/app/.runtime/qlib/dataset/cache/*.json，16 币 4h，约 42k 行）

---

## 关键背景（执行者必读）

- 数据行结构：`{symbol, generated_at(毫秒时间戳), 17个特征列, future_return_pct(字符串), label(buy/sell/watch), is_trainable}`
- 标签构建：`services/worker/qlib_labels.py` 的 `build_label_rows`（earliest_hit 模式：未来 1-3 天窗口内先到 +target% 算 buy，先到 stop% 算 sell）
- 训练：`services/worker/ml/trainer.py` `_prepare_data` 把 `future_return_pct > 0` 转二分类 y；`services/worker/ml/model.py` lightgbm binary
- 配置流：`infra/data/runtime/workbench_config.json` research 段 → `services/worker/qlib_config.py`（label_mode/label_target_pct/label_stop_pct/holding_window_min_days/max_days）→ `qlib_runner._fit_model`
- 评估：`trainer._calculate_metrics` 输出 train_auc/val_auc（sklearn roc_auc_score）
- 数据在**服务器**容器内（/app/.runtime/qlib/dataset/cache/），本地没有。实验脚本必须能在服务器容器内运行（docker exec），或数据拷贝到本地

---

## 阶段 A：标签质量实验（Task 1-3）

### Task 1: 标签对比实验脚本

**Files:**
- Create: `services/worker/tests/test_label_sweep.py`（脚本核心函数的单元测试）
- Create: `scripts/run_label_sweep.py`（实验入口，可在服务器容器内跑）

- [ ] **Step 1: 写标签配置实验核心函数（TDD）**

先在 `scripts/run_label_sweep.py` 实现两个纯函数并写测试：

```python
"""标签配置对比实验：同一数据集上用不同标签配置训练，对比验证 AUC。

用法（服务器容器内）：
    cd /app && python3 scripts/run_label_sweep.py
输出：每组配置的训练/验证 AUC 对比表 + JSON 结果文件。
"""

from __future__ import annotations

import json
import glob
import sys
from decimal import Decimal
from typing import Any

# 实验标签配置组：基准(当前线上) + 5 组候选
LABEL_SWEEP_CONFIGS: list[dict[str, Any]] = [
    {"name": "baseline_1pct_1-3d", "label_mode": "earliest_hit", "target": "1", "stop": "-1", "min_days": 1, "max_days": 3},
    {"name": "target_2pct_1-3d", "label_mode": "earliest_hit", "target": "2", "stop": "-1", "min_days": 1, "max_days": 3},
    {"name": "target_3pct_1-3d", "label_mode": "earliest_hit", "target": "3", "stop": "-1", "min_days": 1, "max_days": 3},
    {"name": "target_2pct_2-5d", "label_mode": "earliest_hit", "target": "2", "stop": "-1", "min_days": 2, "max_days": 5},
    {"name": "target_2pct_stop2_1-3d", "label_mode": "earliest_hit", "target": "2", "stop": "-2", "min_days": 1, "max_days": 3},
    {"name": "close_only_2pct_2-5d", "label_mode": "close_only", "target": "2", "stop": "-1", "min_days": 2, "max_days": 5},
]


def load_dataset_rows(cache_dir: str) -> list[dict[str, Any]]:
    """从 dataset cache 目录加载全部特征行（training/validation/testing 合并）。"""
    rows: list[dict[str, Any]] = []
    for path in sorted(glob.glob(f"{cache_dir}/*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                bundle = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("training_rows", "validation_rows", "testing_rows"):
            rows.extend(bundle.get(key) or [])
    return rows


def split_time_ordered(rows: list[dict[str, Any]], *, train_ratio: float = 0.75) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """按 generated_at 时间升序切分：前 75% 训练、后 25% 验证（与 walk-forward 一致的无泄漏切分）。"""
    ordered = sorted(rows, key=lambda r: int(r.get("generated_at", 0)))
    split_idx = int(len(ordered) * train_ratio)
    return ordered[:split_idx], ordered[split_idx:]


def relabel_rows(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    """按给定标签配置重新生成 future_return_pct（复用 qlib_labels 的窗口分类逻辑）。"""
    from services.worker.qlib_labels import build_label_rows

    result: list[dict[str, Any]] = []
    # 按 symbol 分组，因为 build_label_rows 需要该币的完整 K 线序列
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_symbol.setdefault(str(row.get("symbol", "")), []).append(row)
    for symbol, symbol_rows in by_symbol.items():
        # build_label_rows 接受 candles（含 close_time），特征行自带 generated_at=close_time
        candles = [{"close_time": int(r.get("generated_at", 0)), "close": Decimal("1"), "high": Decimal("1"), "low": Decimal("1"), "open": Decimal("1"), "volume": Decimal("1")} for r in symbol_rows]
        # 注意：真实 close 值在特征行里不存在（标签在特征构建前已算好），
        # 这里直接修改现有行的 future_return_pct 字段：
        # 简化方案：标签值已经从特征行不可恢复，改为“实验只比较不同 target/窗口对现有标签的再分类”。
        # 若无法从特征行恢复价格，则本函数退化为：按 config 从现有 future_return_pct 重分类——
        # 见下方 _reclassify_from_existing。
    return result
```

**重要说明（执行者必须先读）**：特征行里**没有价格字段**（raw_row 只有特征和 future_return_pct），无法从 cache 恢复 K 线价格重新打标签。因此实验必须**从 K 线源头重建**：实验脚本改为读取 K 线存储（`services/api/app/services/kline_store.py` 或数据库），重建特征+标签。若 K 线不可用，则退化为"标签阈值对比"（把现有 future_return_pct 按不同 target 阈值重分类，仅比较阈值敏感性，不做完整标签重算）。

**具体实现（执行者按此做，若与上面冲突以此为准）**：
1. 优先：读 K 线源（`services/api/app/services/kline_store.py` 的 `read()`，按 symbol 读 4h K 线，lookback 365 天），用 `qlib_features.build_feature_rows` + `qlib_labels.build_label_rows` 重建特征+标签，然后训练对比
2. 退化方案（K 线不可用）：对现有 cache 行的 `future_return_pct` 按新阈值重分类——`label = buy if f >= target else (sell if f <= stop else watch)`，二分类 y = 1 if label == buy else 0，训练对比 AUC。该方案只能体现阈值敏感性，报告里注明
3. 训练复用 `services/worker/ml/trainer.py` 的 ModelTrainer（model_type=lightgbm，label_threshold 保持 0 或按 buy/sell 调整），对比 val_auc
4. 输出：打印每组的 train_auc/val_auc/正样本率/样本数，并把结果写入 `/tmp/label_sweep_result.json`

- [ ] **Step 2: 测试核心函数**

`services/worker/tests/test_label_sweep.py`：
```python
"""标签对比实验核心函数测试。"""

import json
import tempfile
from pathlib import Path

from scripts.run_label_sweep import load_dataset_rows, split_time_ordered


def test_load_dataset_rows_merges_three_row_kinds() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        bundle = {
            "training_rows": [{"symbol": "BTCUSDT", "generated_at": 1}],
            "validation_rows": [{"symbol": "BTCUSDT", "generated_at": 2}],
            "testing_rows": [{"symbol": "BTCUSDT", "generated_at": 3}],
        }
        (Path(tmp) / "cache_1.json").write_text(json.dumps(bundle), encoding="utf-8")
        rows = load_dataset_rows(tmp)
        assert len(rows) == 3


def test_split_time_ordered_respects_timestamp() -> None:
    rows = [{"symbol": "A", "generated_at": i * 10} for i in range(10)]
    train, valid = split_time_ordered(rows, train_ratio=0.75)
    assert len(train) == 7 and len(valid) == 3
    assert all(int(r["generated_at"]) < int(v["generated_at"]) for r in train for v in valid)
```

- [ ] **Step 3: 运行测试（先失败后通过）**

Run: `cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_label_sweep.py -v`
Expected: 初始 FAIL（模块不存在），实现后 PASS

- [ ] **Step 4: 提交**

```bash
git add scripts/run_label_sweep.py services/worker/tests/test_label_sweep.py
git commit -m "feat: 标签配置对比实验脚本+测试"
```

### Task 2: 服务器执行标签实验并分析

- [ ] **Step 1: 把脚本同步到服务器并在容器内执行**

```bash
# 推送代码到 git 后：
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "cd ~/Quant && git pull"
ssh -i ~/.ssh/id_aliyun_djy djy@39.106.11.65 "docker exec quant-api sh -c 'cd /app && python3 scripts/run_label_sweep.py 2>&1 | tail -40'"
```

Expected: 每组配置输出 train_auc/val_auc/正样本率；结果存 /tmp/label_sweep_result.json

- [ ] **Step 2: 分析结果并记录结论**

分析要点：
- 对比 6 组配置的 val_auc，找出**显著更高**（> +0.01）的组
- 同时看正样本率（太低如 <0.2 说明标签太严，模型学不到正例；太高如 >0.6 说明标签太松）
- 把结论写入 Task 3 的决策依据（在提交信息里注明）

### Task 3: 最优标签配置设为默认

**Files:**
- Modify: `services/api/app/services/workbench_config_service.py`（research 段默认值，约 139-165 行 presets）
- Modify: `services/worker/qlib_config.py`（label 相关默认值，约 334-368 行）
- Test: `services/api/tests/test_workbench_config_service.py`（如果存在默认值断言则更新）

- [ ] **Step 1: 按实验结果更新默认标签配置**

把 Task 2 选出的最优配置写入 workbench_config_service 的默认 preset 和 qlib_config 的默认值（例如 target 1→2、窗口 1-3d→2-5d 等，具体数值以实验为准）。

- [ ] **Step 2: 更新相关测试断言（如有）**

```bash
cd /home/djy/Quant && python3 -m pytest services/api/tests/test_workbench_config_service.py -q 2>&1 | tail -3
```
如测试断言了旧默认值，更新为新值。允许既有失败（基线已确认的 9 个 workbench 失败）保持原样。

- [ ] **Step 3: 提交**

```bash
git add -A && git commit -m "feat: 标签配置按实验最优更新(target/窗口), 提升信噪比"
```

---

## 阶段 B：排序学习（Task 4-7）

### Task 4: MLModel 增加 lambdarank 支持

**Files:**
- Modify: `services/worker/ml/model.py`
- Test: `services/worker/tests/test_model_ranking.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
"""排序学习模式单元测试。"""

import numpy as np
import pytest

from services.worker.ml.model import MLModel


def test_ranking_model_trains_and_predicts() -> None:
    """LGBMRanker 可训练并输出分数。"""
    model = MLModel(model_type="lightgbm", params={"objective": "lambdarank", "label_gain": [0, 1, 3]})
    # 3 组样本（按组排序），每组 4 条
    X = np.random.RandomState(42).rand(12, 5)
    y = np.array([0, 1, 2, 1, 0, 2, 1, 1, 1, 2, 0, 1], dtype=np.int32)
    groups = np.array([4, 4, 4], dtype=np.int32)
    model.fit(X, y, eval_set=(X, y), groups=groups, eval_groups=groups)
    preds = model.predict(X)
    assert preds.shape == (12,)
    assert np.isfinite(preds).all()


def test_binary_model_rejects_groups() -> None:
    """binary 模式不接受 group 参数（防止误用）。"""
    model = MLModel(model_type="lightgbm", params={"objective": "binary"})
    X = np.random.RandomState(1).rand(6, 3)
    y = np.array([0, 1, 0, 1, 0, 1])
    with pytest.raises(ValueError, match="group"):
        model.fit(X, y, groups=np.array([3, 3], dtype=np.int32))
```

- [ ] **Step 2: 实现 ranking 支持**

修改 `services/worker/ml/model.py`：
1. `MLModel.__init__` 支持 `objective` 参数来自 `params["objective"]`（现在硬编码 binary，见 64/79 行）
2. `fit()` 增加可选参数 `groups: np.ndarray | None`、`eval_groups: np.ndarray | None`
3. `_fit_lightgbm`：当 objective == "lambdarank" 时：
   - 用 `lgb.Dataset(X, label=y, group=groups, feature_name=...)`
   - eval_set 同样带 group
   - `lgb.train(params, train_data, valid_sets=[...], callbacks=[record_evaluation, early_stopping])`
   - 其余分支（binary）保持原逻辑；非 ranking 模式传入 groups 时抛 `ValueError("groups 仅排序模式使用")`
4. `predict()` 保持现状（lambdarank 模型 predict 返回分数，可直接排序）
5. `MLModel` 新增 `is_ranking` 属性：`params.get("objective") == "lambdarank"`

- [ ] **Step 3: 运行测试**

Run: `cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_model_ranking.py -v`
Expected: PASS（含既有 model 测试不回归：`python3 -m pytest services/worker/tests/ -q -k "model" | tail -2`）

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: MLModel支持lambdarank排序训练"
```

### Task 5: trainer 支持排序训练与排序评估

**Files:**
- Modify: `services/worker/ml/trainer.py`
- Modify: `services/worker/ml/evaluator.py`（如存在评估工具则扩展；否则在 trainer 内实现）
- Test: `services/worker/tests/test_trainer_ranking.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
"""排序训练器测试。"""

import numpy as np

from services.worker.ml.trainer import ModelTrainer


def _make_rows(n: int, start_ts: int = 0) -> list[dict]:
    return [
        {
            "symbol": f"S{i % 4}",
            "generated_at": start_ts + i // 4,
            "f1": float(i % 7),
            "f2": float((i * 3) % 11),
            "future_return_pct": str((i % 5) - 2),
        }
        for i in range(n)
    ]


def test_ranking_trainer_builds_groups_and_metrics() -> None:
    trainer = ModelTrainer(
        model_type="lightgbm",
        model_params={"objective": "lambdarank", "label_gain": [0, 1, 2]},
        label_column="future_return_pct",
    )
    rows = _make_rows(48)  # 12 个时间点 × 4 币
    result = trainer.train(
        training_rows=rows[:36],
        validation_rows=rows[36:],
        feature_columns=("f1", "f2"),
    )
    assert "val_auc" in result.metrics
    assert "val_ndcg_at_5" in result.metrics or "val_top5_hit_rate" in result.metrics
    assert result.metrics["val_auc"] >= 0.0


def test_binary_trainer_does_not_output_ranking_metrics() -> None:
    trainer = ModelTrainer(model_type="lightgbm", model_params={"objective": "binary"}, label_column="future_return_pct")
    result = trainer.train(
        training_rows=_make_rows(24),
        validation_rows=_make_rows(12, start_ts=1000),
        feature_columns=("f1", "f2"),
    )
    assert "val_ndcg_at_5" not in result.metrics
```

- [ ] **Step 2: 实现**

修改 `services/worker/ml/trainer.py`：
1. `train()` 增加 group 构建：调用新增的 `_build_groups(rows)`——按 `generated_at` 时间戳分组（同一时间戳的样本为一组），返回 `np.ndarray`（每组样本数）
2. 模型为 ranking 时：
   - `_prepare_data` 不变（y 用 label 值转排序 relevance：`int(round(label_value))` 或分级 `clip(round(future_return*2), 0, 3)`，具体用 `int(np.clip(np.round(label_value), 0, 3))`——把 future_return 转 0-3 四级 relevance）
   - `model.fit(X_train, y_train, groups=train_groups, eval_set=(X_val, y_val), eval_groups=val_groups)`
3. `_calculate_metrics` 增加排序指标（仅 ranking 模式）：
   - `ndcg_at_5`：按 group 分别算 ndcg@5 后平均（实现见下）
   - `top5_hit_rate`：验证集按 group 取预测分 top 5，看真实 relevance 最高的是否在其中（平均）
   - AUC 照常计算（把 relevance>0 视为正类）
4. `_build_groups` 实现：
```python
def _build_groups(self, rows: list[dict[str, Any]]) -> np.ndarray:
    """按 generated_at 构建 lightgbm group（同时间戳的样本一组）。"""
    if not rows:
        return np.array([], dtype=np.int32)
    timestamps = [int(r.get("generated_at", 0)) for r in rows]
    groups: list[int] = []
    prev = timestamps[0]
    count = 0
    for ts in timestamps:
        if ts == prev:
            count += 1
        else:
            groups.append(count)
            prev = ts
            count = 1
    groups.append(count)
    return np.array(groups, dtype=np.int32)
```
5. ndcg@k 实现（放在 trainer.py 内）：
```python
def _ndcg_at_k(self, y_true: np.ndarray, y_score: np.ndarray, k: int = 5) -> float:
    """按单组计算 ndcg@k。"""
    order = np.argsort(-y_score)
    rel = y_true[order][:k].astype(float)
    dcg = sum((2 ** r - 1) / np.log2(i + 2) for i, r in enumerate(rel))
    ideal = np.sort(y_true)[::-1][:k].astype(float)
    idcg = sum((2 ** r - 1) / np.log2(i + 2) for i, r in enumerate(ideal))
    return float(dcg / idcg) if idcg > 0 else 0.0
```

- [ ] **Step 3: 运行测试**

Run: `cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_trainer_ranking.py -v`
Expected: PASS；回归：`python3 -m pytest services/worker/tests/test_qlib_runner.py -q | tail -2` 失败数与基线一致

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: trainer支持排序训练(group构建+ndcg/top5评估)"
```

### Task 6: qlib_runner 集成排序模式（配置开关）

**Files:**
- Modify: `services/worker/qlib_config.py`（新增 `model_mode: str` 配置，默认 binary，env `QUANT_QLIB_MODEL_MODE`）
- Modify: `services/worker/qlib_runner.py`（`_fit_model` 使用 model_mode；模型元数据记录 model_mode）
- Test: `services/worker/tests/test_qlib_runner.py` 追加 1 个排序模式测试

- [ ] **Step 1: 配置项**

`services/worker/qlib_config.py`：
```python
# QlibRuntimeConfig 增加字段
model_mode: str  # "binary" | "ranking"

# load_qlib_config 中解析
model_mode = str(values.get("QUANT_QLIB_MODEL_MODE", "binary") or "binary").strip().lower()
if model_mode not in ("binary", "ranking"):
    model_mode = "binary"
```

- [ ] **Step 2: qlib_runner._fit_model 适配**

查找 `_fit_model`（约 480 行），当前用 ModelTrainer 训练。改动：
```python
# 训练参数里根据 model_mode 选择 objective
model_params = dict(self._config.model_params or {})
if self._config.model_mode == "ranking":
    model_params["objective"] = "lambdarank"
    model_params["label_gain"] = [0, 1, 2, 3]
else:
    model_params.setdefault("objective", "binary")
```
并在返回的 metrics/training_context 里记录 `"model_mode": self._config.model_mode`。若 `_fit_model` 不直接用 ModelTrainer（可能走 heuristic），需先确认实际训练入口（读代码后按实际结构改，保持接口不变）。

- [ ] **Step 3: 测试**

在 `services/worker/tests/test_qlib_runner.py` 追加：
```python
def test_training_records_model_mode(self) -> None:
    """训练结果记录 model_mode（binary 默认）。"""
    # 复用现有测试的 runner 构建方式（tempfile runtime root），训练小数据集，
    # 断言 training payload 的 metrics/training_context 含 model_mode == "binary"
```
（具体实现参照同文件已有 test_training_* 的构建模式）

Run: `cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_qlib_runner.py -q -k "model_mode" -v`
Expected: PASS；全量 runner 测试失败数与基线一致（5 个既有失败）

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: qlib_runner集成model_mode配置(binary/ranking)"
```

### Task 7: 排序模式对比实验 + 部署 + 效果验证

- [ ] **Step 1: 对比实验**

在服务器上跑两组训练对比（用 Task 1 脚本同源数据）：
- binary 模式（当前）
- ranking 模式（QUANT_QLIB_MODEL_MODE=ranking）
记录 val_auc + val_ndcg@5 + top5_hit_rate，比较排序质量（重点看 top-5 命中率：预测的前 5 个币里实际涨的比例）

- [ ] **Step 2: 决定默认模式并部署**

如果 ranking 的排序指标明显更好（top5_hit_rate 提升 >5%），把 qlib_config 默认 model_mode 改为 ranking；否则保持 binary 并在 api.env 配置 QUANT_QLIB_MODEL_MODE 做线上对照。部署：
```bash
ssh ... "cd ~/Quant && git pull && cd infra/deploy && docker compose build api && docker compose up -d --no-deps api"
```

- [ ] **Step 3: 触发一轮自动化周期验证线上效果**

重置自动化状态（如暂停中）→ 触发周期 → 观察新训练结果（训练样本数、AUC、排序指标）与线上页面指标（选币回测页）。

---

## Review 与验收

- [ ] **Review 1（Task 3 后）**：标签实验结论 + 配置变更 review
- [ ] **Review 2（Task 7 前）**：排序学习代码 review（模型/trainer/runner 三层改动）
- [ ] **验收**：线上选币回测页指标更新；验证 AUC 较 0.532 提升（目标 ≥0.55 或 top5 命中率显著改善）；无新测试失败

## 注意事项

- 特征行无价格字段：标签实验若无法从 cache 恢复 K 线，用"阈值重分类"退化方案并在结果注明
- 服务器 1.6G 内存：实验/训练避免并发；训练数据 42k 行 lightgbm 无压力
- 每次 git 提交保持小步；每个 Task 结束跑相关测试
- 全程中文注释
