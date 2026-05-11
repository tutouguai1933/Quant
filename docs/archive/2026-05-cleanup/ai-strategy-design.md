# AI策略架构设计文档

## 1. 概述

本文档定义了Quant系统的AI策略架构，包括强化学习框架、训练流程、自适应参数调整和策略评估体系。

### 1.1 目标

- 构建可扩展的强化学习策略框架
- 实现市场状态自适应的参数调整机制
- 提供完善的训练数据收集与标注体系
- 建立多维度策略评估指标

### 1.2 设计原则

- **模块化**: 各组件独立可测试，支持插件化扩展
- **渐进式**: 从规则策略过渡到学习策略，平滑迁移
- **可解释**: 提供决策依据和因子贡献分析
- **鲁棒性**: 异常市场状态下的降级机制

---

## 2. 强化学习框架

### 2.1 核心组件架构

```
┌─────────────────────────────────────────────────────────────┐
│                    RL Strategy Framework                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │ Environment │───▶│   Agent     │───▶│   Policy Store  │  │
│  │ (Market)    │    │ (Strategy)  │    │   (Weights)     │  │
│  └─────────────┘    └─────────────┘    └─────────────────┘  │
│        │                  │                    │            │
│        ▼                  ▼                    ▼            │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │ State       │    │ Action      │    │ Reward          │  │
│  │ Extractor   │    │ Executor    │    │ Calculator      │  │
│  └─────────────┘    └─────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 状态空间定义 (State Space)

状态空间包含市场特征、技术指标和持仓信息：

```python
State = {
    # 市场状态
    "market": {
        "volatility_regime": float,      # 波动率状态 (0-1)
        "trend_strength": float,         # 趋势强度 (0-1)
        "volume_profile": float,         # 成交量特征
        "price_position": float,         # 价格相对位置
    },

    # 技术指标
    "indicators": {
        "rsi": float,                    # RSI值
        "macd_signal": float,            # MACD信号
        "bb_position": float,            # 布林带位置
        "ma_distance": float,            # 与均线距离
    },

    # 持仓状态
    "position": {
        "has_position": bool,            # 是否持仓
        "position_duration": int,        # 持仓时长(bars)
        "unrealized_pnl_pct": float,     # 未实现盈亏比例
        "entry_distance_pct": float,     # 与入场价距离
    },

    # 时间特征
    "time": {
        "hour_of_day": int,              # 小时
        "day_of_week": int,              # 星期
        "is_trading_hours": bool,        # 是否交易时段
    }
}
```

### 2.3 动作空间定义 (Action Space)

动作空间设计为离散+连续混合：

```python
Action = {
    "type": Enum[                        # 动作类型
        "hold",                          # 持有/观望
        "open_long",                     # 开多
        "open_short",                    # 开空
        "close_position",                # 平仓
        "adjust_params",                 # 调整参数
    ],

    "params": {                          # 动作参数(可选)
        "size_pct": float,               # 仓位比例 (0-1)
        "stop_loss_pct": float,          # 止损比例
        "take_profit_pct": float,        # 止盈比例
    }
}
```

### 2.4 奖励函数设计 (Reward Function)

奖励函数综合考虑收益、风险和执行质量：

```python
Reward = {
    # 收益贡献
    "pnl_component": {
        "realized_pnl": float,           # 已实现盈亏
        "unrealized_change": float,      # 未实现变化
        "weight": 0.40,
    },

    # 风险贡献
    "risk_component": {
        "max_drawdown_penalty": float,   # 最大回撤惩罚
        "volatility_adjustment": float,  # 波动率调整
        "weight": 0.30,
    },

    # 执行质量
    "execution_component": {
        "slippage_penalty": float,       # 滑点惩罚
        "timing_score": float,           # 时机评分
        "weight": 0.20,
    },

    # 策略一致性
    "consistency_component": {
        "signal_alignment": float,       # 与信号一致性
        "weight": 0.10,
    },
}

