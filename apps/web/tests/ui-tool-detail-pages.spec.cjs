const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("home, strategies, and tasks expose stable detail-page jump drawers", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.getByRole("heading", { name: "首页主动作区" })).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name: "查看详情页跳转" }).click();
  const homeDrawer = page.getByRole("dialog", { name: "查看详情页跳转" });
  await expect(homeDrawer.getByRole("link", { name: "查看市场详情" })).toBeVisible();
  await expect(homeDrawer.getByRole("link", { name: "查看余额详情" })).toBeVisible();
  await expect(homeDrawer.getByRole("link", { name: "查看订单详情" })).toBeVisible();
  await expect(homeDrawer.getByRole("link", { name: "查看持仓详情" })).toBeVisible();
  await expect(homeDrawer.getByRole("link", { name: "查看风险详情" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  await loginAsAdmin(page, "/strategies");
  await expect(page.getByRole("heading", { name: "策略主动作区" })).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name: "查看工具详情" }).click();
  const strategiesDrawer = page.getByRole("dialog", { name: "查看工具详情" });
  await expect(strategiesDrawer.getByRole("link", { name: "查看市场详情" })).toBeVisible();
  await expect(strategiesDrawer.getByRole("link", { name: "查看余额详情" })).toBeVisible();
  await expect(strategiesDrawer.getByRole("link", { name: "查看订单详情" })).toBeVisible();
  await expect(strategiesDrawer.getByRole("link", { name: "查看持仓详情" })).toBeVisible();
  await expect(strategiesDrawer.getByRole("link", { name: "查看风险详情" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.getByRole("heading", { name: "任务主动作区" })).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name: "查看详情页跳转" }).click();
  const tasksDrawer = page.getByRole("dialog", { name: "查看详情页跳转" });
  await expect(tasksDrawer.getByRole("link", { name: "查看市场详情" })).toBeVisible();
  await expect(tasksDrawer.getByRole("link", { name: "查看余额详情" })).toBeVisible();
  await expect(tasksDrawer.getByRole("link", { name: "查看订单详情" })).toBeVisible();
  await expect(tasksDrawer.getByRole("link", { name: "查看持仓详情" })).toBeVisible();
  await expect(tasksDrawer.getByRole("link", { name: "查看风险详情" })).toBeVisible();
});

test("tool pages present themselves as detail views with clear return links", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/market");

  for (const path of ["/market", "/balances", "/orders", "/positions", "/risk"]) {
    await page.goto(`${WEB_BASE_URL}${path}`, { waitUntil: "commit", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "工具详情定位" })).toBeVisible({ timeout: 60000 });
    await expect(page.getByRole("heading", { name: "这页只负责查明细" })).toBeVisible();
    await expect(page.getByRole("link", { name: "回到主工作台" })).toBeVisible();
    await expect(page.getByRole("link", { name: "回到执行工作台" })).toBeVisible();
    await expect(page.getByRole("link", { name: "回到运维工作台" })).toBeVisible();
  }
});
