const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("tasks config save persists across tasks and evaluation workbenches", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/tasks");

  const formFor = (currentPage) =>
    currentPage
      .locator('form[action="/actions"]')
      .filter({ has: currentPage.locator('input[name="section"][value="operations"]') })
      .first();
  const nextNumericValue = (value, fallback, maximum) => {
    const current = Number.parseInt(value, 10);
    const normalized = Number.isFinite(current) ? current : fallback;
    return String(normalized >= maximum ? normalized - 1 : normalized + 1);
  };

  await expect(page.locator("body")).toContainText("长期运行配置", { timeout: 60000 });

  const tasksForm = formFor(page);
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

    const savedTasksForm = formFor(page);
    await expect(savedTasksForm.locator('input[name="comparison_run_limit"]')).toHaveValue(nextComparison);
    await expect(savedTasksForm.locator('input[name="review_limit"]')).toHaveValue(nextReview);

    await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "commit", timeout: 90000 });
    await expect(page.locator("body")).toContainText("实验对比与复盘窗口", { timeout: 60000 });
    const evaluationForm = formFor(page);
    await expect(evaluationForm.locator('input[name="comparison_run_limit"]')).toHaveValue(nextComparison);
    await expect(evaluationForm.locator('input[name="review_limit"]')).toHaveValue(nextReview);
  } finally {
    if (page.isClosed()) {
      return;
    }
    await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "commit", timeout: 90000 });
    await expect(page.locator("body")).toContainText("长期运行配置", { timeout: 60000 });
    const restoreForm = formFor(page);
    await restoreForm.locator('input[name="comparison_run_limit"]').fill(originalComparison);
    await restoreForm.locator('input[name="review_limit"]').fill(originalReview);
    await restoreForm.getByRole("button", { name: "保存当前配置" }).click();
    await expect(formFor(page).locator('input[name="comparison_run_limit"]')).toHaveValue(originalComparison);
    await expect(formFor(page).locator('input[name="review_limit"]')).toHaveValue(originalReview);
  }
});

test("evaluation workspace shows threshold story and live gate breakdown", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/evaluation");

  await expect(page.locator("body")).toContainText("当前准入选择", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("准入门槛目录", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("live 门槛", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("门控分解", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("live 门", { timeout: 60000 });
});

test("evaluation and strategies pages show stable recommendation story", async ({ page }) => {
  test.setTimeout(120000);

  await loginAsAdmin(page, "/evaluation");

  await expect(page.locator("body")).toContainText("推荐摘要", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前优先进入 dry-run", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前综合排序第一", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前卡在哪个门", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("先怎么修", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("研究侧", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("执行侧", { timeout: 60000 });

  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("策略中心", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("为什么先推进", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("当前综合排序第一", { timeout: 60000 });
  await expect(page.locator("body")).toContainText("研究 / 执行差异", { timeout: 60000 });
});
