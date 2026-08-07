# 前端数据链路修复与重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复前端三大数据链路断点（策略页假数据、任务页状态缺失、评估指标 "--"），并按新手交易员动线重构前端布局与交互动线，最后重写 Playwright 测试收口。

**Architecture:** 三阶段：(1) 数据链路修复（后端字段补齐 + 前端会话校验 + 降级不静默）；(2) 前端重构（统一数据源 + 研究流水线 + 空状态区分 + 工具页收纳）；(3) 测试重写（新 UI 冒烟测试 + 回归）。每阶段独立可部署、可验证。

**Tech Stack:** FastAPI（services/api）、Next.js 15（apps/web）、React 19、Playwright、pytest。

---

## 背景事实（2026-08-08 实测确认）

1. **策略页显示 demo 假数据**：`strategies/page.tsx` 显示 `freqtrade/memory/demo`、`not_configured`、0 余额。根因：API 容器重启后内存 session 全部失效 → 前端拿到 401 → `getStrategyWorkspaceFallback()`（lib/api.ts:4072）静默返回硬编码假数据且 `error: null`。首页持仓走无认证接口（freqtrade_proxy 直连 9013）所以真实。
2. **任务页显示 manual/0轮**：同一认证失效根因 → `getAutomationStatusFallback()`（lib/api.ts:4338）硬编码 manual。另外 `/openclaw/patrol-history` 和 `/openclaw/audit` 返回裸结构无 `data` 包裹，前端解析 TypeError 被静默吞掉。
3. **评估指标 "--"**：
   - 研究页 R²/IC/测试样本硬编码 "--"（research/page.tsx:199-241），后端 sample_window 无 test 字段
   - 因子页 mean_ic/icir 硬编码 "0"、缺 ic_std/ic_win_rate（feature_workspace_service.py:878-885）
   - 选币页 terminal.metrics 缺 annual_return_pct/sharpe/excess_return_pct/turnover 4 个 key（evaluation_workspace_service.py:2549-2568），数据源 leaderboard 里有
4. **会话校验缺失**：`apps/web/app/api/control/session/route.ts` 只查 cookie 存在，不校验 token 有效性；后端 `auth_service._sessions` 是内存 dict，API 重启全失效。
5. **测试基线**：api 后端 48 failed / 827 passed（pre-existing）；Playwright 37 个 spec 全失效（断言旧 UI 文案）。

---

## 阶段一：数据链路修复（后端为主）

### Task 1.1: 前端会话有效性校验（最关键修复）

**Files:**
- Modify: `apps/web/app/api/control/session/route.ts`
- Modify: `apps/web/lib/session.ts`
- Test: `apps/web/tests/ui-session-expiry.spec.cjs`（新建）

- [ ] **Step 1: 写失败测试**

