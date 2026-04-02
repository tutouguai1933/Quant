# Qlib 多周期交易视图与页面动线重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把市场页、单币页、策略页重构成“先筛选 -> 再看图 -> 再执行”的动线，并为单币页补上 Binance 风格的多周期交易视图。

**Architecture:** 图表主数据继续使用交易所 K 线，`Qlib` 继续负责研究判断、打点、多周期摘要和解释。后端在现有市场接口上补多周期摘要和周期元数据，前端通过新组件把单币页重构成交易视图，并把市场页、策略页分别收口成筛选入口和执行页。

**Tech Stack:** Python、FastAPI、unittest、Next.js、TypeScript、现有 Binance 市场适配器、Qlib 研究摘要服务

---

## 关联设计

- 设计文档：`docs/superpowers/specs/2026-04-02-qlib-trading-view-flow-design.md`

## 范围

### 本计划要做

- 市场接口补多周期图表元数据和多周期研究摘要
- 单币页支持 `1m / 3m / 5m / 15m / 30m / 1h / 4h / 1d / 1w`
- 单币页重构为交易视图：周期切换、K 线主图、研究打点、右侧判断卡、多周期摘要
- 市场页重构为筛选入口
- 策略页收口为执行页
- 补测试、review、真实页面验证、文档和提交

### 本计划不做

- 引入新的图表依赖
- 新增独立研究页面
- 改软门控规则
- 改 `Freqtrade` 执行边界
- 开放自动下单

## 文件分工

### 新建

- `services/api/app/services/market_timeframe_service.py`
  - 负责定义支持的周期、校验周期、生成多周期摘要
- `services/api/tests/test_market_timeframe_service.py`
  - 验证周期白名单、降级和多周期摘要
- `apps/web/components/market-filter-bar.tsx`
  - 市场页顶部筛选入口
- `apps/web/components/market-focus-board.tsx`
  - 市场页右侧优先关注区
- `apps/web/components/timeframe-tabs.tsx`
  - 单币页顶部周期切换条
- `apps/web/components/trading-chart-panel.tsx`
  - 单币页主图表区，负责 SVG K 线、入场线、止损线、信号点
- `apps/web/components/research-sidecard.tsx`
  - 单币页右侧固定判断卡
- `apps/web/components/multi-timeframe-summary.tsx`
  - 单币页主图下方多周期摘要

### 修改

- `services/api/app/services/market_service.py`
  - 接入周期服务，返回当前周期、支持周期和多周期摘要
- `services/api/app/routes/market.py`
  - 校验和透传周期参数
- `services/api/tests/test_market_service.py`
  - 验证图表接口的新字段和周期切换
- `apps/web/lib/api.ts`
  - 增加多周期图表数据类型和归一化
- `apps/web/app/market/page.tsx`
  - 改成筛选入口和优先关注视图
- `apps/web/app/market/[symbol]/page.tsx`
  - 改成交易视图主页面
- `apps/web/app/strategies/page.tsx`
  - 收口成执行页，减少图表解释性文案
- `tests/test_market_workspace.py`
  - 验证市场页和单币页新结构
- `tests/test_frontend_refactor.py`
  - 验证策略页执行页收口
- `README.md`
  - 补多周期交易视图和动线变化
- `docs/architecture.md`
  - 补市场筛选、交易视图、执行页三段关系
- `docs/api.md`
  - 补市场图表接口新增字段
- `CONTEXT.md`
  - 记录阶段进度和关键决定

## Task 1：补多周期后端契约

**Files:**
- Create: `services/api/app/services/market_timeframe_service.py`
- Create: `services/api/tests/test_market_timeframe_service.py`
- Modify: `services/api/app/services/market_service.py`
- Modify: `services/api/tests/test_market_service.py`

- [ ] **Step 1: 写失败测试，固定周期白名单和默认周期**

```python
def test_normalize_market_interval_supports_binance_style_choices(self) -> None:
    self.assertEqual(normalize_market_interval("15m"), "15m")
    self.assertEqual(normalize_market_interval("1d"), "1d")
    self.assertEqual(normalize_market_interval("weird"), "4h")
    self.assertEqual(get_supported_market_intervals(), ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"))
```

- [ ] **Step 2: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_market_timeframe_service -v
```

Expected:

- FAIL，提示 `market_timeframe_service` 或相关函数不存在

- [ ] **Step 3: 用最小实现补周期服务**

```python
SUPPORTED_MARKET_INTERVALS = ("1m", "3m", "5m", "15m", "30m", "1h", "4h", "1d", "1w")
DEFAULT_MARKET_INTERVAL = "4h"


def get_supported_market_intervals() -> tuple[str, ...]:
    return SUPPORTED_MARKET_INTERVALS


