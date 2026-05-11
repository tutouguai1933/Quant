# ML 自动优化集成方案

> **目标**：将已有的 Optuna 超参数优化、自动重训练、模型注册表集成到自动化工作流中，实现模型自提升和长期自动化运营。

---

## 一、现状分析

### 1.1 已实现但未集成的功能

| 功能 | 文件 | API | 问题 |
|------|------|-----|------|
| 超参数优化 | `optuna_optimizer.py` | `/ml/hyperopt/start` | 需手动触发，使用模拟数据 |
| 自动重训练 | `auto_retrain.py` | 无 | 未被工作流调用 |
| 模型注册表 | `model_registry.py` | `/ml/models` | 训练后未自动注册，返回空列表 |
| ML训练器 | `ml/trainer.py` | 无 | 已在用，但结果未持久化到注册表 |

### 1.2 当前训练流程

```
automation_workflow_service.run_cycle()
    └─> scheduler.run_named_task("research_train")
        └─> qlib_runner.train()
            └─> _fit_ml_model()
                └─> trainer.train()
                    └─> model.save(path)  # 只保存文件，未注册
```

### 1.3 缺失的环节

1. **训练后未注册**：模型保存了，但没注册到 registry
2. **超参数未优化**：使用默认参数，没有自动调优
3. **重训练未触发**：代码存在但从未被调用
4. **模型未对比**：没有比较新旧模型决定是否提升

---

## 二、目标架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         自动化优化工作流                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        自动化周期 (每15分钟)                          │   │
│   │                                                                     │   │
│   │   run_cycle()                                                       │   │
│   │       │                                                             │   │
│   │       ├─> check_retrain_needed()  ◀── 新增：检查是否需要重训练      │   │
│   │       │       │                                                     │   │
│   │       │       ├─> 性能下降？                                        │   │
│   │       │       ├─> 样本增加？                                        │   │
│   │       │       └─> 定时触发？                                        │   │
│   │       │                                                             │   │
│   │       ├─> research_train                                            │   │
│   │       │       │                                                     │   │
│   │       │       └─> _fit_ml_model()                                   │   │
│   │       │              │                                              │   │
│   │       │              ├─> 获取最优参数 ◀── 新增：从hyperopt读取      │   │
│   │       │              ├─> trainer.train()                            │   │
│   │       │              ├─> registry.register() ◀── 新增：注册模型     │   │
│   │       │              └─> compare_and_promote() ◀── 新增：对比提升   │   │
│   │       │                                                             │   │
│   │       ├─> research_infer                                            │   │
│   │       ├─> signal_output                                             │   │
│   │       ├─> dispatch                                                  │   │
│   │       └─> review                                                    │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                     后台超参数优化 (每天一次)                         │   │
│   │                                                                     │   │
│   │   check_hyperopt_schedule()                                        │   │
│   │       │                                                             │   │
│   │       └─> start_optimization()                                     │   │
│   │              │                                                      │   │
│   │              ├─> 从数据快照加载真实数据                             │   │
│   │              ├─> 运行 Optuna 优化 (50 trials)                       │   │
│   │              └─> 保存最佳参数到配置                                 │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        模型版本管理                                   │   │
│   │                                                                     │   │
│   │   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │   │
│   │   │ Staging  │───>│Production│───>│ Archived │    │ 删除     │    │   │
│   │   │ (新模型) │    │ (当前使用)│    │ (历史)   │    │ (清理)   │    │   │
│   │   └──────────┘    └──────────┘    └──────────┘    └──────────┘    │   │
│   │                                                                     │   │
│   │   提升条件：                                                         │   │
│   │   - val_auc 比当前生产模型高 1% 以上                                │   │
│   │   - 或者当前无生产模型                                               │   │
│   │                                                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 三、详细实施计划

### Phase 1: 训练后自动注册模型

#### 3.1.1 修改 `qlib_runner.py`

**文件**: `services/worker/qlib_runner.py`

**修改点**: `_fit_ml_model()` 方法末尾添加注册逻辑

