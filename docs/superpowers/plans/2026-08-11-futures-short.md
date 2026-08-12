# 合约做空：阶段 0 验证 + 阶段 1 模拟盘 实施计划

## 更新（08-13）：方向做空验证通过，方案改为"方向做空 BTC"

- 截面选币做空（原方案）：❌ 已验证 ≈随机，放弃
- **时序方向做空（新方案）：✅ 已通过 OOS 验证**（TEST 段命中率 77.8%、平均收益 +2.58%/次）
  - 规则：模型 16 币平均分数 < 0.38（极度看跌）时做空 BTCUSDT；回升 > 0.45 平仓
  - 触发频率约 8% 时间点（保守）
- 实施方式改为 **api 侧调度**（openclaw 巡检检查方向 → forceenter short）：
  - api 新增市场方向接口（读 latest_inference 平均分数）
  - 方向做空调度服务（空头仓位状态机：开空/平空）
  - futures 模拟盘独立容器（9014）先行验证 1-2 周
  - 实盘需币安合约账户+key（用户后续准备）


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ①验证模型"做空方向"（选最低分币做空）是否有效（命中率 ≥55% 硬门槛）；②搭建 freqtrade futures 模拟盘并验证做空信号到下单的完整链路，为后续实盘合约做准备。

**Architecture:** 阶段 0 用历史数据滚动验证：训练模型 → 对验证段 K 线打分 → 选分数最低的币模拟做空 → 统计命中率（未来收益<0 比例）与平均收益。阶段 1 新增独立 freqtrade 模拟容器（futures + dry_run，端口 9014，不影响实盘 9013），策略开 can_short，执行层适配 futures API，用脚本验证 short 信号 → forceenter 开空 → 平仓 全链路。

**Tech Stack:** Python + lightgbm（现有训练管线）+ freqtrade（futures 模式）+ 服务器 16 币 4h K 线数据

---

## 阶段 0：做空方向验证（Task 1-2）

### Task 1: 做空验证实验脚本 + 测试

**Files:**
- Create: `services/worker/tests/test_short_validation.py`
- Create: `scripts/run_short_validation.py`

- [ ] **Step 1: 写核心函数测试（TDD）**

`services/worker/tests/test_short_validation.py`：

```python
"""做空方向验证核心函数测试。"""

import json
import tempfile
from pathlib import Path

from scripts.run_short_validation import (
    build_short_pairs,
    compute_short_hit_rate,
)


def test_build_short_pairs_selects_lowest_scores() -> None:
    """选分数最低的 k 个作为做空候选。"""
    rows = [
        {"symbol": "A", "score": 0.6, "future_return_pct": "1.2"},
        {"symbol": "B", "score": 0.3, "future_return_pct": "-0.8"},
        {"symbol": "C", "score": 0.2, "future_return_pct": "-1.5"},
        {"symbol": "D", "score": 0.5, "future_return_pct": "0.4"},
    ]
    pairs = build_short_pairs(rows, top_k=2)
    assert [p["symbol"] for p in pairs] == ["C", "B"]  # 最低分优先


def test_compute_short_hit_rate() -> None:
    """做空命中率 = 未来收益为负的比例。"""
    pairs = [
        {"symbol": "A", "future_return_pct": "-1.0"},  # 命中（跌了）
        {"symbol": "B", "future_return_pct": "0.5"},   # 未命中（涨了）
        {"symbol": "C", "future_return_pct": "-0.2"},  # 命中
        {"symbol": "D", "future_return_pct": "0.0"},   # 平（不计命中）
    ]
    result = compute_short_hit_rate(pairs)
    assert result["hit_rate"] == 0.5
    assert result["avg_return"] < 0  # 做空收益 = -未来收益，平均应为正
```

- [ ] **Step 2: 实现脚本核心逻辑**

`scripts/run_short_validation.py`：

