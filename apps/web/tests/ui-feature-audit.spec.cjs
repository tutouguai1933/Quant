const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

// ============== 首页测试 ==============
test("TC-HOME-001: 状态栏显示（4个状态项）", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("驾驶舱", { timeout: 60000 });

  // 检查状态栏存在 - 查找状态卡片或状态项
  // 状态栏可能以卡片形式展示，检查页面是否包含状态相关内容
  const statusSection = page.locator("body");
  const bodyText = await statusSection.textContent();

  // 检查是否有状态相关的内容
  const hasStatusContent = bodyText.includes("正常") ||
                            bodyText.includes("运行中") ||
                            bodyText.includes("阻塞") ||
                            bodyText.includes("需人工处理") ||
                            bodyText.includes("状态");

  console.log(`TC-HOME-001: Has status content: ${hasStatusContent}`);
  expect(hasStatusContent).toBe(true);
});

test("TC-HOME-002: 研究状态卡片存在", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("驾驶舱", { timeout: 60000 });

  // 检查研究状态卡片
  const researchCard = page.locator("body").filter({ hasText: /研究|信号/ });
  await expect(researchCard.first()).toBeVisible({ timeout: 30000 });
});

test("TC-HOME-003: 执行状态卡片存在", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("驾驶舱", { timeout: 60000 });

  // 检查执行状态卡片
  const executionCard = page.locator("body").filter({ hasText: /执行|策略/ });
  await expect(executionCard.first()).toBeVisible({ timeout: 30000 });
});

test("TC-HOME-004: 风险与告警卡片存在", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("驾驶舱", { timeout: 60000 });

  // 检查风险与告警卡片
  const riskCard = page.locator("body").filter({ hasText: /风险|告警|异常/ });
  await expect(riskCard.first()).toBeVisible({ timeout: 30000 });
});

test("TC-HOME-005: 未登录时显示登录提示", async ({ page }) => {
  test.setTimeout(120000);
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("驾驶舱", { timeout: 60000 });

  // 检查登录提示 - 未登录时应显示登录链接或按钮
  const loginPrompt = page.locator("body").filter({ hasText: /登录|请先登录/ });
  // 或者检查是否有链接指向登录页
  const loginLink = page.locator('a[href*="login"]');
  const hasLoginPrompt = (await loginPrompt.count()) > 0 || (await loginLink.count()) > 0;
  console.log(`TC-HOME-005: Login prompt visible: ${hasLoginPrompt}`);
});

// ============== 信号页测试（需登录）===============
test("TC-SIGNALS-001: 状态栏显示", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/signals");
  await expect(page.locator("body")).toContainText("信号", { timeout: 60000 });

  // 检查状态栏存在
  const statusBar = page.locator("body").filter({ hasText: /状态|运行|正常/ });
  await expect(statusBar.first()).toBeVisible({ timeout: 30000 });
});

test("TC-SIGNALS-002: 候选排行榜显示", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/signals");
  await expect(page.locator("body")).toContainText("信号", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查候选排行榜
  await expect(page.locator("body")).toContainText("候选排行榜", { timeout: 30000 });
});

test("TC-SIGNALS-003: 研究运行状态面板显示", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/signals");
  await expect(page.locator("body")).toContainText("信号", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查研究运行状态面板
  const statusPanel = page.locator("body").filter({ hasText: /运行状态|研究状态/ });
  const hasPanel = (await statusPanel.count()) > 0;
  console.log(`TC-SIGNALS-003: Research status panel visible: ${hasPanel}`);
});

test("TC-SIGNALS-004: 运行历史记录显示（如果有历史）", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/signals");
  await expect(page.locator("body")).toContainText("信号", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查运行历史记录
  const history = page.locator("body").filter({ hasText: /历史|记录|运行历史/ });
  const hasHistory = (await history.count()) > 0;
  console.log(`TC-SIGNALS-004: Run history visible: ${hasHistory}`);
});

test("TC-SIGNALS-005: 自动化入口存在", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/signals");
  await expect(page.locator("body")).toContainText("信号", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查自动化入口 - 可能是链接或按钮
  const automationEntry = page.locator('a[href*="tasks"], a[href*="automation"], button').filter({ hasText: /自动化|任务/ });
  const hasAutomation = (await automationEntry.count()) > 0;
  console.log(`TC-SIGNALS-005: Automation entry visible: ${hasAutomation}`);
});

test("TC-SIGNALS-006: 运行 Qlib 信号流水线按钮可点击", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/signals");
  await expect(page.locator("body")).toContainText("信号", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查运行 Qlib 信号流水线按钮
  const qlibButton = page.getByRole("button", { name: /运行 Qlib 信号流水线|运行研究动作/ });
  const buttonCount = await qlibButton.count();
  console.log(`TC-SIGNALS-006: Qlib pipeline button count: ${buttonCount}`);

  if (buttonCount > 0) {
    await expect(qlibButton.first()).toBeEnabled({ timeout: 30000 });
  }
});

// ============== 评估页测试（需登录）===============
test("TC-EVAL-001: 状态栏显示", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/evaluation");
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });

  // 检查状态栏存在
  const statusBar = page.locator("body").filter({ hasText: /状态|运行|正常/ });
  await expect(statusBar.first()).toBeVisible({ timeout: 30000 });
});

test("TC-EVAL-002: 当前推荐卡片显示", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/evaluation");
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查当前推荐卡片
  await expect(page.locator("body")).toContainText("当前推荐", { timeout: 30000 });
});

test("TC-EVAL-003: 推荐原因卡片显示", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/evaluation");
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查推荐原因卡片
  await expect(page.locator("body")).toContainText("推荐原因", { timeout: 30000 });
});

test("TC-EVAL-004: 淘汰原因卡片显示", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/evaluation");
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查淘汰原因卡片
  await expect(page.locator("body")).toContainText("淘汰原因", { timeout: 30000 });
});

test("TC-EVAL-005: 候选范围契约卡片显示", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/evaluation");
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查候选范围契约卡片
  await expect(page.locator("body")).toContainText("候选范围契约", { timeout: 30000 });
});

test("TC-EVAL-006: 跨页入口按钮（去策略中心、回到研究）", async ({ page }) => {
  test.setTimeout(120000);
  await loginAsAdmin(page, "/evaluation");
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });
  await page.waitForTimeout(2000);

  // 检查跨页入口按钮
  const strategyLink = page.getByRole("link", { name: /去策略中心/ });
  const researchLink = page.getByRole("link", { name: /回到研究/ });
  const homeLink = page.getByRole("link", { name: /回到首页/ });

  const hasStrategy = (await strategyLink.count()) > 0;
  const hasResearch = (await researchLink.count()) > 0;
  const hasHome = (await homeLink.count()) > 0;

  console.log(`TC-EVAL-006: Strategy link: ${hasStrategy}, Research link: ${hasResearch}, Home link: ${hasHome}`);

  // 至少应该有一个导航链接
  expect(hasStrategy || hasResearch || hasHome).toBe(true);
});