```python
def _fit_ml_model(self, training_rows, validation_rows) -> dict:
    """拟合 ML 模型并注册到版本管理"""
    # ... 现有训练逻辑 ...
    
    # === 新增：注册模型到版本管理 ===
    try:
        from services.worker.model_registry import get_model_registry
        
        registry = get_model_registry()
        version_id = registry.register(
            model_path=model_path,
            model_type=model_type,
            metrics={
                "train_auc": result.metrics.get("train_auc", 0.0),
                "val_auc": result.metrics.get("val_auc", 0.0),
                "train_f1": result.metrics.get("train_f1", 0.0),
                "val_f1": result.metrics.get("val_f1", 0.0),
            },
            training_context=result.training_context,
            tags=["auto_train", self._config.research_template],
            description=f"自动化周期训练 - {model_version}",
        )
        
        # 返回版本ID
        return {
            ...现有返回字段...,
            "registry_version_id": version_id,
        }
    except Exception as e:
        # 注册失败不影响训练结果
        logger.warning(f"模型注册失败: {e}")
    
    return {...现有返回...}
```

#### 3.1.2 新增配置项

**文件**: `services/worker/qlib_config.py`

```python
# 模型注册配置
enable_model_registry: bool = True  # 是否启用模型注册
auto_promote_threshold: float = 0.01  # 自动提升阈值 (AUC提升1%)
```

---

### Phase 2: 集成自动重训练检查

#### 3.2.1 修改 `automation_workflow_service.py`

**文件**: `services/api/app/services/automation_workflow_service.py`

**新增方法**:

```python
def _check_and_prepare_retrain(self, *, source: str) -> dict[str, object]:
    """检查是否需要重训练，并准备训练参数"""
    from services.worker.auto_retrain import get_auto_retrainer
    from services.worker.model_registry import get_model_registry
    
    auto_retrainer = get_auto_retrainer()
    registry = get_model_registry()
    
    # 获取当前生产模型指标
    production_model = registry.get_production_model()
    current_metrics = {}
    if production_model:
        current_metrics = {
            "val_auc": production_model.metrics.get("val_auc", 0.0),
            "val_f1": production_model.metrics.get("val_f1", 0.0),
        }
    
    # 获取当前样本数量
    current_sample_count = self._get_current_sample_count()
    
    # 检查重训练需求
    decision = auto_retrainer.check_retrain_needed(
        current_metrics=current_metrics,
        current_sample_count=current_sample_count,
    )
    
    return {
        "should_retrain": decision.should_retrain,
        "trigger": decision.trigger,
        "reason": decision.reason,
        "use_best_params": decision.trigger in ("performance_drop", "schedule"),
    }
```

**修改 `run_cycle()` 方法**:

```python
def run_cycle(self, *, source: str = "automation", review_limit: int = 10) -> dict:
    """执行自动化工作流"""
    
    # === 新增：重训练检查 ===
    retrain_check = self._check_and_prepare_retrain(source=source)
    if retrain_check["should_retrain"]:
        self._automation.record_alert(
            level="info",
            code="auto_retrain_triggered",
            message=f"触发自动重训练: {retrain_check['reason']}",
            source=source,
        )
    
    # ... 现有流程 ...
```

---

### Phase 3: 集成超参数优化

#### 3.3.1 修改 `ml_hyperopt.py` - 使用真实数据

**文件**: `services/api/app/routes/ml_hyperopt.py`

**修改 `start_ml_hyperopt()` 方法**:

```python
@router.post("/start")
def start_ml_hyperopt(...) -> dict:
    """启动超参数优化 - 使用真实数据"""
    
    # === 修改：从数据快照加载真实数据 ===
    from services.worker.qlib_dataset import deserialize_dataset_bundle
    
    config = load_qlib_config()
    
    # 加载最新的数据快照
    snapshot_path = config.paths.artifacts_dir / "latest_dataset_snapshot.pkl"
    if snapshot_path.exists():
        bundle = deserialize_dataset_bundle(snapshot_path)
        training_rows = bundle.training_rows
        validation_rows = bundle.validation_rows
        feature_columns = bundle.feature_columns
    else:
        return _error("no_data_snapshot", "没有可用的数据快照，请先执行研究训练")
    
    # 启动优化
    start_optimization(
        optimizer_id=optimizer_id,
        training_rows=training_rows,
        validation_rows=validation_rows,
        feature_columns=feature_columns,
        model_type=model_type,
        n_trials=n_trials,
        timeout_seconds=timeout_seconds,
    )
    
    return _success({...})
```

