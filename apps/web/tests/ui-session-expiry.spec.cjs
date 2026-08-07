/* 会话过期后页面应跳登录，而非静默显示假数据。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("失效token访问策略页应跳登录", async ({ page }) => {
  test.setTimeout(90000);
  await page.goto(`${WEB_BASE_URL}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate((t) => {
    document.cookie = `quant_admin_token=${t}; path=/`;
  }, "invalid-token-for-test");
  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(3000);
  // 应被重定向到登录页（URL 包含 /login）
  await expect(page).toHaveURL(/\/login/, { timeout: 15000 });
});
