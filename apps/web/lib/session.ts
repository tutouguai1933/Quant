/* 这个文件负责读取和管理前端控制面会话令牌。 */

import { cookies } from "next/headers";
import { readSingleParam, normalizeAppPath, SESSION_COOKIE_NAME } from "./session-client";

export { readSingleParam, normalizeAppPath, SESSION_COOKIE_NAME };

/* 返回当前 cookie 对应的页面会话状态，页面只看 cookie 是否存在。 */
export async function getControlSessionState(): Promise<{ token: string; isAuthenticated: boolean }> {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";
  return {
    token,
    isAuthenticated: token.length > 0,
  };
}