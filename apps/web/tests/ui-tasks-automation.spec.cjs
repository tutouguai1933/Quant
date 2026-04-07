const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("tasks page shows latest automation decision after login", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await loginAsAdmin(page, "/tasks");
  await page.waitForFunction(() => document.body.innerText.includes("任务") && !document.body.innerText.includes("正在切换工作区"));

  await expect(page.getByText("本轮自动化判断")).toBeVisible();
  await expect(page.getByText("推荐策略实例")).toBeVisible();
  await expect(page.getByText("派发结果")).toBeVisible();
  await expect(page.getByText("失败原因")).toBeVisible();
  await expect(page.getByText("告警强度")).toBeVisible();
  await expect(page.getByText("人工接管原因")).toBeVisible();
  await expect(page.getByText("恢复前先做什么", { exact: true })).toBeVisible();
  await expect(page.getByText("风险等级摘要", { exact: true })).toBeVisible();
  await expect(page.getByText("恢复清单", { exact: true })).toBeVisible();
  await expect(page.getByText(/接管原因：/, { exact: false }).first()).toBeVisible();

  expect(errors).toEqual([]);
});
