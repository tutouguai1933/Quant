# 系统健壮性优化设计方案（P0-P3）

> 最后更新：2026-08-01
> 目标：支持 4 个 team agent 并发开发。本文档冻结各模块的**接口契约**，实现前先对齐契约，各 P 并行推进。

---

## 0. 总览

### 0.1 背景与优先级

| 优先级 | 方向 | 核心问题 | 教训来源 |
|--------|------|---------|---------|
| P0 | 下单前交易所校验 + 滑点建模 | 市价单裸奔，无价格保护、无滑点预算、只查了 min_notional | BNB 教训，真实资金安全 |
| P1 | 标签工程 + walk-forward 验证 | 标签固定 ±1%，切分是块内分层，无严格时间序列验证 | 门控再完善，模型质量不提升就是空转 |
| P2 | 本地数据仓库 | 行情用完即弃，每次训练现抓，无增量同步 | 回测和训练的地基 |
| P3 | 代理主备自动切换 | 已有自动切换雏形，但无主备优先级、切换无预验证、探测无节流 | 停机 5-7 周的直接根因 |

### 0.2 依赖关系（DAG）

```
P2 (数据仓库) ──接口先行──┐
                          ├── 相互独立，可全并行
P0 (交易校验) ────────────┤
P1 (标签+WF) ──接口先行───┘
P3 (代理主备) ────────────┘
```

- 4 个 P 完全相互独立，各自一个 feature 分支、一个 agent。
- 跨 P 依赖仅在**接口契约层**（见 0.4），契约先冻结，实现并行。
- P0 的 `BinanceMarketClient.get_klines()` 参数扩展与 P2 共用同一处改动，由 P2 负责实现，P0 只依赖其签名（该改动本身不破坏现有调用）。

### 0.3 分支与并发组织

| 分支 | 对应设计章节 | 建议 agent |
|------|-------------|-----------|
| `feat/p0-trade-validation` | §1 | agent-A |
| `feat/p1-label-walkforward` | §2 | agent-B |
| `feat/p2-kline-store` | §3 | agent-C |
| `feat/p3-vpn-failover` | §4 | agent-D |

合并顺序：P2 → P0 → P1 → P3（P2 最先合入，P0 的 klines 参数改动随 P2 一起合）。每个分支合并前必须通过：本分支 pytest + `python -m compileall` + 不破坏 `services/api/tests/test_execution_flow.py`。

### 0.4 公共约定（所有 agent 必须遵守）

1. **代码位置**：服务逻辑 → `services/api/app/services/`；外部适配 → `services/api/app/adapters/`；worker 侧 → `services/worker/`。
2. **配置命名**：一律 `QUANT_*` 环境变量，集中读取。API 侧在 `services/api/app/core/settings.py`（新增字段带默认值），worker 侧在 `services/worker/qlib_config.py`。
3. **测试**：pytest，API 侧放 `services/api/tests/`，worker 侧放 `services/worker/tests/`。新增模块必须带单测。
4. **数据量意识**：服务器仅 1.6G 内存。禁止引入 pandas/pyarrow/duckdb/sqlalchemy 等重依赖；存储用 JSON/JSONL/CSV 即可（数据规模 < 10MB）。
5. **Binance 风控意识**：对外部 API 的探测/拉取必须节流（间隔 ≥ 10s/次），禁止快速连续请求。
6. **兼容性**：所有新增行为默认**关闭**或与现状等价，通过 env 开关启用，避免一次合入改变线上行为。

---

## 1. P0：下单前交易所校验 + 滑点建模

### 1.1 现状（调查结论）

