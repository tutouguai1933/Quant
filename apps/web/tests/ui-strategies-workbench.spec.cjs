const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("strategies page collapses default view into execution workbench with drawers", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;
  await loginAsAdmin(page, "/strategies");
  await page.goto(`${WEB_BASE_URL}/strategies`, navigation);

  await expect(page.locator("body")).toContainText("策略", { timeout: renderTimeout });
  await expect(page.getByRole("button", { name: "启动策略" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "暂停策略" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "停止策略" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "派发最新信号" }).first()).toBeVisible();

  const strategyActionForms = await page.locator('form[action="/actions"]').evaluateAll((forms) =>
    forms
      .map((form) => {
        const data = new FormData(form);
        return {
          action: String(data.get("action") || ""),
          strategyId: String(data.get("strategyId") || ""),
          returnTo: String(data.get("returnTo") || ""),
        };
      })
      .filter((item) =>
        ["start_strategy", "pause_strategy", "stop_strategy", "dispatch_latest_signal"].includes(item.action),
      ),
  );
  expect(strategyActionForms).toEqual(
    expect.arrayContaining([
      { action: "start_strategy", strategyId: "1", returnTo: "/strategies" },
      { action: "pause_strategy", strategyId: "1", returnTo: "/strategies" },
      { action: "stop_strategy", strategyId: "1", returnTo: "/strategies" },
      { action: "dispatch_latest_signal", strategyId: "1", returnTo: "/strategies" },
    ]),
  );

  await expect(page.getByText("执行确认")).toBeVisible();
  await expect(page.locator("body")).toContainText("确认执行器状态和最新信号后再操作。");
});
