# Qlib 图表图层与研究文案统一 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不引入新依赖的前提下，把单币页补成轻量图表图层，并把市场页、单币页、策略页统一成同一套研究文案口径。

**Architecture:** 继续复用现有 `research_brief`、`research_cockpit` 和 `markers`。后端只补必要的轻量辅助字段，前端重点收口 `CandleChart`、单币页和策略页的展示顺序与标签，不新建独立页面。

**Tech Stack:** Python、FastAPI、unittest、Next.js、TypeScript、现有市场接口和研究驾驶舱服务

---

## 关联设计

- 设计文档：`docs/superpowers/specs/2026-04-02-qlib-chart-visual-layer-design.md`

## 范围

### 本计划要做

- 单币页补轻量图表图层摘要
- 三个页面统一研究文案顺序和标签
- 在必要处补最小后端辅助字段
- 补失败测试、review、真实页面验证、文档和提交

### 本计划不做

- 引入新图表库
- 新增独立驾驶舱页面
- 修改软门控规则
- 修改执行链路

## 文件分工

### 新建

- 无

### 修改

- `services/api/app/services/research_cockpit_service.py`
  - 只在必要时补图层摘要需要的轻量辅助字段
- `services/api/tests/test_research_cockpit_service.py`
  - 验证新增辅助字段和降级
- `apps/web/components/candle-chart.tsx`
  - 增加图表图层摘要展示
- `apps/web/app/market/page.tsx`
  - 统一市场页研究文案标签
- `apps/web/app/market/[symbol]/page.tsx`
  - 把单币页摘要顺序统一成图表摘要、图表图层摘要、当前判断、研究解释
- `apps/web/app/strategies/page.tsx`
  - 统一策略卡片字段顺序和标签
- `apps/web/lib/api.ts`
  - 在需要时补前端类型
- `tests/test_market_workspace.py`
  - 验证市场页和单币页的新标签与图层摘要
- `tests/test_frontend_refactor.py`
  - 验证策略页统一后的标签
- `README.md`
  - 补页面展示变化
- `docs/architecture.md`
  - 补图表图层摘要职责
- `CONTEXT.md`
  - 记录阶段进度和关键决定

## Task 1：补图表图层摘要的最小契约

**Files:**
- Modify: `services/api/app/services/research_cockpit_service.py`
- Modify: `services/api/tests/test_research_cockpit_service.py`

- [ ] **Step 1: 写失败测试，固定图表图层摘要需要的字段**

```python
def test_build_symbol_research_cockpit_includes_overlay_summary_fields(self) -> None:
    summary = build_symbol_research_cockpit(
        symbol="BTCUSDT",
        recommended_strategy="trend_breakout",
        evaluation={
            "decision": "signal",
            "confidence": "high",
            "reason": "close_breaks_recent_high_research_confirmed",
            "research_gate": {"status": "confirmed_by_research"},
        },
        research_summary={
            "score": "0.7100",
            "signal": "long",
            "model_version": "qlib-minimal-20260402120000",
            "explanation": "trend_gap=2.1%",
            "generated_at": "2026-04-02T12:00:00+00:00",
        },
        markers={
            "signals": [{"price": "107"}],
            "entries": [{"price": "105"}],
            "stops": [{"price": "99"}],
        },
    )

    self.assertEqual(summary["signal_count"], 1)
    self.assertEqual(summary["entry_hint"], "105")
    self.assertEqual(summary["stop_hint"], "99")
    self.assertEqual(summary["overlay_summary"], "1 个信号点 / 入场 105 / 止损 99")
```

- [ ] **Step 2: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_research_cockpit_service -v
```

Expected:

- FAIL，提示 `overlay_summary` 不存在

- [ ] **Step 3: 用最小实现补辅助字段**

```python
summary["overlay_summary"] = _build_overlay_summary(
    signal_count=len(signals),
    entry_hint=summary["entry_hint"],
    stop_hint=summary["stop_hint"],
)
```

- [ ] **Step 4: 再补降级测试**

```python
def test_build_symbol_research_cockpit_overlay_summary_degrades_to_na(self) -> None:
    summary = build_symbol_research_cockpit(
        symbol="BTCUSDT",
        recommended_strategy="none",
        evaluation=None,
        research_summary=None,
        markers={"signals": [], "entries": [], "stops": []},
    )

    self.assertEqual(summary["overlay_summary"], "0 个信号点 / 入场 n/a / 止损 n/a")
```

- [ ] **Step 5: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_research_cockpit_service -v
```

Expected:

- PASS

- [ ] **Step 6: 提交当前小步**

```bash
git add services/api/app/services/research_cockpit_service.py services/api/tests/test_research_cockpit_service.py
git commit -m "Add chart overlay summary field"
```

## Task 2：补单币页图表图层摘要

**Files:**
- Modify: `apps/web/components/candle-chart.tsx`
- Modify: `apps/web/app/market/[symbol]/page.tsx`
- Modify: `apps/web/lib/api.ts`
- Modify: `tests/test_market_workspace.py`

- [ ] **Step 1: 写失败测试，固定单币页和图表组件的新展示**

```python
def test_symbol_page_and_chart_show_overlay_summary(self) -> None:
    page_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")
    chart_content = (WEB_COMPONENTS / "candle-chart.tsx").read_text(encoding="utf-8")

    self.assertIn("图表图层摘要", page_content)
    self.assertIn("overlay_summary", page_content)
    self.assertIn("研究门控", page_content)
    self.assertIn("判断信心", page_content)
    self.assertIn("信号点", chart_content)
    self.assertIn("入场参考", chart_content)
    self.assertIn("止损参考", chart_content)
```