```python
"""做空方向验证：模型选最低分币做空，验证命中率与收益。

用法（服务器容器内）：
    cd /app && PYTHONPATH=/app python3 scripts/run_short_validation.py

流程：
1. 读 16 币 4h K 线 → 特征 + 标签（沿用线上最优标签配置 close_only/2%/2-5d）
2. 时间序切分：前 60% 训练模型、后 40% 滚动验证（每 120 根 K 线为一个验证窗口，
   用窗口前的数据训练/增量预测，窗口内每根 K 线给 16 币打分）
3. 每个时间点选分数最低的 top-3 币做空，记录未来收益
4. 统计：做空命中率（未来收益<0 比例）、平均做空收益（-未来收益）、
   对比随机做空基准（随机选 3 币）
5. 输出结论：命中率 ≥55% 且明显优于随机 → 做空方向有效；否则不建议进入阶段 1
"""

from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from typing import Any

from scripts.run_label_sweep import build_labeled_rows, split_time_ordered, SYMBOLS

OPT_LABEL_CONFIG = {
    "name": "opt_close_only_2pct_2-5d",
    "label_mode": "close_only",
    "target": "2",
    "stop": "-1",
    "min_days": 2,
    "max_days": 5,
}

FEATURE_COLS = [
    "close_return_pct", "range_pct", "body_pct", "volume_ratio",
    "trend_gap_pct", "ema20_gap_pct", "ema55_gap_pct", "atr_pct",
    "breakout_strength", "roc6", "trend_strength", "momentum_accel",
    "volatility_contraction", "volume_price_divergence",
    "bull_bear_ratio", "taker_buy_ratio", "btc_correlation",
]

VALIDATION_WINDOW_BARS = 120  # 每 120 根 4h K 线（20 天）重训一次
SHORT_TOP_K = 3               # 每轮做空 top-k 个最低分币


def build_short_pairs(rows: list[dict[str, Any]], top_k: int = SHORT_TOP_K) -> list[dict[str, Any]]:
    """从同一时间点的候选里选分数最低的 top_k 个做空。

    Args:
        rows: 同一时间点的候选行（含 score 和 future_return_pct）
        top_k: 做空数量

    Returns:
        做空候选列表（按分数升序）
    """
    sorted_rows = sorted(rows, key=lambda r: float(r.get("score", 0)))
    return list(sorted_rows[:top_k])


def compute_short_hit_rate(pairs: list[dict[str, Any]]) -> dict[str, float]:
    """统计做空命中率与平均收益。

    做空收益 = -未来收益（跌了赚钱）。
    未来收益为 0 的样本不计入命中分母。

    Returns:
        {hit_rate, avg_return, sample_count}
    """
    hits = 0
    counted = 0
    returns: list[float] = []
    for p in pairs:
        future = float(p.get("future_return_pct", 0))
        if future == 0:
            continue
        counted += 1
        if future < 0:
            hits += 1
        returns.append(-future)  # 做空收益
    return {
        "hit_rate": round(hits / counted, 4) if counted else 0.0,
        "avg_return": round(sum(returns) / len(returns), 4) if returns else 0.0,
        "sample_count": counted,
    }
```

- [ ] **Step 3: 实现主流程（main）**

`scripts/run_short_validation.py` 追加：

