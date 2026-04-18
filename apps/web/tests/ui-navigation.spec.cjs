const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("sidebar splits primary workbenches from tool entry points", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("研究") && !document.body.innerText.includes("正在切换工作区"));

  const primaryNav = page.getByRole("navigation", { name: "主工作区" });
  await expect(primaryNav).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /总览/ })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /因子/ })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /研究/ })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /决策/ })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /执行/ })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /运维/ })).toBeVisible();
  await expect(primaryNav.getByRole("link", { name: /市场/ })).toHaveCount(0);

  const toolNav = page.getByRole("navigation", { name: "工具入口" });
  await expect(toolNav).toBeVisible();
  await expect(toolNav.getByRole("link", { name: /市场/ })).toBeVisible();
  await expect(toolNav.getByRole("link", { name: /余额/ })).toBeVisible();
  await expect(toolNav.getByRole("link", { name: /持仓/ })).toBeVisible();
  await expect(toolNav.getByRole("link", { name: /订单/ })).toBeVisible();
  await expect(toolNav.getByRole("link", { name: /风险/ })).toBeVisible();
  await expect(toolNav.getByRole("link", { name: /研究/ })).toHaveCount(0);

  await primaryNav.getByRole("link", { name: /决策/ }).click();
  await page.waitForURL("**/evaluation");
  await page.waitForFunction(() => document.body.innerText.includes("评估") && !document.body.innerText.includes("正在切换工作区"));

  await toolNav.getByRole("link", { name: /市场/ }).click();
  await page.waitForURL("**/market");
  await page.waitForFunction(() => document.body.innerText.includes("市场") && !document.body.innerText.includes("正在切换工作区"));

  expect(errors).toEqual([]);
});

test("protected primary and tool links still redirect unauthenticated users to login", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("研究") && !document.body.innerText.includes("正在切换工作区"));

  await page.getByRole("navigation", { name: "主工作区" }).getByRole("link", { name: /执行/ }).click();
  await page.waitForURL(/\/login\?next=%2Fstrategies/);

  await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "networkidle" });
  await page.getByRole("navigation", { name: "工具入口" }).getByRole("link", { name: /风险/ }).click();
  await page.waitForURL(/\/login\?next=%2Frisk/);

  expect(errors).toEqual([]);
});
