const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

const PATHS = ["/", "/signals", "/market/BTCUSDT", "/strategies", "/login", "/balances", "/orders", "/positions"];

test.use({
  launchOptions: { executablePath: "/snap/bin/chromium" },
  viewport: { width: 1440, height: 1100 },
});

for (const path of PATHS) {
  test(`axe ${path}`, async ({ page }) => {
    await page.goto(`http://127.0.0.1:9012${path}`, { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, `${path} should not have axe violations`).toEqual([]);
  });
}
