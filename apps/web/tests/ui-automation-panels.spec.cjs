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

  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "load" });
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

  await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "load" });
  await page.waitForFunction(() => document.body.innerText.includes("模型说明"));
  await expect(page.getByText("模型说明").first()).toBeVisible();
  await expect(page.getByText("标签方式说明").first()).toBeVisible();
  await expect(page.getByText("持有窗口说明").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/backtest`, { waitUntil: "load" });
  await page.waitForFunction(() => document.body.innerText.includes("成本模型说明"));
  await expect(page.getByText("成本模型说明").first()).toBeVisible();
  await expect(page.getByText("准入门槛预览").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "load" });
  await page.waitForFunction(() => document.body.innerText.includes("回到研究链"));
  await expect(page.getByRole("link", { name: "回到研究链" })).toBeVisible();
  await expect(page.getByRole("link", { name: "去回测工作台" })).toBeVisible();
  await expect(page.getByRole("link", { name: "去评估与实验中心" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Kill Switch" })).toBeVisible();
  await expect(page.getByText("活跃告警").first()).toBeVisible();
  await expect(page.getByText("最近复盘记录").first()).toBeVisible();
  await expect(page.getByText("当前处理队列").first()).toBeVisible();
  await expect(page.getByText("恢复检查项").first()).toBeVisible();
  await expect(page.getByText("告警快捷处理")).toBeVisible();
  await expect(page.getByRole("button", { name: "确认头号告警" })).toBeVisible();
  await expect(page.getByRole("button", { name: "清理非错误告警" })).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "load" });
  await page.waitForFunction(() => document.body.innerText.includes("最近复盘记录"));
  await expect(page.getByText("实验对比与复盘窗口")).toBeVisible();
  await expect(page.getByRole("heading", { name: "准入预设", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "自选实验对比", exact: true })).toBeVisible();
  await expect(page.getByText("分阶段最佳候选")).toBeVisible();
  await expect(page.getByText("研究候选池")).toBeVisible();
  await expect(page.getByText("live 子集")).toBeVisible();
  await expect(page.getByText("为什么这里只到 dry-run")).toBeVisible();
  await expect(page.getByText("研究 / 回测 / 执行对照")).toBeVisible();
  await expect(page.getByText("最近复盘记录").first()).toBeVisible();
  await expect(page.getByText("最近训练实验快照").first()).toBeVisible();
  await expect(page.getByText("最近推理实验快照").first()).toBeVisible();
  await expect(page.getByText("候选推进板").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "去任务页看自动化" })).toBeVisible();
  await page.goto(`${WEB_BASE_URL}/features`, { waitUntil: "load" });
  await page.waitForFunction(() => document.body.innerText.includes("类别权重配置"));
  await expect(page.getByText("类别权重配置")).toBeVisible();
  await expect(page.getByText("趋势权重").first()).toBeVisible();
  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "load" });
  await page.waitForFunction(() => document.body.innerText.includes("调度顺序矩阵"));
  await expect(page.getByText("调度顺序矩阵")).toBeVisible();
  await expect(page.getByText("失败规则矩阵")).toBeVisible();
});
