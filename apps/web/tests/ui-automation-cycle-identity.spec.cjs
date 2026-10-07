/* 只读验证自动训练历史的模型等待、候选拦截和参考 RSI 快照。 */
const { test, expect } = require("@playwright/test");
const { WEB_BASE_URL } = require("./test-urls.cjs");

/* 用固定历史验证真实页面组件；所有点击只展开详情或切换参考标签。 */
async function openHistory(page) {
  const base = {
    strategy_family: "automation_ml", status: "waiting", mode: "auto_dry_run",
    next_action: "continue_research", armed_symbol: "", candidates: [],
    task_summary: { train: { status: "succeeded", duration_seconds: 2 } },
  };
  const items = [
    { ...base, recorded_at: "2026-10-08T06:00:00Z", recommended_symbol: "ORDIUSDT",
      display_status: "waiting_model", waiting_reason: "awaiting_model",
      display_message: "等待合格AI模型，当前候选继续研究。",
      failure_reason: "candidate_blocked", message: "模型使用旧评估，需按新协议验证",
      task_summary: { train: { status: "succeeded", duration_seconds: 0, skipped: true,
        message: "距离上次训练不足24小时，本轮复用已有模型。" } },
      rsi_snapshot: { ORDIUSDT: 61.2 } },
    { ...base, recorded_at: "2026-10-08T05:00:00Z", recommended_symbol: "BTCUSDT",
      display_status: "blocked", failure_reason: "candidate_blocked",
      message: "实际风险已达到上限", rsi_snapshot: {} },
    { ...base, recorded_at: "2026-10-08T04:00:00Z", recommended_symbol: "ETHUSDT",
      status: "failed", display_status: "failed", failure_reason: "execution_failed",
      message: "执行器连接失败", rsi_snapshot: {} },
  ];
  await page.route("**/strategies/public/cycle-history?*", route => route.fulfill({
    json: { data: { items, summary: { total: 3, succeeded_count: 0, blocked_count: 1,
      cooldown_count: 0, failed_count: 1, waiting_count: 1 } }, error: null, meta: {} },
  }));
  // 该测试不允许发出任何改变运行状态、参数或交易的请求。
  await page.route("**/api/control/**", route => {
    if (route.request().method() !== "GET") return route.abort();
    return route.fallback();
  });
  await page.goto(WEB_BASE_URL, { waitUntil: "domcontentloaded" });
  await page.getByText("更多详情", { exact: true }).click();
  await expect(page.getByText("自动训练策略周期历史", { exact: true })).toBeVisible();
}

test("模型等待明确属于自动训练策略，展开后保留原始原因和 RSI 指标快照", async ({ page }) => {
  await openHistory(page);
  const record = page.getByTestId("automation-cycle-record").filter({ hasText: "ORDI" });
  await expect(record).toContainText("⏳ 等待模型");
  await expect(record).not.toContainText("🚫");
  await record.getByRole("button", { name: /ORDI/ }).click();
  await expect(record).toContainText("策略: 自动训练策略");
  await expect(record).toContainText("原始原因: 模型使用旧评估，需按新协议验证");
  await expect(record.getByRole("button", { name: "训练任务", exact: true })).toBeVisible();
  await record.getByRole("button", { name: "训练任务", exact: true }).click();
  await expect(record).toContainText("本轮跳过重训");
  await expect(record).toContainText("距离上次训练不足24小时，本轮复用已有模型。");
  await record.getByRole("button", { name: "RSI指标快照", exact: true }).click();
  await expect(record).toContainText("日线 RSI 参考指标");
  await expect(record).toContainText("不是 RSI 自然策略的执行记录");
  await expect(record).toContainText("61.2");
  await expect(record.getByRole("button", { name: "RSI", exact: true })).toHaveCount(0);
});

test("真实候选风险拦截与执行失败保留原状态", async ({ page }) => {
  await openHistory(page);
  const blocked = page.getByTestId("automation-cycle-record").filter({ hasText: "BTC" });
  await expect(blocked).toContainText("🚫 拦阻");
  await expect(blocked).not.toContainText("等待模型");
  await blocked.getByRole("button", { name: /BTC/ }).click();
  await expect(blocked).toContainText("实际风险已达到上限");
  const failed = page.getByTestId("automation-cycle-record").filter({ hasText: "ETH" });
  await expect(failed).toContainText("❌ 失败");
  await expect(failed).not.toContainText("等待模型");
});
