/* 已打开页面的会话失效后，重新聚焦应跳登录，避免显示后端故障提示。 */
const { test, expect } = require("@playwright/test");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
test("打开页面失效后聚焦可重新登录", async ({ page }) => {
  await loginAsAdmin(page, "/tasks");
  await page.context().addCookies([{
    name: "quant_admin_token", value: "expired-session-recovery-test",
    url: WEB_BASE_URL, httpOnly: true, sameSite: "Lax",
  }]);
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(page).toHaveURL(/\/login\?next=/, { timeout: 12000 });
  await expect(page.locator('input[name="password"]')).toBeVisible();
});

test("后端短时不可达时保持当前登录页面", async ({ page }) => {
  await loginAsAdmin(page, "/tasks");
  await page.route("**/api/control/session", route => route.fulfill({
    json: { token: "", isAuthenticated: false, hasSessionCookie: true, status: "unavailable" },
  }));
  const checked = page.waitForResponse(response => response.url().endsWith("/api/control/session"));
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await checked;
  await expect(page).toHaveURL(/\/tasks(?:\?|$)/);
  await expect(page.locator('input[name="password"]')).toHaveCount(0);
});
