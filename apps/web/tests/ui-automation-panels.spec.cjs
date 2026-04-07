const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("signals, strategies and tasks pages show automation summaries", async ({ page }) => {
  await loginAsAdmin(page, "/signals");
  await page.waitForFunction(() => document.body.innerText.includes("自动化入口"));
  await expect(page.getByText("自动化入口")).toBeVisible();
  await expect(page.getByText("当前模式").first()).toBeVisible();
  await expect(page.getByText("下一步动作").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("自动化判断"));
  await expect(page.getByText("自动化判断")).toBeVisible();
  await expect(page.getByText("自动化推荐").first()).toBeVisible();
  await expect(page.getByText("下一步动作").first()).toBeVisible();
  await expect(page.getByText("当前配置摘要")).toBeVisible();
  await expect(page.getByText("研究范围").first()).toBeVisible();
  await expect(page.getByText("自动化策略").first()).toBeVisible();
  await expect(page.getByText("执行安全门配置")).toBeVisible();
  await expect(page.getByText("live_allowed_symbols")).toBeVisible();
  await expect(page.getByText("研究链入口")).toBeVisible();
  await expect(page.getByText("评估与实验中心").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("回到研究链"));
  await expect(page.getByRole("link", { name: "回到研究链" })).toBeVisible();
  await expect(page.getByRole("link", { name: "去回测工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "去评估与实验中心" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Kill Switch" })).toBeVisible();
  await expect(page.getByText("活跃告警").first()).toBeVisible();
  await expect(page.getByText("最近复盘记录").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("最近复盘记录"));
  await expect(page.getByText("实验对比与复盘窗口")).toBeVisible();
  await expect(page.getByText("最近复盘记录").first()).toBeVisible();
  await expect(page.getByText("最近训练实验快照").first()).toBeVisible();
  await expect(page.getByText("最近推理实验快照").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "去任务页看自动化" })).toBeVisible();
});
