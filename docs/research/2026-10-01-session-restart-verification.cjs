/* 明确启用后验证线上API重启保留登录；只重启quant-api，不操作交易容器。 */
const { chromium, expect } = require("../../apps/web/node_modules/@playwright/test");
const { loginAsAdmin } = require("../../apps/web/tests/test-auth.cjs");
const { execFileSync } = require("node:child_process");
const base = process.env.QUANT_WEB_BASE_URL;
const api = process.env.QUANT_API_BASE_URL;
if (process.env.QUANT_VERIFY_API_RESTART !== "true" || !base || !api
    || !process.env.QUANT_SSH_KEY || !process.env.QUANT_SSH_HOST) {
  throw new Error("必须显式启用API重启验证并配置网站、API、SSH主机和密钥路径");
}

/* 使用同一浏览器cookie跨重启读取真实自动化状态，令牌不会打印到日志。 */
(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH, headless: true,
  });
  try {
    const page = await browser.newPage();
    await loginAsAdmin(page, "/tasks");
    const before = (await page.context().cookies()).find(c => c.name === "quant_admin_token");
    expect(Boolean(before)).toBe(true);
    execFileSync("ssh", [
      "-i", process.env.QUANT_SSH_KEY, "-o", "BatchMode=yes",
      process.env.QUANT_SSH_HOST, "docker restart -t 10 quant-api",
    ], { timeout: 45000, stdio: ["ignore", "pipe", "pipe"] });
    let healthy = false;
    for (let count = 0; count < 30; count += 1) {
      try {
        const health = await fetch(api + "/health", { signal: AbortSignal.timeout(2000) });
        if (health.ok) { healthy = true; break; }
      } catch {}
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    expect(healthy).toBe(true);
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    const sessionResponse = await page.request.get(base + "/api/control/session", { timeout: 15000 });
    const session = await sessionResponse.json();
    expect(session.isAuthenticated).toBe(true);
    expect(session.status).toBe("authenticated");
    expect(page.url().includes("/login")).toBe(false);
    const after = (await page.context().cookies()).find(c => c.name === "quant_admin_token");
    expect(after?.value === before?.value).toBe(true);
    const response = await page.request.get(base + "/api/control/tasks/automation", { timeout: 20000 });
    const payload = await response.json();
    expect(payload.error).toBeNull();
    console.log("实际API重启保留登录：1通过，0失败");
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
