const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("strategies and tasks pages hand off next action from arbitration", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;

  await page.goto(`${WEB_BASE_URL}/strategies`, navigation);
  await expect(page.locator("body")).toContainText("当前仲裁动作", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("这一步和评估页顶部的当前仲裁结论保持一致", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("策略页和任务页不再各自猜下一步动作", { timeout: renderTimeout });
  await expect(page.getByRole("link", { name: "去研究页继续训练和推理" })).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/tasks`, navigation);
  await expect(page.locator("body")).toContainText("当前仲裁动作", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("这一步和评估页顶部的当前仲裁结论保持一致", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("策略页和任务页不再各自猜下一步动作", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("任务页需要管理员登录", { timeout: renderTimeout });
  await expect(page.getByRole("main").getByRole("link", { name: "前往登录" })).toBeVisible();
});