def normalize_market_interval(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in SUPPORTED_MARKET_INTERVALS else DEFAULT_MARKET_INTERVAL
```

- [ ] **Step 4: 再写失败测试，固定图表接口新增字段**

```python
def test_get_symbol_chart_returns_interval_metadata_and_multi_timeframe_summary(self) -> None:
    chart = service.get_symbol_chart("BTCUSDT", interval="15m", limit=50)

    self.assertEqual(chart["active_interval"], "15m")
    self.assertEqual(chart["supported_intervals"][0], "1m")
    self.assertEqual(chart["supported_intervals"][-1], "1w")
    self.assertEqual([item["interval"] for item in chart["multi_timeframe_summary"]], ["1d", "4h", "1h", "15m"])
```

- [ ] **Step 5: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_market_service -v
```

Expected:

- FAIL，提示 `active_interval` 或 `multi_timeframe_summary` 缺失

- [ ] **Step 6: 用最小实现补市场服务接线**

```python
active_interval = normalize_market_interval(interval)
multi_timeframe_summary = build_multi_timeframe_summary(
    symbol=symbol.strip().upper(),
    intervals=("1d", "4h", "1h", "15m"),
    evaluate_interval=lambda candidate_interval: self._build_market_strategy_summary(
        symbol.strip().upper(),
        tuple(self._catalog_service.get_whitelist()),
        interval=candidate_interval,
    ),
)

return {
    "items": items,
    "overlays": dict(chart.get("overlays") or {}),
    "markers": markers,
    "active_interval": active_interval,
    "supported_intervals": get_supported_market_intervals(),
    "multi_timeframe_summary": multi_timeframe_summary,
    "strategy_context": strategy_context,
    "research_cockpit": build_symbol_research_cockpit(
        symbol=symbol.strip().upper(),
        recommended_strategy=str(strategy_context.get("recommended_strategy", "none")),
        evaluation=_resolve_primary_evaluation(
            str(strategy_context.get("recommended_strategy", "none")),
            dict(strategy_context.get("evaluations") or {}),
        ),
        research_summary=research_summary,
        markers=markers,
    ),
}
```

- [ ] **Step 7: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_market_timeframe_service services.api.tests.test_market_service -v
```

Expected:

- PASS

- [ ] **Step 8: 提交当前小步**

```bash
git add services/api/app/services/market_timeframe_service.py services/api/tests/test_market_timeframe_service.py services/api/app/services/market_service.py services/api/tests/test_market_service.py
git commit -m "Add market timeframe service"
```

## Task 2：补前端多周期类型与单币页交易视图骨架

**Files:**
- Create: `apps/web/components/timeframe-tabs.tsx`
- Create: `apps/web/components/trading-chart-panel.tsx`
- Create: `apps/web/components/research-sidecard.tsx`
- Create: `apps/web/components/multi-timeframe-summary.tsx`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/market/[symbol]/page.tsx`
- Modify: `tests/test_market_workspace.py`

- [ ] **Step 1: 写失败测试，固定单币页的新结构**

```python
def test_symbol_page_uses_trading_view_components(self) -> None:
    page_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")

    self.assertIn("TimeframeTabs", page_content)
    self.assertIn("TradingChartPanel", page_content)
    self.assertIn("ResearchSidecard", page_content)
    self.assertIn("MultiTimeframeSummary", page_content)
    self.assertIn("active_interval", page_content)
    self.assertIn("supported_intervals", page_content)
    self.assertIn("multi_timeframe_summary", page_content)
```

- [ ] **Step 2: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace -v
```

Expected:

- FAIL，提示单币页或新组件不存在

- [ ] **Step 3: 用最小实现补前端类型**

```ts
export type MultiTimeframeSummaryItem = {
  interval: string;
  trend_state: "uptrend" | "pullback" | "neutral";
  research_bias: string;
  recommended_strategy: "trend_breakout" | "trend_pullback" | "none";
  confidence: string;
  primary_reason: string;
};

export type MarketChartData = {
  items: MarketCandle[];
  overlays: ChartIndicatorSummary;
  markers: ChartMarkerGroups;
  active_interval: string;
  supported_intervals: string[];
  multi_timeframe_summary: MultiTimeframeSummaryItem[];
  research_cockpit: ResearchCockpitSummary;
  strategy_context: {
    recommended_strategy: "trend_breakout" | "trend_pullback" | "none";
    trend_state: "uptrend" | "pullback" | "neutral";
    next_step: string;
    primary_reason: string;
    evaluations: Record<string, Record<string, unknown>>;
  };
  freqtrade_readiness: {
    executor: string;
    backend: string;
    runtime_mode: string;
    ready_for_real_freqtrade: boolean;
    reason: string;
    next_step: string;
  };
};
```

- [ ] **Step 4: 用最小实现补单币页交易视图骨架**

```tsx
<TimeframeTabs symbol={symbol} activeInterval={chartData.active_interval} supportedIntervals={chartData.supported_intervals} />
<div className="trading-layout">
  <TradingChartPanel
    symbol={symbol}
    interval={chartData.active_interval}
    items={items}
    markers={chartData.markers}
  />
  <ResearchSidecard
    cockpit={research_cockpit}
    nextStep={strategyContext.next_step}
  />
</div>
<MultiTimeframeSummary items={chartData.multi_timeframe_summary} />
```

- [ ] **Step 5: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace -v
```

Expected:

- PASS

- [ ] **Step 6: 提交当前小步**

```bash
git add apps/web/components/timeframe-tabs.tsx apps/web/components/trading-chart-panel.tsx apps/web/components/research-sidecard.tsx apps/web/components/multi-timeframe-summary.tsx apps/web/lib/api.ts apps/web/app/market/[symbol]/page.tsx tests/test_market_workspace.py
git commit -m "Add trading view shell for market symbol page"
```

## Task 3：把 K 线主图做成可读交易视图

**Files:**
- Modify: `apps/web/components/trading-chart-panel.tsx`
- Modify: `tests/test_market_workspace.py`

- [ ] **Step 1: 写失败测试，固定图表主区要显示的关键元素**

```python
def test_trading_chart_panel_renders_candles_and_research_layers(self) -> None:
    content = (WEB_COMPONENTS / "trading-chart-panel.tsx").read_text(encoding="utf-8")

    self.assertIn("<svg", content)
    self.assertIn("entry", content)
    self.assertIn("stop", content)
    self.assertIn("signal", content)
    self.assertIn("当前价格", content)
    self.assertIn("当前周期", content)
```

- [ ] **Step 2: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace -v
```

Expected:

- FAIL，提示主图表组件还没有 SVG K 线和图层元素

- [ ] **Step 3: 用最小实现补 SVG K 线和研究图层**

```tsx
<svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${symbol} ${interval} candlestick chart`}>
  {candles.map((item) => (
    <g key={item.open_time}>
      <line x1={item.x} x2={item.x} y1={item.highY} y2={item.lowY} className="chart-wick" />
      <rect x={item.bodyX} y={item.bodyY} width={bodyWidth} height={item.bodyHeight} className={item.rising ? "chart-body-up" : "chart-body-down"} />
    </g>
  ))}
  {entryLine ? <line y1={entryLine} y2={entryLine} x1="0" x2={String(width)} className="chart-entry-line" /> : null}
  {stopLine ? <line y1={stopLine} y2={stopLine} x1="0" x2={String(width)} className="chart-stop-line" /> : null}
  {signals.map((signal) => <circle key={signal.key} cx={signal.x} cy={signal.y} r="4" className="chart-signal-dot" />)}
</svg>
```

- [ ] **Step 4: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace -v
```

Expected:

- PASS

- [ ] **Step 5: 提交当前小步**

```bash
git add apps/web/components/trading-chart-panel.tsx tests/test_market_workspace.py
git commit -m "Render SVG trading chart with research layers"
```

## Task 4：重构市场页为筛选入口

**Files:**
- Create: `apps/web/components/market-filter-bar.tsx`
- Create: `apps/web/components/market-focus-board.tsx`
- Modify: `apps/web/app/market/page.tsx`
- Modify: `tests/test_market_workspace.py`

- [ ] **Step 1: 写失败测试，固定市场页的新职责**

```python
def test_market_page_uses_filter_bar_and_focus_board(self) -> None:
    content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")

    self.assertIn("MarketFilterBar", content)
    self.assertIn("MarketFocusBoard", content)
    self.assertIn("多周期状态", content)
    self.assertIn("优先关注", content)
    self.assertIn("高信心", content)
```

- [ ] **Step 2: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace -v
```

Expected:

- FAIL，提示市场页还没有新的筛选和优先关注结构

- [ ] **Step 3: 用最小实现补市场页筛选入口**

```tsx
<MarketFilterBar />
<div className="market-layout">
  <table className="market-table">
    <thead>
      <tr>
        <th>Symbol</th>
        <th>Last Price</th>
        <th>24h Change</th>
        <th>多周期状态</th>
        <th>研究倾向</th>
        <th>推荐策略</th>
        <th>判断信心</th>
        <th>主判断</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <MarketFocusBoard items={items} />
</div>
```

- [ ] **Step 4: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace -v
```

Expected:

- PASS

- [ ] **Step 5: 提交当前小步**

```bash
git add apps/web/components/market-filter-bar.tsx apps/web/components/market-focus-board.tsx apps/web/app/market/page.tsx tests/test_market_workspace.py
git commit -m "Refactor market page into screening flow"
```

## Task 5：收口策略页为执行页

**Files:**
- Modify: `apps/web/app/strategies/page.tsx`
- Modify: `tests/test_frontend_refactor.py`

- [ ] **Step 1: 写失败测试，固定策略页执行页口径**

```python
def test_strategies_page_focuses_on_execution_not_chart_explanation(self) -> None:
    content = (WEB_APP / "strategies" / "page.tsx").read_text(encoding="utf-8")

    self.assertIn("执行器状态", content)
    self.assertIn("执行器控制", content)
    self.assertIn("最近执行结果", content)
    self.assertIn("推荐策略", content)
    self.assertNotIn("图表图层摘要", content)
    self.assertNotIn("止损参考", content)
```

- [ ] **Step 2: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_frontend_refactor -v
```

Expected:

- FAIL，提示策略页还保留了过多图表解释性结构，或者没有明确执行页文案

- [ ] **Step 3: 用最小实现收口策略页**

```tsx
<section className="panel">
  <p className="eyebrow">执行决策</p>
  <h3>这里不再重复看图，只负责决定能不能执行</h3>
  <p>图表判断留在单币页，策略页只保留执行器状态、最近信号和动作控制。</p>
</section>
```

- [ ] **Step 4: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_frontend_refactor -v
```

Expected:

- PASS

- [ ] **Step 5: 提交当前小步**

```bash
git add apps/web/app/strategies/page.tsx tests/test_frontend_refactor.py
git commit -m "Refocus strategies page on execution flow"
```

## Task 6：完成验证、文档和最终提交

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/api.md`
- Modify: `CONTEXT.md`

- [ ] **Step 1: 做代码 review，优先看三个风险点**

检查点：

- 多周期切换是不是严格限制在支持周期里
- 单币页在某个周期没研究结果时，K 线是否仍可显示
- 市场页和策略页是否已经彻底拉开职责

- [ ] **Step 2: 跑完整验证**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/api/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/worker/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s tests -v
cd /home/djy/Quant/apps/web && pnpm exec tsc --noEmit
cd /home/djy/Quant/apps/web && pnpm build
```

Expected:

- 所有测试通过
- 类型检查通过
- 构建通过

- [ ] **Step 3: 做真实页面验证**

Run:

```bash
curl -s "http://127.0.0.1:8000/api/v1/market/BTCUSDT/chart?interval=15m"
curl -s "http://127.0.0.1:8000/api/v1/market/BTCUSDT/chart?interval=1d"
curl -s http://127.0.0.1:3000/market
curl -s "http://127.0.0.1:3000/market/BTCUSDT?interval=15m"
curl -s "http://127.0.0.1:3000/market/BTCUSDT?interval=1d"
curl -i -s -c /tmp/quant-strategy.cookies -X POST -d "username=admin&password=1933&next=/strategies" http://127.0.0.1:3000/login/submit
curl -s -b /tmp/quant-strategy.cookies http://127.0.0.1:3000/strategies
```

Expected:

- 图表接口返回 `active_interval / supported_intervals / multi_timeframe_summary`
- `/market` 能看到筛选入口和优先关注区
- `/market/BTCUSDT?interval=15m` 能看到周期切换条、主图表、右侧判断卡、多周期摘要
- `/market/BTCUSDT?interval=1d` 会正确切换到日线
- 登录后的 `/strategies` 仍显示统一研究字段，但不会重复承担图表解释

- [ ] **Step 4: 更新文档**

```markdown
- README.md：补多周期交易视图和三页动线
- docs/architecture.md：补“市场筛选 -> 单币交易视图 -> 执行页”
- docs/api.md：补图表接口新增字段
- CONTEXT.md：记录当前阶段完成项和关键决定
```

- [ ] **Step 5: 最终提交**

```bash
git add README.md docs/architecture.md docs/api.md CONTEXT.md
git add services/api/app/services/market_timeframe_service.py services/api/tests/test_market_timeframe_service.py services/api/app/services/market_service.py services/api/tests/test_market_service.py
git add apps/web/components/market-filter-bar.tsx apps/web/components/market-focus-board.tsx apps/web/components/timeframe-tabs.tsx apps/web/components/trading-chart-panel.tsx apps/web/components/research-sidecard.tsx apps/web/components/multi-timeframe-summary.tsx
git add apps/web/lib/api.ts apps/web/app/market/page.tsx apps/web/app/market/[symbol]/page.tsx apps/web/app/strategies/page.tsx
git add tests/test_market_workspace.py tests/test_frontend_refactor.py
git commit -m "Implement qlib trading view flow"
```
