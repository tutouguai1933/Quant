/* 读取控制面会话，区分已失效登录与后端暂时不可达，避免错误退出登录。 */

import { cookies } from "next/headers";
import { readSingleParam, normalizeAppPath, SESSION_COOKIE_NAME } from "./session-client";

export { readSingleParam, normalizeAppPath, SESSION_COOKIE_NAME };

/* 返回cookie及后端确认的状态，只有明确失效才要求重新登录。 */
export async function getControlSessionState(): Promise<{
  token: string;
  isAuthenticated: boolean;
  hasSessionCookie: boolean;
  status: "anonymous" | "authenticated" | "expired" | "unavailable";
}> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";
  if (!token) {
    return { token: "", isAuthenticated: false, hasSessionCookie: false, status: "anonymous" };
  }
  const apiBase = process.env.QUANT_API_BASE_URL ?? "http://127.0.0.1:9011/api/v1";
  try {
    const response = await fetch(`${apiBase}/auth/session?token=${encodeURIComponent(token)}`, {
      cache: "no-store", signal: AbortSignal.timeout(5000),
    });
    const body = (await response.json().catch(() => null)) as {
      error?: { code?: string } | null; data?: { item?: unknown };
    } | null;
    if (response.ok && body?.error == null && body?.data?.item) {
      return { token, isAuthenticated: true, hasSessionCookie: true, status: "authenticated" };
    }
    if (response.status === 401 || ["session_not_found", "unauthorized"].includes(body?.error?.code ?? "")) {
      return { token: "", isAuthenticated: false, hasSessionCookie: true, status: "expired" };
    }
  } catch {
    // 短时断网或API重启尚未完成，不等同于令牌失效。
  }
  return { token, isAuthenticated: false, hasSessionCookie: true, status: "unavailable" };
}
