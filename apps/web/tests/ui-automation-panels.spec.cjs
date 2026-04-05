const { test, expect } = require("@playwright/test");

test.use({
  launchOptions: { executablePath: "/snap/bin/chromium" },
  viewport: { width: 1440, height: 1100 },
});

test("signals and strategies pages show automation summaries", async ({ page }) => {
  const loginResponse = await page.request.post("http://127.0.0.1:9011/api/v1/auth/login", {
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

  await page.goto("http://127.0.0.1:9012/signals", { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("自动化入口"));
  await expect(page.getByText("自动化入口")).toBeVisible();
  await expect(page.getByText("当前模式").first()).toBeVisible();
  await expect(page.getByText("下一步动作").first()).toBeVisible();

  await page.goto("http://127.0.0.1:9012/strategies", { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("自动化判断"));
  await expect(page.getByText("自动化判断")).toBeVisible();
  await expect(page.getByText("自动化推荐").first()).toBeVisible();
  await expect(page.getByText("下一步动作").first()).toBeVisible();
});
