/* 这个文件负责在浏览器测试里复用真实登录流程。 */

const { expect } = require("@playwright/test");
const { WEB_BASE_URL } = require("./test-urls.cjs");

async function loginAsAdmin(page, nextPath = "/strategies") {
  // 先清掉旧 cookie，保证每次都是干净的登录流程（避免残留 cookie 干扰）
  await page.context().clearCookies();
  await page.goto(`${WEB_BASE_URL}/login?next=${encodeURIComponent(nextPath)}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  // 等登录表单出现（水合完成后才有输入框）
  const usernameInput = page.locator('input[name="username"]');
  await expect(usernameInput).toBeVisible({ timeout: 30000 });
  await page.locator('input[name="password"]').fill("1933");
  await usernameInput.fill("admin");
  await page.getByRole("button", { name: "登录并继续" }).click();
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}${nextPath}(?:\\?.*)?$`), { timeout: 20000 });
  await expect(page.locator("body")).not.toContainText("正在建立管理员会话", { timeout: 15000 });
  // 确认 cookie 已种上
  const cookies = await page.context().cookies();
  if (!cookies.some((c) => c.name === "quant_admin_token")) {
    throw new Error("登录后未找到 quant_admin_token cookie");
  }
}

module.exports = {
  loginAsAdmin,
};
