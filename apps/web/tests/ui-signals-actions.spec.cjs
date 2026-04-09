const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

async function expectPipelineFeedback(page) {
  await expect(page.getByRole("heading", { name: "动作反馈" })).toBeVisible();
  const successMessage = page.getByText("Qlib 信号流水线已进入后台");
  const cycleMessage = page.getByText("手动信号流水线已进入后台");
  const runningMessage = page.getByText("研究任务正在运行，请等当前任务完成后再发起。");
  await expect(async () => {
    const successCount = await successMessage.count();
    const cycleCount = await cycleMessage.count();
    const runningCount = await runningMessage.count();
    expect(successCount + cycleCount + runningCount).toBeGreaterThan(0);
  }).toPass({ timeout: 20000 });
}

test("signals page shows pending feedback before pipeline form leaves the page", async ({ page }) => {
  test.setTimeout(60000);
  await loginAsAdmin(page, "/signals");
  await page.goto(`${WEB_BASE_URL}/signals`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator('button[data-hydrated="true"]').first()).toBeVisible({ timeout: 30000 });
  await page.evaluate(() => {
    const forms = Array.from(document.querySelectorAll('form[action="/actions"]'));
    const target = forms.find((form) => {
      const input = form.querySelector('input[name="action"]');
      return input instanceof HTMLInputElement && input.value === "run_pipeline";
    });
    target?.addEventListener(
      "submit",
      (event) => {
        event.preventDefault();
      },
      { once: true },
    );
  });

  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expect(page.getByRole("button", { name: "运行 Qlib 信号流水线运行中…" })).toBeVisible();
  await expect(page.getByText("研究动作已发出，页面会在结果返回后自动刷新。")).toBeVisible();
});

test("signals page shows final feedback after qlib pipeline submission", async ({ page }) => {
  await page.goto(
    `${WEB_BASE_URL}/signals?tone=success&title=%E5%8A%A8%E4%BD%9C%E5%8F%8D%E9%A6%88&message=%E6%B5%8B%E8%AF%95%E6%8F%90%E4%BA%A4%E6%88%90%E5%8A%9F%E3%80%82`,
    { waitUntil: "commit", timeout: 90000 },
  );
  await expect(page.getByRole("heading", { name: "动作反馈" })).toBeVisible();
  await expect(page.getByText("测试提交成功。")).toBeVisible();
});

test("signals page can start qlib pipeline without proxy unavailable feedback", async ({ page }) => {
  await loginAsAdmin(page, "/signals");

  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();

  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/signals`), {
    timeout: 20000,
  });
  await expect(page.getByText("客户端代理暂时不可用。")).toHaveCount(0);
  await expectPipelineFeedback(page);
});

test("manual qlib pipeline is reflected in tasks workspace", async ({ page }) => {
  test.setTimeout(90000);
  await loginAsAdmin(page, "/signals");

  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expectPipelineFeedback(page);

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "commit", timeout: 90000 });
  await expect(page.locator("body")).toContainText("任务", { timeout: 60000 });
  await expect(page.getByText("本轮自动化判断")).toBeVisible();
  await expect(async () => {
    const sourceCount = await page.getByText("最近工作流来源：手动信号流水线").count();
    const runningCount = await page.getByText("当前可以去研究页、评估页和任务页跟进阶段变化。").count();
    const finishedCount = await page.getByText("这一轮结果已经同步进统一复盘和任务页。").count();
    expect(sourceCount + runningCount + finishedCount).toBeGreaterThan(0);
  }).toPass({ timeout: 20000 });
});
