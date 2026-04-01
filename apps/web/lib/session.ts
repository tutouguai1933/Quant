/* 这个文件负责读取和管理前端控制面会话令牌。 */

import { cookies } from "next/headers";

import { getAdminSession } from "./api";

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

/* 返回当前 cookie 对应的有效会话状态。 */
export async function getControlSessionState(): Promise<{ token: string; isAuthenticated: boolean }> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";
  if (!token) {
    return { token: "", isAuthenticated: false };
  }

  try {
    const response = await getAdminSession(token);
    if (!response.error) {
      return { token, isAuthenticated: true };
    }
  } catch {
    // 会话校验失败时按未登录处理。
  }

  return { token: "", isAuthenticated: false };
}