- 下单链路：`SignalService` → `StrategyDispatchService` → `ExecutionService.dispatch_signal()`（`services/api/app/services/execution_service.py:44`）→ `_guard_live_execution()`（L110，本地安全检查）→ `FreqtradeRestClient.submit_execution_action()`（`services/api/app/adapters/freqtrade/rest_client.py:168`）→ `POST /api/v1/forceenter`（L201-210，**hardcode `ordertype: market`**）→ freqtrade 内部 ccxt 下单。
- 现有校验：ExecutionService guard（symbol 白名单、max stake、open trades、min_notional）+ RiskGuardService（日亏损/次数/崩溃阈值）+ RiskService（曝光度）。**全部基于本地状态，无交易所实时校验**。
- 滑点：实时链路零滑点概念；回测有 `slippage_bps`（`qlib_backtest.py`），两者脱节。
- `BinanceMarketClient`（`services/api/app/adapters/binance/market_client.py`）有 `get_tickers/get_klines/get_exchange_info`，**无订单簿接口**。
- freqtrade 侧 `config.live.base.json` 已是 limit 单（order_book top 1），但 api 的 forceenter 传 `ordertype: market` **覆盖了**这个保护。

### 1.2 目标

下单前从交易所拉取实时数据完成 6 项校验（状态/精度/流动性/价差/余额/价格偏离），任一 `block` 级失败则拒绝下单并告警；滑点建模输出 expected/worst-case bps，超阈值拦截；下单参数可配置为 limit 单 + 撤单超时；成交后记录实际滑点。

### 1.3 设计

```
ExecutionService._guard_live_execution()
        │  (现有本地检查，不动)
        ▼
PreTradeValidator.validate()  ──▶  blocked → 拒绝 + Feishu 告警
        │  passed/warn
        ▼
SlippageModel.estimate()  ──▶  worst_case_bps > 阈值 → 拒绝
        │
        ▼
FreqtradeRestClient.submit_execution_action()
        │  (ordertype 由 QUANT_TRADE_ORDER_TYPE 控制)
        ▼
成交 → 记录实际成交价 vs 参考价 → slippage 实测入 .runtime/trade_slippage.jsonl
```

### 1.4 模块与接口契约

**M0.1 `PreTradeValidator`** — `services/api/app/services/pre_trade_validator.py`（新）

```python
@dataclass
class PreTradeCheck:
    name: str                          # symbol_status / price_precision / liquidity / spread / balance / price_deviation
    passed: bool
    detail: str | None
    severity: Literal["block", "warn"]

@dataclass
class PreTradeReport:
    symbol: str
    side: Literal["buy", "sell"]
    stake_amount: Decimal
    reference_price: Decimal
    checks: list[PreTradeCheck]
    blocked: bool                      # 任一 block 级失败
    warnings: list[str]
    slippage: "SlippageEstimate | None"

class PreTradeValidator:
    def __init__(self, market_client, account_client, config: "PreTradeConfig"): ...
    def validate(self, symbol: str, side: str, stake_amount: Decimal,
                 reference_price: Decimal, candles_4h: list[dict] | None = None) -> PreTradeReport: ...
```

检查项明细（每条都产出 `PreTradeCheck`）：

| name | 数据源 | block 条件 |
|------|--------|-----------|
| symbol_status | `get_exchange_info()` | status != TRADING，或缺少 filters |
| price_precision | exchange_info tickSize | 参考价按 tickSize 取整后偏离 > 0.5 tick |
| liquidity | `get_order_book()`（新接口，见下） | 可见深度累计量 < stake/price × `min_depth_coverage`(默认3) |
| spread | 订单簿 | 买一/卖一价差 > `max_spread_bps`(默认20) |
| balance | `get_balances()` | 可用 USDT < stake（buy）；持仓可用量 < stake/price（sell） |
| price_deviation | `get_tickers()` | 最新价 vs 参考价偏离 > `max_deviation_bps`(默认100) |

配置项（settings.py 新增，全带默认值）：`QUANT_PRE_TRADE_ENABLED`（默认 true）、`QUANT_PRE_TRADE_MIN_DEPTH_COVERAGE=3`、`QUANT_PRE_TRADE_MAX_SPREAD_BPS=20`、`QUANT_PRE_TRADE_MAX_DEVIATION_BPS=100`、`QUANT_PRE_TRADE_MAX_SLIPPAGE_BPS=30`。

**M0.2 `SlippageModel`** — `services/api/app/services/slippage_model.py`（新）

