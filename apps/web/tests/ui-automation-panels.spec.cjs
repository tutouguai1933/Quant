const { test, expect } = require("@playwright/test");
const { API_BASE_URL, WEB_BASE_URL } = require("./test-urls.cjs");

test.use({
  launchOptions: { executablePath: "/snap/bin/chromium" },
  viewport: { width: 1440, height: 1100 },
});

test("signals, strategies and tasks pages show automation summaries", async ({ page }) => {
  const loginResponse = await page.request.post(`${API_BASE_URL}/auth/login`, {
    data: { username: "admin", password: "1933" },
  });
  const loginPayload = await loginResponse.json();
  const token = loginPayload?.data?.item?.token;

  expect(typeof token).toBe("string");
  expect(token.length).toBeGreaterThan(10);

  await page.context().addCookies([
    {
      name: "quant_admin_token",
      value: token,
      domain: "127.0.0.1",
      path: "/",
      httpOnly: false,
      sameSite: "Lax",
    },
  ]);

  await page.goto(`${WEB_BASE_URL}/signals`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("自动化入口"));
  await expect(page.getByText("自动化入口")).toBeVisible();
  await expect(page.getByText("当前模式").first()).toBeVisible();
  await expect(page.getByText("下一步动作").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("自动化判断"));
  await expect(page.getByText("自动化判断")).toBeVisible();
  await expect(page.getByText("自动化推荐").first()).toBeVisible();
  await expect(page.getByText("下一步动作").first()).toBeVisible();
  await expect(page.getByText("研究链入口")).toBeVisible();
  await expect(page.getByText("评估与实验中心").first()).toBeVisible();

  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("回到研究链"));
  await expect(page.getByText("回到研究链")).toBeVisible();
  await expect(page.getByText("去回测工作台")).toBeVisible();
  await expect(page.getByText("去评估与实验中心")).toBeVisible();
  await expect(page.getByText("Kill Switch")).toBeVisible();
});
