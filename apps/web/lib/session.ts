/* 这个文件负责读取和管理前端控制面会话令牌。 */

import { cookies } from "next/headers";

export const SESSION_COOKIE_NAME = "quant_admin_token";
const KNOWN_APP_PATHS = new Set(["/", "/login", "/signals", "/market", "/strategies", "/balances", "/positions", "/orders", "/risk", "/tasks"]);

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

/* 返回当前 cookie 对应的页面会话状态，页面只看 cookie 是否存在。 */
export async function getControlSessionState(): Promise<{ token: string; isAuthenticated: boolean }> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";
  return {
    token,
    isAuthenticated: token.length > 0,
  };
}
