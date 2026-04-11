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
  await expect(page.locator("body")).toContainText("候选范围契约", { timeout: renderTimeout });

  const researchHeadline = await readInfoValue(page, "统一说明");
  const researchCandidatePool = await readInfoValue(page, "研究 / dry-run 候选池");
  const researchLiveSubset = await readInfoValue(page, "live 子集");

  await page.goto(`${WEB_BASE_URL}/evaluation`, navigation);
  await expect(page.locator("body")).toContainText("统一范围契约", { timeout: renderTimeout });

  const evaluationHeadline = await readInfoValue(page, "统一范围契约");
  const evaluationCandidatePool = await readInfoValue(page, "研究候选池");
  const evaluationLiveSubset = await readInfoValue(page, "live 子集");

  expect(evaluationHeadline).toBe(researchHeadline);
  expect(evaluationCandidatePool).toBe(researchCandidatePool);
  expect(evaluationLiveSubset).toBe(researchLiveSubset);

  await page.goto(`${WEB_BASE_URL}/strategies`, navigation);
  await expect(page.locator("body")).toContainText(researchHeadline, { timeout: renderTimeout });

  await expect(page.locator("body")).toContainText("候选池摘要", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText(researchCandidatePool);
  await expect(page.locator("body")).toContainText(researchLiveSubset);
});

async function readInfoValue(page, label) {
  const locator = page.locator(`xpath=(//p[normalize-space()="${label}"]/following-sibling::p[1])[1]`);
  await expect(locator).toBeVisible();
  return ((await locator.textContent()) || "").trim();
}