```python
@dataclass
class SlippageEstimate:
    expected_bps: Decimal      # 深度成本法：沿订单簿累计到目标量，加权均价 vs 买一价偏差
    worst_case_bps: Decimal    # max(expected_bps × 2, 波动率法：近20根K线收益std × 2)
    depth_coverage_pct: Decimal  # 目标量在可见深度内的覆盖比例

class SlippageModel:
    def __init__(self, config: "SlippageConfig"): ...
    def estimate(self, symbol: str, side: str, stake_amount: Decimal,
                 order_book: dict, candles_4h: list[dict]) -> SlippageEstimate: ...
```

依赖：`BinanceMarketClient` 新增 `get_order_book(symbol, limit=20) -> dict`（走 `data-api.binance.vision` 直连，复用现有重试逻辑）。此接口由 **P2 的 agent 一并实现**（同文件小改动），契约先行：`get_order_book(self, symbol: str, limit: int = 20) -> dict`，返回 `{bids: [[price, qty], ...], asks: [...]}`。

**M0.3 ExecutionService 集成** — `services/api/app/services/execution_service.py`（改）

- `_guard_live_execution()` 之后、`submit_execution_action()` 之前插入 `pre_trade_validator.validate()`。
- `blocked=True` → 拒绝执行，返回结构化错误，推送 Feishu 告警（复用 `feishu_push_service`），写入 `risk_events`（type=`pre_trade_blocked`）。
- 滑点校验：`worst_case_bps > QUANT_PRE_TRADE_MAX_SLIPPAGE_BPS` → 同样拒绝。
- 成交后：从 forceenter 响应提取成交价，与 reference_price 对比，追写 `.runtime/trade_slippage.jsonl`（一行一条：`{ts, symbol, side, ref_price, fill_price, slippage_bps}`）。
- 模式开关：`QUANT_PRE_TRADE_ENABLED=false` 时完全跳过（保持现状）。

**M0.4 FreqtradeRestClient 下单参数** — `services/api/app/adapters/freqtrade/rest_client.py`（改）

- 删除 hardcode `"ordertype": "market"`，改由 `QUANT_TRADE_ORDER_TYPE`（默认 `market`，兼容现状）控制。
- `limit` 模式：`ordertype=limit`，`price = reference_price × (1 ± slippage_budget_bps/10000)`（buy 向上、sell 向下），`QUANT_TRADE_UNFILLED_TIMEOUT_SECONDS`（默认 15）超时后经 freqtrade `/api/v1/cancelopenorders` 撤单。
- `market` 模式：行为与现状一致（前置校验已兜底）。

### 1.5 任务拆分

| 任务 | 内容 | 依赖 | 验收标准 |
|------|------|------|---------|
| T0.1 | PreTradeValidator 实现 + 6 项检查单测 | 无 | 单测覆盖每项检查的 block/warn 分支；用 `_FakeBinanceMarketClient` 模式 mock（参考 `test_execution_flow.py:34`） |
| T0.2 | SlippageModel 实现 + 单测 | T0.1（类型引用） | 深度成本法在合成订单簿上数值正确；波动率法用合成 K 线 |
| T0.3 | ExecutionService 集成 + risk_events 写入 + 告警 | T0.1、T0.2 | `test_execution_flow.py` 全部通过；新增测试：validator 拒绝时不下单 |
| T0.4 | rest_client 下单参数改造 + limit 模式 | T0.3 | 现有测试通过；limit 模式下单参数断言 |
| T0.5 | 成交滑点记录 + 端到端集成测试 | T0.3、T0.4 | 单测验证 `.runtime/trade_slippage.jsonl` 写入格式 |

**T0.3 是集成点，建议 T0.1/T0.2 并行、T0.4 并行，最后 T0.3/T0.5。**

---

## 2. P1：标签工程 + walk-forward 验证

### 2.1 现状（调查结论）

- 标签：`services/worker/qlib_labels.py` `build_label_rows()`（L26）——未来 1-3 天窗口 `earliest_hit` 模式，±1% 阈值，buy/sell/watch 三元，阈值硬编码在 `qlib_config.py`（`QUANT_QLIB_LABEL_TARGET_PCT/STOP_PCT`）。
- 切分：`qlib_dataset.py` `_split_rows()`（L199）——5 时间块内 60/20/20 分层抽样，**无严格 walk-forward，无泄漏隔离**。
- ML 训练：`services/worker/ml/trainer.py` L171 二值化（future_return > 1%）。
- 门控：`qlib_ranking.py` 6 道门控已实现且可开关，Validation Gate 用 per-symbol 简单指标（sample_count/positive_rate）。

