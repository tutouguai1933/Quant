/* 真实页面验证策略区分、准入提示及自动刷新；只读取状态，不触发交易或训练。 */
const { test, expect } = require("@playwright/test");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test("真实页面包含独立 AI 状态与准入节点，脚本及状态接口正常", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const received = page.waitForResponse(response => response.url().includes("/signals/research/direction-short-status") && response.request().method() === "GET");
  await loginAsAdmin(page, "/tasks");
  const response = await received;
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  const item = body.item || body.data;
  expect(item.market.short_trigger).toBe(false);
  expect(item.market.execution_guard.passed).toBe(false);
  await expect(page.getByText("AI 方向策略（自动化）", { exact: true })).toBeVisible();
  await expect(page.getByTestId("direction-model-admission")).toBeVisible();
  const html = await page.request.get(`${WEB_BASE_URL}/tasks`);
  expect(html.ok()).toBeTruthy();
  expect(await html.text()).toContain('data-testid="direction-model-admission"');
  expect(errors).toEqual([]);
});

test("自动刷新会更新页面准入状态，恢复真实数据后仍保持阻断提示", async ({ page }) => {
  const initial = page.waitForResponse(response => response.url().includes("/signals/research/direction-short-status") && response.request().method() === "GET");
  await loginAsAdmin(page, "/tasks");
  const response = await initial;
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  await expect(page.getByTestId("direction-model-admission")).toBeVisible();
  await page.clock.install();
  const item = body.item || body.data;
  item.market.execution_guard = { passed: true, reasons: [] };
  item.market.prediction_semantics = "downside_probability";
  // 使用刚读取的真实返回验证状态变化，避免虚拟时钟同时触发额外网络等待。
  await page.route("**/signals/research/direction-short-status*", route => route.fulfill({ status: 200, json: body }));
  const updated = page.waitForResponse(response => response.url().includes("/signals/research/direction-short-status"));
  await page.clock.runFor(61000);
  await updated;
  await expect(page.getByTestId("direction-model-admission")).toBeHidden();
  await page.unroute("**/signals/research/direction-short-status*");
  await page.reload();
  await expect(page.getByTestId("direction-model-admission")).toBeVisible();
});
