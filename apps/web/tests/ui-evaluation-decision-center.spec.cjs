const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("evaluation page separates current arbitration from historical evidence", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "commit", timeout: 90000 });

  await expect(page.locator("body")).toContainText("当前仲裁结论", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("这一块才回答现在该先做什么", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("历史判断只做参考", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("现在该去哪一页", { timeout: 60000 });
});