### 2.2 目标

标签参数化（阈值/窗口/中性区）+ 标签质量报告；严格时间序列 walk-forward 验证（含防泄漏 gap），产出每折指标与汇总；标签敏感性网格扫描输出报告供调参。

### 2.3 设计

```
candles → LabelEngine.build(spec) → LabeledRow[]
                                        │
WalkForwardValidator.split(rows, cfg)   │  ← 时间升序切分 + gap 隔离
        ▼                               │
每折: train_fn(train) → predict(test) → 折指标
        ▼
WalkForwardReport {folds: [...], summary: {mean, std}}  → 供 Validation Gate 可选使用
```

兼容性：`LabelSpec` 默认值 = 现有行为；`QUANT_QLIB_ENABLE_WALK_FORWARD`（默认 false）时训练仍走现有 `_split_rows`。A/B 对比通过后由人工开启。

### 2.4 模块与接口契约

**M1.1 `LabelEngine`** — `services/worker/qlib_labels.py`（重构，保持 `build_label_rows` 签名兼容）

```python
@dataclass
class LabelSpec:
    target_pct: float = 1.0
    stop_pct: float = -1.0
    window_bars: int = 18          # 4h×18=72h≈3天，与现状"1-3天"对齐
    mode: str = "earliest_hit"     # earliest_hit / close_only / window_majority（现有三种）
    neutral_threshold_pct: float = 0.0   # 新增：|收益| ≤ 此值 → watch，过滤噪声标签

@dataclass
class LabeledRow:
    open_time: int
    future_return_pct: float
    label: str                     # buy / sell / watch
    is_trainable: bool

@dataclass
class LabelQuality:
    total: int
    buy_ratio: float
    sell_ratio: float
    watch_ratio: float
    trainable_ratio: float

class LabelEngine:
    def build(self, candles: list[dict], spec: LabelSpec) -> list[LabeledRow]: ...
    def quality_report(self, rows: list[LabeledRow]) -> LabelQuality: ...
```

新增 env：`QUANT_QLIB_LABEL_WINDOW_BARS`、`QUANT_QLIB_LABEL_NEUTRAL_PCT`（读取在 `qlib_config.py`）。

**M1.2 `WalkForwardValidator`** — `services/worker/qlib_walk_forward.py`（新）

```python
@dataclass
class WalkForwardConfig:
    n_folds: int = 4
    min_train_bars: int = 120
    gap_bars: int = 18             # 默认 = 标签窗口（防泄漏），训练/测试之间的隔离带
    mode: str = "expanding"        # expanding（滚动扩展）/ rolling（固定窗口）
    step_bars: int | None = None   # rolling 时的窗口长度

@dataclass
class Fold:
    index: int
    train: list[dict]
    test: list[dict]
    test_start_ts: int
    test_end_ts: int

@dataclass
class FoldMetrics:
    fold: int
    n_test: int
    positive_rate: float
    auc: float | None
    avg_future_return_pct: float

@dataclass
class WalkForwardReport:
    folds: list[FoldMetrics]
    summary: dict                   # {mean: {...}, std: {...}}

class WalkForwardValidator:
    def split(self, rows: list[dict], config: WalkForwardConfig) -> list[Fold]: ...
    def run(self, predict_fn, rows: list[dict], config: WalkForwardConfig) -> WalkForwardReport: ...
```

约束：rows 按 open_time 升序；每折 test 严格在 train 之后且间隔 ≥ gap_bars × interval；`min_train_bars` 不足则自动减少折数并记录。

**M1.3 标签敏感性扫描** — `services/worker/qlib_label_sweep.py`（新）

