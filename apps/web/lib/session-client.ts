/* 这个文件负责处理应用路径规范化，不依赖 next/headers，可以在客户端组件中安全导入。 */

export const SESSION_COOKIE_NAME = "quant_admin_token";

const KNOWN_APP_PATHS = new Set([
  "/",
  "/login",
  "/signals",
  "/market",
  "/data",
  "/features",
  "/research",
  "/backtest",
  "/evaluation",
  "/strategies",
  "/balances",
  "/positions",
  "/orders",
  "/risk",
  "/tasks",
]);

/* 读取搜索参数里的单值字符串。 */
export function readSingleParam(value?: string | string[]): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

/* 只允许站内已知页面作为回跳目标。 */
export function normalizeAppPath(value?: string | string[], fallback = "/"): string {
  const resolved = readSingleParam(value);
  if (!resolved.startsWith("/") || resolved.startsWith("//")) {
    return fallback;
  }
  return KNOWN_APP_PATHS.has(resolved) ? resolved : fallback;
}