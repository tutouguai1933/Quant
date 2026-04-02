# Qlib 专业 K 线终端、登录保持与市场页提速 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把单币页升级成接近 Binance 的专业交易主战场，同时完成 7 天登录保持、修掉登录卡住感，并把市场页改成更快的骨架加载体验。

**Architecture:** 保留现有 `market` 与 `market/{symbol}/chart` API 契约，前端把静态 SVG 主图替换成专业金融图表库驱动的客户端图表组件；页面壳子继续保留当前控制面结构，但市场页取数、单币页切周期和登录体验改成更偏客户端的快路径。会话分成“页面可见性”与“动作保护”两层，动作继续严格走服务端校验。

**Tech Stack:** Next.js 15 App Router、React 19、TypeScript、客户端图表库（通过前端集成方式接入）、Python `unittest`、现有 FastAPI 控制面。

---

## 预期变更结构

### 前端页面与组件

- Modify: `apps/web/app/market/page.tsx`
  - 改成壳子页，主要承载市场页 hero 和客户端表格入口
- Modify: `apps/web/app/market/[symbol]/page.tsx`
  - 改成提供初始数据给客户端交易工作区，不再让切周期走整页刷新
- Modify: `apps/web/app/login/page.tsx`
  - 调整登录文案与状态展示，配合 7 天保持和更快跳转
- Modify: `apps/web/app/login/submit/route.ts`
  - 写入 7 天 cookie，优化登录成功后的跳转链路
- Modify: `apps/web/lib/session.ts`
  - 把页面可见性和动作保护拆开，减少每页都做同步会话校验
- Modify: `apps/web/lib/api.ts`
  - 增加市场页客户端取数和单币页客户端图表取数需要的轻量工具
- Create: `apps/web/components/pro-chart-script.tsx`
  - 负责装载专业图表库脚本和可用状态
- Create: `apps/web/components/pro-kline-chart.tsx`
  - 负责真实 K 线、坐标、十字光标、拖拽、缩放、成交量、副图和研究标记
- Create: `apps/web/components/market-symbol-workspace.tsx`
  - 客户端单币工作区，负责周期切换、图表区更新和侧卡联动
- Create: `apps/web/components/market-snapshot-workspace.tsx`
  - 客户端市场页工作区，负责骨架、缓存和表格刷新
- Modify: `apps/web/components/timeframe-tabs.tsx`
  - 改成适配图左右的紧凑周期轨
- Modify: `apps/web/components/trading-chart-panel.tsx`
  - 收缩成兼容层或被新主图替代，避免双主图并存
- Modify: `apps/web/components/research-sidecard.tsx`
  - 改成适配右侧固定判断卡
- Modify: `apps/web/components/multi-timeframe-summary.tsx`
  - 改成更贴近交易终端的横向摘要条
- Modify: `apps/web/app/globals.css`
  - 补专业交易主区、骨架加载、周期轨和侧卡样式

### 测试

- Modify: `tests/test_market_workspace.py`
  - 补单币页主图、客户端切周期、市场页骨架与缓存断言
- Modify: `tests/test_frontend_refactor.py`
  - 补登录保持、登录提交链路和页面会话快路径断言
- Create: `tests/test_login_and_market_performance.py`
  - 专门覆盖 7 天 cookie、登录跳转和市场页客户端加载结构

### 文档

- Modify: `CONTEXT.md`
  - 每个阶段同步当前进度
- Modify: `README.md`
  - 在功能简介和测试方式里补“专业 K 线终端 / 7 天会话保持 / 市场页骨架加载”
- Modify: `docs/architecture.md`
  - 补新图表组件和客户端工作区职责
- Modify: `docs/api.md`
  - 说明前端仍复用现有 API 契约，但加载方式变了

---

### Task 1: 建立图表与会话改造的失败测试

**Files:**
- Modify: `tests/test_market_workspace.py`
- Modify: `tests/test_frontend_refactor.py`
- Create: `tests/test_login_and_market_performance.py`

- [ ] **Step 1: 先写单币页图表能力的失败测试**

