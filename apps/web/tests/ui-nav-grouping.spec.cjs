/* 导航分组：主线6项 + 高级模式折叠。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("导航含高级模式折叠入口", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/");
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  // 高级模式折叠入口存在
  await expect(page.getByText("研究员工具", { exact: false }).first()).toBeVisible();
});

test("高级模式默认折叠, 点击展开工具项", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/");
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  // 默认折叠：参数优化/配置管理 等工具项不可见
  await expect(page.getByText("参数优化", { exact: true })).not.toBeVisible();
  // 点击展开后可见
  await page.getByText("研究员工具", { exact: false }).first().click();
  await expect(page.getByText("参数优化", { exact: true })).toBeVisible({ timeout: 5000 });
  await expect(page.getByText("配置管理", { exact: true })).toBeVisible();
});
