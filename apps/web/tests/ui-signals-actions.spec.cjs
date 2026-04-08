const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("signals page shows pending feedback before pipeline form leaves the page", async ({ page }) => {
  await loginAsAdmin(page, "/signals");
  await page.goto(`${WEB_BASE_URL}/signals`, { waitUntil: "load" });
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
    { waitUntil: "load" },
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
  await expect(page.getByRole("heading", { name: "动作反馈" })).toBeVisible();
  await expect(page.getByText("Qlib 信号流水线已进入后台")).toBeVisible();
});

test("manual qlib pipeline is reflected in tasks workspace", async ({ page }) => {
  await loginAsAdmin(page, "/signals");

  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expect(page.getByText("Qlib 信号流水线已进入后台")).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "load" });
  await page.waitForFunction(() => document.body.innerText.includes("任务"));
  await expect(page.getByText("最近工作流来源：手动信号流水线")).toBeVisible({ timeout: 15000 });
});