```python
def _train_model(train_rows: list[dict[str, Any]]) -> Any:
    """训练 binary 模型并返回。"""
    from services.worker.ml.trainer import ModelTrainer

    trainer = ModelTrainer(
        model_type="lightgbm",
        model_params={
            "objective": "binary",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "n_estimators": 200,
            "early_stopping_rounds": 20,
            "verbosity": -1,
        },
        label_column="future_return_pct",
    )
    result = trainer.train(
        training_rows=train_rows,
        validation_rows=[],
        feature_columns=tuple(FEATURE_COLS),
    )
    return result.model


def _predict_scores(model: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """给每行打分（上涨概率），写回 score 字段。"""
    if not rows:
        return []
    import numpy as np

    X = np.array(
        [[float(r.get(c, 0)) for c in FEATURE_COLS] for r in rows],
        dtype=np.float64,
    )
    proba = model.predict_proba(X)
    scores = proba[:, 1] if proba.ndim > 1 else proba
    for row, score in zip(rows, scores):
        row["score"] = float(score)
    return rows


def main() -> int:
    kline_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/.runtime/kline_store"
    started = time.time()

    # 1. 构建特征+标签（全部数据）
    rows = build_labeled_rows(
        kline_dir=kline_dir,
        symbols=SYMBOLS,
        interval="4h",
        label_config=OPT_LABEL_CONFIG,
    )
    ordered = sorted(rows, key=lambda r: (int(r.get("generated_at", 0)), str(r.get("symbol", ""))))
    print(f"总样本: {len(ordered)}", flush=True)

    # 2. 时间序切分：前 60% 训练，后 40% 滚动验证
    split_idx = int(len(ordered) * 0.6)
    train_rows = ordered[:split_idx]
    valid_rows = ordered[split_idx:]
    print(f"训练 {len(train_rows)} / 验证 {len(valid_rows)}", flush=True)

    # 3. 滚动验证：每 VALIDATION_WINDOW_BARS 重训一次
    model = _train_model(train_rows)
    all_short_pairs: list[dict[str, Any]] = []
    all_random_pairs: list[dict[str, Any]] = []

    # 按时间点分组验证
    from collections import defaultdict

    ts_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in valid_rows:
        ts_groups[int(row["generated_at"])].append(row)

    timestamps = sorted(ts_groups.keys())
    retrain_count = 0
    for idx, ts in enumerate(timestamps):
        group = ts_groups[ts]
        if len(group) < 4:
            continue
        # 每 VALIDATION_WINDOW_BARS 个时间点重训一次（用该时间点之前的数据）
        if retrain_count == 0 or idx % VALIDATION_WINDOW_BARS == 0:
            history = [r for r in ordered if int(r["generated_at"]) < ts]
            if len(history) > 500:
                model = _train_model(history)
                retrain_count += 1
        scored = _predict_scores(model, [dict(r) for r in group])
        short_pairs = build_short_pairs(scored)
        all_short_pairs.extend(short_pairs)
        # 随机基准：随机选 3 币
        import random

        random.seed(ts)
        random_pairs = random.sample(scored, min(SHORT_TOP_K, len(scored)))
        all_random_pairs.extend(random_pairs)

    # 4. 统计
    short_result = compute_short_hit_rate(all_short_pairs)
    random_result = compute_short_hit_rate(all_random_pairs)
    print("\n=== 做空方向验证结果 ===")
    print(f"模型做空: 命中率={short_result['hit_rate']} 平均收益={short_result['avg_return']}% 样本={short_result['sample_count']}")
    print(f"随机做空: 命中率={random_result['hit_rate']} 平均收益={random_result['avg_return']}% 样本={random_result['sample_count']}")
    passed = short_result["hit_rate"] >= 0.55 and short_result["hit_rate"] > random_result["hit_rate"] + 0.03
    print(f"结论: {'✅ 做空方向有效，可进入阶段 1' if passed else '❌ 做空方向不足，不建议进入阶段 1'}")
    print(f"耗时 {time.time() - started:.1f}s")

    with open("/tmp/short_validation_result.json", "w", encoding="utf-8") as f:
        json.dump({"short": short_result, "random": random_result, "passed": passed}, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试**

Run: `cd /home/djy/Quant && python3 -m pytest services/worker/tests/test_short_validation.py -v`
Expected: PASS（2 个测试）

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 做空方向验证脚本+测试(阶段0)"
```

### Task 2: 服务器执行做空验证 + 分析结论

- [ ] **Step 1: 同步脚本到服务器容器并执行**

```bash
git push 后：
ssh ... "cd ~/Quant && git pull"
ssh ... "docker cp scripts/run_short_validation.py quant-api:/app/scripts/"
ssh ... "docker exec quant-api sh -c 'cd /app && PYTHONPATH=/app setsid nohup python3 scripts/run_short_validation.py > /tmp/short_val.log 2>&1 < /dev/null &'"
# 监控：grep -E '===|命中率|结论' /tmp/short_val.log（预计 10-20 分钟）
```

- [ ] **Step 2: 分析结果**

判定标准（写入 commit 信息）：
- 命中率 ≥ 0.55 且比随机高 0.03+ → 做空方向有效，进入阶段 1
- 否则 → 记录结论，阶段 1 暂停（向用户汇报并等决策）