- 网格：`target_pct ∈ {0.5, 1.0, 1.5, 2.0}` × `window_bars ∈ {6, 12, 18, 24}` × `neutral ∈ {0, 0.3}`。
- 每组合：LabelEngine.build → WalkForwardValidator.run（复用同一 predict 管线）→ 汇总 `{label_quality, wf_auc_mean, wf_return_mean}`。
- 输出 `.runtime/qlib/label_sweep/sweep_report.csv` + JSON；**只出报告，不自动改生产参数**。
- 限制：总组合 32 个 × 每折训练，必须复用现有训练超时控制（`ml/trainer.py` 现有 timeout 模式），预计 < 15 分钟。

**M1.4 QlibRunner 集成** — `services/worker/qlib_runner.py`（改）

- `train()` 增加 walk-forward 分支：`QUANT_QLIB_ENABLE_WALK_FORWARD=true` 时用 `WalkForwardValidator` 替代 `_split_rows` 的 train/valid/test 构造；模型训练仍用 train 折，Validation Gate 输入改用 walk-forward 汇总指标（`wf_auc_mean`、`wf_return_mean`，替代/补充 per-symbol validation，env 开关 `QUANT_QLIB_GATE_USE_WALK_FORWARD` 默认 false）。
- 推理路径不变。
- 标签构建处改用 `LabelEngine.build()`（默认 spec 与现状等价，回归测试必须通过）。

### 2.5 任务拆分

| 任务 | 内容 | 依赖 | 验收标准 |
|------|------|------|---------|
| T1.1 | LabelEngine 重构 + LabelQuality | 无 | 默认 spec 输出与现有 `build_label_rows` 完全一致（对比测试）；`neutral_threshold` 生效测试 |
| T1.2 | WalkForwardValidator 实现 | 无 | 切分单调性/泄漏隔离单测；合成数据上 run() 指标正确 |
| T1.3 | 标签敏感性扫描 | T1.1、T1.2 | 32 组合 ≤ 15 分钟跑完；报告 CSV 字段齐全 |
| T1.4 | QlibRunner 集成 | T1.1、T1.2 | 现有 `tests/test_qlib_runner.py`、`test_qlib_dataset.py` 全过（默认路径回归）；开启 WF 的开关测试 |

**T1.1/T1.2 并行；T1.3/T1.4 并行收尾。**

---

## 3. P2：本地数据仓库

### 3.1 现状（调查结论）

- 行情链路「实时抓取 → 内存加工 → 用完丢弃」：`BinanceMarketClient.get_klines()`（`services/api/app/adapters/binance/market_client.py:80`，limit 固定 200、无 start/end 参数）每次 HTTP 拉取，无持久化。
- `.runtime/` 只有 JSON 状态文件，无行情存储。`packages/db/schema.sql` 是控制面 schema（8 张表，无行情表）。
- freqtrade 侧有 `infra/freqtrade/user_data/data/binance/*.feather`（11 币 4h，无项目内调用方）。
- 无增量同步、无回填机制。
- 依赖：项目未引入 pandas/pyarrow/duckdb/sqlalchemy（**本方案继续不引入**）。

### 3.2 目标

16 币 × 3 周期（4h/1h/15m）× 90 天的 K 线本地仓库：首次回填 + 每日/每次训练前增量同步，缺口检测与自动补齐；训练/行情服务从仓库读数据，网络故障时降级用仓库数据。

### 3.3 设计

```
BinanceMarketClient.get_klines()（增加 start/end/limit 参数）
        │
        ▼
KlineSyncService ──▶ KlineStore.upsert()    .runtime/kline_store/{SYM}_{INT}.jsonl
        ▲                                    每行一个 bar：{open_time, open, high, low, close, volume, close_time}
        │
MarketService / 自动化周期 ──▶ KlineStore.read()（缺口自动触发补齐）
```

数据规模评估：16 币 × 90 天 4h ≈ 16 × 540 ≈ 8.6k 行；加 1h/15m ≈ 100k 行，JSONL 总量 < 20MB，完全可承受。

### 3.4 模块与接口契约

**M2.1 `KlineStore`** — `services/api/app/services/kline_store.py`（新）