#### 3.3.2 新增超参数存储

**新文件**: `services/worker/best_params_store.py`

```python
"""最优超参数存储"""

from pathlib import Path
import json
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class BestParams:
    params: dict
    auc: float
    generated_at: datetime
    n_trials: int

class BestParamsStore:
    def __init__(self, store_path: Path):
        self._store_path = store_path
        self._best_params: dict | None = None
        
    def save(self, params: dict, auc: float, n_trials: int) -> None:
        """保存最优参数"""
        self._best_params = {
            "params": params,
            "auc": auc,
            "n_trials": n_trials,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._store_path.write_text(json.dumps(self._best_params, indent=2))
    
    def load(self) -> BestParams | None:
        """加载最优参数"""
        if not self._store_path.exists():
            return None
        try:
            data = json.loads(self._store_path.read_text())
            return BestParams(
                params=data["params"],
                auc=data["auc"],
                n_trials=data["n_trials"],
                generated_at=datetime.fromisoformat(data["generated_at"]),
            )
        except:
            return None
```

#### 3.3.3 修改训练逻辑使用最优参数

**文件**: `services/worker/qlib_runner.py`

```python
def _fit_ml_model(self, training_rows, validation_rows) -> dict:
    """使用最优参数训练模型"""
    
    # === 新增：尝试加载最优参数 ===
    from services.worker.best_params_store import BestParamsStore
    
    store = BestParamsStore(self._config.paths.best_params_path)
    best_params = store.load()
    
    if best_params and best_params.auc > 0.6:
        # 使用优化过的参数
        model_params = best_params.params
        logger.info(f"使用优化参数，AUC={best_params.auc:.4f}")
    else:
        # 使用默认参数
        model_params = dict(self._config.model_params)
    
    # ... 训练逻辑 ...
```

---

### Phase 4: 模型自动对比与提升

#### 3.4.1 新增自动提升服务

**新文件**: `services/api/app/services/model_promotion_service.py`

```python
"""模型自动提升服务"""

from services.worker.model_registry import get_model_registry

class ModelPromotionService:
    """模型提升决策服务"""
    
    def __init__(self, promote_threshold: float = 0.01):
        self._promote_threshold = promote_threshold
    
    def evaluate_promotion(self, new_version_id: str) -> dict:
        """评估是否应该提升新模型"""
        registry = get_model_registry()
        
        new_model = registry.get_model(new_version_id)
        if not new_model:
            return {"should_promote": False, "reason": "新模型不存在"}
        
        production_model = registry.get_production_model()
        
        # 没有生产模型，直接提升
        if not production_model:
            return {
                "should_promote": True,
                "reason": "无生产模型，直接提升",
            }
        
        # 对比 AUC
        new_auc = new_model.metrics.get("val_auc", 0.0)
        prod_auc = production_model.metrics.get("val_auc", 0.0)
        
        improvement = new_auc - prod_auc
        
        if improvement > self._promote_threshold:
            return {
                "should_promote": True,
                "reason": f"AUC 提升 {improvement:.4f}，超过阈值",
                "improvement": improvement,
            }
        elif improvement > 0:
            return {
                "should_promote": False,
                "reason": f"AUC 提升 {improvement:.4f}，未达阈值",
                "improvement": improvement,
            }
        else:
            return {
                "should_promote": False,
                "reason": f"AUC 下降 {-improvement:.4f}，不提升",
                "improvement": improvement,
            }
    
    def auto_promote(self, new_version_id: str) -> dict:
        """自动提升模型（如果满足条件）"""
        evaluation = self.evaluate_promotion(new_version_id)
        
        if evaluation["should_promote"]:
            registry = get_model_registry()
            success = registry.promote(new_version_id, "production")
            evaluation["promoted"] = success
        
        return evaluation
```