- [ ] **Step 2: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace -v
```

Expected:

- FAIL，提示单币页或图表组件缺少新标签

- [ ] **Step 3: 最小实现图表图层摘要**

```tsx
<CandleChart
  symbol={symbol}
  items={items}
  overlaySummary={research_cockpit.overlay_summary}
  signalCount={Number(research_cockpit.signal_count ?? markers.signals.length)}
  entryHint={formatText(research_cockpit.entry_hint, formatLatestMarkerPrice(markers.entries))}
  stopHint={formatText(research_cockpit.stop_hint, formatLatestMarkerPrice(markers.stops))}
  researchBias={formatResearchBias(research_cockpit.research_bias)}
/>
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
git add apps/web/components/candle-chart.tsx apps/web/app/market/[symbol]/page.tsx apps/web/lib/api.ts tests/test_market_workspace.py
git commit -m "Add chart overlay summary to market page"
```

## Task 3：统一三页研究文案顺序和标签

**Files:**
- Modify: `apps/web/app/market/page.tsx`
- Modify: `apps/web/app/market/[symbol]/page.tsx`
- Modify: `apps/web/app/strategies/page.tsx`
- Modify: `tests/test_market_workspace.py`
- Modify: `tests/test_frontend_refactor.py`

- [ ] **Step 1: 写失败测试，固定统一标签**

```python
def test_pages_use_unified_research_labels(self) -> None:
    market_content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")
    symbol_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")
    strategies_content = (WEB_APP / "strategies" / "page.tsx").read_text(encoding="utf-8")

    for content in (market_content, symbol_content, strategies_content):
        self.assertIn("研究倾向", content)
        self.assertIn("推荐策略", content)
        self.assertIn("判断信心", content)
        self.assertIn("研究门控", content)
```

- [ ] **Step 2: 运行目标测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace tests.test_frontend_refactor -v
```

Expected:

- FAIL，提示市场页缺少“判断信心”或策略页缺少统一标签

- [ ] **Step 3: 最小实现统一标签和顺序**

```tsx
columns={[
  "Symbol",
  "Last Price",
  "24h Change",
  "研究倾向",
  "推荐策略",
  "判断信心",
  "主判断",
  "Action",
]}
```

```tsx
<p>推荐策略：{formatPreferredStrategy(item.research_cockpit.recommended_strategy)}</p>
<p>研究倾向：{formatResearchBias(item.research_cockpit.research_bias)}</p>
<p>判断信心：{formatValue(item.research_cockpit.confidence, "n/a")}</p>
<p>研究门控：{formatValue(gate.status, "n/a")}</p>
<p>主判断：{formatValue(item.research_cockpit.primary_reason, "n/a")}</p>
```

- [ ] **Step 4: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace tests.test_frontend_refactor -v
```

Expected:

- PASS

- [ ] **Step 5: 提交当前小步**

```bash
git add apps/web/app/market/page.tsx apps/web/app/market/[symbol]/page.tsx apps/web/app/strategies/page.tsx tests/test_market_workspace.py tests/test_frontend_refactor.py
git commit -m "Unify research labels across cockpit pages"
```

## Task 4：完成 review、验证、文档和提交

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `CONTEXT.md`

- [ ] **Step 1: 做代码 review，优先看页面口径、降级和真实输出**

检查点：

- 三个页面是不是都使用同一套标签
- 单币页没有研究结果时是不是仍然能显示空状态
- 图表图层摘要是否会把 `None` 显示成字符串
- 市场页没有因为统一标签丢掉主判断

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
curl -s http://127.0.0.1:3000/market
curl -s http://127.0.0.1:3000/market/BTCUSDT
curl -s -b /tmp/quant-strategy.cookies http://127.0.0.1:3000/strategies
curl -s http://127.0.0.1:8000/api/v1/market
curl -s http://127.0.0.1:8000/api/v1/market/BTCUSDT/chart
```

Expected:

- `/market` HTML 中能看到“研究倾向 / 推荐策略 / 判断信心 / 主判断”
- `/market/BTCUSDT` HTML 中能看到“图表图层摘要 / 研究门控 / 判断信心 / 入场参考 / 止损参考”
- `/strategies` HTML 中能看到统一后的标签顺序
- 市场和图表接口仍返回统一研究字段

- [ ] **Step 4: 更新文档**

```markdown
- README.md：补“图表图层摘要”和统一研究标签
- docs/architecture.md：补 `CandleChart` 和三页统一研究展示关系
- CONTEXT.md：记录当前阶段完成项、停留位置和关键决定
```

- [ ] **Step 5: 最终提交**

```bash
git add README.md docs/architecture.md CONTEXT.md docs/superpowers/specs/2026-04-02-qlib-chart-visual-layer-design.md docs/superpowers/plans/2026-04-02-qlib-chart-visual-layer-implementation.md
git add services/api/app/services/research_cockpit_service.py services/api/tests/test_research_cockpit_service.py
git add apps/web/components/candle-chart.tsx apps/web/app/market/page.tsx apps/web/app/market/[symbol]/page.tsx apps/web/app/strategies/page.tsx apps/web/lib/api.ts
git add tests/test_market_workspace.py tests/test_frontend_refactor.py
git commit -m "Add chart overlay summary and unify research copy"
```
