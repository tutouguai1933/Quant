const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("evaluation and strategies pages show execution backfill ledger states", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;

  await page.goto(`${WEB_BASE_URL}/evaluation`, navigation);
  await expect(page.locator("body")).toContainText("执行对齐明细", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("订单回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("持仓回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("同步回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前轮还没有订单回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前轮还没有持仓回填", { timeout: renderTimeout });

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
  await expect(page.locator("body")).toContainText("账户收口", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前研究跟进", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("订单回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("持仓回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("同步回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前轮还没有订单回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前轮还没有持仓回填", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前还没有同步结果回填", { timeout: renderTimeout });
});
