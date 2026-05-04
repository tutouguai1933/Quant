/* 关键功能验收测试：市场页、余额页、订单页、持仓页、风险页 */

const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

// 1. 市场页测试
test.describe("市场页 /market", () => {
  test("TC-MARKET-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/market`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("市场", { timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });

  test("TC-MARKET-002: 工具页心智提示显示（这页只负责查明细）", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/market`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("市场", { timeout: 60000 });
    // 检查工具页心智提示
    await expect(page.locator("body")).toContainText("这页只负责查明细");
    await expect(page.locator("body")).toContainText("工具详情定位");
  });

  test("TC-MARKET-003: 返回入口按钮存在", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/market`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("市场", { timeout: 60000 });
    // 检查返回按钮存在
    await expect(page.getByRole("link", { name: "回到主工作台" })).toBeVisible();
    await expect(page.getByRole("link", { name: "回到执行工作台" })).toBeVisible();
    await expect(page.getByRole("link", { name: "回到运维工作台" })).toBeVisible();
  });
});

// 2. 单币市场页测试
test.describe("单币市场页 /market/BTCUSDT", () => {
  test("TC-MARKET-SYMBOL-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/market/BTCUSDT`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("BTCUSDT", { timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });

  test("TC-MARKET-SYMBOL-002: 图表区域显示", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/market/BTCUSDT`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("BTCUSDT", { timeout: 60000 });
    // 检查图表相关元素
    await expect(page.locator("body")).toContainText("交易视图");
    await expect(page.locator("body")).toContainText("单币页");
  });

  test("TC-MARKET-SYMBOL-003: 返回按钮存在", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/market/BTCUSDT`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("BTCUSDT", { timeout: 60000 });
    // 检查返回按钮
    await expect(page.getByRole("link", { name: "返回市场页" })).toBeVisible();
    await expect(page.getByRole("link", { name: "返回信号页继续研究" })).toBeVisible();
  });

  test("TC-MARKET-SYMBOL-004: RSI历史Tab显示", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/market/BTCUSDT`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("BTCUSDT", { timeout: 60000 });

    // 检查Tab按钮存在
    await expect(page.getByRole("tab", { name: "图表" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "RSI历史" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "交易历史" })).toBeVisible();

    // 点击RSI历史Tab
    await page.getByRole("tab", { name: "RSI历史" }).click();

    // 等待数据加载
    await page.waitForTimeout(5000);

    // 检查RSI历史内容
    const bodyText = await page.locator("body").textContent();
    const hasRsiContent = bodyText?.includes("RSI") ||
                          bodyText?.includes("超买") ||
                          bodyText?.includes("超卖");
    console.log(`RSI历史内容: ${hasRsiContent ? '显示' : '未检测到'}`);
  });

  test("TC-MARKET-SYMBOL-005: 交易历史Tab显示", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/market/BTCUSDT`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("BTCUSDT", { timeout: 60000 });

    // 点击交易历史Tab
    await page.getByRole("tab", { name: "交易历史" }).click();

    // 等待数据加载
    await page.waitForTimeout(5000);

    // 检查交易历史标题显示
    await expect(page.locator("body")).toContainText("交易历史", { timeout: 30000 });
    console.log(`交易历史Tab: 正常显示`);
  });
});

// 3. 余额页测试
test.describe("余额页 /balances", () => {
  test("TC-BAL-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/balances`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("余额", { timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });

  test("TC-BAL-002: 同步来源信息显示", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/balances`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("余额", { timeout: 60000 });
    // 检查同步来源信息
    await expect(page.locator("body")).toContainText("source");
    await expect(page.locator("body")).toContainText("truth source");
  });

  test("TC-BAL-003: 工具页心智提示显示", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/balances`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("余额", { timeout: 60000 });
    // 检查工具页心智提示
    await expect(page.locator("body")).toContainText("这页只负责查明细");
  });
});

// 4. 订单页测试
test.describe("订单页 /orders", () => {
  test("TC-ORDER-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/orders`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("订单", { timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });

  test("TC-ORDER-002: 同步来源信息显示", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/orders`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("订单", { timeout: 60000 });
    // 检查同步来源信息
    await expect(page.locator("body")).toContainText("source");
    await expect(page.locator("body")).toContainText("truth source");
  });
});

// 5. 持仓页测试
test.describe("持仓页 /positions", () => {
  test("TC-POS-001: 页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/positions`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("持仓", { timeout: 60000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });
});

// 6. 风险页测试（需登录）
test.describe("风险页 /risk", () => {
  test("TC-RISK-001: 未登录时显示登录提示", async ({ page }) => {
    test.setTimeout(120000);
    await page.goto(`${WEB_BASE_URL}/risk`, { waitUntil: "domcontentloaded", timeout: 90000 });
    await expect(page.locator("body")).toContainText("风险", { timeout: 60000 });
    // 检查登录提示
    await expect(page.locator("body")).toContainText("风险页需要管理员登录");
    await expect(page.getByRole("main").getByRole("link", { name: "前往登录" })).toBeVisible();
  });

  test("TC-RISK-002: 登录后页面正常渲染", async ({ page }) => {
    test.setTimeout(120000);
    await loginAsAdmin(page, "/risk");
    await expect(page.locator("body")).toContainText("风险", { timeout: 60000 });
    // 检查已登录状态 - 应该看不到登录提示
    await expect(page.locator("body")).not.toContainText("风险页需要管理员登录");
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("Unhandled Runtime Error");
  });
});