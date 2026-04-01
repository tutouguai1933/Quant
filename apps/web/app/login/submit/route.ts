/* 这个文件负责处理登录表单并写入会话 cookie。 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { loginAdmin } from "../../../lib/api";
import { normalizeAppPath, SESSION_COOKIE_NAME } from "../../../lib/session";


/* 处理登录提交。 */
export async function POST(request: Request) {
  const formData = await request.formData();
  const username = String(formData.get("username") ?? "admin");
  const password = String(formData.get("password") ?? "");
  const nextPath = normalizeAppPath(formData.get("next")?.toString(), "/strategies");
  const baseUrl = new URL(request.url);

  try {
    const response = await loginAdmin(username, password);
    if (response.error) {
      return NextResponse.redirect(new URL(`/login?state=error&next=${encodeURIComponent(nextPath)}`, baseUrl));
    }

    const cookieStore = await cookies();
    cookieStore.set(SESSION_COOKIE_NAME, response.data.item.token, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
    });

    return NextResponse.redirect(new URL(`${nextPath}?tone=success&title=${encodeURIComponent("登录反馈")}&message=${encodeURIComponent("管理员认证成功，受保护页面已解锁。")}`, baseUrl));
  } catch {
    return NextResponse.redirect(new URL(`/login?state=error&next=${encodeURIComponent(nextPath)}`, baseUrl));
  }
}
