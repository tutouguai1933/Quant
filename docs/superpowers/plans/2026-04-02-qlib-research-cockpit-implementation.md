# Qlib 统一研究驾驶舱 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把统一研究摘要接入市场页、单币图表页和策略页，让三个页面用同一种研究表达。

**Architecture:** 后端先集中生成统一研究摘要，再由市场页消费简版摘要、单币图表页和策略页消费完整版摘要。继续沿用现有软门控规则，不新增独立研究页面，也不改执行链路。

**Tech Stack:** Python、FastAPI、unittest、Next.js、TypeScript、现有研究服务与策略服务

---

## 关联设计

- 设计文档：`docs/superpowers/specs/2026-04-02-qlib-research-cockpit-design.md`

## 范围

### 本计划要做

- 在后端生成统一研究摘要结构
- 把统一研究摘要接到市场总览页
- 把统一研究摘要接到单币图表页
- 把策略页当前研究字段改成统一口径
- 补失败测试、review、真实页面验证、文档和提交

### 本计划不做

- 新增独立研究驾驶舱页面
- 修改软门控阈值
- 接入新的执行链路
- 新增复杂图形化图表面板

## 文件分工

### 新建

- `services/api/app/services/research_cockpit_service.py`
  - 负责把研究结果、策略结论和图表标记收敛成统一研究摘要
- `services/api/tests/test_research_cockpit_service.py`
  - 覆盖统一研究摘要字段、降级和异常处理

### 修改

- `services/api/app/services/market_service.py`
  - 在市场快照和单币图表返回中补统一研究摘要
- `services/api/app/services/strategy_workspace_service.py`
  - 让策略页复用统一研究摘要，不再单独拼字段
- `services/api/app/services/strategy_engine.py`
  - 只在必要时补充统一摘要所需的门控字段读取辅助
- `services/api/tests/test_market_service.py`
  - 验证市场快照和图表接口返回统一研究摘要
- `services/api/tests/test_strategy_workspace_service.py`
  - 验证策略页返回统一研究摘要和降级行为
- `apps/web/lib/api.ts`
  - 增加统一研究摘要类型和归一化逻辑
- `apps/web/app/market/page.tsx`
  - 展示市场总览页简版研究摘要
- `apps/web/app/market/[symbol]/page.tsx`
  - 展示单币图表页完整版研究摘要
- `apps/web/app/strategies/page.tsx`
  - 展示统一字段口径
- `tests/test_market_workspace.py`
  - 验证市场页和单币页使用统一研究摘要字段
- `tests/test_frontend_refactor.py`
  - 验证策略页使用统一研究摘要字段
- `README.md`
  - 补统一研究驾驶舱说明
- `docs/architecture.md`
  - 补统一研究摘要职责和调用关系
- `docs/api.md`
  - 补统一研究摘要字段说明
- `CONTEXT.md`
  - 记录阶段进度和关键决定

## Task 1：定义统一研究摘要后端契约

**Files:**
- Create: `services/api/app/services/research_cockpit_service.py`
- Create: `services/api/tests/test_research_cockpit_service.py`

- [ ] **Step 1: 写失败测试，固定统一研究摘要的字段集合**

```python
def test_build_market_research_brief_returns_unified_fields(self) -> None:
    summary = build_market_research_brief(
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
    )

    self.assertEqual(summary["research_bias"], "bullish")
    self.assertEqual(summary["recommended_strategy"], "trend_breakout")
    self.assertEqual(summary["confidence"], "high")
    self.assertEqual(summary["model_version"], "qlib-minimal-20260402120000")
```

