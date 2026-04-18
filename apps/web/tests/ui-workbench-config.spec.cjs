const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("research config save persists inside research drawer", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/research");

  const openResearchConfigDrawer = async () => {
    await page.getByRole("button", { name: "查看完整配置" }).click();
    const configDrawer = page.getByRole("dialog", { name: "研究配置详情" });
    await expect(configDrawer).toContainText("研究参数配置");
    return configDrawer;
  };

  const configDrawer = await openResearchConfigDrawer();
  const researchForm = configDrawer.locator('select[name="force_validation_top_candidate"]').locator("xpath=ancestor::form").first();
  const validationMode = researchForm.locator('select[name="force_validation_top_candidate"]');
  const originalValue = await validationMode.inputValue();
  const nextValue = originalValue === "true" ? "false" : "true";

  try {
    await validationMode.selectOption(nextValue);
    await researchForm.getByRole("button", { name: "保存当前配置" }).click();

    await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/research`), {
      timeout: 30000,
    });
    await expect(page.locator("body")).toContainText("工作台配置已更新，当前页面和后续研究链都会按新配置刷新。", {
      timeout: 60000,
    });

    const savedDrawer = await openResearchConfigDrawer();
    const savedForm = savedDrawer.locator('select[name="force_validation_top_candidate"]').locator("xpath=ancestor::form").first();
    await expect(savedForm.locator('select[name="force_validation_top_candidate"]')).toHaveValue(nextValue);
    await page.getByRole("button", { name: "关闭详情抽屉" }).click();
    await expect(savedDrawer).toHaveCount(0);
  } finally {
    if (page.isClosed()) {
      return;
    }
    await page.goto(`${WEB_BASE_URL}/research`, { waitUntil: "commit", timeout: 90000 });
    const restoreDrawer = await openResearchConfigDrawer();
    const restoreForm = restoreDrawer.locator('select[name="force_validation_top_candidate"]').locator("xpath=ancestor::form").first();
    await restoreForm.locator('select[name="force_validation_top_candidate"]').selectOption(originalValue);
    await restoreForm.getByRole("button", { name: "保存当前配置" }).click();
    const restoredDrawer = await openResearchConfigDrawer();
    const restoredForm = restoredDrawer.locator('select[name="force_validation_top_candidate"]').locator("xpath=ancestor::form").first();
    await expect(restoredForm.locator('select[name="force_validation_top_candidate"]')).toHaveValue(originalValue);
  }
});

test("tasks config save persists across tasks and evaluation workbenches", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/tasks");

  const formFor = (scope) => scope.locator('input[name="comparison_run_limit"]').locator("xpath=ancestor::form").first();
  const nextNumericValue = (value, fallback, maximum) => {
    const current = Number.parseInt(value, 10);
    const normalized = Number.isFinite(current) ? current : fallback;
    return String(normalized >= maximum ? normalized - 1 : normalized + 1);
  };
  const openWorkflowDrawer = async () => {
    await page.getByRole("button", { name: "查看工作流详情" }).click();
    const workflowDrawer = page.getByRole("dialog", { name: "工作流详情" });
    await expect(workflowDrawer).toContainText("长期运行配置");
    return workflowDrawer;
  };

  await expect(page.locator("body")).toContainText("最近工作流摘要", { timeout: 60000 });

  const workflowDrawer = await openWorkflowDrawer();
  const tasksForm = formFor(workflowDrawer);
  const comparisonInput = tasksForm.locator('input[name="comparison_run_limit"]');
  const reviewInput = tasksForm.locator('input[name="review_limit"]');
  const originalComparison = await comparisonInput.inputValue();
  const originalReview = await reviewInput.inputValue();
  const nextComparison = nextNumericValue(originalComparison, 5, 20);
  const nextReview = nextNumericValue(originalReview, 10, 100);

  try {
    await comparisonInput.fill(nextComparison);
    await reviewInput.fill(nextReview);
    await tasksForm.getByRole("button", { name: "保存当前配置" }).click();

    await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/tasks`), {
      timeout: 30000,
    });
    await expect(page.locator("body")).toContainText("工作台配置已更新，当前页面和后续研究链都会按新配置刷新。", {
      timeout: 60000,
    });

    const savedWorkflowDrawer = await openWorkflowDrawer();
    const savedTasksForm = formFor(savedWorkflowDrawer);
    await expect(savedTasksForm.locator('input[name="comparison_run_limit"]')).toHaveValue(nextComparison);
    await expect(savedTasksForm.locator('input[name="review_limit"]')).toHaveValue(nextReview);
    await page.getByRole("button", { name: "关闭详情抽屉" }).click();

    await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "commit", timeout: 90000 });
    await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: 60000 });
    await page.getByRole("button", { name: "查看评估配置" }).click();
    const evaluationDrawer = page.getByRole("dialog", { name: "评估配置详情" });
    await expect(evaluationDrawer.locator('input[name="comparison_run_limit"]')).toHaveValue(nextComparison);
    await expect(evaluationDrawer.locator('input[name="review_limit"]')).toHaveValue(nextReview);
    await page.getByRole("button", { name: "关闭详情抽屉" }).click();
    await expect(evaluationDrawer).toHaveCount(0);
  } finally {
    if (page.isClosed()) {
      return;
    }
    await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "commit", timeout: 90000 });
    await expect(page.locator("body")).toContainText("最近工作流摘要", { timeout: 60000 });
    const restoreWorkflowDrawer = await openWorkflowDrawer();
    const restoreForm = formFor(restoreWorkflowDrawer);
    await restoreForm.locator('input[name="comparison_run_limit"]').fill(originalComparison);
    await restoreForm.locator('input[name="review_limit"]').fill(originalReview);
    await restoreForm.getByRole("button", { name: "保存当前配置" }).click();
    const restoredWorkflowDrawer = await openWorkflowDrawer();
    await expect(formFor(restoredWorkflowDrawer).locator('input[name="comparison_run_limit"]')).toHaveValue(originalComparison);
    await expect(formFor(restoredWorkflowDrawer).locator('input[name="review_limit"]')).toHaveValue(originalReview);
  }
});

