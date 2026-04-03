/* 这个脚本负责复用已经启动的 Chromium 调试端口，对关键页面执行 Lighthouse 审查。 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const ROOT = path.resolve(__dirname, "..");
const URLS = [
  "http://127.0.0.1:9012/signals",
  "http://127.0.0.1:9012/market/BTCUSDT",
];
const DEBUG_PORT = process.env.LIGHTHOUSE_PORT ?? "9223";
const LIGHTHOUSE_OUTPUT_DIR = path.join(os.tmpdir(), "quant-lighthouse-audit");

async function main() {
  fs.mkdirSync(LIGHTHOUSE_OUTPUT_DIR, { recursive: true });
  await waitForChrome();

  for (const url of URLS) {
    const fileName = url.includes("/market/") ? "market.json" : "signals.json";
    const outputPath = path.join(LIGHTHOUSE_OUTPUT_DIR, fileName);
    const result = await runLighthouse(url, outputPath);
    const accessibility = Number(result.categories.accessibility.score ?? 0);
    const bestPractices = Number(result.categories["best-practices"].score ?? 0);
    assert.equal(accessibility, 1, `${url} accessibility score should be 1`);
    assert.equal(bestPractices, 1, `${url} best-practices score should be 1`);
    console.log(`LIGHTHOUSE ${url} => accessibility=${accessibility} bestPractices=${bestPractices}`);
  }
}

/* 等待已有 Chromium 调试端口就绪。 */
async function waitForChrome() {
  const deadline = Date.now() + 5_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
      if (response.ok) {
        return;
      }
    } catch {
      // 调试端口尚未启动时继续等待。
    }
    await sleep(200);
  }

  throw new Error(
    `Chromium 调试端口 ${DEBUG_PORT} 未就绪。请先启动浏览器，例如：/snap/bin/chromium --headless=new --remote-debugging-port=${DEBUG_PORT} --user-data-dir=/tmp/lighthouse-chrome http://127.0.0.1:9012/signals`,
  );
}

/* 执行单个 Lighthouse 审查。 */
async function runLighthouse(url, outputPath) {
  await runCommand("pnpm", [
    "exec",
    "lighthouse",
    url,
    "--quiet",
    `--port=${DEBUG_PORT}`,
    "--disable-storage-reset",
    "--only-categories=accessibility,best-practices",
    "--output=json",
    `--output-path=${outputPath}`,
  ]);
  return JSON.parse(fs.readFileSync(outputPath, "utf8"));
}

/* 以 Promise 方式等待子进程结束。 */
function runCommand(command, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: ROOT,
      stdio: "ignore",
    });

    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(`${command} ${args.join(" ")} failed with code ${code}`));
    });
  });
}

/* 等待指定毫秒。 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