- [ ] **Step 2: 运行测试，确认现在失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_research_cockpit_service -v
```

Expected:

- FAIL，提示 `research_cockpit_service` 或统一摘要函数尚不存在

- [ ] **Step 3: 用最小实现补统一研究摘要服务**

```python
def build_market_research_brief(...):
    return {
        "research_bias": _resolve_research_bias(research_summary),
        "recommended_strategy": recommended_strategy,
        "confidence": str(evaluation.get("confidence", "low")),
        "research_gate": _normalize_gate(evaluation.get("research_gate")),
        "primary_reason": str(evaluation.get("reason", "")),
        "research_explanation": str(research_summary.get("explanation", "")),
        "model_version": str(research_summary.get("model_version", "")),
        "generated_at": str(research_summary.get("generated_at", "")),
    }


def build_symbol_research_cockpit(...):
    return {
        **brief,
        "signal_count": len(markers.get("signals", [])),
        "entry_hint": _latest_marker_price(markers.get("entries", [])),
        "stop_hint": _latest_marker_price(markers.get("stops", [])),
    }
```

- [ ] **Step 4: 再补失败测试，固定降级规则**

```python
def test_build_symbol_research_cockpit_degrades_when_score_is_invalid(self) -> None:
    summary = build_symbol_research_cockpit(
        symbol="BTCUSDT",
        recommended_strategy="trend_breakout",
        evaluation={
            "decision": "signal",
            "confidence": "high",
            "reason": "close_breaks_recent_high",
            "research_gate": {"status": "invalid_score"},
        },
        research_summary={"score": "NaN"},
        markers={"signals": [], "entries": [], "stops": []},
    )

    self.assertEqual(summary["research_bias"], "unavailable")
    self.assertEqual(summary["research_gate"]["status"], "invalid_score")
    self.assertEqual(summary["entry_hint"], "n/a")
    self.assertEqual(summary["stop_hint"], "n/a")
```

- [ ] **Step 5: 运行测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_research_cockpit_service -v
```

Expected:

- PASS

- [ ] **Step 6: 提交当前小步**

```bash
git add services/api/app/services/research_cockpit_service.py services/api/tests/test_research_cockpit_service.py
git commit -m "Add research cockpit service"
```

## Task 2：把统一研究摘要接到市场接口

**Files:**
- Modify: `services/api/app/services/market_service.py`
- Modify: `services/api/tests/test_market_service.py`

- [ ] **Step 1: 写失败测试，要求市场总览返回简版研究摘要**

```python
def test_list_market_snapshots_returns_research_brief(self) -> None:
    items = service.list_market_snapshots(("BTCUSDT",))
    brief = items[0]["research_brief"]

    self.assertEqual(brief["research_bias"], "bullish")
    self.assertEqual(brief["recommended_strategy"], "trend_breakout")
    self.assertEqual(brief["confidence"], "high")
```

- [ ] **Step 2: 写失败测试，要求单币图表返回完整版研究摘要**

```python
def test_get_symbol_chart_returns_research_cockpit(self) -> None:
    chart = service.get_symbol_chart("BTCUSDT", interval="1h", limit=50)
    cockpit = chart["research_cockpit"]

    self.assertEqual(cockpit["signal_count"], 1)
    self.assertEqual(cockpit["entry_hint"], "105")
    self.assertEqual(cockpit["stop_hint"], "99")
```

- [ ] **Step 3: 运行目标测试，确认失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_market_service -v
```

Expected:

- FAIL，提示 `research_brief` 或 `research_cockpit` 字段缺失

- [ ] **Step 4: 最小实现市场接口接线**

```python
snapshot.update(
    {
        "research_brief": build_market_research_brief(
            symbol=normalized_symbol,
            recommended_strategy=snapshot["recommended_strategy"],
            evaluation=snapshot["strategy_summary"].get(snapshot["recommended_strategy"], {}),
            research_summary=research_summary,
        )
    }
)

return {
    "items": items,
    "overlays": ...,
    "markers": ...,
    "strategy_context": ...,
    "research_cockpit": build_symbol_research_cockpit(...),
}
```

- [ ] **Step 5: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_market_service -v
```

Expected:

- PASS

- [ ] **Step 6: 提交当前小步**

