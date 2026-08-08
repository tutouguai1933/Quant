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
  // 用页面实际标题（含后缀），避免与侧边栏"因子知识库"混淆
  await expect(page.getByRole("heading", { name: "训练模型" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "因子研究" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "选币回测" })).toBeVisible();
});
