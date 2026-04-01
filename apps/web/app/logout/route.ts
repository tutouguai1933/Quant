/* 这个文件负责处理退出登录请求。 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { logoutAdmin } from "../../lib/api";
import { SESSION_COOKIE_NAME } from "../../lib/session";


/* 处理退出登录。 */
export async function POST(request: Request) {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "";

  if (token) {
    try {
      await logoutAdmin(token);
    } catch {
      // 即使 API 退出失败，也优先清掉本地会话。
    }
  }

  cookieStore.delete(SESSION_COOKIE_NAME);
  return NextResponse.redirect(new URL("/login?tone=info&title=退出成功&message=当前会话已经清除。", request.url));
}
