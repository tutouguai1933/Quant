const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("tasks page shows latest automation decision after login", async ({ page }) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await loginAsAdmin(page, "/tasks");
  await expect(page.locator("body")).toContainText("任务", { timeout: 60000 });
  await expect(page.locator("body")).not.toContainText("正在切换工作区", { timeout: 60000 });

  await expect(page.getByText("本轮自动化判断")).toBeVisible();
  await expect(page.getByText("推荐策略实例")).toBeVisible();
  await expect(page.getByText("派发结果")).toBeVisible();
  await expect(page.getByText("失败原因：", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "任务主动作区" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前自动化模式" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前头号告警" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前人工接管状态" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前恢复建议" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "最近工作流摘要" })).toBeVisible();
  await expect(page.getByRole("button", { name: "切换自动化模式" })).toBeVisible();
  await expect(page.getByRole("button", { name: "执行调度动作" })).toBeVisible();
  await expect(page.getByRole("button", { name: "处理告警动作" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看详情页跳转" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看模式详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看告警详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看接管详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看恢复详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看工作流详情" })).toBeVisible();
  await expect(page.getByText("三种模式和一个停机开关")).toHaveCount(0);
  await expect(page.getByText("一键跑完整一轮自动化工作流")).toHaveCount(0);
  await expect(page.getByText("先去最该处理的那一页")).toHaveCount(0);
  await expect(page.getByText("先把最会干扰判断的告警处理掉")).toHaveCount(0);
  await expect(page.getByText("先按仲裁回到对应工作台")).toHaveCount(0);
  await expect(page.getByText("长期运行窗口", { exact: true })).toHaveCount(0);
  await expect(page.getByText("风险等级摘要", { exact: true })).toHaveCount(0);
  await expect(page.getByText("告警摘要", { exact: true })).toHaveCount(0);
  await expect(page.getByText("调度顺序", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "执行调度动作" }).click();
  const dispatchDrawer = page.getByRole("dialog", { name: "执行调度动作" });
  await expect(dispatchDrawer.getByRole("button", { name: "运行自动化工作流" })).toBeVisible();
  await expect(dispatchDrawer.getByRole("button", { name: "暂停自动化" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  await page.getByRole("button", { name: "处理告警动作" }).click();
  const alertDrawer = page.getByRole("dialog", { name: "处理告警动作" });
  await expect(alertDrawer.getByRole("button", { name: "确认头号告警" })).toBeVisible();
  await expect(alertDrawer.getByRole("button", { name: "清理非错误告警" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  await page.getByRole("button", { name: "查看告警详情" }).click();
  const alertDetailDrawer = page.getByRole("dialog", { name: "告警详情" });
  await expect(alertDetailDrawer).toContainText("活跃告警");
  await expect(alertDetailDrawer).toContainText("告警等级处理口径");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  await page.getByRole("button", { name: "查看恢复详情" }).click();
  const recoveryDrawer = page.getByRole("dialog", { name: "恢复详情" });
  await expect(recoveryDrawer).toContainText("恢复检查项");
  await expect(recoveryDrawer).toContainText("失败规则矩阵");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  await page.getByRole("button", { name: "查看工作流详情" }).click();
  const workflowDrawer = page.getByRole("dialog", { name: "工作流详情" });
  await expect(workflowDrawer).toContainText("长期运行配置");
  await expect(workflowDrawer).toContainText("自动化运行参数");
  await expect(workflowDrawer).toContainText("调度顺序矩阵");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  await page.getByRole("button", { name: "查看详情页跳转" }).click();
  const detailRouteDrawer = page.getByRole("dialog", { name: "查看详情页跳转" });
  await expect(detailRouteDrawer.getByRole("link", { name: "查看市场详情" })).toBeVisible();
  await expect(detailRouteDrawer.getByRole("link", { name: "查看余额详情" })).toBeVisible();
  await expect(detailRouteDrawer.getByRole("link", { name: "查看订单详情" })).toBeVisible();
  await expect(detailRouteDrawer.getByRole("link", { name: "查看持仓详情" })).toBeVisible();
  await expect(detailRouteDrawer.getByRole("link", { name: "查看风险详情" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  expect(errors).toEqual([]);
});