```python
class KlineStore:
    def __init__(self, root: Path): ...          # 默认 .runtime/kline_store
    def upsert(self, symbol: str, interval: str, rows: list[dict]) -> int: ...
        # 按 open_time 去重合并，返回新增条数；文件尾部顺序追加 + 内存索引去重
    def read(self, symbol: str, interval: str,
             start_ts: int | None = None, end_ts: int | None = None) -> list[dict]: ...
        # 升序返回规范化 bar dict（字段与 MarketService._normalize_kline_rows 一致）
    def last_timestamp(self, symbol: str, interval: str) -> int | None: ...
    def gaps(self, symbol: str, interval: str, start_ts: int, end_ts: int,
             interval_ms: int) -> list[tuple[int, int]]: ...
        # 返回缺口区间列表 [(start,end), ...]
```

文件布局：`.runtime/kline_store/BTCUSDT_4h.jsonl`，每行一个 bar JSON。写操作加文件锁（`fcntl.flock`），保证巡检/周期并发安全。

**M2.2 `KlineSyncService`** — `services/api/app/services/kline_sync_service.py`（新）

```python
@dataclass
class SyncReport:
    symbol: str
    interval: str
    fetched: int
    inserted: int
    gaps_filled: int
    duration_s: float

class KlineSyncService:
    def __init__(self, store: KlineStore, market_client: BinanceMarketClient): ...
    def backfill(self, symbols: list[str], intervals: list[str], days: int = 90) -> list[SyncReport]: ...
        # 用 get_klines(limit=1000) 分页倒序回填；4h×90天≈540根，一次即可；15m 需分页
    def incremental_sync(self, symbols: list[str], intervals: list[str]) -> list[SyncReport]: ...
        # 从 last_timestamp 起增量拉取，重复调用安全（upsert 幂等）
    def ensure_window(self, symbol: str, interval: str, days: int) -> None: ...
        # 训练前调用：窗口内数据不足则增量补齐
```

`BinanceMarketClient.get_klines()` 签名扩展（**由本 P 负责**，P0 依赖此签名）：

```python
def get_klines(self, symbol: str, interval: str = "4h",
               limit: int = 200, start_ts: int | None = None, end_ts: int | None = None) -> list[dict]: ...
```

同时新增 `get_order_book(self, symbol: str, limit: int = 20) -> dict`（P0 需要，一并实现）。两个方法都复用现有 `_safe_public_get` 重试逻辑。

**M2.3 数据源切换** — `services/api/app/services/market_service.py` + 自动化周期数据源（改）

- `MarketService` 增加 `get_klines_with_store()`：优先读 `KlineStore`，缺口触发 `ensure_window` 补齐，补齐失败时返回仓库已有数据（降级）。
- 自动化周期构造 market_payload 处（训练/推理前）调用 `incremental_sync`（16 币 × 3 周期，每次 < 30s）。
- 增量同步调度：挂在自动化周期训练前 + `ScheduledPatrolService` 每 15 分钟轻量同步一次。
- **不改变** `get_klines()` 现有调用方的行为（新增接口，原接口保留）。

### 3.5 任务拆分

| 任务 | 内容 | 依赖 | 验收标准 |
|------|------|------|---------|
| T2.1 | `get_klines` 参数扩展 + `get_order_book` 新接口 | 无 | 现有 market_client 测试全过；新参数单测（mock 断言 URL 带 start/end/limit） |
| T2.2 | KlineStore 实现 | 无 | upsert 幂等/去重、read 范围过滤、gaps 检测单测；并发写锁测试 |
| T2.3 | KlineSyncService 实现 | T2.1、T2.2 | mock 客户端回填/增量报告正确；重复同步不重复插入 |
| T2.4 | MarketService + 自动化周期数据源切换 | T2.2、T2.3 | 训练数据源切仓库后，现有 worker 测试全过（数据不变）；断网降级单测 |

**T2.1/T2.2 并行；T2.3/T2.4 串行收尾。**

---

## 4. P3：代理主备自动切换

### 4.1 现状（调查结论）

已有闭环（勿重造）：`OpenclawPatrolService._check_vpn_health()`（`services/api/app/services/openclaw_patrol_service.py:470`）每分钟检查（Binance ping + 出口 IP 白名单）→ 不健康时 `vpn_switch_service.auto_switch_to_healthy_node_sync()`（`services/api/app/services/vpn_switch_service.py`）按 `DEFAULT_AVAILABLE_NODES` **顺序尝试**切换（mihomo API PUT `/proxies/BestSSR`）。

