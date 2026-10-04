/* 首页账户余额：真实金额、明细跳转及错误后的刷新恢复，只读操作。 */
const {test, expect} = require("@playwright/test");
const {WEB_BASE_URL} = require("./test-urls.cjs");
const {loginAsAdmin} = require("./test-auth.cjs");

test("首页首屏显示完整总余额，点击明细跳余额页", async ({page}) => {
  const errors=[];
  page.on("pageerror", e=>errors.push(e.message));
  const pending = page.waitForResponse(r=>r.url().includes("/balances/summary") && r.request().method()==="GET");
  await loginAsAdmin(page, "/");
  const response = await pending;
  expect(response.ok()).toBeTruthy();
  const item = (await response.json()).data;
  expect(item.status).toBe("available");
  await expect(page.getByTestId("home-account-equity")).toBeInViewport();
  await expect(page.getByTestId("home-equity-total")).toContainText(Number(item.total_equity).toFixed(2) + " USDT");
  await expect(page.getByTestId("home-equity-breakdown")).toContainText("合约");
  const html = await page.request.get(WEB_BASE_URL + "/");
  expect(html.ok()).toBeTruthy();
  expect((await html.text()).includes('data-testid="home-account-equity"')).toBeTruthy();
  await page.getByTestId("home-account-equity").getByRole("link", {name: "余额明细"}).click();
  await expect(page).toHaveURL(/\/balances(?:\?.*)?$/);
  await expect(page.getByTestId("balance-account-total")).toContainText("USDT");
  expect(errors).toEqual([]);
});

test("首页读取失败不显示假总额，刷新按钮恢复当前真实余额", async ({page}) => {
  await page.route("**/balances/summary*", route=>route.fulfill({status: 200, json: {
    data:{status:"unavailable",total_equity:null,spot_equity:"12.04",futures_equity:null,
      assets:[],issues:["合约账户读取失败"],scope:"现货 + U本位合约"},error:null,meta:{}
  }}));
  await loginAsAdmin(page, "/");
  await expect(page.getByTestId("home-equity-total")).toContainText("暂不可用");
  await expect(page.getByTestId("home-equity-status")).toContainText("合约账户读取失败");
  await page.unroute("**/balances/summary*");
  await page.getByTestId("home-account-equity").getByRole("button", {name:"刷新余额"}).click();
  await expect(page.getByTestId("home-equity-total")).toContainText("USDT");
  await expect(page.getByTestId("home-equity-status")).toContainText("现货");
});
