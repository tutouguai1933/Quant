const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("main research to execution flow stays usable across core workbenches", async ({ page }) => {
  test.setTimeout(60000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await loginAsAdmin(page, "/signals");

  await expect(page.getByRole("heading", { name: "信号" })).toBeVisible();
  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expect(page.locator("body")).toContainText("Qlib 信号流水线已进入后台", { timeout: 20000 });
  await expect(page.locator("body")).toContainText("研究运行状态");

  await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText("策略研究工作台");
  await expect(page.locator("body")).toContainText("研究准备状态");
  await expect(page.locator("body")).toContainText("研究模板");
  await expect(page.locator("body")).toContainText("标签定义");
  await expect(page.locator("body")).toContainText("模型目录");
  await expect(page.locator("body")).toContainText("训练切分说明");
  await expect(page.locator("body")).toContainText("标签目标与止损说明");
  await expect(page.locator("body")).toContainText("模型和标签怎么影响结果");

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText("评估与实验中心");
  await expect(page.locator("body")).toContainText("最近两轮对比");
  await expect(page.locator("body")).toContainText("配置差异拆解");

  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText("先看判断，再决定要不要派发");
  await expect(page.locator("body")).toContainText("当前推荐执行候选");

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText("先确认自动化模式，再决定要不要触发下一轮工作流。");
  await expect(page.locator("body")).toContainText("最近工作流来源：手动信号流水线", { timeout: 15000 });
  await expect(page.locator("body")).toContainText("长期运行与人工接管策略");

  await page.goto(`${WEB_BASE_URL}/balances`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText("真实账户余额");

  await page.goto(`${WEB_BASE_URL}/orders`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText("同步来源");

  await page.goto(`${WEB_BASE_URL}/positions`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText("同步来源");

  await page.goto(`${WEB_BASE_URL}/market/BTCUSDT`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toContainText("本地主图");

  expect(errors).toEqual([]);
});
