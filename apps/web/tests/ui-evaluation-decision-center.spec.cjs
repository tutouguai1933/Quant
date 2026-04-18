const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("evaluation page separates current arbitration from historical evidence", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "commit", timeout: 90000 });

  await expect(page.locator("body")).toContainText("当前仲裁结论", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("这一块才回答现在该先做什么", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("历史判断只做参考", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("现在该去哪一页", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("候选篮子", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("执行篮子", { timeout: 60000 });
});

test("evaluation page can open decision details in drawer and experiment evidence in dialog", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "commit", timeout: 90000 });

  await expect(page.getByRole("button", { name: "查看门控详情" })).toBeVisible({ timeout: 60000 });
  await page.getByRole("button", { name: "查看门控详情" }).click();
  await expect(page.getByRole("dialog", { name: "门控详情" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("dialog", { name: "门控详情" })).toContainText("当前为什么这么判断");
  await page.getByRole("button", { name: "关闭门控详情" }).click();
  await expect(page.getByRole("dialog", { name: "门控详情" })).toHaveCount(0);

  await expect(page.getByRole("button", { name: "打开实验对比弹窗" })).toBeVisible();
  await page.getByRole("button", { name: "打开实验对比弹窗" }).click();
  await expect(page.getByRole("dialog", { name: "实验对比弹窗" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("dialog", { name: "实验对比弹窗" })).toContainText("研究侧阶段判断");
  await page.getByRole("button", { name: "关闭实验对比弹窗" }).click();
  await expect(page.getByRole("dialog", { name: "实验对比弹窗" })).toHaveCount(0);
});

test("evaluation page routes page-level actions through one primary action section", async ({ page }) => {
  test.setTimeout(120000);

  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "commit", timeout: 90000 });

  await expect(page.getByRole("heading", { name: "评估主动作区" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("button", { name: "更新阶段视图" })).toBeVisible();
  await expect(page.getByRole("button", { name: "更新实验对比" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看下一步跳转" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看评估配置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究执行差异" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "自选实验对比", exact: true })).toHaveCount(0);
  await expect(page.getByText("阶段筛选", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "下一步动作", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "当前推荐" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前阻塞" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前下一步动作" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "推荐摘要" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "淘汰摘要" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "当前准入选择", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "准入门槛配置", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "最近两轮对比", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "配置差异拆解", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "研究与执行差异", exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "查看推荐详情" }).click();
  const recommendationDrawer = page.getByRole("dialog", { name: "查看推荐详情" });
  await expect(recommendationDrawer).toContainText("当前推荐标的");
  await expect(recommendationDrawer).toContainText("推荐动作");
  await expect(recommendationDrawer).toContainText("候选篮子");
  await expect(recommendationDrawer).toContainText("执行篮子");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(recommendationDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "更新阶段视图" }).click();
  const stageDrawer = page.getByRole("dialog", { name: "更新阶段视图" });
  await expect(stageDrawer).toContainText("当前阶段视图");
  await stageDrawer.locator('select[name="stageView"]').selectOption("research");
  await stageDrawer.getByRole("button", { name: "更新阶段视图" }).click();
  await expect(page).toHaveURL(/stageView=research/);
  await expect(page.locator("body")).toContainText("继续研究", { timeout: 60000 });

  await page.getByRole("button", { name: "更新实验对比" }).click();
  const experimentDialog = page.getByRole("dialog", { name: "实验对比详情" });
  await expect(experimentDialog).toContainText("对比对象 A");
  await expect(experimentDialog).toContainText("对比对象 B");
  await page.getByRole("button", { name: "关闭详情弹窗" }).click();
  await expect(experimentDialog).toHaveCount(0);
});
