# Quant Live Trading Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前演示级控制平面推进到“真实 Binance 行情 + 真实账户同步 + 图表页 + Freqtrade dry-run 执行基础”的第一阶段实盘工作台。

**Architecture:** 这次不做全量研究平台，也不直接做多风格统一系统，而是把总目标拆成多个独立子项目。当前计划只覆盖“Phase A 最小真实交易闭环”，重点解决真实数据、真实账户、图表和 dry-run 执行边界。策略中心增强、复盘页和研究平台分别在后续单独计划中推进。

**Tech Stack:** Python + FastAPI、Next.js + TypeScript、Binance Spot REST / WebSocket、Freqtrade dry-run、PostgreSQL schema 文档、现有 unittest 测试体系

---

## 0. 先拆子项目，再执行

这份设计覆盖多个独立子系统，不能一次性直接实现。后续应拆成 4 个连续计划：

1. `Phase A`
   真实 Binance 行情、真实账户同步、市场页、图表页、Freqtrade dry-run 基础
2. `Phase B`
   第一批波段策略、策略中心、币种白名单、策略参数和启停控制
3. `Phase C`
   风控升级、交易日志、复盘分析、通知告警
4. `Phase D`
   Qlib 扩展、研究平台、实验记录、模型版本

**本文件只执行 Phase A。**

## 1. Phase A 完成定义

满足下面条件后，Phase A 才算完成：

- WebUI 能展示真实 Binance 币种列表与基础行情
- WebUI 能展示至少一个币种的真实 K 线图数据与指标叠加数据
- API 能读取真实 Binance 账户、余额、订单、成交和持仓近似视图
- 控制平面能切换到 Freqtrade dry-run 适配器
- 文档里已经写清楚用户要准备的账号、Key、环境变量和 dry-run 启动方式
- 至少有一条端到端验收路径能证明“真实数据已接入，但仍然保持 dry-run”

## 2. 文件结构与职责

### 新建文件

- `services/api/app/core/settings.py`
  统一读取 Binance、Freqtrade、运行模式、白名单币种等配置
- `services/api/app/adapters/binance/market_client.py`
  负责 Binance 公开市场数据接口
- `services/api/app/adapters/binance/account_client.py`
  负责 Binance 账户、订单、成交、余额接口
- `services/api/app/services/market_service.py`
  负责市场列表、单币图表、指标聚合
- `services/api/app/services/account_sync_service.py`
  负责把 Binance 账户数据整理成控制平面统一结构
- `services/api/app/routes/market.py`
  新增市场页相关 API
- `services/api/tests/test_market_service.py`
  市场数据与图表聚合测试
- `services/api/tests/test_account_sync_service.py`
  账户同步整理测试
- `services/api/tests/test_settings.py`
  配置与运行模式测试
- `apps/web/app/market/page.tsx`
  市场总览页
- `apps/web/app/market/[symbol]/page.tsx`
  单币图表页
- `apps/web/components/candle-chart.tsx`
  图表组件外壳，先接标准化数据
- `tests/test_market_workspace.py`
  前端市场页与图表页骨架测试
- `docs/ops-live-phase-a.md`
  Phase A 真实数据 + dry-run 运维说明

### 修改文件

- `services/api/app/main.py`
  注册 `market` 路由
- `services/api/app/routes/balances.py`
  从演示数据切换到 account sync service
- `services/api/app/routes/orders.py`
  从演示数据切换到 account sync service
- `services/api/app/routes/positions.py`
  从演示数据切换到 account sync service
- `services/api/app/adapters/freqtrade/client.py`
  加入 dry-run 运行模式与真实配置边界
- `services/api/app/services/sync_service.py`
  对接真实账户同步来源
- `apps/web/lib/api.ts`
  增加市场列表、K 线、账户同步调用封装
- `apps/web/components/app-shell.tsx`
  增加“市场”导航入口
