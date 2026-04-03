const { test, expect } = require("@playwright/test");

const PATHS = ["/signals", "/market/BTCUSDT"];

test.use({
  launchOptions: { executablePath: "/snap/bin/chromium" },
  viewport: { width: 1440, height: 1100 },
});

for (const path of PATHS) {
  test(`console ${path}`, async ({ page }) => {
    const errors = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        errors.push(message.text());
      }
    });
    page.on("pageerror", (error) => {
      errors.push(error.message);
    });

    await page.goto(`http://127.0.0.1:9012${path}`, { waitUntil: "networkidle" });
    expect(errors, `${path} should not log console errors`).toEqual([]);
  });
}
