const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test.use(getPlaywrightUseOptions());

test("research evaluation and strategies pages share one candidate scope contract", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;

  await loginAsAdmin(page, "/research");
  await expect(page.getByRole("button", { name: "查看配置说明" })).toBeVisible({ timeout: renderTimeout });
  await page.getByRole("button", { name: "查看配置说明" }).click();
  const researchConfigDrawer = page.getByRole("dialog", { name: "研究配置说明" });
  await expect(researchConfigDrawer).toContainText("候选范围契约", { timeout: renderTimeout });

  const researchHeadline = await readInfoValue(researchConfigDrawer, "统一说明");
  const researchCandidateBasket = await readInfoValue(researchConfigDrawer, "研究 / dry-run 候选篮子");
  const researchExecutionBasket = await readInfoValue(researchConfigDrawer, "执行篮子");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(researchConfigDrawer).toHaveCount(0);

  await page.goto(`${WEB_BASE_URL}/evaluation`, navigation);
  await expect(page.getByRole("button", { name: "查看推荐详情" })).toBeVisible({ timeout: renderTimeout });
  await page.getByRole("button", { name: "查看推荐详情" }).click();
  const evaluationCandidateDrawer = page.getByRole("dialog", { name: "查看推荐详情" });
  await expect(evaluationCandidateDrawer).toContainText(researchHeadline);
  await expect(evaluationCandidateDrawer).toContainText(researchCandidateBasket);
  await expect(evaluationCandidateDrawer).toContainText(researchExecutionBasket);
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(evaluationCandidateDrawer).toHaveCount(0);

  await page.goto(`${WEB_BASE_URL}/strategies`, navigation);
  await expect(page.locator("body")).toContainText("当前候选可推进性", { timeout: renderTimeout });
  await page.getByRole("button", { name: "查看候选篮子" }).click();
  const candidateDrawer = page.getByRole("dialog", { name: "候选篮子详情" });
  await expect(candidateDrawer).toContainText(researchHeadline, { timeout: renderTimeout });
  await expect(candidateDrawer).toContainText(researchCandidateBasket);
  await expect(candidateDrawer).toContainText(researchExecutionBasket);
});

async function readInfoValue(scope, label) {
  const locator = scope.locator(`xpath=(//p[normalize-space()="${label}"]/following-sibling::p[1])[1]`);
  await expect(locator).toBeVisible();
  return ((await locator.textContent()) || "").trim();
}