#### 3.4.2 集成到训练流程

**文件**: `services/worker/qlib_runner.py`

```python
def _fit_ml_model(self, ...) -> dict:
    # ... 训练和注册 ...
    
    # === 新增：自动评估提升 ===
    if version_id:
        from services.api.app.services.model_promotion_service import ModelPromotionService
        
        promotion_service = ModelPromotionService(
            promote_threshold=self._config.auto_promote_threshold
        )
        promotion_result = promotion_service.auto_promote(version_id)
        
        return {
            ...现有字段...,
            "promotion": promotion_result,
        }
```

---

### Phase 5: 定期后台超参数优化

#### 3.5.1 新增调度服务

**新文件**: `services/api/app/services/hyperopt_schedule_service.py`

```python
"""超参数优化调度服务"""

from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

@dataclass
class HyperoptSchedule:
    enabled: bool = True
    interval_hours: int = 24  # 每24小时运行一次
    n_trials: int = 50
    last_run_at: datetime | None = None
    last_result: dict | None = None

class HyperoptScheduleService:
    """定期触发超参数优化"""
    
    def __init__(self):
        self._schedule = HyperoptSchedule()
        self._running = False
    
    def should_run(self) -> bool:
        """检查是否应该运行优化"""
        if not self._schedule.enabled:
            return False
        if self._running:
            return False
        
        if self._schedule.last_run_at is None:
            return True
        
        elapsed = datetime.now(timezone.utc) - self._schedule.last_run_at
        return elapsed.total_seconds() >= self._schedule.interval_hours * 3600
    
    def mark_started(self) -> None:
        """标记开始"""
        self._running = True
    
    def mark_completed(self, result: dict) -> None:
        """标记完成"""
        self._running = False
        self._schedule.last_run_at = datetime.now(timezone.utc)
        self._schedule.last_result = result
    
    def get_status(self) -> dict:
        """获取状态"""
        return {
            "enabled": self._schedule.enabled,
            "running": self._running,
            "interval_hours": self._schedule.interval_hours,
            "last_run_at": self._schedule.last_run_at.isoformat() if self._schedule.last_run_at else None,
            "last_result": self._schedule.last_result,
        }
```

#### 3.5.2 集成到 OpenClaw 巡检

**文件**: `services/openclaw/openclaw_scheduler.py`

```python
def run_scheduler():
    """运行定时调度器"""
    
    # 新增：超参数优化检查
    HYPEROPT_CHECK_INTERVAL = int(os.getenv("HYPEROPT_CHECK_INTERVAL", "3600"))  # 每小时检查
    
    last_hyperopt_check = 0
    
    while True:
        now = time.time()
        
        # ... 现有巡检逻辑 ...
        
        # === 新增：超参数优化检查 ===
        if now - last_hyperopt_check >= HYPEROPT_CHECK_INTERVAL:
            check_and_run_hyperopt()
            last_hyperopt_check = now
```

---

## 四、配置变更

### 4.1 环境变量

**文件**: `infra/deploy/api.env`

```bash
# 模型注册
QUANT_ENABLE_MODEL_REGISTRY=true
QUANT_AUTO_PROMOTE_THRESHOLD=0.01

# 自动重训练
QUANT_RETRAIN_INTERVAL_DAYS=7
QUANT_PERFORMANCE_DROP_THRESHOLD=0.05
QUANT_SAMPLE_INCREASE_THRESHOLD=1000
QUANT_MIN_RETRAIN_INTERVAL_HOURS=6

# 超参数优化
QUANT_HYPEROPT_ENABLED=true
QUANT_HYPEROPT_INTERVAL_HOURS=24
QUANT_HYPEROPT_N_TRIALS=50
```

### 4.2 默认配置

**文件**: `services/worker/qlib_config.py`

