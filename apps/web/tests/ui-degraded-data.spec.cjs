/* API 失败时页面应显示降级提示而非假数据。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

// 登录辅助：统一使用可靠登录流程（clearCookies + 等表单 + 校验cookie）
const { loginAsAdmin } = require("./test-auth.cjs");

test("策略页API失败时显示降级提示条", async ({ page }) => {
  test.setTimeout(120000);
  // 先正常登录拿有效 cookie
  await loginAsAdmin(page, "/strategies");
  // 拦截数据接口返回 503，模拟后端不可达
  await page.route("**/api/control/strategies/workspace**", (route) =>
    route.fulfill({
      status: 503,
      body: JSON.stringify({ data: null, error: { code: "proxy_unavailable", message: "客户端代理暂时不可用。" }, meta: {} }),
      contentType: "application/json",
    }),
  );
  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(5000);
  // 应显示降级提示条（页面实际文案为"策略工作区：后端数据暂不可用…"）
  await expect(page.getByText("数据暂不可用", { exact: false }).first()).toBeVisible({ timeout: 15000 });
  // 数据区仍渲染兜底内容，而不是整页报错
  await expect(page.getByText("执行器连接")).toBeVisible({ timeout: 15000 });
  await expect(page.locator("body")).not.toContainText("Application error");
});

test("任务页API失败时显示降级提示条", async ({ page }) => {
  test.setTimeout(120000);
  // 先正常登录拿有效 cookie
  await loginAsAdmin(page, "/tasks");
  // 拦截自动化状态接口返回 503，模拟后端不可达
  await page.route("**/api/control/tasks/automation**", (route) =>
    route.fulfill({
      status: 503,
      body: JSON.stringify({ data: null, error: { code: "proxy_unavailable", message: "客户端代理暂时不可用。" }, meta: {} }),
      contentType: "application/json",
    }),
  );
  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(5000);
  // 应显示降级提示条（页面实际文案为"后端数据暂不可用…"）
  await expect(page.getByText("数据暂不可用", { exact: false }).first()).toBeVisible({ timeout: 15000 });
  // 数据区仍渲染兜底内容（恢复建议兜底文案），而不是整页报错
  await expect(page.getByText("当前可以继续自动化").first()).toBeVisible({ timeout: 15000 });
  await expect(page.locator("body")).not.toContainText("Application error");
});
