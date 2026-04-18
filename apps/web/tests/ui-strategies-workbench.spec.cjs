const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("strategies page collapses default view into execution workbench with drawers", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;

  await page.context().addCookies([
    {
      name: "quant_admin_token",
      value: "fake-token",
      domain: "127.0.0.1",
      path: "/",
      httpOnly: false,
      secure: false,
      sameSite: "Lax",
    },
  ]);

  await page.goto(`${WEB_BASE_URL}/strategies`, navigation);

  await expect(page.getByRole("heading", { name: "当前执行器状态" })).toBeVisible({ timeout: renderTimeout });
  await expect(page.getByRole("heading", { name: "当前候选可推进性" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前执行模式" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前账户收口摘要" })).toBeVisible();

  // 默认视图不再铺满候选篮子、配置表单和回填明细。
  await expect(page.locator("body")).not.toContainText("执行安全门配置");
  await expect(page.locator("body")).not.toContainText("候选篮子摘要");
  await expect(page.locator("body")).toContainText("候选篮子");
  await expect(page.locator("body")).toContainText("执行篮子");
  await expect(page.locator("body")).not.toContainText("订单回填：");

  await page.getByRole("button", { name: "查看候选篮子" }).click();
  const candidateDrawer = page.getByRole("dialog", { name: "候选篮子详情" });
  await expect(candidateDrawer).toContainText("队列摘要");
  await expect(candidateDrawer).toContainText("执行篮子");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(candidateDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看研究执行差异" }).click();
  const alignmentDrawer = page.getByRole("dialog", { name: "研究执行差异详情" });
  await expect(alignmentDrawer).toContainText("研究结果 vs 执行结果");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(alignmentDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看账户回填" }).click();
  const backfillDrawer = page.getByRole("dialog", { name: "账户回填详情" });
  await expect(backfillDrawer).toContainText("订单回填");
  await expect(backfillDrawer).toContainText("持仓回填");
  await expect(backfillDrawer).toContainText("同步回填");
});
