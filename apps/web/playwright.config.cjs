/* 这个文件负责收口浏览器测试的并发和超时，避免工作台流式页面在本地被并发压垮。 */

const { defineConfig, devices } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: Number(process.env.PLAYWRIGHT_WORKERS || 1),
  timeout: 300000, // 5 minutes overall timeout
  expect: {
    timeout: 60000,
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        headless: true,
        launchOptions: {
          executablePath: process.env.CHROMIUM_PATH || "/home/djy/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome",
        },
        actionTimeout: 60000,
        navigationTimeout: 120000, // 2 minutes for slow dev server
      },
    },
  ],
});