```python
def test_symbol_page_uses_client_trading_workspace_and_not_static_svg_main_chart(self) -> None:
    page_content = (WEB_APP / "market" / "[symbol]" / "page.tsx").read_text(encoding="utf-8")
    chart_content = (WEB_COMPONENTS / "pro-kline-chart.tsx").read_text(encoding="utf-8")

    self.assertIn("MarketSymbolWorkspace", page_content)
    self.assertIn("use client", chart_content)
    self.assertIn("crosshair", chart_content)
    self.assertIn("priceScale", chart_content)
    self.assertIn("timeScale", chart_content)
    self.assertIn("histogram", chart_content)
    self.assertNotIn("<svg", chart_content)
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace.MarketWorkspaceTests.test_symbol_page_uses_client_trading_workspace_and_not_static_svg_main_chart -v
```

Expected:

- FAIL，提示缺少 `MarketSymbolWorkspace` 或 `pro-kline-chart.tsx`

- [ ] **Step 3: 写登录保持和市场页加载的失败测试**

```python
def test_login_submit_sets_long_lived_cookie(self) -> None:
    content = (WEB_APP / "login" / "submit" / "route.ts").read_text(encoding="utf-8")
    self.assertIn("maxAge", content)
    self.assertIn("60 * 60 * 24 * 7", content)

def test_market_page_switches_to_client_loading_shell(self) -> None:
    content = (WEB_APP / "market" / "page.tsx").read_text(encoding="utf-8")
    self.assertIn("MarketSnapshotWorkspace", content)
    self.assertNotIn("listMarketSnapshots()", content)
```

- [ ] **Step 4: 运行登录和市场页测试并确认失败**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_frontend_refactor tests.test_login_and_market_performance -v
```

Expected:

- FAIL，提示缺少长期 cookie、缺少客户端市场工作区或仍在服务端直接拉市场数据

- [ ] **Step 5: 提交测试基线**

```bash
git add tests/test_market_workspace.py tests/test_frontend_refactor.py tests/test_login_and_market_performance.py
git commit -m "Add failing tests for chart workspace and session persistence"
```

---

### Task 2: 接入专业图表主图并完成单币页客户端工作区

**Files:**
- Create: `apps/web/components/pro-chart-script.tsx`
- Create: `apps/web/components/pro-kline-chart.tsx`
- Create: `apps/web/components/market-symbol-workspace.tsx`
- Modify: `apps/web/app/market/[symbol]/page.tsx`
- Modify: `apps/web/components/timeframe-tabs.tsx`
- Modify: `apps/web/components/research-sidecard.tsx`
- Modify: `apps/web/components/multi-timeframe-summary.tsx`
- Modify: `apps/web/app/globals.css`
- Test: `tests/test_market_workspace.py`

- [ ] **Step 1: 写客户端图表脚本装载器**

```tsx
"use client";

import Script from "next/script";

export function ProChartScript() {
  return (
    <Script
      id="lightweight-charts-runtime"
      src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"
      strategy="afterInteractive"
    />
  );
}
```

- [ ] **Step 2: 写最小可用的专业 K 线图组件**

```tsx
"use client";

import { useEffect, useRef } from "react";

export function ProKlineChart({ items, markers, interval }: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const runtime = (window as Window & { LightweightCharts?: ChartRuntime }).LightweightCharts;
    if (!runtime || !hostRef.current) {
      return;
    }

    const chart = runtime.createChart(hostRef.current, {
      crosshair: { mode: 0 },
      rightPriceScale: { visible: true },
      timeScale: { timeVisible: true, secondsVisible: interval === "1m" },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });

    const candleSeries = chart.addCandlestickSeries();
    const volumeSeries = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
    candleSeries.setData(toCandles(items));
    volumeSeries.setData(toVolumes(items));
    applyResearchLayers(chart, candleSeries, markers);

    return () => chart.remove();
  }, [items, markers, interval]);

  return <div ref={hostRef} className="pro-kline-chart" />;
}
```

- [ ] **Step 3: 写单币页客户端工作区，切周期只刷新图表区**

```tsx
"use client";

