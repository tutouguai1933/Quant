const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("login page submits and redirects without getting stuck", async ({ page }) => {
  test.setTimeout(60000);
  await page.goto(`${WEB_BASE_URL}/login?next=%2Fstrategies`, { waitUntil: "networkidle" });
  await expect(page.locator('button[type="submit"][data-hydrated="true"]').first()).toBeVisible({ timeout: 30000 });

  await expect(page.locator('input[name="password"]')).not.toHaveAttribute("placeholder", "1933");

  await page.locator('input[name="username"]').fill("admin");
  await page.locator('input[name="password"]').fill("1933");
  await page.getByRole("button", { name: "登录并继续" }).click();

  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/strategies(?:\\?.*)?$`), {
    timeout: 30000,
  });
  await expect(page.locator("body")).not.toContainText("正在切换工作区", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("策略中心", { timeout: 60000 });
});

test("login page shows pending feedback when submitting with Enter", async ({ page }) => {
  await page.goto(`${WEB_BASE_URL}/login?next=%2Fstrategies`, { waitUntil: "domcontentloaded" });
  await expect(page.locator('button[type="submit"][data-hydrated="true"]').first()).toBeVisible({ timeout: 30000 });
  await page.evaluate(() => {
    const form = document.querySelector('form[action="/login/submit"]');
    form?.addEventListener(
      "submit",
      (event) => {
        event.preventDefault();
      },
      { once: true },
    );
  });
  await page.locator('input[name="username"]').fill("admin");
  await page.locator('input[name="password"]').fill("1933");
  await page.locator('input[name="password"]').press("Enter");

  await expect(page.locator('button[data-hydrated="true"]')).toContainText("登录中…");
  await expect(page.getByText("正在建立管理员会话，完成后会自动跳转。")).toBeVisible();
});
