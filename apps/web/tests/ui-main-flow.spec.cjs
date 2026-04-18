const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("main research to execution flow stays usable across core workbenches", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await loginAsAdmin(page, "/signals");

  await expect(page.locator("body")).toContainText("信号", { timeout: renderTimeout });
  await expect(page.locator("body")).not.toContainText("正在切换工作区", { timeout: renderTimeout });
  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expect
    .poll(async () => (await page.locator("body").textContent()) ?? "", { timeout: renderTimeout })
    .toMatch(/Qlib 信号流水线已进入后台|研究动作已发出|研究任务正在运行，请等当前任务完成后再发起。/);
  await expect(page.locator("body")).toContainText("研究运行状态", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("模板适配判断", { timeout: renderTimeout });
  await page.waitForURL(/\/signals(?:\?|$)/, { timeout: renderTimeout });
  await page.waitForLoadState("domcontentloaded");

  await gotoWorkbench(page, `${WEB_BASE_URL}/research`, navigation);
  await expect(page.locator("body")).toContainText("策略研究工作台", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("研究主动作区", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前研究摘要", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前状态", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前配置摘要", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前产物", { timeout: renderTimeout });
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
  await expect(page.locator("body")).not.toContainText("模型目录");
  await expect(page.locator("body")).not.toContainText("训练切分说明");
  await expect(page.locator("body")).not.toContainText("标签目标与止损说明");
  await expect(page.locator("body")).not.toContainText("模型和标签怎么影响结果");
  await page.getByRole("button", { name: "运行研究动作" }).click();
  const researchActionDrawer = page.getByRole("dialog", { name: "运行研究动作" });
  await expect(researchActionDrawer.getByRole("button", { name: "研究训练" })).toBeVisible();
  await expect(researchActionDrawer.getByRole("button", { name: "研究推理" })).toBeVisible();
  await expect(researchActionDrawer.getByRole("link", { name: "回到信号页看研究报告" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(researchActionDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看完整配置" }).click();
  const researchConfigDrawer = page.getByRole("dialog", { name: "研究配置详情" });
  await expect(researchConfigDrawer).toContainText("研究参数配置");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(researchConfigDrawer).toHaveCount(0);

  await gotoWorkbench(page, `${WEB_BASE_URL}/evaluation`, navigation);
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前推荐");
  await expect(page.locator("body")).toContainText("当前仲裁结论");
  await expect(page.locator("body")).toContainText("推荐原因");
  await expect(page.locator("body")).toContainText("淘汰原因");
  await expect(page.locator("body")).not.toContainText("最近两轮对比");
  await expect(page.locator("body")).not.toContainText("配置差异拆解");
  await expect(page.getByRole("button", { name: "查看研究执行差异" })).toBeVisible();
  await page.getByRole("button", { name: "查看研究执行差异" }).click();
  const evaluationAlignmentDrawer = page.getByRole("dialog", { name: "研究执行差异详情" });
  await expect(evaluationAlignmentDrawer).toContainText("研究结果 vs 执行结果");
  await expect(evaluationAlignmentDrawer).toContainText("研究与执行差异");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(evaluationAlignmentDrawer).toHaveCount(0);

  await gotoWorkbench(page, `${WEB_BASE_URL}/strategies`, navigation);
  await expect(page.locator("body")).toContainText("先看判断，再决定要不要派发", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("为什么先推进");
  await expect(page.locator("body")).toContainText("策略主动作区");
  await expect(page.getByRole("button", { name: "处理自动化动作" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看执行器动作" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究链跳转" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看工具详情" })).toBeVisible();
  await expect(page.getByText("自动化快捷入口")).toHaveCount(0);
  await expect(page.getByText("研究链入口")).toHaveCount(0);
  await expect(page.getByText("这些动作控制的是整台执行器")).toHaveCount(0);
  const strategiesBody = (await page.locator("body").textContent()) ?? "";
  await page.getByRole("button", { name: "处理自动化动作" }).click();
  const strategyAutomationDrawer = page.getByRole("dialog", { name: "处理自动化动作" });
  if (strategiesBody.includes("手动模式下决定何时重开自动化")) {
    await expect(strategyAutomationDrawer.getByRole("button", { name: "保持手动" })).toBeVisible();
    await expect(strategyAutomationDrawer.getByRole("button", { name: "切到 dry-run only" })).toBeVisible();
    await expect(strategyAutomationDrawer.getByRole("button", { name: "确认后恢复自动化" })).toHaveCount(0);
  } else if (strategiesBody.includes("接管中先决定保留什么模式")) {
    await expect(strategyAutomationDrawer.getByRole("button", { name: "保持手动" })).toBeVisible();
    await expect(strategyAutomationDrawer.getByRole("button", { name: "只恢复到 dry-run" })).toBeVisible();
    await expect(strategyAutomationDrawer.getByRole("button", { name: "确认后恢复自动化" })).toBeDisabled();
  } else if (strategiesBody.includes("暂停后先决定怎么继续")) {
    await expect(strategyAutomationDrawer.getByRole("button", { name: "切到手动" })).toBeVisible();
    await expect(strategyAutomationDrawer.getByRole("button", { name: /确认后恢复自动化|恢复自动化/ })).toBeVisible();
  } else if (strategiesBody.includes("接管中先决定怎么恢复")) {
    await expect(strategyAutomationDrawer.getByRole("button", { name: "保持手动" })).toBeVisible();
    await expect(strategyAutomationDrawer.getByRole("button", { name: /确认后恢复自动化|恢复自动化/ })).toBeVisible();
  } else {
    await expect(strategyAutomationDrawer.getByRole("button", { name: "暂停自动化" })).toBeVisible();
    await expect(strategyAutomationDrawer.getByRole("button", { name: /转人工接管|切到手动/ })).toBeVisible();
  }
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();

  await gotoWorkbench(page, `${WEB_BASE_URL}/tasks`, navigation);
  await expect(page.locator("body")).toContainText("先确认自动化模式，再决定要不要触发下一轮工作流。", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("本轮自动化判断");
  await expect(page.locator("body")).toContainText("任务主动作区");
  await expect(page.locator("body")).toContainText("当前自动化模式");
  await expect(page.locator("body")).toContainText("当前头号告警");
  await expect(page.locator("body")).toContainText("当前人工接管状态");
  await expect(page.locator("body")).toContainText("当前恢复建议");
  await expect(page.locator("body")).toContainText("最近工作流摘要");

  await gotoWorkbench(page, `${WEB_BASE_URL}/balances`, navigation);
  await expect(page.locator("body")).toContainText("真实账户余额", { timeout: renderTimeout });

  await gotoWorkbench(page, `${WEB_BASE_URL}/orders`, navigation);
  await expect(page.locator("body")).toContainText("同步来源", { timeout: renderTimeout });

  await gotoWorkbench(page, `${WEB_BASE_URL}/positions`, navigation);
  await expect(page.locator("body")).toContainText("同步来源", { timeout: renderTimeout });

  await gotoWorkbench(page, `${WEB_BASE_URL}/market/BTCUSDT`, navigation);
  await expect(page.locator("body")).toContainText("本地主图", { timeout: renderTimeout });

  expect(errors).toEqual([]);
});

async function gotoWorkbench(page, url, navigation) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      await page.goto(url, navigation);
      return;
    } catch (error) {
      const message = String(error);
      if (!message.includes("net::ERR_ABORTED") || attempt === 1) {
        throw error;
      }
      await page.waitForLoadState("domcontentloaded");
    }
  }
}
