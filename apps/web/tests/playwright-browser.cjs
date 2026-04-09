/* 这个文件负责统一管理 Playwright 浏览器启动参数，默认优先使用 Playwright 自带浏览器。 */

function getPlaywrightUseOptions() {
  const executablePath = (process.env.PLAYWRIGHT_EXECUTABLE_PATH || "").trim();
  return {
    viewport: { width: 1440, height: 1100 },
    launchOptions: executablePath ? { executablePath } : {},
  };
}

module.exports = {
  getPlaywrightUseOptions,
};