```python
# 模型管理默认值
DEFAULT_ENABLE_MODEL_REGISTRY = True
DEFAULT_AUTO_PROMOTE_THRESHOLD = 0.01

# 重训练默认值
DEFAULT_RETRAIN_INTERVAL_DAYS = 7
DEFAULT_PERFORMANCE_DROP_THRESHOLD = 0.05
DEFAULT_SAMPLE_INCREASE_THRESHOLD = 1000
DEFAULT_MIN_RETRAIN_INTERVAL_HOURS = 6

# 超参数优化默认值
DEFAULT_HYPEROPT_ENABLED = True
DEFAULT_HYPEROPT_INTERVAL_HOURS = 24
DEFAULT_HYPEROPT_N_TRIALS = 50
```

---

## 五、API 变更

### 5.1 新增端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ml/models` | GET | 列出模型版本（已有） |
| `/api/v1/ml/models/{id}` | GET | 获取模型详情（已有） |
| `/api/v1/ml/models/{id}/promote` | POST | 提升模型（已有） |
| `/api/v1/ml/hyperopt/status` | GET | 获取优化状态（已有） |
| `/api/v1/ml/hyperopt/start` | POST | 启动优化（已有，修改数据源） |
| `/api/v1/ml/hyperopt/schedule` | GET | 获取优化调度状态（新增） |
| `/api/v1/ml/retrain/status` | GET | 获取重训练状态（新增） |
| `/api/v1/ml/retrain/trigger` | POST | 手动触发重训练（新增） |

### 5.2 修改现有端点

**`POST /api/v1/ml/hyperopt/start`**:
- 从数据快照加载真实数据
- 完成后自动保存最优参数

**训练响应增加字段**:
```json
{
  "model_version": "lightgbm-20260512...",
  "registry_version_id": "v_20260512...",
  "promotion": {
    "should_promote": true,
    "reason": "AUC 提升 0.0234，超过阈值",
    "promoted": true
  }
}
```

---

## 六、前端支持

### 6.1 新增页面

| 页面 | 路由 | 说明 |
|------|------|------|
| 模型管理 | `/models` | 已有，展示模型列表和对比 |
| 训练曲线 | `/training` | 展示训练过程 |

### 6.2 首页增强

在 `DualStrategyCard` 中增加模型信息：
- 当前模型版本
- 模型 AUC
- 上次优化时间

---

## 七、测试计划

### 7.1 单元测试

| 测试文件 | 测试内容 |
|----------|----------|
| `test_model_registry.py` | 注册、提升、对比 |
| `test_auto_retrain.py` | 重训练触发条件 |
| `test_optuna_optimizer.py` | 优化流程 |
| `test_model_promotion.py` | 提升决策 |

### 7.2 集成测试

1. **完整训练流程**: 训练 → 注册 → 评估 → 提升
2. **超参数优化**: 启动 → 运行 → 保存参数 → 下次训练使用
3. **自动重训练**: 性能下降 → 触发重训练 → 恢复

---

## 八、实施顺序

| 阶段 | 内容 | 预计时间 | 优先级 |
|------|------|----------|--------|
| Phase 1 | 训练后自动注册模型 | 0.5 天 | P0 |
| Phase 4 | 模型自动对比与提升 | 0.5 天 | P0 |
| Phase 2 | 集成自动重训练检查 | 1 天 | P1 |
| Phase 3 | 集成超参数优化 | 1 天 | P1 |
| Phase 5 | 定期后台优化 | 0.5 天 | P2 |
| 测试 | 单元测试和集成测试 | 1 天 | P0 |
| **总计** | | **4.5 天** | |

---

## 九、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 超参数优化时间过长 | 阻塞自动化周期 | 后台异步运行，不阻塞主流程 |
| 模型提升后效果变差 | 实盘损失 | 设置严格阈值，增加回测验证 |
| 注册表损坏 | 模型丢失 | 定期备份，文件持久化 |
| 内存溢出 | 服务崩溃 | 限制样本数量，使用增量训练 |

---

## 十、验收标准

1. **训练后自动注册**: 每次训练后 `GET /api/v1/ml/models` 返回新模型
2. **模型自动提升**: AUC 提升 1% 以上自动提升到 production
3. **超参数优化**: 优化后新模型使用最优参数训练
4. **自动重训练**: 7 天未训练或性能下降时自动触发
5. **长期运营**: 系统连续运行 30 天，模型持续更新
