const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("signals, strategies and tasks pages show automation summaries", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;

  await loginAsAdmin(page, "/signals");
  await expect(page.locator("body")).toContainText("自动化入口", { timeout: renderTimeout });
  await expect(page.getByText("自动化入口")).toBeVisible();
  await expect(page.getByText("当前模式").first()).toBeVisible();
  await expect(page.getByText("下一步动作").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/strategies`, navigation);
  await expect(page.locator("body")).toContainText("自动化判断", { timeout: renderTimeout });
  await expect(page.getByText("自动化判断")).toBeVisible();
  await expect(page.getByText("自动化推荐").first()).toBeVisible();
  await expect(page.getByText("下一步动作").first()).toBeVisible();
  await expect(page.getByText("当前配置摘要")).toBeVisible();
  await expect(page.getByText("为什么先推进")).toBeVisible();
  await expect(page.getByText("候选池摘要").first()).toBeVisible();
  await expect(page.getByText("研究范围").first()).toBeVisible();
  await expect(page.getByText("自动化策略").first()).toBeVisible();
  await expect(page.getByText("执行安全门配置")).toBeVisible();
  await expect(page.getByText("live_allowed_symbols")).toBeVisible();
  await expect(page.getByText("研究链入口")).toBeVisible();
  await expect(page.getByText("评估与实验中心").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/research`, navigation);
  await expect(page.locator("body")).toContainText("模型说明", { timeout: renderTimeout });
  await expect(page.getByText("模型说明").first()).toBeVisible();
  await expect(page.getByText("标签方式说明").first()).toBeVisible();
  await expect(page.getByText("持有窗口说明").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/backtest`, navigation);
  await expect(page.locator("body")).toContainText("成本模型说明", { timeout: renderTimeout });
  await expect(page.getByText("成本模型说明").first()).toBeVisible();
  await expect(page.getByText("当前回测选择").first()).toBeVisible();
  await expect(page.getByText("过滤参数目录").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/tasks`, navigation);
  await expect(page.locator("body")).toContainText("统一调度入口", { timeout: renderTimeout });
  await expect(page.getByRole("link", { name: "回到研究链" })).toBeVisible();
  await expect(page.getByRole("link", { name: "去回测工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "去评估与实验中心" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Kill Switch" }).first()).toBeVisible();
  await expect(page.getByText("统一调度入口")).toBeVisible();
  await expect(page.getByText("长期运行窗口")).toBeVisible();
  await expect(page.getByText("本轮自动化判断")).toBeVisible();
  await expect(page.getByText("恢复自动化前先把这几项过一遍").first()).toBeVisible();
  await expect(page.getByText("现在先处理什么", { exact: true })).toBeVisible();
  await expect(page.getByText("调度什么时候继续", { exact: true })).toBeVisible();
  await expect(page.getByText("恢复后先推谁", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /保持手动|切到手动/ })).toBeVisible();
  await expect(page.getByText("告警快捷处理")).toBeVisible();
  await expect(page.getByRole("button", { name: "确认头号告警" })).toBeVisible();
  await expect(page.getByRole("button", { name: "清理非错误告警" })).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/evaluation`, navigation);
  await expect(page.locator("body")).toContainText("最近复盘记录", { timeout: renderTimeout });
  await expect(page.getByText("实验对比与复盘窗口")).toBeVisible();
  await expect(page.getByRole("heading", { name: "准入预设", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "自选实验对比", exact: true })).toBeVisible();
  await expect(page.getByText("这一轮更值得推进什么")).toBeVisible();
  await expect(page.getByText("先推荐谁")).toBeVisible();
  await expect(page.getByText("先淘汰谁")).toBeVisible();
  await expect(page.getByText("研究和执行差几步")).toBeVisible();
  await expect(page.getByText("分阶段最佳候选")).toBeVisible();
  await expect(page.getByText("研究候选池")).toBeVisible();
  await expect(page.getByText("live 子集", { exact: true })).toBeVisible();
  await expect(page.getByText("为什么这里只到 dry-run")).toBeVisible();
  await expect(page.getByText("研究 / 回测 / 执行对照")).toBeVisible();
  await expect(page.getByText("最近复盘记录").first()).toBeVisible();
  await expect(page.getByText("最近训练实验快照").first()).toBeVisible();
  await expect(page.getByText("最近推理实验快照").first()).toBeVisible();
  await expect(page.getByText("候选推进板").first()).toBeVisible();
  const candidateBoardTable = page.getByRole("columnheader", { name: "候选推进板" }).locator("xpath=ancestor::table");
  const nextStepCell = candidateBoardTable.getByRole("row").nth(1).getByRole("cell").nth(6);
  await expect
    .poll(async () => (await nextStepCell.textContent())?.trim() ?? "", { timeout: renderTimeout })
    .toMatch(
      /继续研究|推进到 dry-run|推进到 live|先处理同步和执行差异|先处理人工接管|先完成恢复复核|等待冷却结束|等待下一日窗口|当前正在推进|当前先处理卡点|暂时跳过|排队等待上一位|当前没有明确下一步/,
    );
  await expect(nextStepCell).not.toContainText(/^(active|blocked|skipped|standby)$/);
  await expect(page.getByRole("link", { name: "去任务页看自动化" })).toBeVisible();
  await page.goto(`${WEB_BASE_URL}/features`, navigation);
  await expect(page.locator("body")).toContainText("类别权重配置", { timeout: renderTimeout });
  await expect(page.getByText("类别权重配置")).toBeVisible();
  await expect(page.getByText("趋势权重").first()).toBeVisible();
  await page.goto(`${WEB_BASE_URL}/tasks`, navigation);
  await expect(page.locator("body")).toContainText("调度顺序矩阵", { timeout: renderTimeout });
  await expect(page.getByText("调度顺序矩阵")).toBeVisible();
  await expect(page.getByText("失败规则矩阵")).toBeVisible();
});
