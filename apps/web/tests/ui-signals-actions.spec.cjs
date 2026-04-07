const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("signals page shows pending feedback while qlib pipeline is submitting", async ({ page }) => {
  await page.route("**/actions", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800));
    await route.fulfill({
      status: 303,
      headers: {
        location: "/signals?tone=success&title=%E5%8A%A8%E4%BD%9C%E5%8F%8D%E9%A6%88&message=%E6%B5%8B%E8%AF%95%E6%8F%90%E4%BA%A4%E6%88%90%E5%8A%9F%E3%80%82",
      },
      body: "",
    });
  });

  await page.goto(`${WEB_BASE_URL}/signals`, { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();

  await expect(page.getByRole("button", { name: "运行 Qlib 信号流水线运行中…" })).toBeVisible();
  await expect(page.getByText("研究动作已发出，页面会在结果返回后自动刷新。")).toBeVisible();
});
