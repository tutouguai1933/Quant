const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("main research to execution flow stays usable across core workbenches", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;
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

  await expect(page.locator("body")).toContainText("信号", { timeout: renderTimeout });
  await expect(page.locator("body")).not.toContainText("正在切换工作区", { timeout: renderTimeout });
  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expect(page.locator("body")).toContainText("Qlib 信号流水线已进入后台", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("研究运行状态", { timeout: renderTimeout });

  await page.goto(`${WEB_BASE_URL}/research`, navigation);
  await expect(page.locator("body")).toContainText("策略研究工作台", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("研究准备状态");
  await expect(page.locator("body")).toContainText("研究模板");
  await expect(page.locator("body")).toContainText("标签定义");
  await expect(page.locator("body")).toContainText("模型目录");
  await expect(page.locator("body")).toContainText("训练切分说明");
  await expect(page.locator("body")).toContainText("标签目标与止损说明");
  await expect(page.locator("body")).toContainText("模型和标签怎么影响结果");

  await page.goto(`${WEB_BASE_URL}/evaluation`, navigation);
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("最近两轮对比");
  await expect(page.locator("body")).toContainText("配置差异拆解");

  await page.goto(`${WEB_BASE_URL}/strategies`, navigation);
  await expect(page.locator("body")).toContainText("先看判断，再决定要不要派发", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("为什么现在先推进这个币");

  await page.goto(`${WEB_BASE_URL}/tasks`, navigation);
  await expect(page.locator("body")).toContainText("先确认自动化模式，再决定要不要触发下一轮工作流。", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("本轮自动化判断");
  await expect(page.locator("body")).toContainText("统一调度入口");
  await expect(page.locator("body")).toContainText("长期运行与人工接管");

  await page.goto(`${WEB_BASE_URL}/balances`, navigation);
  await expect(page.locator("body")).toContainText("真实账户余额", { timeout: renderTimeout });

  await page.goto(`${WEB_BASE_URL}/orders`, navigation);
  await expect(page.locator("body")).toContainText("同步来源", { timeout: renderTimeout });

  await page.goto(`${WEB_BASE_URL}/positions`, navigation);
  await expect(page.locator("body")).toContainText("同步来源", { timeout: renderTimeout });

  await page.goto(`${WEB_BASE_URL}/market/BTCUSDT`, navigation);
  await expect(page.locator("body")).toContainText("本地主图", { timeout: renderTimeout });

  expect(errors).toEqual([]);
});
