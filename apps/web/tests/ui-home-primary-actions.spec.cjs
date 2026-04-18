const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("home page routes dashboard actions through one primary action section", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "commit", timeout: 90000 });

  await expect(page.getByRole("heading", { name: "首页主动作区" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("button", { name: "运行研究动作" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看执行入口" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看异常入口" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看详情页跳转" })).toBeVisible();
  await expect(page.getByText("驾驶舱", { exact: true })).toBeVisible();
  await expect(page.getByText("推荐下一步", { exact: true })).toBeVisible();
  await expect(page.getByText("成功链路", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("异常链路", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "运行 Qlib 信号流水线" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "启动策略" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "制造失败任务" })).toHaveCount(0);

  await page.getByRole("button", { name: "运行研究动作" }).click();
  const researchDrawer = page.getByRole("dialog", { name: "运行研究动作" });
  await expect(researchDrawer.getByRole("button", { name: "运行 Qlib 信号流水线" })).toBeVisible();
  await expect(researchDrawer.getByRole("button", { name: "运行演示信号流水线" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(researchDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看执行入口" }).click();
  const executionDrawer = page.getByRole("dialog", { name: "查看执行入口" });
  await expect(executionDrawer.getByRole("button", { name: "启动策略" })).toBeVisible();
  await expect(executionDrawer.getByRole("button", { name: "派发最新信号" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(executionDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看异常入口" }).click();
  const exceptionDrawer = page.getByRole("dialog", { name: "查看异常入口" });
  await expect(exceptionDrawer.getByRole("button", { name: "制造失败任务" })).toBeVisible();
  await expect(exceptionDrawer.getByRole("link", { name: "查看风险事件" })).toBeVisible();
  await expect(exceptionDrawer.getByRole("link", { name: "查看风险事件" })).toHaveAttribute("href", "/login?next=%2Frisk");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(exceptionDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看详情页跳转" }).click();
  const routeDrawer = page.getByRole("dialog", { name: "查看详情页跳转" });
  await expect(routeDrawer.getByRole("link", { name: "查看统一研究报告" })).toBeVisible();
  await expect(routeDrawer.getByRole("link", { name: "查看市场详情" })).toBeVisible();
  await expect(routeDrawer.getByRole("link", { name: "查看余额详情" })).toBeVisible();
  await expect(routeDrawer.getByRole("link", { name: "查看订单详情" })).toBeVisible();
  await expect(routeDrawer.getByRole("link", { name: "查看持仓详情" })).toBeVisible();
  await expect(routeDrawer.getByRole("link", { name: "查看风险详情" })).toHaveAttribute("href", "/login?next=%2Frisk");
  await expect(routeDrawer.getByRole("link", { name: "去任务页看自动化" })).toHaveAttribute("href", "/login?next=%2Ftasks");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(routeDrawer).toHaveCount(0);
});