---

## 阶段 1：freqtrade futures 模拟盘（Task 3-6）

### Task 3: futures 模拟盘配置（独立容器，不影响实盘）

**Files:**
- Create: `infra/freqtrade/user_data/config.futures.sim.json`
- Modify: `infra/freqtrade/docker-compose.yml`（新增 freqtrade-sim 服务）
- Create: `infra/freqtrade/user_data/tradesv3.sim.sqlite`（空文件占位，git 忽略）

- [ ] **Step 1: 写 futures 模拟配置**

`infra/freqtrade/user_data/config.futures.sim.json`：

```json
{
  "bot_name": "quant-futures-sim",
  "dry_run": true,
  "dry_run_wallet": 1000,
  "max_open_trades": 3,
  "stake_currency": "USDT",
  "stake_amount": 20,
  "tradable_balance_ratio": 0.95,
  "timeframe": "1h",
  "cancel_open_orders_on_exit": true,
  "trading_mode": "futures",
  "margin_mode": "isolated",
  "db_url": "sqlite:////freqtrade/user_data/tradesv3.sim.sqlite",
  "unfilledtimeout": {"entry": 10, "exit": 10, "exit_timeout_count": 0, "unit": "minutes"},
  "exchange": {
    "name": "binance",
    "key": "",
    "secret": "",
    "enable_ws": false,
    "ccxt_config": {"enableRateLimit": true},
    "ccxt_async_config": {"enableRateLimit": true, "rateLimit": 200},
    "pair_whitelist": [
      "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "BNB/USDT",
      "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOT/USDT"
    ],
    "pair_blacklist": []
  },
  "order_types": {
    "entry": "limit", "exit": "limit",
    "emergency_exit": "market", "stoploss": "limit",
    "stoploss_on_exchange": false
  },
  "order_time_in_force": {"entry": "IOC", "exit": "IOC"},
  "pairlists": [{"method": "StaticPairList"}],
  "api_server": {
    "enabled": true, "listen_ip_address": "0.0.0.0", "listen_port": 9014,
    "verbosity": "error", "enable_openapi": false, "CORS_origins": []
  },
  "initial_state": "running",
  "force_entry_enable": true,
  "internals": {"process_throttle_secs": 5}
}
```

- [ ] **Step 2: compose 新增 freqtrade-sim 服务**

`infra/freqtrade/docker-compose.yml` 追加：

```yaml
  freqtrade-sim:
    image: ${QUANT_FREQTRADE_IMAGE:-freqtradeorg/freqtrade:stable}
    container_name: quant-freqtrade-sim
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./user_data:/freqtrade/user_data
    environment:
      HTTP_PROXY: ${QUANT_PROXY_HTTP:-}
      HTTPS_PROXY: ${QUANT_PROXY_HTTP:-}
      NO_PROXY: ${NO_PROXY:-127.0.0.1,localhost,freqtrade,mihomo}
    command: >
      trade
      --config /freqtrade/user_data/config.futures.sim.json
      --strategy EnhancedStrategy
```

- [ ] **Step 3: 本地校验配置合法性（freqtrade 命令 validate）**

```bash
ssh ... "cd ~/Quant/infra/freqtrade && docker compose up -d freqtrade-sim"
ssh ... "docker logs quant-freqtrade-sim --tail 20"   # 应显示 futures 模式启动成功
```

