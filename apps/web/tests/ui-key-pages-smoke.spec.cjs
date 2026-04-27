const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

// 1. 因子页测试
test.describe("因子页 /features", () => {
  test("TC-FEATURE-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/features");
    await page.goto(`${WEB_BASE_URL}/features`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "因子主动作区" })).toBeVisible({ timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });

  test("TC-FEATURE-002: 因子预设选择器存在", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/features");
    await page.goto(`${WEB_BASE_URL}/features`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "因子主动作区" })).toBeVisible({ timeout: 60000 });
    await page.getByRole("button", { name: "查看因子配置" }).click();
    const configDrawer = page.getByRole("dialog", { name: "因子配置详情" });
    await expect(configDrawer).toBeVisible({ timeout: 30000 });
    await expect(configDrawer).toContainText("因子预设");
    const presetSelect = configDrawer.locator('select[name="feature_preset_key"]');
    await expect(presetSelect).toBeVisible();
    const presetOptionCount = await presetSelect.locator("option").count();
    expect(presetOptionCount).toBeGreaterThan(0);
    await page.getByRole("button", { name: "关闭详情抽屉" }).click();
    await expect(configDrawer).toHaveCount(0);
  });

  test("TC-FEATURE-003: 因子分类总览显示", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/features");
    await page.goto(`${WEB_BASE_URL}/features`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "因子分类总览" })).toBeVisible({ timeout: 60000 });
    // 查看分类详情按钮存在
    await expect(page.getByRole("button", { name: "查看分类详情" })).toBeVisible();
    // 点击展开查看更多内容
    await page.getByRole("button", { name: "查看分类详情" }).click();
    const drawer = page.getByRole("dialog", { name: "因子分类详情" });
    await expect(drawer).toContainText("因子分类清单");
  });

  test("TC-FEATURE-004: 当前启用因子显示", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/features");
    await page.goto(`${WEB_BASE_URL}/features`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "当前启用因子" })).toBeVisible({ timeout: 60000 });
    // 查看启用详情按钮存在
    await expect(page.getByRole("button", { name: "查看启用详情" })).toBeVisible();
    // 点击展开查看内容
    await page.getByRole("button", { name: "查看启用详情" }).click();
    const drawer = page.getByRole("dialog", { name: "当前启用详情" });
    await expect(drawer).toContainText("主判断因子");
    await expect(drawer).toContainText("辅助确认因子");
  });
});

// 2. 研究页测试
test.describe("研究页 /research", () => {
  test("TC-RESEARCH-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/research");
    await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "研究主动作区" })).toBeVisible({ timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });

  test("TC-RESEARCH-002: 研究预设选择器存在", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/research");
    await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "研究主动作区" })).toBeVisible({ timeout: 60000 });
    await page.getByRole("button", { name: "查看完整配置" }).click();
    const configDrawer = page.getByRole("dialog", { name: "研究配置详情" });
    await expect(configDrawer).toBeVisible({ timeout: 30000 });
    await expect(configDrawer).toContainText("研究预设");
    const presetSelect = configDrawer.locator('select[name="research_preset_key"]');
    await expect(presetSelect).toBeVisible();
    const presetOptionCount = await presetSelect.locator("option").count();
    expect(presetOptionCount).toBeGreaterThan(0);
    await page.getByRole("button", { name: "关闭详情抽屉" }).click();
    await expect(configDrawer).toHaveCount(0);
  });

  test("TC-RESEARCH-003: 研究配置卡片显示", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/research");
    await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "当前研究摘要" })).toBeVisible({ timeout: 60000 });
    await expect(page.getByRole("heading", { name: "当前状态" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "当前配置摘要" })).toBeVisible();
  });
});

// 3. 数据页测试
test.describe("数据页 /data", () => {
  test("TC-DATA-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/data");
    await page.goto(`${WEB_BASE_URL}/data`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "数据快照" })).toBeVisible({ timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });

  test("TC-DATA-002: 数据快照卡片显示", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/data");
    await page.goto(`${WEB_BASE_URL}/data`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "数据快照" })).toBeVisible({ timeout: 60000 });
    // 确认数据快照卡片包含关键信息
    const snapshotCard = page.getByRole("heading", { name: "数据快照" }).locator("..").locator("..");
    await expect(snapshotCard.getByText("快照来源", { exact: true })).toBeVisible();
    await expect(snapshotCard.getByText("快照生成时间", { exact: true })).toBeVisible();
    await expect(snapshotCard.getByText("快照 ID", { exact: true })).toBeVisible();
  });

  test("TC-DATA-003: 候选篮子预设选择器存在", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/data");
    await page.goto(`${WEB_BASE_URL}/data`, { waitUntil: "domcontentloaded", timeout: 90000 });
    // 确认数据范围配置卡片存在
    await expect(page.getByRole("heading", { name: "数据范围配置", exact: true })).toBeVisible({ timeout: 60000 });
    // 使用精确选择器查找 eyebrow 样式的候选篮子预设标签
    const presetLabel = page.locator("p.eyebrow").filter({ hasText: "候选篮子预设" });
    await expect(presetLabel.first()).toBeVisible({ timeout: 60000 });
    // 确认选择器存在
    const presetSelect = page.locator('select[name="candidate_pool_preset_key"]');
    await expect(presetSelect).toBeVisible();
    const presetOptionCount = await presetSelect.locator("option").count();
    expect(presetOptionCount).toBeGreaterThan(0);
  });
});

// 4. 回测页测试
test.describe("回测页 /backtest", () => {
  test("TC-BACKTEST-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/backtest");
    await page.goto(`${WEB_BASE_URL}/backtest`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "回测预设", exact: true })).toBeVisible({ timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });

  test("TC-BACKTEST-002: 回测配置卡片显示", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/backtest");
    await page.goto(`${WEB_BASE_URL}/backtest`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.getByRole("heading", { name: "回测预设", exact: true })).toBeVisible({ timeout: 60000 });
    // 验证成本模型卡片存在
    await expect(page.getByRole("heading", { name: "成本模型", exact: true })).toBeVisible();
    // 在成本模型卡片内查找精确的 eyebrow 标签
    const costCardSection = page.getByRole("heading", { name: "成本模型", exact: true }).locator("..").locator("..");
    // 使用精确匹配查找 eyebrow 标签
    await expect(costCardSection.locator("p.eyebrow").filter({ hasText: "手续费" }).first()).toBeVisible();
    await expect(costCardSection.locator("p.eyebrow").filter({ hasText: "滑点" }).first()).toBeVisible();
    await expect(costCardSection.locator("p.eyebrow").filter({ hasText: "成本模型" }).first()).toBeVisible();
  });
});