Total_Reward = sum(component.value * component.weight for component in Reward)
```

---

## 3. 训练流程

### 3.1 数据收集管道

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Market Data │───▶│  Feature     │───▶│  Label       │
│  (K-lines)   │    │  Extractor   │    │  Generator   │
└──────────────┘    └──────────────┘    └──────────────┘
                           │                    │
                           ▼                    ▼
                    ┌──────────────┐    ┌──────────────┐
                    │  Indicator   │    │  Trade       │
                    │  Service     │    │  Results     │
                    └──────────────┘    └──────────────┘
                           │                    │
                           └────────────┬───────┘
                                        ▼
                               ┌──────────────┐
                               │ Training     │
                               │ Dataset      │
                               └──────────────┘
```

### 3.2 训练数据结构

```python
TrainingSample = {
    "timestamp": datetime,
    "symbol": str,

    # 输入特征
    "state": State,                      # 状态向量

    # 标签(根据策略)
    "label": {
        "optimal_action": Action,        # 最优动作
        "action_confidence": float,      # 动作置信度
        "alternative_actions": list,     # 替代动作
    },

    # 事后评估
    "outcome": {
        "actual_pnl": float,             # 实际盈亏
        "holding_period": int,           # 持仓周期
        "max_drawdown": float,           # 最大回撤
        "market_context": str,           # 市场环境标签
    },

    # 元数据
    "metadata": {
        "source_strategy": str,          # 来源策略
        "data_quality": float,           # 数据质量评分
        "noise_level": float,            # 噪声水平估计
    }
}
```

### 3.3 离线训练流程

```python
def offline_training_pipeline():
    # 1. 数据准备
    historical_data = load_historical_candles()
    indicators = calculate_indicators(historical_data)
    trades = load_historical_trades()

    # 2. 特征工程
    states = extract_states(historical_data, indicators)
    labels = generate_labels(trades, historical_data)

    # 3. 数据清洗
    clean_samples = filter_low_quality_samples(states, labels)
    balanced_samples = balance_action_distribution(clean_samples)

    # 4. 模型训练
    model = initialize_model(config.model_type)
    model.train(balanced_samples, validation_split=0.2)

    # 5. 评估与选择
    metrics = evaluate_model(model, test_set)
    best_model = select_best_checkpoint(model, metrics)

    # 6. 部署准备
    save_model_weights(best_model)
    register_model_version(best_model)
```

### 3.4 在线学习流程

```python
def online_learning_loop():
    while True:
        # 1. 观察状态
        state = get_current_market_state()

        # 2. 选择动作(探索/利用)
        action = policy.select_action(state, epsilon=exploration_rate)

        # 3. 执行动作
        execute_trade(action)

        # 4. 观察结果
        reward = calculate_reward(action_result)

        # 5. 更新策略
        policy.update(state, action, reward)

        # 6. 定期评估
        if should_evaluate():
            performance = evaluate_current_policy()
            if performance < threshold:
                trigger_model_update()
```

---

## 4. 自适应参数调整

### 4.1 市场状态识别

```python
MarketRegime = Enum[
    "trending_up",       # 上升趋势
    "trending_down",     # 下降趋势
    "ranging",           # 震荡区间
    "volatile",          # 高波动
    "quiet",             # 低波动
    "transition",        # 状态转换
]

def detect_market_regime(data: MarketData) -> MarketRegime:
    volatility = calculate_volatility(data, window=20)
    trend_strength = calculate_trend_strength(data, window=50)
    range_bound = calculate_range_bound(data, window=20)

    if volatility > HIGH_VOL_THRESHOLD:
        return MarketRegime.volatile
    elif trend_strength > TREND_THRESHOLD and price_trend > 0:
        return MarketRegime.trending_up
    elif trend_strength > TREND_THRESHOLD and price_trend < 0:
        return MarketRegime.trending_down
    elif range_bound < RANGE_THRESHOLD:
        return MarketRegime.ranging
    else:
        return MarketRegime.transition
```

### 4.2 参数调整策略