```bash
git add services/api/app/services/market_service.py services/api/tests/test_market_service.py
git commit -m "Wire research cockpit into market service"
```

## Task 3：把统一研究摘要接到策略工作台

**Files:**
- Modify: `services/api/app/services/strategy_workspace_service.py`
- Modify: `services/api/tests/test_strategy_workspace_service.py`

- [ ] **Step 1: 写失败测试，要求策略卡片返回统一研究摘要**

```python
def test_workspace_cards_include_research_cockpit(self) -> None:
    workspace = service.get_workspace()
    cockpit = workspace["strategies"][0]["research_cockpit"]

    self.assertEqual(cockpit["research_bias"], "bullish")
    self.assertEqual(cockpit["confidence"], "high")
    self.assertEqual(cockpit["research_gate"]["status"], "confirmed_by_research")
```

- [ ] **Step 2: 写失败测试，要求缺研究结果时正确降级**

```python
def test_workspace_research_cockpit_degrades_without_symbol_result(self) -> None:
    workspace = service.get_workspace()
    cockpit = workspace["strategies"][0]["research_cockpit"]

    self.assertEqual(cockpit["research_bias"], "unavailable")
    self.assertEqual(cockpit["research_explanation"], "该币种暂无研究结论")
```

- [ ] **Step 3: 运行目标测试，确认失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_strategy_workspace_service -v
```

Expected:

- FAIL，提示 `research_cockpit` 字段缺失或字段值不符

- [ ] **Step 4: 最小实现策略工作台接线**

```python
card["research_cockpit"] = build_strategy_research_cockpit(
    symbol=primary_symbol,
    recommended_strategy=strategy_key,
    evaluation=current_evaluation,
    research_summary=research_summary,
)
```

- [ ] **Step 5: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest services.api.tests.test_strategy_workspace_service -v
```

Expected:

- PASS

- [ ] **Step 6: 提交当前小步**

```bash
git add services/api/app/services/strategy_workspace_service.py services/api/tests/test_strategy_workspace_service.py
git commit -m "Add research cockpit to strategy workspace"
```

## Task 4：更新前端类型和三个页面

**Files:**
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/market/page.tsx`
- Modify: `apps/web/app/market/[symbol]/page.tsx`
- Modify: `apps/web/app/strategies/page.tsx`
- Modify: `tests/test_market_workspace.py`
- Modify: `tests/test_frontend_refactor.py`

- [ ] **Step 1: 写失败测试，要求市场页和单币页使用统一摘要字段**

```python
def test_market_pages_render_research_cockpit_copy(self) -> None:
    market_content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")
    symbol_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")

    self.assertIn("research_brief", market_content)
    self.assertIn("research_cockpit", symbol_content)
    self.assertIn("研究倾向", market_content)
    self.assertIn("研究门控", symbol_content)
```

- [ ] **Step 2: 写失败测试，要求策略页展示统一字段口径**

```python
def test_strategy_page_shows_research_cockpit_fields(self) -> None:
    content = (WEB_APP / "strategies" / "page.tsx").read_text(encoding="utf-8")

    self.assertIn("research_cockpit", content)
    self.assertIn("研究倾向", content)
    self.assertIn("判断信心", content)
    self.assertIn("研究门控", content)
```

- [ ] **Step 3: 运行目标测试，确认失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace tests.test_frontend_refactor -v
```

Expected:

- FAIL，提示页面还没有使用统一摘要字段

- [ ] **Step 4: 最小实现前端类型和页面渲染**

```ts
export type ResearchCockpitSummary = {
  research_bias: string;
  recommended_strategy: string;
  confidence: string;
  research_gate: Record<string, unknown>;
  primary_reason: string;
  research_explanation: string;
  signal_count?: number;
  entry_hint?: string;
  stop_hint?: string;
  model_version: string;
  generated_at: string;
};
```