test("evaluation workspace shows threshold story and live gate breakdown", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/evaluation");

  await expect(page.locator("body")).toContainText("当前阻塞", { timeout: 60000 });
  await expect(page.getByRole("button", { name: "查看评估配置" })).toBeVisible();
  await page.getByRole("button", { name: "查看评估配置" }).click();
  const configDrawer = page.getByRole("dialog", { name: "评估配置详情" });
  await expect(configDrawer).toContainText("准入门槛配置");
  await expect(configDrawer).toContainText("准入门槛目录");
  await expect(configDrawer).toContainText("live 门槛");
  await expect(configDrawer).toContainText("门控开关");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(configDrawer).toHaveCount(0);
});

test("evaluation and strategies pages show stable recommendation story", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/evaluation");

  await expect(page.locator("body")).toContainText("推荐摘要", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前推荐", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前下一步动作", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前仲裁结论", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("现在先推进哪一层", { timeout: 60000 });
  await page.getByRole("button", { name: "查看推荐证据" }).click();
  const recommendationDrawer = page.getByRole("dialog", { name: "查看推荐证据" });
  await expect(recommendationDrawer).toContainText("为什么推荐");
  await expect(recommendationDrawer).toContainText("更适合哪套模板");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(recommendationDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看淘汰证据" }).click();
  const eliminationDrawer = page.getByRole("dialog", { name: "查看淘汰证据" });
  await expect(eliminationDrawer).toContainText("当前卡在哪个门");
  await expect(eliminationDrawer).toContainText("先怎么修");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(eliminationDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看研究执行差异" }).click();
  const alignmentDrawer = page.getByRole("dialog", { name: "研究执行差异详情" });
  await expect(alignmentDrawer).toContainText("研究结果 vs 执行结果");
  await expect(alignmentDrawer).toContainText("执行现状");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(alignmentDrawer).toHaveCount(0);

  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("策略中心", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前候选可推进性", { timeout: 60000 });
  await expect(page.getByRole("button", { name: "查看候选篮子" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究执行差异" })).toBeVisible();

  await page.getByRole("button", { name: "查看候选篮子" }).click();
  const candidateDrawer = page.getByRole("dialog", { name: "候选篮子详情" });
  await expect(candidateDrawer).toContainText("为什么先推进");
  await expect(candidateDrawer).toContainText("执行篮子");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(candidateDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看研究执行差异" }).click();
  const strategiesAlignmentDrawer = page.getByRole("dialog", { name: "研究执行差异详情" });
  await expect(strategiesAlignmentDrawer).toContainText("研究结果 vs 执行结果");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(strategiesAlignmentDrawer).toHaveCount(0);
});
