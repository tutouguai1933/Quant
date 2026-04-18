const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("home page shows current workbench cards with detail drawers", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "commit", timeout: 90000 });

  await expect(page.getByRole("heading", { name: "当前推荐" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("heading", { name: "当前研究状态" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前执行状态" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前风险与告警" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前下一步动作" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "最近结果回看" })).toBeVisible();
  await expect(page.locator("body")).toContainText("当前主线", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("候选篮子", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("执行篮子", { timeout: 60000 });
  await expect(page.getByRole("button", { name: "查看推荐详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看执行详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看风险详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看下一步详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看回看详情" })).toBeVisible();
  await expect(page.getByText("成功链路说明", { exact: true })).toHaveCount(0);
  await expect(page.getByText("研究确认后，再进入策略控制", { exact: true })).toHaveCount(0);
  await expect(page.getByText("你现在最应该先确认的 4 个状态", { exact: true })).toHaveCount(0);
  await expect(page.getByText("失败入口保留在右侧", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "查看推荐详情" }).click();
  const recommendationDrawer = page.getByRole("dialog", { name: "查看推荐详情" });
  await expect(recommendationDrawer.getByRole("link", { name: "去评估与实验中心" })).toBeVisible();
  await expect(recommendationDrawer.getByRole("link", { name: "去市场页筛选目标" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(recommendationDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看研究详情" }).click();
  const researchDrawer = page.getByRole("dialog", { name: "查看研究详情" });
  await expect(researchDrawer.getByRole("link", { name: "回到研究工作台" })).toBeVisible();
  await expect(researchDrawer.getByRole("link", { name: "回到信号页看研究报告" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(researchDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看下一步详情" }).click();
  const actionDrawer = page.getByRole("dialog", { name: "查看下一步详情" });
  await expect(actionDrawer.getByRole("link", { name: "去任务页看自动化" })).toBeVisible();
  await expect(actionDrawer.getByRole("link", { name: "去策略页确认执行" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(actionDrawer).toHaveCount(0);
});

test("home page keeps action feedback usable after admin login", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/");

  await expect(page.getByRole("heading", { name: "当前主工作台" })).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name: "运行研究动作" }).click();
  const researchDrawer = page.getByRole("dialog", { name: "运行研究动作" });
  await expect(researchDrawer.getByRole("button", { name: "运行 Qlib 信号流水线" })).toBeVisible();
  await researchDrawer.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expect
    .poll(async () => (await page.locator("body").textContent()) ?? "", { timeout: 60000 })
    .toMatch(/Qlib 信号流水线已进入后台|研究动作已发出|研究任务正在运行，请等当前任务完成后再发起。/);
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/(?:\\?.*)?$`), { timeout: 30000 });
});
