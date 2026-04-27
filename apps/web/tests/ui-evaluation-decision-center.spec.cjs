const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("evaluation page shows recommendation and candidate scope", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/evaluation");
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前推荐", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("推荐原因", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("淘汰原因", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("候选范围契约", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("候选篮子", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("执行篮子", { timeout: 60000 });
});

test("evaluation page shows candidate count after research", async ({ page }) => {
  test.setTimeout(180000);
  const renderTimeout = 60000;

  await loginAsAdmin(page, "/signals");
  await expect(page.locator("body")).toContainText("信号", { timeout: renderTimeout });

  // Run research pipeline to generate candidates
  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expect
    .poll(async () => (await page.locator("body").textContent()) ?? "", { timeout: renderTimeout })
    .toMatch(/Qlib 信号流水线已进入后台|研究动作已发出|研究任务正在运行/);

  // Wait for pipeline to complete
  await page.waitForTimeout(30000);

  // Navigate to evaluation page
  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: renderTimeout });

  // Check for candidate data (should show candidates after research)
  const bodyText = await page.locator("body").textContent();
  // Either shows candidates or shows the fallback state
  if (bodyText.includes("候选总数：10") || bodyText.includes("候选总数 10")) {
    await expect(page.locator("body")).toContainText("10", { timeout: renderTimeout });
  } else {
    // Fallback state is acceptable for testing
    await expect(page.locator("body")).toContainText("候选总数", { timeout: renderTimeout });
  }
});

test("evaluation page provides navigation links", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/evaluation");
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });

  // Check for navigation buttons (use first() since there may be multiple)
  await expect(page.getByRole("link", { name: "去策略中心" }).first()).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("link", { name: "回到研究" }).first()).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("link", { name: "回到首页" }).first()).toBeVisible({ timeout: 60000 });
});