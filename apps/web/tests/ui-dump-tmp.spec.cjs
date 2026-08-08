const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const fs = require("fs");

test.use(getPlaywrightUseOptions());

for (const p of ["/signals", "/strategies"]) {
  test(`dump ${p}`, async ({ page }) => {
    test.setTimeout(90000);
    await loginAsAdmin(page, p);
    await page.goto(`${WEB_BASE_URL}${p}`, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(6000);
    const body = await page.locator("body").innerText();
    fs.appendFileSync("/tmp/opencode/ui-dump.txt", `\n========== ${p} ==========\n${body}\n`);
  });
}
