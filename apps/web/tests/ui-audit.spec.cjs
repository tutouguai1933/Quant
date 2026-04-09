const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

const PATHS = [
  "/",
  "/data",
  "/features",
  "/research",
  "/backtest",
  "/evaluation",
  "/signals",
  "/market/BTCUSDT",
  "/market/ETHUSDT",
  "/strategies",
  "/login",
  "/balances",
  "/orders",
  "/positions",
];

test.use(getPlaywrightUseOptions());

for (const path of PATHS) {
  test(`ui audit ${path}`, async ({ page }) => {
    await page.goto(`${WEB_BASE_URL}${path}`, { waitUntil: "load" });
    const report = await page.evaluate(() => {
      const viewportWidth = window.innerWidth;
      const bright = [];
      const overflow = [];

      for (const element of Array.from(document.querySelectorAll("body *"))) {
        const rect = element.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) {
          continue;
        }

        const style = window.getComputedStyle(element);
        const background = style.backgroundColor;
        const color = style.color;

        if (rect.right > viewportWidth + 4) {
          overflow.push({
            tag: element.tagName,
            className: String(element.className || "").slice(0, 120),
            right: Math.round(rect.right),
            width: Math.round(rect.width),
            text: (element.textContent || "").trim().slice(0, 40),
          });
        }

        const match = background.match(/rgba?\(([^)]+)\)/);
        if (!match) {
          continue;
        }

        const parts = match[1].split(",").map((value) => Number(value.trim()));
        const [red, green, blue, alpha = 1] = parts;
        const brightness = (red + green + blue) / 3;
        if (alpha > 0.92 && brightness > 230) {
          bright.push({
            tag: element.tagName,
            className: String(element.className || "").slice(0, 120),
            background,
            color,
            text: (element.textContent || "").trim().slice(0, 40),
          });
        }
      }

      return {
        overflow: overflow.slice(0, 10),
        bright: bright.slice(0, 10),
      };
    });

    console.log(`PAGE ${path} => ${JSON.stringify(report)}`);
    expect(report.overflow, `${path} should not have horizontal overflow`).toEqual([]);
    expect(report.bright, `${path} should not contain bright blocks in terminal theme`).toEqual([]);
  });
}
