/* 这个文件负责在浏览器测试里复用真实登录流程。 */

const { expect } = require("@playwright/test");
const { WEB_BASE_URL } = require("./test-urls.cjs");

async function loginAsAdmin(page, nextPath = "/strategies") {
  await page.goto(`${WEB_BASE_URL}/login?next=${encodeURIComponent(nextPath)}`, { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 20000 }).catch(() => {});
  // 已登录（cookie 有效）时登录页会直接跳走，探测后跳过
  const loginBtn = page.getByRole("button", { name: "登录并继续" });
  const alreadyLoggedIn = await page
    .waitForSelector('input[name="username"]', { timeout: 5000 })
    .then(() => false)
    .catch(() => true);
  if (alreadyLoggedIn) {
    // 已登录：等跳转完成
    await page.waitForURL(/strategies|\/pipeline|\/$/, { timeout: 20000 }).catch(() => {});
    await page.goto(`${WEB_BASE_URL}${nextPath}`, { waitUntil: "domcontentloaded" });
    return;
  }
  await page.locator('input[name="username"]').fill("admin");
  await page.locator('input[name="password"]').fill("1933");
  await loginBtn.click();
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}${nextPath}(?:\\?.*)?$`), { timeout: 20000 });
  await expect(page.locator("body")).not.toContainText("正在建立管理员会话", { timeout: 15000 });
}

module.exports = {
  loginAsAdmin,
};
