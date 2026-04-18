const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("dashboard status badges use the shared human status vocabulary", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("评估") && !document.body.innerText.includes("正在切换工作区"));

  const decisionBoard = page.getByRole("button", { name: "查看门控详情" }).locator("xpath=ancestor::div[contains(@class,'rounded-2xl')]").first();

  await expect(
    decisionBoard.locator('[aria-label^="正常："], [aria-label^="运行中："], [aria-label^="阻塞："], [aria-label^="需人工处理："]'),
  ).toHaveCount(3);
  await expect(page.locator("body")).not.toContainText("login required");
});

test("evaluation config status card uses the shared human status vocabulary", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("评估") && !document.body.innerText.includes("正在切换工作区"));
  await page.getByRole("button", { name: "查看评估配置" }).click();

  const statusCard = page.getByRole("heading", { name: "评估 配置状态" }).locator("xpath=ancestor::div[contains(@class,'rounded-2xl')]").first();

  await expect(
    statusCard.locator('[aria-label^="正常："], [aria-label^="运行中："], [aria-label^="阻塞："], [aria-label^="需人工处理："]'),
  ).toHaveCount(1);
});
