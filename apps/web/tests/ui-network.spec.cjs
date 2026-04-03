const { test, expect } = require("@playwright/test");

const PATHS = ["/signals", "/market/BTCUSDT"];

test.use({
  launchOptions: { executablePath: "/snap/bin/chromium" },
  viewport: { width: 1440, height: 1100 },
});

for (const path of PATHS) {
  test(`network ${path}`, async ({ page }) => {
    const notFound = [];
    page.on("response", (response) => {
      if (response.status() === 404) {
        notFound.push(response.url());
      }
    });

    await page.goto(`http://127.0.0.1:9012${path}`, { waitUntil: "networkidle" });
    console.log(`NETWORK ${path} => ${JSON.stringify(notFound)}`);
    expect(notFound, `${path} should not request missing resources`).toEqual([]);
  });
}