Expected: 日志含 `trading_mode: futures`、`Dry run`、API 监听 9014

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: freqtrade futures模拟盘配置(独立容器9014, dry_run)"
```

### Task 4: EnhancedStrategy 做空支持

**Files:**
- Modify: `infra/freqtrade/user_data/strategies/EnhancedStrategy.py`

- [ ] **Step 1: 开启做空**

```python
can_short = True
```

- [ ] **Step 2: 增加做空进出场逻辑**

在 `populate_entry_trend` 增加 `enter_short` 条件（对称于做多）：
- 入场做空：RSI 超买（> 80 - threshold 映射）+ 4h 趋势向下（价格在 SMA200 下方）+ 量能确认
- 出场做空：RSI 超卖或价格突破 SMA50

`populate_exit_trend` 增加 `exit_short`。

**注意**：freqtrade futures 模式要求 enter_short/exit_short 列存在（否则开空失败）。保持原有 long 逻辑不动。

- [ ] **Step 3: 模拟盘跑通做空下单**

```bash
# 手动触发做空验证（用 freqtrade API）
ssh ... "curl -s -X POST 'http://127.0.0.1:9014/api/v1/forceenter' -H 'Content-Type: application/json' -d '{\"pair\": \"BTC/USDT\", \"side\": \"short\"}'"
# 查持仓
ssh ... "curl -s 'http://127.0.0.1:9014/api/v1/status' | python3 -m json.tool | head -30"
```

Expected: forceenter short 成功，status 显示 short 持仓

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: EnhancedStrategy开启做空+模拟盘验证forceenter short"
```

### Task 5: 执行层适配（rest_client futures 支持）

**Files:**
- Modify: `services/api/app/adapters/freqtrade/rest_client.py`

- [ ] **Step 1: 检查现有 side 处理是否支持 short**

阅读 `submit_execution_action`（198-260 行）：确认 side=short 时 forceenter 的 payload 是否正确（freqtrade forceenter 支持 `side: "short"`）。如不支持则补充。

- [ ] **Step 2: 补充杠杆设置**

新增方法 `set_leverage(pair: str, leverage: int)`：

```python
def set_leverage(self, pair: str, leverage: int) -> dict[str, object]:
    """设置合约杠杆（futures 模式，模拟盘固定 1 倍）。"""
    return self._request_json(
        "POST",
        "/api/v1/leverage",
        auth=True,
        payload={"pair": pair, "leverage": leverage},
    )
```

- [ ] **Step 3: 单元测试**

`services/api/tests/test_freqtrade_rest_client.py`（如无则新建）：mock `_request_json` 验证 set_leverage 和 submit_execution_action(side=short) 的参数构造正确。

- [ ] **Step 4: 提交**

```bash
git add -A && git commit -m "feat: rest_client支持合约杠杆设置与short下单"
```

### Task 6: 集成验证（信号 → 模拟盘下单）+ Review

- [ ] **Step 1: 端到端验证脚本**

写一次性验证脚本（scripts/verify_short_flow.py，或直接 ssh 命令）：
1. 用最近推理的模型对 16 币打分，选最低分币
2. 调模拟盘 API（9014）：set_leverage(pair, 1) → forceenter short → 查询持仓确认
3. forceexit 平仓 → 确认平仓成功

- [ ] **Step 2: 全量测试回归**

```bash
cd /home/djy/Quant && python3 -m pytest services/api/tests/ services/worker/tests/ -q 2>&1 | tail -3
```
失败数与基线一致（当前基线 70 个既有失败，无新增）。

- [ ] **Step 3: Review 2（阶段 1 代码审查）**

检查点：
- 策略做空逻辑与做多对称、无方向性 bug
- rest_client 的 short payload 符合 freqtrade futures API
- 模拟盘与实盘完全隔离（不同容器/端口/数据库）
- 模拟盘配置无真实 API key（dry_run 不需要 key，但需确认不误用私钥配置）

- [ ] **Step 4: 总结报告**

向用户输出：
- 阶段 0 结论（做空方向是否有效 + 数据）
- 阶段 1 成果（模拟盘就绪、做空链路验证结果）
- 下一步建议（阶段 2 实盘最小仓位的准入条件）

---

## 注意事项

- 阶段 0 是**硬门槛**：做空方向验证不过，阶段 1 不实施（向用户汇报等决策）
- 模拟盘（9014）与实盘（9013）完全隔离：不同容器、不同端口、不同 sqlite、dry_run=true
- 模拟盘用**无 key 配置**（futures 模拟不需要真实 key），避免误操作实盘账户
- 服务器 1.6G 内存：模拟盘容器额外占 ~150MB，可接受；实验/训练避免并发
- 全程中文注释；每个 Task 结束跑相关测试
