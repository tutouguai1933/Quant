const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

async function expectResearchActionFeedback(page) {
  await expect(page.locator("body")).toContainText("动作反馈");
  const trainingMessage = page.getByText("研究训练已进入后台");
  const inferenceMessage = page.getByText("研究推理已进入后台");
  const runningMessage = page.getByText("研究任务正在运行，请等当前任务完成后再发起。");
  await expect(async () => {
    const trainingCount = await trainingMessage.count();
    const inferenceCount = await inferenceMessage.count();
    const runningCount = await runningMessage.count();
    expect(trainingCount + inferenceCount + runningCount).toBeGreaterThan(0);
  }).toPass({ timeout: 20000 });
}

test("research page routes launch actions through one primary action section", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "commit", timeout: 90000 });

  await expect(page.getByRole("heading", { name: "研究主动作区" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("heading", { name: "当前研究摘要" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前状态" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前配置摘要" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前产物" })).toBeVisible();
  await expect(page.getByRole("button", { name: "运行研究动作" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看配置摘要" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究说明" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究链跳转" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看完整配置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看配置说明" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看产物详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "打开实验弹窗" })).toBeVisible();
  await expect(page.getByRole("button", { name: "研究训练" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "研究推理" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "研究模板" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "标签定义" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "研究分数与权重" })).toHaveCount(0);

  await page.getByRole("button", { name: "运行研究动作" }).click();
  const actionDrawer = page.getByRole("dialog", { name: "运行研究动作" });
  await expect(actionDrawer.getByRole("button", { name: "研究训练" })).toBeVisible();
  await expect(actionDrawer.getByRole("button", { name: "研究推理" })).toBeVisible();
  await expect(actionDrawer.getByRole("link", { name: "回到信号页看研究报告" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(actionDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看研究链跳转" }).click();
  const routeDrawer = page.getByRole("dialog", { name: "查看研究链跳转" });
  await expect(routeDrawer.getByRole("link", { name: "去评估与实验中心" })).toBeVisible();
  await expect(routeDrawer.getByRole("link", { name: "去策略页看执行承接" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(routeDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看完整配置" }).click();
  const configDrawer = page.getByRole("dialog", { name: "研究配置详情" });
  await expect(configDrawer).toContainText("研究预设");
  await expect(configDrawer).toContainText("研究参数配置");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(configDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "打开实验弹窗" }).click();
  const experimentDialog = page.getByRole("dialog", { name: "研究实验详情" });
  await expect(experimentDialog).toContainText("训练切分说明");
  await expect(experimentDialog).toContainText("研究分数与权重");
  await page.getByRole("button", { name: "关闭详情弹窗" }).click();
  await expect(experimentDialog).toHaveCount(0);
});

test("research page shows final feedback after training and inference submission", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/research");

  await page.getByRole("button", { name: "运行研究动作" }).click();
  const actionDrawer = page.getByRole("dialog", { name: "运行研究动作" });
  await expect(actionDrawer.getByRole("button", { name: "研究训练" })).toBeVisible();
  await actionDrawer.getByRole("button", { name: "研究训练" }).click();
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/research`), {
    timeout: 30000,
  });
  await expectResearchActionFeedback(page);

  await page.getByRole("button", { name: "运行研究动作" }).click();
  const inferenceDrawer = page.getByRole("dialog", { name: "运行研究动作" });
  await expect(inferenceDrawer.getByRole("button", { name: "研究推理" })).toBeVisible();
  await inferenceDrawer.getByRole("button", { name: "研究推理" }).click();
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/research`), {
    timeout: 30000,
  });
  await expectResearchActionFeedback(page);
});
