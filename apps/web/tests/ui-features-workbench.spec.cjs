const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("features page defaults to factor summary instead of expanded tables and forms", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/features");
  await page.goto(`${WEB_BASE_URL}/features`, { waitUntil: "domcontentloaded", timeout: 90000 });

  await expect(page.getByRole("heading", { name: "因子主动作区" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("button", { name: "查看因子配置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看因子说明" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究承接" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看因子详情" })).toBeVisible();

  await expect(page.getByRole("heading", { name: "当前因子摘要" })).toBeVisible();
  await expect(page.getByText("因子挖掘", { exact: true })).toBeVisible();
  await expect(page.getByText("因子验证", { exact: true })).toBeVisible();
  await expect(page.getByText("去冗余", { exact: true })).toBeVisible();
  await expect(page.getByText("候选篮子", { exact: true })).toBeVisible();
  await expect(page.getByText("执行篮子", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "因子分类总览" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前启用因子" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "因子有效性摘要" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "因子冗余摘要" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "总分解释入口" })).toBeVisible();

  await expect(page.getByRole("dialog", { name: "因子配置详情" })).toHaveCount(0);
  await expect(page.getByRole("dialog", { name: "因子详情抽屉" })).toHaveCount(0);

  await page.getByRole("button", { name: "查看因子配置" }).click();
  const configDrawer = page.getByRole("dialog", { name: "因子配置详情" });
  await expect(configDrawer).toContainText("因子预设");
  await expect(configDrawer).toContainText("因子组合配置");
  await expect(configDrawer).toContainText("类别权重配置");
  await expect(configDrawer).not.toContainText("当前还没有因子预设");
  const presetOptionCount = await configDrawer.locator('select[name="feature_preset_key"] option').count();
  expect(presetOptionCount).toBeGreaterThan(1);
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(configDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看因子详情" }).click();
  const factorDrawer = page.getByRole("dialog", { name: "因子详情抽屉" });
  await expect(factorDrawer).toContainText("因子说明");
  await expect(factorDrawer).toContainText("时间序列");
  await expect(factorDrawer).toContainText("IC");
  await expect(factorDrawer).toContainText("分组收益");
  await expect(factorDrawer).toContainText("稳定性");
  await expect(factorDrawer).toContainText("相关性");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(factorDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看总分解释" }).click();
  const scoreDrawer = page.getByRole("dialog", { name: "总分解释详情" });
  await expect(scoreDrawer).toContainText("总分解释");
  await expect(scoreDrawer).toContainText("当前最影响总分的类别");
  await expect(scoreDrawer).toContainText("候选篮子");
  await expect(scoreDrawer).toContainText("执行篮子");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(scoreDrawer).toHaveCount(0);
});