```python
AdaptiveParams = {
    # 趋势市场参数
    "trending": {
        "stop_loss_pct": 0.03,           # 较宽止损
        "take_profit_pct": 0.08,         # 较大止盈
        "entry_threshold": 0.65,         # 较高入场阈值
        "position_size_pct": 0.8,        # 较大仓位
    },

    # 震荡市场参数
    "ranging": {
        "stop_loss_pct": 0.02,           # 较窄止损
        "take_profit_pct": 0.03,         # 较小止盈
        "entry_threshold": 0.70,         # 更高入场阈值
        "position_size_pct": 0.5,        # 较小仓位
    },

    # 高波动市场参数
    "volatile": {
        "stop_loss_pct": 0.04,           # 更宽止损
        "take_profit_pct": 0.06,         # 中等止盈
        "entry_threshold": 0.75,         # 最高入场阈值
        "position_size_pct": 0.3,        # 最小仓位
    },

    # 低波动市场参数
    "quiet": {
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.04,
        "entry_threshold": 0.60,
        "position_size_pct": 0.6,
    },
}
```

### 4.3 参数平滑过渡

```python
def smooth_param_transition(
    current_params: dict,
    target_params: dict,
    transition_speed: float = 0.1
) -> dict:
    """平滑过渡参数，避免剧烈变化。"""
    new_params = {}
    for key, current_value in current_params.items():
        target_value = target_params.get(key, current_value)
        # 线性插值过渡
        new_value = current_value + (target_value - current_value) * transition_speed
        new_params[key] = new_value
    return new_params
```

---

## 5. 策略评估体系

### 5.1 评估指标

| 指标 | 公式 | 目标范围 |
|------|------|----------|
| 夏普比率 | (收益率 - 无风险利率) / 收益率标准差 | > 1.5 |
| 最大回撤 | max(peak - trough) / peak | < 15% |
| 胜率 | 盈利交易数 / 总交易数 | > 55% |
| 盈亏比 | 平均盈利 / 平均亏损 | > 1.5 |
| 卡玛比率 | 年化收益 / 最大回撤 | > 3.0 |
| Sortino比率 | 收益率 / 下行波动率 | > 2.0 |
| Omega比率 | 盈利阈值以上收益 / 亏损阈值以下损失 | > 1.2 |

### 5.2 评估周期

```python
EvaluationPeriod = {
    "daily": {
        "min_trades": 3,                  # 最少交易数
        "metrics": ["pnl", "win_rate"],
    },
    "weekly": {
        "min_trades": 10,
        "metrics": ["sharpe", "max_dd", "win_rate", "profit_factor"],
    },
    "monthly": {
        "min_trades": 30,
        "metrics": ["sharpe", "calmar", "omega", "sortino", "max_dd"],
    },
    "quarterly": {
        "min_trades": 100,
        "metrics": "all",
    },
}
```

### 5.3 策略健康度评分

```python
def calculate_health_score(metrics: dict) -> float:
    """计算策略综合健康度评分 (0-100)。"""
    weights = {
        "sharpe": 0.25,                   # 夏普权重
        "max_drawdown": 0.20,             # 最大回撤权重
        "win_rate": 0.15,                 # 胜率权重
        "profit_factor": 0.15,            # 盈亏比权重
        "trade_frequency": 0.10,          # 交易频率权重
        "consistency": 0.15,              # 稳定性权重
    }

    score = 0.0
    for metric, weight in weights.items():
        normalized = normalize_metric(metric, metrics[metric])
        score += normalized * weight

    return score * 100
```

---

## 6. 接口定义

### 6.1 RL策略基类接口

```python
class RLStrategyBase(ABC):
    """强化学习策略基类接口。"""

    @abstractmethod
    def get_state(self, market_data: dict) -> np.ndarray:
        """提取状态向量。"""
        pass

    @abstractmethod
    def select_action(self, state: np.ndarray) -> Action:
        """选择动作。"""
        pass

    @abstractmethod
    def calculate_reward(self, action: Action, outcome: dict) -> float:
        """计算奖励。"""
        pass

    @abstractmethod
    def update_policy(self, experience: Experience) -> None:
        """更新策略。"""
        pass

    def get_adaptive_params(self, market_regime: MarketRegime) -> dict:
        """获取自适应参数。"""
        return self._adaptive_params.get_params(market_regime)
```

### 6.2 训练数据服务接口