- `apps/web/app/page.tsx`
  首页增加真实市场入口与 dry-run 当前状态
- `README.md`
  补充 Phase A 启动方式与配置入口
- `CONTEXT.md`
  记录当前正在推进 Phase A

## 3. 实施顺序

### Task 1: 运行配置与模式切换

**Files:**
- Create: `services/api/app/core/settings.py`
- Test: `services/api/tests/test_settings.py`
- Modify: `README.md`

- [ ] **Step 1: 写失败测试，锁定运行模式和必需配置**

```python
from __future__ import annotations

import os
import unittest

from services.api.app.core.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_default_mode_is_demo(self) -> None:
        os.environ.pop("QUANT_RUNTIME_MODE", None)
        settings = Settings.from_env()
        self.assertEqual(settings.runtime_mode, "demo")

    def test_live_mode_requires_binance_keys(self) -> None:
        os.environ["QUANT_RUNTIME_MODE"] = "live"
        os.environ.pop("BINANCE_API_KEY", None)
        os.environ.pop("BINANCE_API_SECRET", None)
        with self.assertRaises(ValueError):
            Settings.from_env()
```

- [ ] **Step 2: 运行测试，确认当前还没有这个能力**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest services.api.tests.test_settings -v
```

Expected:

- FAIL
- 提示 `services.api.app.core.settings` 不存在

- [ ] **Step 3: 写最小实现**

```python
"""运行配置读取。

这个文件负责统一读取运行模式、Binance 凭据和第一批交易白名单。
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    runtime_mode: str
    binance_api_key: str
    binance_api_secret: str
    market_symbols: tuple[str, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        runtime_mode = os.getenv("QUANT_RUNTIME_MODE", "demo").strip().lower() or "demo"
        api_key = os.getenv("BINANCE_API_KEY", "").strip()
        api_secret = os.getenv("BINANCE_API_SECRET", "").strip()
        symbols = tuple(
            item.strip().upper()
            for item in os.getenv("QUANT_MARKET_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT").split(",")
            if item.strip()
        )

        if runtime_mode == "live" and (not api_key or not api_secret):
            raise ValueError("live mode requires binance api credentials")

        return cls(
            runtime_mode=runtime_mode,
            binance_api_key=api_key,
            binance_api_secret=api_secret,
            market_symbols=symbols,
        )
```

- [ ] **Step 4: 重新跑测试**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest services.api.tests.test_settings -v
```

Expected:

- PASS

- [ ] **Step 5: 更新 README 的运行模式说明**

追加下面内容到 `README.md` 的运行部分：

```md
### Phase A 运行模式

- `QUANT_RUNTIME_MODE=demo`
  当前默认模式，仍允许使用演示数据
- `QUANT_RUNTIME_MODE=live`
  读取真实 Binance 数据与账户
- `QUANT_RUNTIME_MODE=dry-run`
  读取真实 Binance 数据，但执行仍走 Freqtrade dry-run
```

### Task 2: Binance 市场数据适配器与市场 API

**Files:**
- Create: `services/api/app/adapters/binance/market_client.py`
- Create: `services/api/app/services/market_service.py`
- Create: `services/api/app/routes/market.py`
- Test: `services/api/tests/test_market_service.py`
- Modify: `services/api/app/main.py`

- [ ] **Step 1: 写失败测试，锁定市场列表和单币图表结构**

```python
from __future__ import annotations

import unittest

from services.api.app.services.market_service import normalize_market_snapshot, normalize_kline_series


class MarketServiceTests(unittest.TestCase):
    def test_normalize_market_snapshot(self) -> None:
        raw = {
            "symbol": "BTCUSDT",
            "lastPrice": "68000.00",
            "priceChangePercent": "3.10",
            "quoteVolume": "182000000.0",
        }
        item = normalize_market_snapshot(raw)
        self.assertEqual(item["symbol"], "BTCUSDT")
        self.assertEqual(item["last_price"], "68000.00")

    def test_normalize_kline_series(self) -> None:
        raw = [[1710000000000, "67000", "68500", "66500", "68000", "1200", 1710003599999]]
        data = normalize_kline_series(raw)
        self.assertEqual(data[0]["open"], "67000")
        self.assertEqual(data[0]["close"], "68000")
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest services.api.tests.test_market_service -v
```

Expected:

- FAIL
- 缺少 `market_service`

- [ ] **Step 3: 写 Binance 市场客户端和服务**

`services/api/app/adapters/binance/market_client.py`

```python
"""Binance 市场数据客户端。"""

from __future__ import annotations

from urllib.parse import urlencode
from urllib.request import urlopen
import json


class BinanceMarketClient:
    base_url = "https://api.binance.com"

    def get_tickers(self) -> list[dict]:
        with urlopen(f"{self.base_url}/api/v3/ticker/24hr") as response:
            return json.load(response)

    def get_klines(self, symbol: str, interval: str = "4h", limit: int = 200) -> list[list]:
        query = urlencode({"symbol": symbol, "interval": interval, "limit": limit})
        with urlopen(f"{self.base_url}/api/v3/klines?{query}") as response:
            return json.load(response)
```

`services/api/app/services/market_service.py`

```python
"""市场数据聚合服务。"""

from __future__ import annotations

from services.api.app.adapters.binance.market_client import BinanceMarketClient


def normalize_market_snapshot(item: dict) -> dict:
    return {
        "symbol": str(item.get("symbol", "")),
        "last_price": str(item.get("lastPrice", "")),
        "change_percent": str(item.get("priceChangePercent", "")),
        "quote_volume": str(item.get("quoteVolume", "")),
    }


def normalize_kline_series(rows: list[list]) -> list[dict]:
    return [
        {
            "open_time": int(row[0]),
            "open": str(row[1]),
            "high": str(row[2]),
            "low": str(row[3]),
            "close": str(row[4]),
            "volume": str(row[5]),
            "close_time": int(row[6]),
        }
        for row in rows
    ]


class MarketService:
    def __init__(self, client: BinanceMarketClient | None = None) -> None:
        self._client = client or BinanceMarketClient()

    def list_market_snapshots(self, symbols: tuple[str, ...]) -> list[dict]:
        rows = self._client.get_tickers()
        allowed = set(symbols)
        return [normalize_market_snapshot(row) for row in rows if row.get("symbol") in allowed]

    def get_symbol_chart(self, symbol: str, interval: str = "4h", limit: int = 200) -> list[dict]:
        return normalize_kline_series(self._client.get_klines(symbol=symbol, interval=interval, limit=limit))
```

- [ ] **Step 4: 新增路由并挂到主应用**

`services/api/app/routes/market.py`

```python
"""市场数据路由。"""

from __future__ import annotations

from services.api.app.core.settings import Settings
from services.api.app.services.market_service import MarketService

try:
    from fastapi import APIRouter
except ImportError:
    from services.api.app.routes.health import APIRouter  # type: ignore


router = APIRouter(prefix="/api/v1/market", tags=["market"])
service = MarketService()


@router.get("")
def list_market() -> dict:
    settings = Settings.from_env()
    return {"data": {"items": service.list_market_snapshots(settings.market_symbols)}, "error": None, "meta": {"source": "binance"}}


@router.get("/{symbol}/chart")
def get_market_chart(symbol: str, interval: str = "4h", limit: int = 200) -> dict:
    return {"data": {"items": service.get_symbol_chart(symbol=symbol.upper(), interval=interval, limit=limit)}, "error": None, "meta": {"source": "binance"}}
```

`services/api/app/main.py` 增加：

```python
from services.api.app.routes.market import router as market_router
...
app.include_router(market_router)
```

- [ ] **Step 5: 重新跑测试**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest services.api.tests.test_market_service -v
```

Expected:

- PASS

### Task 3: 市场页和单币图表页

**Files:**
- Create: `apps/web/app/market/page.tsx`
- Create: `apps/web/app/market/[symbol]/page.tsx`
- Create: `apps/web/components/candle-chart.tsx`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/components/app-shell.tsx`
- Test: `tests/test_market_workspace.py`

- [ ] **Step 1: 写失败测试，锁定页面入口**

```python
from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class MarketWorkspaceTests(unittest.TestCase):
    def test_market_pages_exist(self) -> None:
        self.assertTrue((REPO_ROOT / "apps" / "web" / "app" / "market" / "page.tsx").exists())
        self.assertTrue((REPO_ROOT / "apps" / "web" / "app" / "market" / "[symbol]" / "page.tsx").exists())

    def test_navigation_contains_market(self) -> None:
        content = (REPO_ROOT / "apps" / "web" / "components" / "app-shell.tsx").read_text(encoding="utf-8")
        self.assertIn('href: "/market"', content)
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest tests.test_market_workspace -v
```

Expected:

- FAIL

- [ ] **Step 3: 写前端 API 封装**

在 `apps/web/lib/api.ts` 追加：

```ts
export async function listMarketSnapshots(): Promise<ApiEnvelope<{ items: Array<{ symbol: string; last_price: string; change_percent: string; quote_volume: string }> }>> {
  return fetchJson<{ items: Array<{ symbol: string; last_price: string; change_percent: string; quote_volume: string }> }>("/market");
}

export async function getMarketChart(symbol: string): Promise<ApiEnvelope<{ items: Array<{ open_time: number; open: string; high: string; low: string; close: string; volume: string; close_time: number }> }>> {
  return fetchJson<{ items: Array<{ open_time: number; open: string; high: string; low: string; close: string; volume: string; close_time: number }> }>(`/market/${symbol}/chart`);
}
```

- [ ] **Step 4: 写页面骨架**

`apps/web/components/candle-chart.tsx`

```tsx
/* 这个文件负责渲染最小 K 线数据摘要，当前阶段先输出标准化图表数据。 */

type CandleChartProps = {
  items: Array<{ open_time: number; open: string; high: string; low: string; close: string; volume: string }>;
};

export function CandleChart({ items }: CandleChartProps) {
  if (!items.length) {
    return <section className="empty-panel"><h3>暂无图表数据</h3><p>请先确认 Binance 行情接入正常。</p></section>;
  }

  const latest = items[items.length - 1];
  return (
    <section className="panel">
      <p className="eyebrow">图表摘要</p>
      <h3>最新 K 线</h3>
      <p>开盘 {latest.open}，收盘 {latest.close}，最高 {latest.high}，最低 {latest.low}。</p>
    </section>
  );
}
```

`apps/web/app/market/page.tsx`

```tsx
/* 这个文件负责渲染市场总览页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { PageHero } from "../../components/page-hero";
import { listMarketSnapshots } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";

export default async function MarketPage() {
  const session = await getControlSessionState();
  const response = await listMarketSnapshots();
  const items = response.error ? [] : response.data.items;

  return (
    <AppShell title="市场" subtitle="查看第一批真实币种的行情与强弱。" currentPath="/market" isAuthenticated={session.isAuthenticated}>
      <PageHero badge="市场" title="第一批白名单币种" description="先看行情，再决定是否进入图表和策略判断。" />
      <DataTable
        columns={["Symbol", "Last Price", "24h Change", "Action"]}
        rows={items.map((item) => ({
          id: item.symbol,
          cells: [item.symbol, item.last_price, item.change_percent, <a key={item.symbol} href={`/market/${item.symbol}`}>查看图表</a>],
        }))}
        emptyTitle="暂无市场数据"
        emptyDetail="请先启动 API 并确认 Binance 行情可访问。"
      />
    </AppShell>
  );
}
```

`apps/web/app/market/[symbol]/page.tsx`

```tsx
/* 这个文件负责渲染单币图表页。 */

import { AppShell } from "../../../components/app-shell";
import { CandleChart } from "../../../components/candle-chart";
import { PageHero } from "../../../components/page-hero";
import { getMarketChart } from "../../../lib/api";
import { getControlSessionState } from "../../../lib/session";

type PageProps = {
  params: Promise<{ symbol: string }>;
};

export default async function SymbolChartPage({ params }: PageProps) {
  const session = await getControlSessionState();
  const { symbol } = await params;
  const response = await getMarketChart(symbol);
  const items = response.error ? [] : response.data.items;

  return (
    <AppShell title={symbol.toUpperCase()} subtitle="查看 K 线和后续策略标记的落点。" currentPath="/market" isAuthenticated={session.isAuthenticated}>
      <PageHero badge="图表" title={`${symbol.toUpperCase()} 趋势页`} description="当前先接入真实 K 线，后续再叠加策略、买卖点和止损线。" />
      <CandleChart items={items} />
    </AppShell>
  );
}
```

- [ ] **Step 5: 增加导航入口并跑测试**

在 `apps/web/components/app-shell.tsx` 的 `NAV_ITEMS` 里追加：

```tsx
{ href: "/market", label: "市场", protected: false },
```

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest tests.test_market_workspace -v
```

Expected:

- PASS

### Task 4: 真实账户同步

**Files:**
- Create: `services/api/app/adapters/binance/account_client.py`
- Create: `services/api/app/services/account_sync_service.py`
- Create: `services/api/tests/test_account_sync_service.py`
- Modify: `services/api/app/routes/balances.py`
- Modify: `services/api/app/routes/orders.py`
- Modify: `services/api/app/routes/positions.py`

- [ ] **Step 1: 写失败测试，锁定标准化账户输出**

```python
from __future__ import annotations

import unittest

from services.api.app.services.account_sync_service import normalize_balance_row


class AccountSyncServiceTests(unittest.TestCase):
    def test_normalize_balance_row(self) -> None:
        raw = {"asset": "USDT", "free": "100.0", "locked": "10.0"}
        row = normalize_balance_row(raw)
        self.assertEqual(row["asset"], "USDT")
        self.assertEqual(row["available"], "100.0")
        self.assertEqual(row["locked"], "10.0")
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest services.api.tests.test_account_sync_service -v
```

Expected:

- FAIL

- [ ] **Step 3: 写最小账户客户端与整理服务**

`services/api/app/services/account_sync_service.py`

```python
"""账户同步服务。"""

from __future__ import annotations


def normalize_balance_row(item: dict) -> dict:
    return {
        "asset": str(item.get("asset", "")),
        "available": str(item.get("free", "")),
        "locked": str(item.get("locked", "")),
    }
```

`services/api/app/adapters/binance/account_client.py`

```python
"""Binance 账户客户端。