差距：
1. 无「主/备」概念——顺序尝试，不区分白名单节点优先；
2. 切换前**无预验证**（切过去才发现不通）；
3. **无节流**——每分钟全量探测多个节点，易触发 Binance 风控（2026-08-01 实测：连续快速切换触发 TLS 拒绝）；
4. 切换后无观察期与自动回切；
5. 节点健康状态不持久化（重启丢记忆）。

已知可用白名单节点（2026-08-01 实测）：日本¹=154.31.113.7（主）、日本²=45.95.212.80、日本³=45.95.212.81、日本⁴=45.95.212.82、香港²=154.12.176.56、香港³=152.175.1.118、香港⁴=152.175.1.123。

### 4.2 目标

配置驱动的「主节点 + 备选队列」：主节点连续失败 N 次 → 预验证候选（白名单节点优先、延迟最低）→ 切换 → 观察期；主节点恢复后自动回切；探测节流（间隔 ≥ 10s）+ 结果缓存 + 状态持久化。

### 4.3 设计

```
OpenclawPatrolService._check_vpn_health()（每分钟，仅探测主节点）
        │  失败计数 ≥ N
        ▼
PrimaryBackupPolicy.should_failover() ── true
        ▼
pick_backup(): 白名单节点 → 预验证（探测通过）→ 延迟最低
        ▼
switch_node() → 观察期 5 分钟（持续探测，失败则换下一个）
        ▼
主节点恢复（连续成功 N 次）→ 自动回切
```

探测节流：`NodeHealthProbe` 缓存探测结果（TTL 120s），每分钟 patrol 只做「主节点快速检查」（Binance ping 一次，间隔由缓存保证）；全量探测仅在 failover 流程中触发（且节点间间隔 10s）。

### 4.4 模块与接口契约

**M3.1 `NodeRegistry`** — `services/api/app/services/vpn_node_registry.py`（新）

```python
@dataclass
class NodeEntry:
    name: str
    ip: str | None
    whitelisted: bool
    role: Literal["primary", "backup", "unknown"] = "unknown"
    last_probe_ok: bool | None = None
    last_probe_at: float | None = None

class NodeRegistry:
    def __init__(self, primary: str, backups: list[str], whitelisted_ips: set[str]): ...
    def known_nodes(self) -> list[NodeEntry]: ...          # 主 + 备，配置来源
    def mark_probe(self, name: str, ok: bool, ip: str | None) -> None: ...  # 更新内存+持久化
    def candidates(self) -> list[NodeEntry]: ...           # 备选：whitelisted 优先 → 最近探测通过 → 顺序
    def save_state(self, path: Path) -> None: ...          # .runtime/vpn_nodes.json
    def load_state(self, path: Path) -> None: ...
```

新 env（settings.py）：`QUANT_VPN_PRIMARY_NODE=★ 日本¹`、`QUANT_VPN_BACKUP_NODES=★ 日本²,★ 日本³,★ 日本⁴,★ 香港²,★ 香港³,★ 香港⁴`、`QUANT_VPN_WHITELISTED_IPS=154.31.113.7,45.95.212.80,45.95.212.81,45.95.212.82,154.12.176.56,152.175.1.118,152.175.1.123`。

**M3.2 `NodeHealthProbe`** — 增强 `vpn_switch_service.py`（改，复用现有 `check_node_health_sync` 逻辑）

```python
class NodeHealthProbe:
    def __init__(self, client, cache_ttl_s: float = 120.0): ...
    def check(self, node: str, force: bool = False) -> ProbeResult:
        # ProbeResult {ok, ip, latency_ms, at}
        # Binance ping（api.binance.com/api/v3/time 走代理）+ 出口 IP + 白名单匹配
    def check_with_interval(self, node: str, min_interval_s: float = 10.0) -> ProbeResult: ...
        # 强制节流：距上次 < min_interval_s 时返回缓存
```

**M3.3 `PrimaryBackupPolicy`** — `services/api/app/services/vpn_failover_policy.py`（新）

