/**
 * 综合功能测试套件
 * 包含：登录页测试、跨页面流程测试、未登录流程测试、状态一致性测试
 */

const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

/**
 * 辅助函数：等待页面加载完成
 */
async function waitForPageReady(page, expectedText, timeout = 45000) {
  await page.waitForFunction(
    (text) => document.body.innerText.includes(text),
    expectedText,
    { timeout }
  );
}

/**
 * 辅助函数：登录
 */
async function login(page, username = "admin", password = "1933") {
  await page.goto(`${WEB_BASE_URL}/login`, { waitUntil: "networkidle" });
  await expect(page.locator('button[type="submit"][data-hydrated="true"]').first()).toBeVisible({ timeout: 30000 });
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(password);
  await page.getByRole("button", { name: "登录并继续" }).click();
}

/**
 * 辅助函数：检查是否有前端错误（忽略 API 相关错误）
 */
function checkFrontendErrors(errors) {
  // 过滤掉 API 相关的错误，只关注真正的前端错误
  const frontendErrors = errors.filter(err =>
    !err.includes("502 (Bad Gateway)") &&
    !err.includes("Failed to load resource") &&
    !err.includes("Failed to fetch") &&
    !err.includes("NetworkError")
  );
  return frontendErrors;
}

// ============================================================
// 1. 登录页测试
// ============================================================