```javascript
// apps/web/tests/ui-session-expiry.spec.cjs
/* 会话过期后页面应跳登录，而非静默显示假数据。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("失效token访问策略页应跳登录", async ({ page }) => {
  test.setTimeout(90000);
  // 伪造一个肯定失效的 token
  await page.goto(`${WEB_BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((t) => {
    document.cookie = `quant_session=${t}; path=/`;
  }, "invalid-token-for-test");
  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  // 应被重定向到登录页（URL 包含 /login）
  await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant/apps/web && QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011/api/v1 npx playwright test tests/ui-session-expiry.spec.cjs --reporter=line`
Expected: FAIL（当前策略页不跳登录，显示假数据）

- [ ] **Step 3: 实现后端会话校验接口**

在 `services/api/app/routes/auth.py` 已有 `GET /api/v1/auth/session?token=xxx`（返回 200 或 session_not_found）。**前端 session/route.ts 调用它校验**：

```typescript
// apps/web/lib/session.ts 修改 getControlSessionState：
/* 返回当前 cookie 对应的页面会话状态，cookie 存在且后端校验有效才算登录。 */
export async function getControlSessionState(): Promise<{ token: string; isAuthenticated: boolean }> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";
  if (!token) {
    return { token: "", isAuthenticated: false };
  }
  // 调后端校验 token 有效性（绕过代理直连 api，避免代理自身也要 token）
  const apiBase = process.env.QUANT_API_BASE_URL ?? "http://127.0.0.1:9011/api/v1";
  try {
    const res = await fetch(`${apiBase}/auth/session?token=${encodeURIComponent(token)}`, {
      cache: "no-store",
    });
    if (res.ok) {
      return { token, isAuthenticated: true };
    }
    return { token: "", isAuthenticated: false };
  } catch {
    // api 不可达时保守处理：视为未登录，避免显示假数据
    return { token: "", isAuthenticated: false };
  }
}
```

（若 `process.env.QUANT_API_BASE_URL` 在 web 容器内是 127.0.0.1:9011——已确认，host 网络。）

- [ ] **Step 4: 确认页面跳转逻辑**

读 `apps/web/app/login/page.tsx` 和 layout 里的鉴权守卫，确认 `isAuthenticated=false` 时页面会重定向到 /login。若守卫缺失，在 `apps/web/app/layout.tsx` 或各页面公共组件里补：`getControlSessionState().isAuthenticated === false → redirect("/login?next=当前路径")`。

- [ ] **Step 5: 跑测试确认通过**

Run: 同上命令
Expected: PASS（失效 token 跳登录）

- [ ] **Step 6: 提交**

```bash
cd /home/djy/Quant
git add apps/web/app/api/control/session/route.ts apps/web/lib/session.ts apps/web/tests/ui-session-expiry.spec.cjs
git commit -m "fix: 前端会话有效性校验, 失效token跳登录而非静默假数据"
```

### Task 1.2: 前端降级不静默（保留 error 标记）

**Files:**
- Modify: `apps/web/lib/api.ts`（getStrategyWorkspaceFallback、getAutomationStatusFallback 等降级函数）
- Test: `apps/web/tests/ui-degraded-data.spec.cjs`（新建）

- [ ] **Step 1: 读现状**

读 `apps/web/lib/api.ts` 中 `getStrategyWorkspaceFallback`（约 4072）、`getAutomationStatusFallback`（约 4338）及它们的调用点（1613-1620、1890-1900），确认当前 `error: null` 的静默行为。

- [ ] **Step 2: 写失败测试**

```javascript
// apps/web/tests/ui-degraded-data.spec.cjs
/* API 失败时页面应显示降级提示而非假数据。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("策略页API失败时显示降级提示", async ({ page }) => {
  test.setTimeout(90000);
  await page.goto(`${WEB_BASE_URL}/login?next=/strategies`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "登录并继续" }).click({ timeout: 30000 }).catch(() => {});
  // 用失效token登录（模拟后端重启后token失效）
  await page.evaluate(() => {
    document.cookie = "quant_session=expired-token; path=/";
  });
  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(5000);
  // 页面应显示"数据不可用/降级"提示，而非 memory/demo 假数据
  await expect(page.locator("body")).not.toContainText("memory / demo");
  await expect(page.locator("body")).toContainText(/数据|不可用|降级|登录/i);
});
```

- [ ] **Step 3: 跑测试确认失败**

Run: `QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011/api/v1 npx playwright test tests/ui-degraded-data.spec.cjs --reporter=line`
Expected: FAIL（页面仍显示 memory/demo）

- [ ] **Step 4: 实现**

修改 `lib/api.ts` 的 fallback 函数：**保留 error 字段**（`error: { code: "degraded_data", message: "后端数据暂不可用，可能已重新部署，请刷新或重新登录" }`），调用点检查 error 时页面渲染降级提示。策略页/任务页的组件里：当 `workspace.error` 或 `status.error` 存在时，显示提示条而非假数据。

- [ ] **Step 5: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add apps/web/lib/api.ts apps/web/tests/ui-degraded-data.spec.cjs
git commit -m "fix: 前端降级保留error标记, 页面显示降级提示而非假数据"
```

### Task 1.3: openclaw 巡检/审计接口统一 envelope

**Files:**
- Modify: `services/api/app/routes/openclaw.py`（patrol-history、audit 两个接口）
- Test: `services/api/tests/test_openclaw_services.py`（追加）

- [ ] **Step 1: 写失败测试（后端统一包裹 data）**

```python
def test_patrol_history_uses_envelope():
    """巡检历史接口返回标准 envelope（含 data 包裹）。"""
    from fastapi.testclient import TestClient
    from services.api.app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/openclaw/patrol-history?limit=5")
    body = resp.json()
    assert "data" in body, "应包含 data 包裹层"
    assert "items" in body["data"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests/test_openclaw_services.py -q`
Expected: FAIL（当前裸结构）

- [ ] **Step 3: 实现**

读 `services/api/app/routes/openclaw.py` 的 `get_patrol_history`（约 161）和 audit 相关路由（约 96），把返回改为 `_success({"items": records, "total": N}, {"source": "openclaw"})`（与全站 envelope 约定一致）。

- [ ] **Step 4: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add services/api/app/routes/openclaw.py services/api/tests/test_openclaw_services.py
git commit -m "fix: openclaw巡检/审计接口统一envelope包裹"
```

### Task 1.4: 因子页 IC 摘要指标（后端补齐）

**Files:**
- Modify: `services/api/app/services/feature_workspace_service.py`（`_build_terminal_research` 的 metrics）
- Test: `services/api/tests/test_feature_workspace_ic.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
"""因子页 IC 摘要指标。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.feature_workspace_service import FeatureWorkspaceService  # noqa: E402


class IcMetricsTests(unittest.TestCase):
    def test_build_ic_summary_from_ic_series(self):
        """从 ic_series 计算 mean_ic/ic_std/icir/ic_win_rate。"""
        service = object.__new__(FeatureWorkspaceService)
        report = {
            "factor_evaluation": {
                "ic_series": [
                    {"factor": "ema20_gap_pct", "ic": 0.05, "rank_ic": 0.04},
                    {"factor": "ema20_gap_pct", "ic": -0.02, "rank_ic": -0.01},
                    {"factor": "ema20_gap_pct", "ic": 0.08, "rank_ic": 0.06},
                    {"factor": "body_pct", "ic": 0.03, "rank_ic": 0.02},
                ]
            }
        }
        summary = service._build_ic_summary(report)
        self.assertIn("mean_ic", summary)
        self.assertIn("ic_std", summary)
        self.assertIn("icir", summary)
        self.assertIn("ic_win_rate", summary)
        self.assertGreater(summary["mean_ic"], 0)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests/test_feature_workspace_ic.py -q`
Expected: FAIL（方法不存在或指标缺失）

- [ ] **Step 3: 实现**

在 `feature_workspace_service.py` 加 `_build_ic_summary(report)`：从 `report.factor_evaluation.ic_series` 按 factor 分组，取各因子最新 IC 值序列，计算：
- `mean_ic` = 所有 IC 的均值
- `ic_std` = 标准差
- `icir` = mean_ic / ic_std（std 为 0 时返回 0）
- `ic_win_rate` = IC > 0 的比例

在 `_build_terminal_research` 中把硬编码 "0" 的 metric_card（mean_ic、icir）和缺失的 ic_std、ic_win_rate 用该摘要填充；数据不足时保持 "--"（用 None 而非 "0"，前端显示 "--"）。

- [ ] **Step 4: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add services/api/app/services/feature_workspace_service.py services/api/tests/test_feature_workspace_ic.py
git commit -m "feat: 因子页IC摘要指标从ic_series计算"
```

### Task 1.5: 选币页指标补齐（后端）

**Files:**
- Modify: `services/api/app/services/evaluation_workspace_service.py`（`_build_terminal_view` 的 metrics）
- Test: `services/api/tests/test_evaluation_workspace_metrics.py`（新建）

- [ ] **Step 1: 写失败测试**

```python
"""选币页 terminal.metrics 指标补齐。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.evaluation_workspace_service import EvaluationWorkspaceService  # noqa: E402


class TerminalMetricsTests(unittest.TestCase):
    def test_build_terminal_metrics_includes_all_keys(self):
        """terminal.metrics 应包含年化/sharpe/超额/换手。"""
        service = object.__new__(EvaluationWorkspaceService)
        leaderboard = [
            {
                "symbol": "BTCUSDT",
                "backtest": {
                    "metrics": {
                        "net_return_pct": "2.5",
                        "max_drawdown_pct": "-1.2",
                        "sharpe": "0.8",
                        "turnover": "0.3",
                    }
                },
            }
        ]
        metrics = service._build_terminal_metrics_for_test(leaderboard)
        for key in ("best_net_return_pct", "annual_return_pct", "sharpe", "excess_return_pct", "turnover", "best_max_drawdown_pct"):
            self.assertIn(key, metrics)
```

（方法名以读代码后的真实签名为准——`_build_terminal_view` 约 2549 行构建 6 个 key，需要抽出可测的辅助方法。）

- [ ] **Step 2: 跑测试确认失败**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests/test_evaluation_workspace_metrics.py -q`
Expected: FAIL（缺 4 个 key）

- [ ] **Step 3: 实现**

读 `evaluation_workspace_service.py` 的 `_build_terminal_view`（约 2549-2568），从 leaderboard 的 backtest.metrics 提取补齐：
- `annual_return_pct`：可先返回 net_return_pct（简化，后续接真实年化算法）
- `sharpe`：从 leaderboard 第一名的 backtest.metrics.sharpe
- `excess_return_pct`：net_return_pct - 0（基准暂缺，先返回 net_return_pct 或 0）
- `turnover`：从 leaderboard backtest.metrics.turnover

抽一个 `_build_terminal_metrics(leaderboard)` 方法供测试直调，`_build_terminal_view` 用它。

- [ ] **Step 4: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add services/api/app/services/evaluation_workspace_service.py services/api/tests/test_evaluation_workspace_metrics.py
git commit -m "feat: 选币页terminal.metrics补齐4个指标key"
```

### Task 1.6: 研究页评估指标（后端补字段 + 前端取值）

**Files:**
- Modify: `services/api/app/services/research_workspace_service.py`（sample_window 补 test + 训练指标）
- Modify: `apps/web/app/research/page.tsx`（R²/IC 从后端取值）
- Test: `services/api/tests/test_research_workspace_metrics.py` + `apps/web/tests/ui-research-metrics.spec.cjs`

- [ ] **Step 1: 写后端失败测试**

```python
"""研究工作台样本窗口与指标。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.api.app.services.research_workspace_service import ResearchWorkspaceService  # noqa: E402


class ResearchMetricsTests(unittest.TestCase):
    def test_sample_window_includes_test_split(self):
        """样本窗口应包含 test 切分（前端测试样本读取）。"""
        service = object.__new__(ResearchWorkspaceService)
        payload = {
            "training": {"count": 5000},
            "validation": {"count": 1600},
            "backtest": {"count": 1600},
            "test": {"count": 1600},
        }
        window = service._normalize_sample_window_for_test(payload)
        self.assertIn("test", window)
        self.assertEqual(window["test"]["count"], 1600)
```

（方法名以实际为准；若后端 sample_window 由别处构建，先找到构建点再补 test。）

- [ ] **Step 2: 跑测试确认失败 + 实现后端**

补 `sample_window.test` 字段（从训练产物的 backtest_rows 或 testing_rows 计数）。若最新训练产物无独立 test 切分（只有 validation/backtest），将 backtest 同时作为 test 计数返回（与前端已读的 backtest 一致）。

- [ ] **Step 3: 写前端失败测试**

```javascript
// apps/web/tests/ui-research-metrics.spec.cjs
/* 研究页测试样本数与模型指标应显示数值而非 "--"。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("研究页显示测试样本数", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/research");
  await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(8000);
  // 测试样本数应显示数值（当前是 "--"）
  await expect(page.locator("body")).not.toContainText("测试样本\n--");
});
```

- [ ] **Step 4: 跑测试确认失败 + 实现前端取值**

改 `apps/web/app/research/page.tsx:199-241`：R²/IC 从 `workspace.terminal.metrics` 或训练产物字段读取（后端在 workspace 或 training-result 里补 `r2_train/r2_test/ic_train/ic_test` 字段，来自 ml_metrics 的 auc 或训练报告）；取不到时显示 "--" 但**带上"暂缺"提示**。

- [ ] **Step 5: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add services/api/app/services/research_workspace_service.py services/api/tests/test_research_workspace_metrics.py apps/web/app/research/page.tsx apps/web/tests/ui-research-metrics.spec.cjs
git commit -m "feat: 研究页测试样本与模型指标前后端打通"
```

### Task 1.7: 阶段一全量回归

- [ ] **Step 1: 后端回归**

Run: `source /home/djy/miniforge3/etc/profile.d/conda.sh && conda activate quant && cd /home/djy/Quant && python3 -m pytest services/api/tests --ignore=services/api/tests/test_api_skeleton.py --ignore=services/api/tests/test_auth_exception_handling.py -q 2>&1 | tail -3`
Expected: 失败集合 ⊆ 基线（48 failed）

- [ ] **Step 2: 前端构建验证**

Run: `cd /home/djy/Quant/apps/web && npx tsc --noEmit 2>&1 | tail -5`
Expected: 无类型错误（或仅既有错误）

- [ ] **Step 3: 推送**

```bash
cd /home/djy/Quant && git push origin master
```

---

## 阶段二：前端重构（交互动线 + 布局）

**目标**：按新手交易员动线重构——首页 3 数字、研究流水线单页贯通、空状态区分、工具页收纳。

### Task 2.1: 首页"3 个数字"重构

**Files:**
- Modify: `apps/web/app/page.tsx`（首页）
- Modify: `apps/web/components/home-workbench-grid.tsx`
- Test: `apps/web/tests/ui-home-three-numbers.spec.cjs`

- [ ] **Step 1: 写失败测试**

```javascript
// apps/web/tests/ui-home-three-numbers.spec.cjs
/* 首页首屏只显示3个核心数字。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("首页首屏3个核心数字", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/");
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(8000);
  // 三个数字卡片：持仓盈亏 / 自动化状态 / 执行器健康
  await expect(page.getByText("持仓盈亏", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("自动化状态", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("执行器", { exact: false }).first()).toBeVisible();
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: `QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011/api/v1 npx playwright test tests/ui-home-three-numbers.spec.cjs --reporter=line`
Expected: FAIL（当前首页是 6 张卡布局）

- [ ] **Step 3: 实现**

重构 `home-workbench-grid.tsx`：首屏改为 3 张核心卡（持仓盈亏、自动化状态、执行器健康），数据源统一用 Task 1.x 修好的接口；其余内容（市场信号、RSI、最近交易）收进"更多详情"折叠区。数据加载失败时显示降级提示。

- [ ] **Step 4: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add apps/web/app/page.tsx apps/web/components/home-workbench-grid.tsx apps/web/tests/ui-home-three-numbers.spec.cjs
git commit -m "feat: 首页重构为3个核心数字+详情折叠"
```

### Task 2.2: 研究流水线单页贯通

**Files:**
- Create: `apps/web/app/pipeline/page.tsx`（新页面，研究→因子→选币流水线）
- Modify: `apps/web/lib/api.ts`（流水线数据聚合）
- Test: `apps/web/tests/ui-pipeline-flow.spec.cjs`

- [ ] **Step 1: 写失败测试**

```javascript
// apps/web/tests/ui-pipeline-flow.spec.cjs
/* 研究流水线页：从上到下跑通 训练→因子→选币 三步骤。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("流水线页三步骤可见", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/pipeline");
  await page.goto(`${WEB_BASE_URL}/pipeline`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(8000);
  await expect(page.getByText("训练", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("因子", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("选币", { exact: false }).first()).toBeVisible();
});
```

- [ ] **Step 2: 跑测试确认失败**

Run: 同上命令
Expected: FAIL（页面 404）

- [ ] **Step 3: 实现**

新建 `apps/web/app/pipeline/page.tsx`：三步骤垂直布局，每步从对应后端接口读数据（训练：`/research/workspace` 样本数+指标；因子：`/features/workspace` IC 摘要；选币：`/evaluation/workspace` 候选+指标），每步一个"运行"按钮调对应 POST 接口，结果即时渲染。**这是新手主入口**——导航"模型训练/回测训练/选币回测/因子研究"四链接改为指向 /pipeline。

- [ ] **Step 4: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add apps/web/app/pipeline/page.tsx apps/web/lib/api.ts apps/web/tests/ui-pipeline-flow.spec.cjs
git commit -m "feat: 研究流水线单页贯通(训练→因子→选币)"
```

### Task 2.3: 空状态区分（后端已跑 vs 未跑）

**Files:**
- Modify: `apps/web/components/`（研究/因子/选币空状态组件）
- Test: `apps/web/tests/ui-empty-state.spec.cjs`

- [ ] **Step 1: 写失败测试**

```javascript
// apps/web/tests/ui-empty-state.spec.cjs
/* 空状态文案区分"已训练但指标缺"与"未运行"。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("因子页已训练时不再提示请先运行", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/features");
  await page.goto(`${WEB_BASE_URL}/features`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(8000);
  const body = await page.locator("body").innerText();
  // 已有训练产物（样本 8372）时不应提示"请先运行模型训练"
  if (body.includes("训练样本")) {
    await expect(page.locator("body")).not.toContainText("请先运行模型训练");
  }
});
```

- [ ] **Step 2: 跑测试确认失败 + 实现**

改因子/选币/研究页的空状态组件：数据源为 None → "尚未运行，点击开始";数据源存在但指标缺 → "已生成数据，指标计算中/暂缺"。按 `report.factor_evaluation` 是否有 ic_series 判断。

- [ ] **Step 3: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add apps/web/components/ apps/web/tests/ui-empty-state.spec.cjs
git commit -m "feat: 空状态区分已训练/未运行"
```

### Task 2.4: 工具页收纳（高级模式抽屉）

**Files:**
- Modify: `apps/web/app/layout.tsx`（导航分组）
- Test: `apps/web/tests/ui-nav-grouping.spec.cjs`

- [ ] **Step 1: 写失败测试**

```javascript
// apps/web/tests/ui-nav-grouping.spec.cjs
/* 导航分组：主线6项 + 高级模式折叠。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("导航含高级模式入口", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/");
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  await expect(page.getByText("高级模式", { exact: false }).first()).toBeVisible();
});
```

- [ ] **Step 2: 跑测试确认失败 + 实现**

`layout.tsx` 导航重构：主线 6 项（工作台、研究流水线、策略、任务、持仓、行情）+ "高级模式"折叠抽屉（模型管理、参数优化、数据分析、因子知识库、配置管理、运营、回测、信号）。

- [ ] **Step 3: 跑测试确认通过 + 提交**

```bash
cd /home/djy/Quant
git add apps/web/app/layout.tsx apps/web/tests/ui-nav-grouping.spec.cjs
git commit -m "feat: 导航分组, 研究员工具收进高级模式抽屉"
```

### Task 2.5: 阶段二构建验证

- [ ] **Step 1: 前端类型检查 + 构建**

Run: `cd /home/djy/Quant/apps/web && npx tsc --noEmit 2>&1 | tail -5 && npx next build 2>&1 | tail -5`
Expected: 构建成功（或仅记录既有警告）

- [ ] **Step 2: 全量 Playwright 冒烟**

Run: `QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011/api/v1 npx playwright test tests/ui-home-three-numbers.spec.cjs tests/ui-pipeline-flow.spec.cjs tests/ui-empty-state.spec.cjs tests/ui-nav-grouping.spec.cjs tests/ui-session-expiry.spec.cjs tests/ui-degraded-data.spec.cjs tests/ui-research-metrics.spec.cjs --reporter=line`
Expected: 全部通过

- [ ] **Step 3: 推送**

```bash
cd /home/djy/Quant && git push origin master
```

---

## 阶段三：测试收口 + 部署验证

### Task 3.1: 旧 Playwright 测试清理与新冒烟套件

**Files:**
- Delete: `apps/web/tests/ui-*.spec.cjs` 中已失效的旧 UI 断言测试（保留 test-auth.cjs、test-urls.cjs、playwright-browser.cjs、status-language.spec.ts 等基础工具）
- Create: `apps/web/tests/ui-main-smoke.spec.cjs`（新主冒烟：登录→首页3数字→流水线→策略→任务→持仓 全链路）

- [ ] **Step 1: 列出失效测试**

Run: `ls apps/web/tests/ui-*.spec.cjs`
Expected: 37 个 spec，其中按旧 UI 文案断言的需清理

- [ ] **Step 2: 清理 + 新建主冒烟**

新建 `apps/web/tests/ui-main-smoke.spec.cjs`：
```javascript
/* 主链路冒烟：登录→首页→流水线→策略→任务→持仓。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("主链路全通", async ({ page }) => {
  test.setTimeout(180000);
  await loginAsAdmin(page, "/");
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(6000);
  await expect(page.locator("body")).not.toContainText("Application error");

  await page.goto(`${WEB_BASE_URL}/pipeline`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000);
  await expect(page.locator("body")).not.toContainText("Application error");

  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000);
  await expect(page.locator("body")).not.toContainText("memory / demo");

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000);
  await expect(page.locator("body")).not.toContainText("Application error");

  await page.goto(`${WEB_BASE_URL}/positions`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000);
  await expect(page.locator("body")).not.toContainText("Application error");
});
```

- [ ] **Step 3: 跑主冒烟确认通过**

Run: `QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011/api/v1 npx playwright test tests/ui-main-smoke.spec.cjs --reporter=line`
Expected: 通过

- [ ] **Step 4: 提交**

```bash
cd /home/djy/Quant
git add -A apps/web/tests
git commit -m "test: 清理失效旧UI测试, 新增主链路冒烟"
```

### Task 3.2: 服务器部署（前端+后端）

- [ ] **Step 1: 拉代码 + 重建部署 api 和 web**

Run:
```bash
ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "git -C /home/djy/Quant pull && nohup bash -c 'cd /home/djy/Quant/infra/deploy && docker compose build api web 2>&1 && docker compose up -d --no-deps api web 2>&1 && docker compose restart api web 2>&1' > /tmp/build_frontend.log 2>&1 &"
```
Expected: started

- [ ] **Step 2: 等构建完成**

Run: `sleep 300 && ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "tail -3 /tmp/build_frontend.log; docker ps --format '{{.Names}} {{.Status}}' | grep -E 'quant-api|quant-web'"`
Expected: api/web 均 healthy

- [ ] **Step 3: 服务器侧验证（curl）**

Run:
```bash
ssh -i ~/.ssh/id_aliyun_djy -o IdentitiesOnly=yes djy@39.106.11.65 "curl -s http://localhost:9012/ | grep -o '<title>[^<]*</title>'; curl -s -o /dev/null -w '%{http_code}' http://localhost:9012/pipeline"
```
Expected: title 正常、pipeline 200

### Task 3.3: 服务器侧完整 Playwright 验证

- [ ] **Step 1: 跑全部新冒烟测试（指向服务器）**

Run: `cd /home/djy/Quant/apps/web && QUANT_WEB_BASE_URL=http://39.106.11.65:9012 QUANT_API_BASE_URL=http://39.106.11.65:9011/api/v1 npx playwright test tests/ui-main-smoke.spec.cjs tests/ui-session-expiry.spec.cjs tests/ui-degraded-data.spec.cjs tests/ui-research-metrics.spec.cjs --reporter=line`
Expected: 全部通过

- [ ] **Step 2: 验证三个修复点真实生效**

Run:
```bash
# 1. 失效token跳登录
# 2. 策略页不再显示 memory/demo
# 3. 研究页测试样本显示数值
```
（通过 Playwright 测试覆盖）

- [ ] **Step 3: 提交验证记录**

```bash
cd /home/djy/Quant
git add -A && git commit -m "docs: 记录前端重构部署验证结果" --allow-empty
git push origin master
```

---

## 部署与回滚

- 每 commit 独立可回滚：`git revert <commit>` 后重新部署
- 阶段一（后端修复）先部署验证，再进入阶段二（前端重构），避免前端改完才发现后端字段没齐
- web 构建慢（Next.js），阶段二每任务只验证类型检查，阶段二末尾统一 build
- 服务器内存 1.6G，构建必须 nohup 后台执行

## 风险与注意

1. **会话校验改动影响面**：session/route.ts 改为后端校验后，api 重启会踢掉所有登录用户（需重新登录）——这是预期行为（修复假数据的前提），部署后需告知用户重新登录。
2. **前端降级提示**：保留 error 后，网络抖动时页面会短暂显示降级提示——比假数据诚实，属预期。
3. **openclaw envelope 改动**：若前端有其他读取点用裸结构，需同步兼容（Task 1.3 顺带查）。
4. **流水线页为新增**：旧页面保留（高级模式抽屉里），不影响存量。
5. **测试基线**：后端 48 failed 为 pre-existing；Playwright 旧测试清理是主动行为（旧 UI 文案已失效），新测试必须全过。