```python
class PrimaryBackupPolicy:
    def __init__(self, fail_threshold: int = 3, recover_threshold: int = 3,
                 observe_seconds: int = 300): ...
    def record_probe(self, node: str, ok: bool) -> None: ...
    def should_failover(self, primary: str) -> bool: ...   # 主节点连续失败 ≥ fail_threshold
    def pick_backup(self, registry: NodeRegistry, probe: NodeHealthProbe) -> str | None: ...
        # 白名单 → 探测通过 → 延迟最低；所有候选失败返回 None（保持现状节点）
    def should_failback(self, primary: str) -> bool: ...   # 主节点连续成功 ≥ recover_threshold
    def in_observation(self, switched_at: float) -> bool: ...  # 切换后 observe_seconds 内
```

**M3.4 集成** — `openclaw_patrol_service.py` + `vpn_switch_service.py`（改）

- `_check_vpn_health()` 改走：`probe.check(主节点)` → `policy.should_failover()` → `policy.pick_backup()` → 切换 → 观察期跟踪。
- `auto_switch_to_healthy_node_sync()` 保留签名，内部改用 policy（现有调用方零改动）。
- 切换事件写入 `risk_events`（type=`vpn_failover`，含 from/to/原因）。
- 探测结果持久化到 `.runtime/vpn_nodes.json`（每次 mark_probe 落盘，重启恢复记忆）。

### 4.5 任务拆分

| 任务 | 内容 | 依赖 | 验收标准 |
|------|------|------|---------|
| T3.1 | NodeRegistry + env 配置 | 无 | 配置解析、候选排序（白名单优先）、状态持久化单测 |
| T3.2 | NodeHealthProbe 节流/缓存增强 | 无 | 缓存 TTL 生效、节流间隔生效（mock 计时）单测 |
| T3.3 | PrimaryBackupPolicy | T3.1、T3.2 | 失败计数/回切/观察期/候选选取单测（纯逻辑无 IO） |
| T3.4 | Patrol + VPN 服务集成 | T3.1-T3.3 | 现有 patrol 测试全过；模拟主节点失败 → 自动切到白名单备选 → 恢复回切 的集成测试（mock mihomo API） |

**T3.1/T3.2 并行；T3.3/T3.4 串行收尾。**

---

## 5. 风险与注意事项

| 风险 | 应对 |
|------|------|
| P0 限价单模式可能不成交 | 默认保持 market（现状），limit 为 opt-in；撤单超时兜底 |
| P0 校验数据源本身故障 | validator 对「数据获取失败」降级为 warn（不因校验器故障阻塞交易），但保留日志告警 |
| P1 walk-forward 训练耗时上升 | 默认关闭（env 开关）；开启时折数 4、min_train_bars 120，复用现有训练超时 |
| P2 JSONL 并发写 | 文件锁；单文件单周期单 symbol，无热写 |
| P3 探测打 Binance 触发风控 | 节流 ≥10s + 结果缓存 120s + 每分钟仅探测主节点 |
| 服务器 1.6G 内存 | 全部设计零重依赖、数据 <20MB；新增服务都是进程内模块，无新容器 |
| 一次合入改变线上行为 | 所有新行为默认关闭/等价现状，env 开关启用 |

## 6. 验证与上线顺序

1. 各分支独立：pytest（本分支 + 回归 `test_execution_flow.py` / `test_qlib_runner.py`）。
2. 合并顺序：P2 → P0 → P1 → P3；每步合入后跑全量 `services/api/tests` + `services/worker/tests`。
3. 上线：服务器 git pull + 按 `docs/DEPLOYMENT_GUIDE.md` 重建对应容器；P0 先 `QUANT_PRE_TRADE_ENABLED=true` 观察一轮周期，P1 先开 `QUANT_QLIB_ENABLE_WALK_FORWARD=false` 看报告，P3 先观察 patrol 日志确认切换策略生效。
4. 每 P 合入后更新 `docs/roadmap.md` 与 `CONTEXT.md`。

## 7. 参考

- 现有代码位置见各节「现状」；执行链路详见 `docs/SERVICE_ARCHITECTURE.md`。
- 代理白名单节点清单维护于 `.claude/projects/-home-djy-Quant/memory/mihomo-proxy-maintenance.md`。
