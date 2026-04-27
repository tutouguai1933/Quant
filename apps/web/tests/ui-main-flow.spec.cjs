const { test, expect } = require("@playwright/test");
const { getPlaywrightUseOptions } = require("./playwright-browser.cjs");
const { loginAsAdmin } = require("./test-auth.cjs");
const { WEB_BASE_URL } = require("./test-urls.cjs");

test.use(getPlaywrightUseOptions());

test("main research to execution flow stays usable across core workbenches", async ({ page }) => {
  test.setTimeout(120000);
  const navigation = { waitUntil: "commit", timeout: 90000 };
  const renderTimeout = 60000;
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });

  await loginAsAdmin(page, "/signals");

  await expect(page.locator("body")).toContainText("信号", { timeout: renderTimeout });
  await expect(page.locator("body")).not.toContainText("正在切换工作区", { timeout: renderTimeout });
  await page.getByRole("button", { name: "运行 Qlib 信号流水线" }).click();
  await expect
    .poll(async () => (await page.locator("body").textContent()) ?? "", { timeout: renderTimeout })
    .toMatch(/Qlib 信号流水线已进入后台|研究动作已发出|研究任务正在运行，请等当前任务完成后再发起。/);
  await expect(page.locator("body")).toContainText("研究运行状态", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("模板适配判断", { timeout: renderTimeout });
  await page.waitForURL(/\/signals(?:\?|$)/, { timeout: renderTimeout });
  await page.waitForLoadState("domcontentloaded");

  await gotoWorkbench(page, `${WEB_BASE_URL}/research`, navigation);
  await expect(page.locator("body")).toContainText("策略研究工作台", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("研究主动作区", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前研究摘要", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前状态", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前配置摘要", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前产物", { timeout: renderTimeout });
  await expect(page.getByRole("button", { name: "运行研究动作" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看配置摘要" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究说明" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看研究链跳转" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看完整配置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看配置说明" })).toBeVisible();
  await expect(page.getByRole("button", { name: "查看产物详情" })).toBeVisible();
  await expect(page.getByRole("button", { name: "打开实验弹窗" })).toBeVisible();
  await expect(page.getByRole("button", { name: "研究训练" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "研究推理" })).toHaveCount(0);
  await expect(page.locator("body")).not.toContainText("模型目录");
  await expect(page.locator("body")).not.toContainText("训练切分说明");
  await expect(page.locator("body")).not.toContainText("标签目标与止损说明");
  await expect(page.locator("body")).not.toContainText("模型和标签怎么影响结果");
  await page.getByRole("button", { name: "运行研究动作" }).click();
  const researchActionDrawer = page.getByRole("dialog", { name: "运行研究动作" });
  await expect(researchActionDrawer.getByRole("button", { name: "研究训练" })).toBeVisible();
  await expect(researchActionDrawer.getByRole("button", { name: "研究推理" })).toBeVisible();
  await expect(researchActionDrawer.getByRole("link", { name: "回到信号页看研究报告" })).toBeVisible();
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(researchActionDrawer).toHaveCount(0);

  await page.getByRole("button", { name: "查看完整配置" }).click();
  const researchConfigDrawer = page.getByRole("dialog", { name: "研究配置详情" });
  await expect(researchConfigDrawer).toContainText("研究参数配置");
  await page.getByRole("button", { name: "关闭详情抽屉" }).click();
  await expect(researchConfigDrawer).toHaveCount(0);

  await gotoWorkbench(page, `${WEB_BASE_URL}/evaluation`, navigation);
  await expect(page.locator("body")).toContainText("评估与实验中心", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前推荐");
  await expect(page.locator("body")).toContainText("推荐原因");
  await expect(page.locator("body")).toContainText("淘汰原因");
  await expect(page.locator("body")).toContainText("候选范围契约");
  await expect(page.locator("body")).not.toContainText("最近两轮对比");
  await expect(page.locator("body")).not.toContainText("配置差异拆解");

  await gotoWorkbench(page, `${WEB_BASE_URL}/strategies`, navigation);
  await expect(page.locator("body")).toContainText("策略中心", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前仲裁动作");
  await expect(page.locator("body")).toContainText("执行器");

  await gotoWorkbench(page, `${WEB_BASE_URL}/tasks`, navigation);
  await expect(page.locator("body")).toContainText("自动化控制台", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("当前仲裁动作");
  await expect(page.locator("body")).toContainText("自动化模式");
  await expect(page.locator("body")).toContainText("恢复状态");

  await gotoWorkbench(page, `${WEB_BASE_URL}/balances`, navigation);
  await expect(page.locator("body")).toContainText("余额详情", { timeout: renderTimeout });
  await expect(page.locator("body")).toContainText("同步来源", { timeout: renderTimeout });

  await gotoWorkbench(page, `${WEB_BASE_URL}/positions`, navigation);
  await expect(page.locator("body")).toContainText("同步来源", { timeout: renderTimeout });

  await gotoWorkbench(page, `${WEB_BASE_URL}/market/BTCUSDT`, navigation);
  await expect(page.locator("body")).toContainText("本地主图", { timeout: renderTimeout });

  // Filter out expected 502 errors from rapid navigation
  const filteredErrors = errors.filter(e => !e.includes("502"));
  expect(filteredErrors).toEqual([]);
});

async function gotoWorkbench(page, url, navigation) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      await page.goto(url, navigation);
      return;
    } catch (error) {
      const message = String(error);
      if (!message.includes("net::ERR_ABORTED") || attempt === 1) {
        throw error;
      }
      await page.waitForLoadState("domcontentloaded");
    }
  }
}