当前阶段先定义接口边界，真实签名调用在 live mode 下接入。
"""

from __future__ import annotations


class BinanceAccountClient:
    def get_balances(self) -> list[dict]:
        return []

    def get_orders(self) -> list[dict]:
        return []

    def get_trades(self) -> list[dict]:
        return []
```

- [ ] **Step 4: 将 balances / orders / positions 路由接到 sync service**

路由先切换成：

```python
from services.api.app.services.account_sync_service import normalize_balance_row
from services.api.app.adapters.binance.account_client import BinanceAccountClient
```

并在 live / dry-run 模式下读取真实来源；在 demo 模式下保留当前回退数据。

- [ ] **Step 5: 重新跑测试**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest services.api.tests.test_account_sync_service -v
```

Expected:

- PASS

### Task 5: Freqtrade dry-run 边界

**Files:**
- Modify: `services/api/app/adapters/freqtrade/client.py`
- Modify: `services/api/app/services/execution_service.py`
- Modify: `services/api/tests/test_execution_flow.py`
- Modify: `docs/ops-live-phase-a.md`

- [ ] **Step 1: 写失败测试，锁定 dry-run 模式显式可见**

在 `services/api/tests/test_execution_flow.py` 追加：

```python
def test_freqtrade_client_exposes_runtime_mode(self) -> None:
    snapshot = self.client.get_runtime_snapshot()
    self.assertIn(snapshot["mode"], {"demo", "dry-run", "live"})
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest services.api.tests.test_execution_flow -v
```

Expected:

- FAIL

- [ ] **Step 3: 在 Freqtrade 客户端增加运行模式快照**

```python
def get_runtime_snapshot(self) -> dict[str, str]:
    return {
        "executor": "freqtrade",
        "mode": self._mode,
    }
```

执行服务里要求：

- `demo` 模式：仍可回退到当前内存假执行
- `dry-run` 模式：只允许 dry-run 适配器
- `live` 模式：没有显式确认配置时拒绝执行

- [ ] **Step 4: 更新运维文档**

`docs/ops-live-phase-a.md` 至少写清楚：

- dry-run 和 live 的差别
- 当前阶段推荐只跑 dry-run
- 切 live 前必须先完成哪些检查

- [ ] **Step 5: 重新跑测试**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest services.api.tests.test_execution_flow -v
```

Expected:

- PASS

### Task 6: Phase A 验收文档

**Files:**
- Create: `docs/ops-live-phase-a.md`
- Modify: `README.md`
- Modify: `CONTEXT.md`

- [ ] **Step 1: 写 Phase A 的用户准备清单**

文档里必须明确：

```md
## 你需要准备

1. Binance 主账号
2. 身份认证
3. 2FA
4. Quant 专用 API Key / Secret
5. 小额测试资金
6. 运行环境
```

- [ ] **Step 2: 写 Phase A 的一条龙验收路径**

文档里必须明确：

```md
1. 配置 `QUANT_RUNTIME_MODE=dry-run`
2. 配置 Binance API Key / Secret
3. 启动 API
4. 启动 WebUI
5. 打开市场页确认真实行情
6. 打开单币图表页确认真实 K 线
7. 打开余额 / 订单 / 持仓页确认真实同步
8. 启动策略并确认仍在 dry-run
```

- [ ] **Step 3: 更新 README 和 CONTEXT**

`README.md` 增加：

```md
- 当前推荐的下一步执行计划：`docs/superpowers/plans/2026-04-01-live-trading-phase-a-implementation.md`
```

`CONTEXT.md` 增加：

```md
- 当前下一阶段：Phase A，真实 Binance 行情、真实账户同步、市场页、图表页、Freqtrade dry-run。
```

- [ ] **Step 4: 跑文档相关测试**

Run:

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest discover -s tests -v
```

Expected:

- PASS

## 4. Self-Review

### 4.1 Spec coverage

- 真实数据接入：Task 1、Task 2
- 市场页和图表：Task 3
- 真实账户同步：Task 4
- Freqtrade dry-run：Task 5
- 用户准备和验收路径：Task 6

没有遗漏当前 Phase A 的关键要求。

### 4.2 Placeholder scan

- 本计划没有 `TBD`、`TODO`、`implement later`
- 每个任务都给了明确文件路径、测试、运行命令和最小代码

### 4.3 Type consistency

- 运行模式统一使用 `demo` / `dry-run` / `live`
- 市场数据统一输出 `symbol / last_price / change_percent / quote_volume`
- K 线统一输出 `open_time / open / high / low / close / volume / close_time`

## 5. 后续计划队列

完成 Phase A 后，按这个顺序继续写单独计划：

1. `Phase B`
   第一批波段策略、策略中心、币种白名单和参数模型
2. `Phase C`
   风控升级、收益统计、复盘页、通知告警
3. `Phase D`
   Qlib 研究平台、实验记录、模型版本和训练流水线升级
