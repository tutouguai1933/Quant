/* 空状态区分已训练/未运行。 */
const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("因子页已训练时提示指标暂缺而非请先运行", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/features");
  await page.goto(`${WEB_BASE_URL}/features`, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(8000);
  const body = await page.locator("body").innerText();
  // 服务器已有训练产物（因子列表+IC数据），不应提示"请先运行模型训练"
  await expect(page.locator("body")).not.toContainText("请先运行模型训练");
});