import { useEffect, useState, useTransition } from "react";

export function MarketSymbolWorkspace({ symbol, initialData }: Props) {
  const [chartData, setChartData] = useState(initialData);
  const [activeInterval, setActiveInterval] = useState(initialData.active_interval);
  const [isPending, startTransition] = useTransition();

  function switchInterval(nextInterval: string) {
    startTransition(async () => {
      const response = await getMarketChart(symbol, nextInterval);
      if (!response.error) {
        setChartData(response.data);
        setActiveInterval(response.data.active_interval);
      }
    });
  }

  return (
    <section className="market-symbol-workspace">
      <TimeframeTabs
        symbol={symbol}
        activeInterval={activeInterval}
        supportedIntervals={chartData.supported_intervals}
        onSelect={switchInterval}
        pending={isPending}
      />
      <ProKlineChart items={chartData.items} markers={chartData.markers} interval={activeInterval} />
    </section>
  );
}
```

- [ ] **Step 4: 把单币页改成服务端给初始数据，客户端接管切换**

```tsx
<MarketSymbolWorkspace
  symbol={normalizedSymbol}
  initialData={chartData}
/>
```

- [ ] **Step 5: 运行单币页相关测试**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace -v
```

Expected:

- PASS，新增图表能力测试通过，原有市场/单币页测试继续通过

- [ ] **Step 6: 提交单币页图表主区**

```bash
git add apps/web/app/market/[symbol]/page.tsx apps/web/components/pro-chart-script.tsx apps/web/components/pro-kline-chart.tsx apps/web/components/market-symbol-workspace.tsx apps/web/components/timeframe-tabs.tsx apps/web/components/research-sidecard.tsx apps/web/components/multi-timeframe-summary.tsx apps/web/app/globals.css tests/test_market_workspace.py
git commit -m "Build Binance-style client chart workspace"
```

---

### Task 3: 完成 7 天登录保持并修掉登录卡住感

**Files:**
- Modify: `apps/web/app/login/submit/route.ts`
- Modify: `apps/web/lib/session.ts`
- Modify: `apps/web/app/login/page.tsx`
- Modify: `apps/web/components/app-shell.tsx`
- Modify: `tests/test_frontend_refactor.py`
- Modify: `tests/test_login_and_market_performance.py`

- [ ] **Step 1: 先让登录 cookie 变成长效**

```ts
cookieStore.set(SESSION_COOKIE_NAME, response.data.item.token, {
  httpOnly: true,
  sameSite: "lax",
  path: "/",
  maxAge: 60 * 60 * 24 * 7,
});
```

- [ ] **Step 2: 把页面会话读取改成快路径**

```ts
export async function getControlSessionState(): Promise<{ token: string; isAuthenticated: boolean }> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";
  return { token, isAuthenticated: token.length > 0 };
}
```

- [ ] **Step 3: 登录页和壳子改成不重复阻塞会话校验**

```tsx
<MetricGrid
  items={[
    { label: "会话方式", value: "7 天保持", detail: "登录后默认保持 7 天，只有失效或退出才重登" },
  ]}
/>
```

- [ ] **Step 4: 运行登录相关测试**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_frontend_refactor tests.test_login_and_market_performance -v
```

Expected:

- PASS，登录保持和页面会话快路径相关断言通过

- [ ] **Step 5: 提交登录与会话修复**

```bash
git add apps/web/app/login/submit/route.ts apps/web/lib/session.ts apps/web/app/login/page.tsx apps/web/components/app-shell.tsx tests/test_frontend_refactor.py tests/test_login_and_market_performance.py
git commit -m "Persist control session for seven days"
```

---

### Task 4: 把市场页改成客户端骨架加载和短缓存

**Files:**
- Modify: `apps/web/app/market/page.tsx`
- Create: `apps/web/components/market-snapshot-workspace.tsx`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/components/market-focus-board.tsx`
- Modify: `apps/web/app/globals.css`
- Test: `tests/test_market_workspace.py`
- Test: `tests/test_login_and_market_performance.py`

