const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("login page submits and redirects without getting stuck", async ({ page }) => {
  await page.goto(`${WEB_BASE_URL}/login?next=%2Fstrategies`, { waitUntil: "networkidle" });

  await expect(page.locator('input[name="password"]')).not.toHaveAttribute("placeholder", "1933");

  await page.locator('input[name="username"]').fill("admin");
  await page.locator('input[name="password"]').fill("1933");
  await page.getByRole("button", { name: "登录并继续" }).click();

  await page.waitForURL(`${WEB_BASE_URL}/strategies**`, { timeout: 15000 });
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/strategies`));
  await expect(page.getByText("策略中心", { exact: true })).toBeVisible();
});
