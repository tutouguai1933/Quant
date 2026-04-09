const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("sidebar navigation stays responsive across public pages", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto(`${WEB_BASE_URL}/signals`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("信号") && !document.body.innerText.includes("正在切换工作区"));

  await page.getByRole("link", { name: /市场/ }).click();
  await page.waitForURL("**/market");
  await page.waitForFunction(() => document.body.innerText.includes("市场") && !document.body.innerText.includes("正在切换工作区"));

  await page.getByRole("link", { name: /余额/ }).click();
  await page.waitForURL("**/balances");
  await page.waitForFunction(() => document.body.innerText.includes("余额") && !document.body.innerText.includes("正在切换工作区"));

  await page.getByRole("link", { name: /信号/ }).click();
  await page.waitForURL("**/signals");
  await page.waitForFunction(() => document.body.innerText.includes("信号") && !document.body.innerText.includes("正在切换工作区"));

  expect(errors).toEqual([]);
});