```python
class TrainingDataService:
    """训练数据收集服务接口。"""

    def collect_sample(
        self,
        symbol: str,
        timestamp: datetime,
        include_indicators: bool = True
    ) -> TrainingSample:
        """收集单个训练样本。"""
        pass

    def generate_labels(
        self,
        samples: list[TrainingSample],
        lookahead_bars: int = 20
    ) -> list[TrainingSample]:
        """生成训练标签(最优动作)。"""
        pass

    def export_dataset(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        format: str = "parquet"
    ) -> str:
        """导出训练数据集。"""
        pass
```

### 6.3 策略评估服务接口

```python
class StrategyEvaluatorService:
    """策略评估服务接口。"""

    def evaluate_strategy(
        self,
        strategy_id: str,
        period: EvaluationPeriod,
        trades: list[Trade]
    ) -> EvaluationResult:
        """评估策略表现。"""
        pass

    def calculate_metrics(
        self,
        trades: list[Trade],
        equity_curve: list[float]
    ) -> dict[str, float]:
        """计算所有评估指标。"""
        pass

    def compare_strategies(
        self,
        strategy_ids: list[str],
        baseline_id: str | None = None
    ) -> ComparisonResult:
        """对比多个策略表现。"""
        pass
```

---

## 7. 配置结构

### 7.1 AI策略配置 (ai_strategy_config.json)

```json
{
  "training": {
    "batch_size": 64,
    "learning_rate": 0.001,
    "epochs": 100,
    "validation_split": 0.2,
    "early_stopping_patience": 10,
    "exploration_rate": 0.1,
    "exploration_decay": 0.995
  },
  "model": {
    "type": "ppo",
    "hidden_layers": [128, 64],
    "activation": "relu",
    "dropout": 0.1
  },
  "reward": {
    "pnl_weight": 0.40,
    "risk_weight": 0.30,
    "execution_weight": 0.20,
    "consistency_weight": 0.10
  },
  "adaptive_params": {
    "transition_speed": 0.1,
    "min_observation_bars": 20,
    "regime_detection_window": 50
  },
  "evaluation": {
    "min_trades_daily": 3,
    "min_trades_weekly": 10,
    "min_trades_monthly": 30,
    "health_threshold": 60.0
  },
  "fallback": {
    "enabled": true,
    "fallback_strategy": "trend_breakout",
    "max_rl_trades_pct": 0.3
  }
}
```

---

## 8. 风险控制

### 8.1 RL策略降级机制

当RL策略表现不佳时，自动切换回规则策略：

```python
def check_fallback_condition(performance: dict) -> bool:
    """检查是否需要触发降级。"""
    conditions = [
        performance["win_rate"] < 0.45,
        performance["max_drawdown"] > 0.20,
        performance["sharpe"] < 0.5,
        performance["health_score"] < 50,
    ]
    return any(conditions)
```

### 8.2 RL策略仓位限制

```python
RL_POSITION_LIMITS = {
    "max_rl_position_pct": 0.30,         # RL策略最大仓位比例
    "max_rl_daily_trades": 5,            # RL策略每日最大交易数
    "rl_trade_size_cap": 0.5,            # RL单笔交易上限
}
```

---

## 9. 实施路线图

### Phase 1: 基础架构 (P10-5)
- 完成接口定义和框架搭建
- 创建训练数据收集服务
- 实现自适应参数框架
- 建立策略评估服务

### Phase 2: 离线训练 (后续)
- 收集历史训练数据
- 训练初始RL模型
- 回测验证效果

### Phase 3: 在线部署 (后续)
- 部署RL策略到生产环境
- 启用在线学习
- 监控策略表现

### Phase 4: 持续优化 (后续)
- 根据实盘反馈调优
- 扩展状态空间
- 优化奖励函数

---

## 10. 参考文献

- Sutton & Barto: Reinforcement Learning: An Introduction
- Moody & Saffell: Learning to Trade via Direct Reinforcement
- Deng et al.: Deep Direct Reinforcement Learning for Trading
- Liu et al.: FinRL: A Deep Reinforcement Learning Library for Quantitative Finance