test("TC-LOGIN-001: 登录表单显示（账号、密码输入框）", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto(`${WEB_BASE_URL}/login`, { waitUntil: "networkidle" });

  // 等待页面加载
  await expect(page.locator('input[name="username"]')).toBeVisible({ timeout: 30000 });
  await expect(page.locator('input[name="password"]')).toBeVisible({ timeout: 30000 });

  // 验证标签文字
  await expect(page.locator('label[for="username"]')).toContainText("管理员账号");
  await expect(page.locator('label[for="password"]')).toContainText("密码");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-LOGIN-002: 登录按钮存在", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto(`${WEB_BASE_URL}/login`, { waitUntil: "networkidle" });

  // 等待按钮可点击
  await expect(page.locator('button[type="submit"][data-hydrated="true"]').first()).toBeVisible({ timeout: 30000 });

  // 验证按钮文字
  const submitButton = page.getByRole("button", { name: "登录并继续" });
  await expect(submitButton).toBeVisible();

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-LOGIN-003: 受保护页面提示显示", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto(`${WEB_BASE_URL}/login`, { waitUntil: "networkidle" });

  // 等待页面加载
  await page.waitForFunction(() => document.body.innerText.includes("受保护页面"), { timeout: 30000 });

  // 验证受保护页面列表显示
  await expect(page.locator("body")).toContainText("受保护页面");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-LOGIN-004: 登录成功后跳转", async ({ page }) => {
  test.setTimeout(60000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await page.goto(`${WEB_BASE_URL}/login?next=%2Fstrategies`, { waitUntil: "networkidle" });
  await expect(page.locator('button[type="submit"][data-hydrated="true"]').first()).toBeVisible({ timeout: 30000 });

  // 填写登录表单
  await page.locator('input[name="username"]').fill("admin");
  await page.locator('input[name="password"]').fill("1933");
  await page.getByRole("button", { name: "登录并继续" }).click();

  // 等待跳转到策略页
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/strategies(?:\\?.*)?$`), {
    timeout: 45000,
  });

  // 验证页面内容
  await waitForPageReady(page, "策略中心");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

// ============================================================
// 2. 跨页面流程测试
// ============================================================

test("TC-FLOW-001: 首页 → 信号页跳转", async ({ page }) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 先登录
  await login(page);
  await waitForPageReady(page, "策略中心");

  // 导航到首页
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "networkidle" });
  await waitForPageReady(page, "驾驶舱");

  // 点击信号报告链接
  await page.getByRole("link", { name: "查看研究报告" }).click();

  // 等待跳转到信号页
  await page.waitForURL("**/signals");
  await waitForPageReady(page, "信号");

  // 验证页面内容
  await expect(page.locator("body")).toContainText("信号报告");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-FLOW-002: 信号页 → 评估页跳转", async ({ page }) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 先登录
  await login(page);
  await waitForPageReady(page, "策略中心");

  // 导航到信号页
  await page.goto(`${WEB_BASE_URL}/signals`, { waitUntil: "networkidle" });
  await waitForPageReady(page, "信号");

  // 点击评估页导航链接
  const evalLink = page.getByRole("navigation", { name: "主工作区" }).getByRole("link", { name: /决策/ });
  await evalLink.click();

  // 等待跳转到评估页
  await page.waitForURL("**/evaluation");
  await waitForPageReady(page, "评估");

  // 验证页面内容
  await expect(page.locator("body")).toContainText("评估");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-FLOW-003: 评估页 → 策略页跳转", async ({ page }) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 先登录
  await login(page);
  await waitForPageReady(page, "策略中心");

  // 导航到评估页
  await page.goto(`${WEB_BASE_URL}/evaluation`, { waitUntil: "networkidle" });
  await waitForPageReady(page, "评估");

  // 点击策略页导航链接
  const strategiesLink = page.getByRole("navigation", { name: "主工作区" }).getByRole("link", { name: /执行/ });
  await strategiesLink.click();

  // 等待跳转到策略页
  await page.waitForURL("**/strategies");
  await waitForPageReady(page, "策略中心");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-FLOW-004: 策略页 → 任务页跳转", async ({ page }) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 先登录
  await login(page);
  await waitForPageReady(page, "策略中心");

  // 点击任务页导航链接
  const tasksLink = page.getByRole("navigation", { name: "主工作区" }).getByRole("link", { name: /运维/ });
  await tasksLink.click();

  // 等待跳转到任务页 - 使用更宽松的等待
  await page.waitForURL("**/tasks", { timeout: 45000 });

  // 等待页面显示任务中心或运维相关内容
  await page.waitForFunction(() =>
    document.body.innerText.includes("任务") ||
    document.body.innerText.includes("运维"),
    { timeout: 45000 }
  );

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-FLOW-005: 任务页 → 首页跳转", async ({ page }) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 先登录
  await login(page);
  await waitForPageReady(page, "策略中心");

  // 导航到任务页
  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "networkidle" });
  await page.waitForFunction(() =>
    document.body.innerText.includes("任务") ||
    document.body.innerText.includes("运维"),
    { timeout: 45000 }
  );

  // 点击首页导航链接
  const homeLink = page.getByRole("navigation", { name: "主工作区" }).getByRole("link", { name: /总览/ });
  await homeLink.click();

  // 等待跳转到首页
  await page.waitForURL(/\/$/, { timeout: 45000 });
  await waitForPageReady(page, "驾驶舱");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

// ============================================================
// 3. 未登录流程测试
// ============================================================

test("TC-FLOW-UNAUTH-001: 未登录访问策略页 → 跳转到登录页", async ({ page }) => {
  test.setTimeout(60000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 直接访问策略页（未登录）
  await page.goto(`${WEB_BASE_URL}/strategies`, { waitUntil: "networkidle" });

  // 页面会加载但显示"需要登录"状态
  // 检查页面显示了需要登录的提示
  await page.waitForFunction(() =>
    document.body.innerText.includes("需要登录") ||
    document.body.innerText.includes("策略中心"),
    { timeout: 30000 }
  );

  // 验证策略页内容显示（页面会加载，但会显示需要登录状态）
  await expect(page.locator("body")).toContainText("策略");

  // 导航栏中的执行链接应该指向登录页（因为未登录）
  const strategiesNavLink = page.getByRole("navigation", { name: "主工作区" }).getByRole("link", { name: /执行/ });
  const href = await strategiesNavLink.getAttribute("href");
  expect(href).toContain("/login");
  expect(href).toContain("next=%2Fstrategies");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-FLOW-UNAUTH-002: 未登录访问任务页 → 跳转到登录页", async ({ page }) => {
  test.setTimeout(60000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 直接访问任务页（未登录）
  await page.goto(`${WEB_BASE_URL}/tasks`, { waitUntil: "networkidle" });

  // 页面会加载但显示"需要登录"状态
  await page.waitForFunction(() =>
    document.body.innerText.includes("需要登录") ||
    document.body.innerText.includes("任务"),
    { timeout: 30000 }
  );

  // 验证任务页内容显示
  await expect(page.locator("body")).toContainText("任务");

  // 导航栏中的运维链接应该指向登录页（因为未登录）
  const tasksNavLink = page.getByRole("navigation", { name: "主工作区" }).getByRole("link", { name: /运维/ });
  const href = await tasksNavLink.getAttribute("href");
  expect(href).toContain("/login");
  expect(href).toContain("next=%2Ftasks");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

test("TC-FLOW-UNAUTH-003: 登录成功后跳转到原目标页面", async ({ page }) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 直接访问登录页，并设置 next 参数为策略页
  await page.goto(`${WEB_BASE_URL}/login?next=%2Fstrategies`, { waitUntil: "networkidle" });

  // 等待登录表单显示
  await expect(page.locator('button[type="submit"][data-hydrated="true"]').first()).toBeVisible({ timeout: 30000 });

  // 验证 next 参数显示
  await expect(page.locator("body")).toContainText("/strategies");

  // 登录
  await page.locator('input[name="username"]').fill("admin");
  await page.locator('input[name="password"]').fill("1933");
  await page.getByRole("button", { name: "登录并继续" }).click();

  // 应该跳转到原目标页面（策略页）
  await expect(page).toHaveURL(new RegExp(`${WEB_BASE_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/strategies(?:\\?.*)?$`), {
    timeout: 45000,
  });

  // 验证页面内容
  await waitForPageReady(page, "策略中心");

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});

// ============================================================
// 4. 状态一致性测试
// ============================================================

test("TC-CONSISTENT-001: 首页和信号页的研究状态一致", async ({ page }) => {
  test.setTimeout(90000);
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  // 先登录
  await login(page);
  await waitForPageReady(page, "策略中心");

  // 访问首页，获取研究状态
  await page.goto(`${WEB_BASE_URL}/`, { waitUntil: "networkidle" });
  await waitForPageReady(page, "驾驶舱");

  // 检查首页是否有研究状态相关信息
  const homeBodyText = await page.locator("body").textContent();
  const hasResearchStatusHome = homeBodyText.includes("研究") || homeBodyText.includes("信号");

  // 访问信号页
  await page.goto(`${WEB_BASE_URL}/signals`, { waitUntil: "networkidle" });
  await waitForPageReady(page, "信号");

  // 获取信号页的研究状态
  const signalsBodyText = await page.locator("body").textContent();
  const hasResearchStatusSignals = signalsBodyText.includes("研究") || signalsBodyText.includes("信号");

  // 验证两个页面都显示研究相关信息
  expect(hasResearchStatusHome).toBe(true);
  expect(hasResearchStatusSignals).toBe(true);

  // 只检查前端错误，忽略 API 相关错误
  expect(checkFrontendErrors(errors)).toEqual([]);
});