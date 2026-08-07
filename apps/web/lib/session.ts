/* 这个文件负责读取和管理前端控制面会话令牌。 */

import { cookies } from "next/headers";
import { readSingleParam, normalizeAppPath, SESSION_COOKIE_NAME } from "./session-client";

export { readSingleParam, normalizeAppPath, SESSION_COOKIE_NAME };

/* 返回当前 cookie 对应的页面会话状态，cookie 存在且后端校验有效才算登录。 */
export async function getControlSessionState(): Promise<{
  token: string;
  isAuthenticated: boolean;
  hasSessionCookie: boolean;
}> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";
  const hasSessionCookie = token.length > 0;
  if (!hasSessionCookie) {
    return { token: "", isAuthenticated: false, hasSessionCookie: false };
  }
  // 调后端校验 token 有效性（绕过代理直连 api）
  const apiBase = process.env.QUANT_API_BASE_URL ?? "http://127.0.0.1:9011/api/v1";
  try {
    const res = await fetch(`${apiBase}/auth/session?token=${encodeURIComponent(token)}`, {
      cache: "no-store",
    });
    // 后端对无效 token 也返回 HTTP 200，错误在响应体 error 字段里，需要解析判断
    const body = (await res.json().catch(() => null)) as { error?: unknown } | null;
    const isValid = res.ok && body != null && body.error == null;
    if (isValid) {
      return { token, isAuthenticated: true, hasSessionCookie: true };
    }
    return { token: "", isAuthenticated: false, hasSessionCookie: true };
  } catch {
    // api 不可达时保守处理：视为未登录，避免显示假数据
    return { token: "", isAuthenticated: false, hasSessionCookie: true };
  }
}