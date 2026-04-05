const { test, expect } = require("@playwright/test");

test.use({
  launchOptions: { executablePath: "/snap/bin/chromium" },
  viewport: { width: 1440, height: 1100 },
});

test("login page submits and redirects without getting stuck", async ({ page }) => {
  await page.goto("http://127.0.0.1:9012/login?next=%2Fstrategies", { waitUntil: "networkidle" });

  await expect(page.locator('input[name="password"]')).not.toHaveAttribute("placeholder", "1933");

  await page.locator('input[name="username"]').fill("admin");
  await page.locator('input[name="password"]').fill("1933");
  await page.getByRole("button", { name: "登录并继续" }).click();

  await page.waitForURL("http://127.0.0.1:9012/strategies**", { timeout: 15000 });
  await expect(page).toHaveURL(/http:\/\/127\.0\.0\.1:9012\/strategies/);
  await expect(page.getByText("策略中心", { exact: true })).toBeVisible();
});
