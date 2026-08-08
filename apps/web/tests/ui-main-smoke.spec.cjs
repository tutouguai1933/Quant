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
  // 等数据请求完成（真实数据替换 fallback）：执行器应显示真实状态而非 memory/demo
  await expect(page.locator("body")).not.toContainText("memory / demo", { timeout: 30000 });
  await expect(page.locator("body")).not.toContainText("Application error");

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000);
  await expect(page.locator("body")).not.toContainText("Application error");

  await page.goto(`${WEB_BASE_URL}/positions`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000);
  await expect(page.locator("body")).not.toContainText("Application error");
});
