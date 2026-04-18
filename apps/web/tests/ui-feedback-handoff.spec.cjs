const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

function feedbackUrl(path, tone, title, message) {
  const query = new URLSearchParams({
    tone,
    title: encodeURIComponent(title),
    message: encodeURIComponent(message),
  });
  return `${WEB_BASE_URL}${path}?${query.toString()}`;
}

test("research and evaluation pages render feedback from return query", async ({ page }) => {
  const navigation = { waitUntil: "commit", timeout: 90000 };

  await page.goto(
    feedbackUrl("/research", "success", "登录反馈", "管理员会话已建立。"),
    navigation,
  );
  await expect(page.getByRole("heading", { name: "登录反馈" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByText("管理员会话已建立。")).toBeVisible();

  await page.goto(
    feedbackUrl("/evaluation", "warning", "动作反馈", "当前先处理研究阻塞。"),
    navigation,
  );
  await expect(page.getByRole("heading", { name: "动作反馈" })).toBeVisible({ timeout: 60000 });
  await expect(page.getByText("当前先处理研究阻塞。")).toBeVisible();
});

test("research and evaluation pages keep config save buttons non-misleading when unauthenticated", async ({ page }) => {
  const navigation = { waitUntil: "commit", timeout: 90000 };

  await page.goto(`${WEB_BASE_URL}/research`, navigation);
  await page.getByRole("button", { name: "查看完整配置" }).click();
  const researchConfigDrawer = page.getByRole("dialog", { name: "研究配置详情" });
  await expect(researchConfigDrawer.getByRole("button", { name: "登录后可保存配置" }).first()).toBeDisabled({ timeout: 60000 });
  await expect(page.getByRole("button", { name: "保存当前配置" })).toHaveCount(0);
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(researchConfigDrawer).toHaveCount(0);

  await page.goto(`${WEB_BASE_URL}/evaluation`, navigation);
  await page.getByRole("button", { name: "查看评估配置" }).click();
  const evaluationConfigDrawer = page.getByRole("dialog", { name: "评估配置详情" });
  await expect(evaluationConfigDrawer.getByRole("button", { name: "登录后可保存配置" }).first()).toBeDisabled({ timeout: 60000 });
  await expect(page.getByRole("button", { name: "保存当前配置" })).toHaveCount(0);
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(evaluationConfigDrawer).toHaveCount(0);
});
