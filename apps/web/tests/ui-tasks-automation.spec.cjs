const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("tasks page shows latest automation decision after login", async ({ page }) => {
  test.setTimeout(90000);
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
  await expect(page.locator("body")).toContainText("任务", { timeout: 60000 });
  await expect(page.locator("body")).not.toContainText("正在切换工作区", { timeout: 60000 });

  await expect(page.getByText("本轮自动化判断")).toBeVisible();
  await expect(page.getByText("推荐策略实例")).toBeVisible();
  await expect(page.getByText("派发结果")).toBeVisible();
  await expect(page.getByText("失败原因")).toBeVisible();
  await expect(page.getByText("告警强度", { exact: true })).toBeVisible();
  await expect(page.getByText("人工接管原因", { exact: true })).toBeVisible();
  await expect(page.getByText("恢复前先做什么", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("风险等级摘要", { exact: true })).toBeVisible();
  await expect(page.getByText("恢复清单", { exact: true })).toBeVisible();
  await expect(page.getByText("头号告警", { exact: true })).toBeVisible();
  await expect(page.locator("body")).toContainText("最近发生了什么", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("你现在该做什么", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("系统在等什么", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("为什么现在还不能恢复", { timeout: 60000 });
  await expect
    .poll(async () => (await page.locator("body").textContent()) ?? "", { timeout: 60000 })
    .toMatch(/还不能恢复，因为恢复清单还有|当前还有风险或异常需要先人工处理/);
  await expect(page.getByText("最早恢复时间", { exact: true })).toBeVisible();
  await expect(page.getByText("接管复核截止", { exact: true })).toBeVisible();
  await expect(page.getByText("自动化运行参数", { exact: true })).toBeVisible();
  await expect(page.getByText("长时间接管阈值", { exact: true })).toBeVisible();
  await expect(page.getByText("活跃告警窗口", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/接管原因：/, { exact: false }).first()).toBeVisible();

  expect(errors).toEqual([]);
});
