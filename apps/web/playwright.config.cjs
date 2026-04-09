/* 这个文件负责收口浏览器测试的并发和超时，避免工作台流式页面在本地被并发压垮。 */

const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: Number(process.env.PLAYWRIGHT_WORKERS || 1),
  timeout: 120000,
  expect: {
    timeout: 60000,
  },
});
