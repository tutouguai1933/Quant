const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

const PATHS = ["/", "/signals", "/market/BTCUSDT", "/market/ETHUSDT", "/strategies", "/login", "/balances", "/orders", "/positions"];

test.use(getPlaywrightUseOptions());

for (const path of PATHS) {
  test(`axe ${path}`, async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}${path}`, { waitUntil: "load" });
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, `${path} should not have axe violations`).toEqual([]);
  });
}
