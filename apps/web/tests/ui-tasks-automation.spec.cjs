const { test, expect } = require("@playwright/test");

test.use({
  launchOptions: { executablePath: "/snap/bin/chromium" },
  viewport: { width: 1440, height: 1100 },
});

test("tasks page shows latest automation decision after login", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

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

  await page.goto("http://127.0.0.1:9012/tasks", { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.body.innerText.includes("任务") && !document.body.innerText.includes("正在切换工作区"));

  await expect(page.getByText("本轮自动化判断")).toBeVisible();
  await expect(page.getByText("推荐策略实例")).toBeVisible();
  await expect(page.getByText("派发结果")).toBeVisible();
  await expect(page.getByText("失败原因")).toBeVisible();

  expect(errors).toEqual([]);
});