- [ ] **Step 1: 写市场页客户端工作区**

```tsx
"use client";

import { useEffect, useState } from "react";

let memoryCache: { updatedAt: number; items: MarketSnapshot[] } | null = null;

export function MarketSnapshotWorkspace() {
  const [items, setItems] = useState<MarketSnapshot[]>(memoryCache?.items ?? []);
  const [loading, setLoading] = useState(items.length === 0);

  useEffect(() => {
    if (memoryCache && Date.now() - memoryCache.updatedAt < 30_000) {
      return;
    }
    void listMarketSnapshots().then((response) => {
      if (!response.error) {
        memoryCache = { updatedAt: Date.now(), items: response.data.items };
        setItems(response.data.items);
      }
      setLoading(false);
    });
  }, []);

  return loading ? <MarketTableSkeleton /> : <RealMarketTable items={items} />;
}
```

- [ ] **Step 2: 市场页只保留壳子和客户端工作区入口**

```tsx
<PageHero
  badge="市场"
  title="市场筛选入口"
  description="先秒开骨架，再补表格数据，尽快进入单币页。"
/>
<MarketSnapshotWorkspace />
```

- [ ] **Step 3: 运行市场页测试**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest tests.test_market_workspace tests.test_login_and_market_performance -v
```

Expected:

- PASS，市场页客户端工作区、骨架和缓存断言通过

- [ ] **Step 4: 提交市场页性能改造**

```bash
git add apps/web/app/market/page.tsx apps/web/components/market-snapshot-workspace.tsx apps/web/lib/api.ts apps/web/components/market-focus-board.tsx apps/web/app/globals.css tests/test_market_workspace.py tests/test_login_and_market_performance.py
git commit -m "Speed up market page with client snapshot workspace"
```

---

### Task 5: 统一验证、真实页面检查和文档更新

**Files:**
- Modify: `CONTEXT.md`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/api.md`

- [ ] **Step 1: 运行后端与前端全量验证**

Run:

```bash
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/api/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/worker/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s tests -v
pnpm --dir apps/web build
pnpm --dir apps/web exec tsc --noEmit
```

Expected:

- 全部 PASS

- [ ] **Step 2: 做真实页面验证**

Run:

```bash
curl -s http://127.0.0.1:3000/market | rg "市场筛选入口|骨架|多周期状态"
curl -s "http://127.0.0.1:3000/market/BTCUSDT?interval=1d" | rg "交易主区|研究侧卡|多周期摘要"
curl -s -X POST -H 'Content-Type: application/json' -d '{"username":"admin","password":"1933"}' http://127.0.0.1:8000/api/v1/auth/login
```

Expected:

- 市场页先能看到骨架和客户端工作区结构
- 单币页能看到新的专业图表主区结构
- 登录成功后刷新受保护页仍保持登录态

- [ ] **Step 3: 更新文档**

```md
- README：补“专业 K 线终端 / 7 天会话保持 / 市场页骨架加载”
- architecture：补新客户端工作区和图表组件职责
- api：说明前端加载方式变化但契约保持稳定
- CONTEXT：记录当前已经完成到哪一步
```

- [ ] **Step 4: 提交文档与验证收口**

```bash
git add CONTEXT.md README.md docs/architecture.md docs/api.md
git commit -m "Document chart terminal and fast session flow"
```

---

## 计划自检

- Spec coverage:
  - 专业图表能力：Task 2
  - 7 天登录保持与不卡住：Task 3
  - 市场页先出骨架再补数据：Task 4
  - review / 测试 / 文档 / git 提交：Task 5
- Placeholder scan:
  - 未保留 `TODO/TBD`
  - 每个任务都给出了文件、命令和提交点
- Type consistency:
  - 统一使用 `MarketSymbolWorkspace`、`MarketSnapshotWorkspace`、`ProKlineChart` 这三个名称
  - 统一沿用现有 `MarketChartData`、`MarketSnapshot` 和 `ResearchCockpitSummary`
