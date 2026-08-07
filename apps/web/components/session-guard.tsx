/* 会话守卫组件：cookie 存在但后端校验失败时，把页面跳转到登录页，避免误判已登录后展示假数据。 */

"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

/* 会话守卫 - 挂在根布局里，监听路由变化并做失效会话跳转。 */
export function SessionGuard() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    // 登录/登出相关页面不跳转，避免死循环
    if (!pathname || pathname === "/login" || pathname.startsWith("/logout")) {
      return;
    }
    let cancelled = false;
    fetch("/api/control/session", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        // 只有 cookie 存在但后端校验失败才跳登录；没有 cookie 时保持匿名浏览行为
        if (data && data.hasSessionCookie && !data.isAuthenticated) {
          router.replace(`/login?next=${encodeURIComponent(pathname)}`);
        }
      })
      .catch(() => {
        // 会话接口不可达时保持现状，不做跳转
      });
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  return null;
}
