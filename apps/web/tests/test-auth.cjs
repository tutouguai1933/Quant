/* 这个文件负责在浏览器测试里复用真实登录流程。 */

const { expect } = require("@playwright/test");
const { WEB_BASE_URL } = require("./test-urls.cjs");

async function loginAsAdmin(page, nextPath = "/strategies") {
  await page.goto(`${WEB_BASE_URL}/login?next=${encodeURIComponent(nextPath)}`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: "登录并继续" })).toBeVisible({ timeout: 30000 });
  await page.locator('input[name="username"]').fill("admin");
  await page.locator('input[name="password"]').fill("1933");
  await page.getByRole("button", { name: "登录并继续" }).click();
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}${nextPath}(?:\\?.*)?$`), { timeout: 15000 });
  await expect(page.locator("body")).not.toContainText("正在建立管理员会话", { timeout: 15000 });
}

module.exports = {
  loginAsAdmin,
};
