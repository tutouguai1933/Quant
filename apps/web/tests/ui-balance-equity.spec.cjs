/* 验证完整账户总额与失败提示，所有操作只读取账户，不触发交易。 */
const { test, expect } = require("@playwright/test");
const { WEB_BASE_URL } = require("./test-urls.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");

test("真实余额总额含现货和合约，零头及初始HTML完整", async ({page}) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const pending = page.waitForResponse(r => r.url().includes("/balances/summary") && r.request().method() === "GET");
  await loginAsAdmin(page, "/balances");
  const response = await pending;
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  const item = body.data;
  expect(item.status).toBe("available");
  expect(Number(item.total_equity)).toBeCloseTo(Number(item.spot_equity) + Number(item.futures_equity), 6);
  await expect(page.getByTestId("balance-account-total")).toContainText(Number(item.total_equity).toFixed(2) + " USDT");
  await expect(page.getByRole("cell", { name: "DOGE", exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: "SHIB", exact: true })).toBeVisible();
  await expect(page.getByTestId("balance-equity-status")).toContainText("U本位合约");
  const html = await page.request.get(WEB_BASE_URL + "/balances");
  expect(html.ok()).toBeTruthy();
  expect((await html.text()).includes('data-testid="balance-equity-status"')).toBeTruthy();
  expect(errors).toEqual([]);
});

test("账户读取失败时不显示部分余额为总额，刷新恢复真实值", async ({page}) => {
  await loginAsAdmin(page, "/balances");
  await expect(page.getByTestId("balance-account-total")).toContainText("USDT");
  await page.route("**/balances/summary*", route => route.fulfill({status: 200, json: {
    data: { status: "unavailable", total_equity: null, spot_equity: "12.04", futures_equity: null,
      assets: [], issues: ["合约账户读取失败"], scope: "现货 + U本位合约" },
    error: null, meta: {}
  }}));
  await page.reload();
  await expect(page.getByTestId("balance-account-total")).toContainText("暂不可用");
  await expect(page.getByTestId("balance-equity-status")).toContainText("合约账户读取失败");
  await page.unroute("**/balances/summary*");
  await page.reload();
  await expect(page.getByTestId("balance-account-total")).toContainText("USDT");
});

test("旧分类接口失败仍保留完整资产，未登录接口不泄露总额", async ({page}) => {
  await page.route("**/api/control/balances", route => route.fulfill({
    status: 503, json: {data: null, error: {code: "unavailable", message: "分类信息暂不可用"}, meta: {}}
  }));
  await loginAsAdmin(page, "/balances");
  await expect(page.getByTestId("balance-account-total")).toContainText("USDT");
  await expect(page.getByRole("cell", {name: "DOGE", exact: true})).toBeVisible();
  await expect(page.getByRole("cell", {name: "SHIB", exact: true})).toBeVisible();
  const card = page.getByText("现货可交易价值", {exact: true}).locator("..");
  await expect(card).toContainText("暂不可用");
  const response = await page.request.get(WEB_BASE_URL + "/api/control/balances/summary", {headers: {authorization: "Bearer invalid-check-token"}});
  const body = await response.json();
  expect(body.data).toBeNull();
  expect(body.error.code).toBe("unauthorized");
});
