/* 首页首屏3个核心数字。 */
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
  // 三个核心数字卡
  await expect(page.getByText("持仓盈亏", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("自动化状态", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("执行器健康", { exact: false }).first()).toBeVisible();
});
