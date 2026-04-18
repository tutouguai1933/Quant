const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("evaluation and strategies pages show execution backfill ledger states", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;

  await page.goto(`${WEB_BASE_URL}/evaluation`, navigation);
  await expect(page.getByRole("button", { name: "查看研究执行差异" })).toBeVisible({ timeout: renderTimeout });
  await page.getByRole("button", { name: "查看研究执行差异" }).click();
  const evaluationAlignmentDrawer = page.getByRole("dialog", { name: "研究执行差异详情" });
  await expect(evaluationAlignmentDrawer).toContainText("研究结果 vs 执行结果", { timeout: renderTimeout });
  await expect(evaluationAlignmentDrawer).toContainText("订单回填", { timeout: renderTimeout });
  await expect(evaluationAlignmentDrawer).toContainText("持仓回填", { timeout: renderTimeout });
  await expect(evaluationAlignmentDrawer).toContainText("同步回填", { timeout: renderTimeout });
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(evaluationAlignmentDrawer).toHaveCount(0);

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
  await expect(page.locator("body")).toContainText("当前账户收口摘要", { timeout: renderTimeout });

  await page.getByRole("button", { name: "查看账户回填" }).click();
  const backfillDrawer = page.getByRole("dialog", { name: "账户回填详情" });
  await expect(backfillDrawer).toContainText("当前研究跟进", { timeout: renderTimeout });
  await expect(backfillDrawer).toContainText("订单回填", { timeout: renderTimeout });
  await expect(backfillDrawer).toContainText("持仓回填", { timeout: renderTimeout });
  await expect(backfillDrawer).toContainText("同步回填", { timeout: renderTimeout });
  await expect(backfillDrawer).toContainText("当前轮还没有订单回填", { timeout: renderTimeout });
  await expect(backfillDrawer).toContainText("当前轮还没有持仓回填", { timeout: renderTimeout });
  await expect(backfillDrawer).toContainText("当前还没有同步结果回填", { timeout: renderTimeout });
});