```tsx
<p>研究倾向：{formatResearchBias(item.research_brief.research_bias)}</p>
<p>判断信心：{item.research_cockpit.confidence}</p>
<p>研究门控：{String(item.research_cockpit.research_gate.status ?? "n/a")}</p>
```

- [ ] **Step 5: 运行目标测试，确认通过**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace tests.test_frontend_refactor -v
cd /home/djy/Quant/apps/web && pnpm exec tsc --noEmit
cd /home/djy/Quant/apps/web && pnpm build
```

Expected:

- 页面静态测试 PASS
- 类型检查 PASS
- 构建 PASS

- [ ] **Step 6: 提交当前小步**

```bash
git add apps/web/lib/api.ts apps/web/app/market/page.tsx apps/web/app/market/[symbol]/page.tsx apps/web/app/strategies/page.tsx tests/test_market_workspace.py tests/test_frontend_refactor.py
git commit -m "Render research cockpit across pages"
```

## Task 5：Review、真实验证和文档收口

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/api.md`
- Modify: `CONTEXT.md`

- [ ] **Step 1: 跑完整测试**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/api/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/worker/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s tests -v
cd /home/djy/Quant/apps/web && pnpm exec tsc --noEmit
cd /home/djy/Quant/apps/web && pnpm build
```

Expected:

- API 测试通过
- worker 测试通过
- 前端测试通过
- 类型检查通过
- 构建通过

- [ ] **Step 2: 做真实页面验证**

Run:

```bash
curl -s http://127.0.0.1:8000/api/v1/market
curl -s http://127.0.0.1:8000/api/v1/market/BTCUSDT/chart
curl -s http://127.0.0.1:3000/market
curl -s http://127.0.0.1:3000/market/BTCUSDT
curl -s -b /tmp/quant-strategy.cookies http://127.0.0.1:3000/strategies
```

Expected:

- 市场接口返回 `research_brief`
- 单币图表接口返回 `research_cockpit`
- 市场页 HTML 包含“研究倾向”
- 单币页 HTML 包含“研究门控”“止损参考”
- 策略页 HTML 包含统一研究字段口径

- [ ] **Step 3: 做代码 review**

检查点：

- 统一研究字段是否只在后端集中生成
- 页面是否只是消费字段，没有自己重算结论
- 缺研究结果、异常分数、空图表时是否正确降级
- 是否误改软门控阈值或执行链路

- [ ] **Step 4: 更新文档**

补充内容：

- `README.md`：统一研究驾驶舱能回答什么问题
- `docs/architecture.md`：`research_cockpit_service` 的职责和调用关系
- `docs/api.md`：`research_brief` 与 `research_cockpit` 字段说明
- `CONTEXT.md`：当前阶段完成位置、验证结果和下一步

- [ ] **Step 5: 提交收口**

```bash
git add README.md docs/architecture.md docs/api.md CONTEXT.md
git commit -m "Document research cockpit rollout"
```

## 建议执行方式

- 推荐：Subagent-Driven
  - 用 subagent 分任务实现
  - 每个任务结束后做一次 spec 对齐 review 和一次代码质量 review
- 备选：Inline Execution
  - 在当前会话里顺序执行

## 总体验证命令

```bash
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/api/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/worker/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s tests -v
cd /home/djy/Quant/apps/web && pnpm exec tsc --noEmit
cd /home/djy/Quant/apps/web && pnpm build
curl -s http://127.0.0.1:8000/api/v1/market
curl -s http://127.0.0.1:8000/api/v1/market/BTCUSDT/chart
curl -s http://127.0.0.1:3000/market
curl -s http://127.0.0.1:3000/market/BTCUSDT
curl -s -b /tmp/quant-strategy.cookies http://127.0.0.1:3000/strategies
```

预期结果：

- 后端摘要字段完整
- 页面使用统一字段
- 缺失和异常场景正确降级
- 测试、类型检查、构建、真实页面验证全部通过
