const { test, expect } = require("@playwright/test");
const { WEB_BASE_URL } = require("./test-urls.cjs");

const PATHS = ["/signals", "/market/BTCUSDT", "/market/ETHUSDT"];

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

    await page.goto(`${WEB_BASE_URL}${path}`, { waitUntil: "networkidle" });
    console.log(`NETWORK ${path} => ${JSON.stringify(notFound)}`);
    expect(notFound, `${path} should not request missing resources`).toEqual([]);
  });
}
