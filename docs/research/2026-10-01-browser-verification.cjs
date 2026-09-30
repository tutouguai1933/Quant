/* 验证线上真实登录、页面切换和代理接口数据，保存证据截图。 */
const { chromium, expect } = require("../../apps/web/node_modules/@playwright/test");
const { loginAsAdmin } = require("../../apps/web/tests/test-auth.cjs");
const path = require("path");
const base = process.env.QUANT_WEB_BASE_URL;
if (!base || !process.env.PLAYWRIGHT_EXECUTABLE_PATH) {
  throw new Error("请配置网站地址和已安装浏览器路径");
}

/* 从真实浏览器确认页面已能取数，而不仅仅返回一个登录页。 */
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH, headless: true,
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await loginAsAdmin(page, "/");
    await expect(page.locator("body")).not.toContainText("数据加载中", { timeout: 20000 });
    let expectedMode;
    for (const endpoint of ["/tasks/automation", "/signals/research/runtime", "/freqtrade/status"]) {
      const response = await page.request.get(base + "/api/control" + endpoint, { timeout: 15000 });
      expect(response.status()).toBe(200);
      const payload = await response.json();
      expect(payload.error).toBeNull();
      expect(payload.data).toBeTruthy();
      if (endpoint === "/tasks/automation") expectedMode = payload.data.item.state.mode;
    }
    const link = page.locator('a[href="/tasks"]').first();
    await link.click();
    await expect(page).toHaveURL(base + "/tasks", { timeout: 20000 });
    await expect(page.locator("body")).not.toContainText("Application error");
    await expect(page.locator("body")).not.toContainText("自动化状态加载失败", { timeout: 30000 });
    await expect(page.locator("body")).not.toContainText("自动化状态暂时不可用", { timeout: 30000 });
    await expect(page.locator("body")).toContainText(expectedMode, { timeout: 30000 });
    const tasksResponse = await page.request.get(base + "/api/control/tasks");
    const tasks = await tasksResponse.json();
    expect(tasks.error).toBeNull();
    if (tasks.data.items.length === 0) {
      await expect(page.locator("body")).toContainText("当前还没有任务");
    } else {
      await expect(page.locator("body")).not.toContainText("当前还没有任务", { timeout: 30000 });
    }
    await page.screenshot({ path: path.join(__dirname, "2026-10-01-tasks-restored.png"), fullPage: true });
    expect(errors).toEqual([]);
    console.log("交互与数据验证：1 通过，0 失败");
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
