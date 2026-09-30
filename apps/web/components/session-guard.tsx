/* 会话守卫：页面切换、重新聚焦和鉴权失败时恢复登录入口，避免展示假数据。 */

"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

/* 在保留当前页面地址的同时，处理后台部署或会话过期后的重新登录。 */
export function SessionGuard() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!pathname || pathname === "/login" || pathname.startsWith("/logout")) {
      return;
    }
    let cancelled = false;
    let pending = false;

    /* 已确认令牌失效时返回登录，保留用户正在查看的页面。 */
    const redirectToLogin = () => {
      if (!cancelled) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    };

    /* 复核当前cookie，网络不可达时等待恢复，不重复发出并发请求。 */
    const checkSession = async () => {
      if (pending || cancelled || document.visibilityState === "hidden") return;
      pending = true;
      try {
        const response = await fetch("/api/control/session", {
          cache: "no-store", signal: AbortSignal.timeout(5000),
        });
        const data = await response.json();
        if (!cancelled && data.status === "expired") {
          redirectToLogin();
        }
      } catch {
        // 会话检查暂时不可达时保持页面，等待下一次聚焦或周期检查。
      } finally {
        pending = false;
      }
    };

    void checkSession();
    const timer = window.setInterval(() => void checkSession(), 60000);
    window.addEventListener("focus", checkSession);
    document.addEventListener("visibilitychange", checkSession);
    window.addEventListener("quant:session-expired", redirectToLogin);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener("focus", checkSession);
      document.removeEventListener("visibilitychange", checkSession);
      window.removeEventListener("quant:session-expired", redirectToLogin);
    };
  }, [pathname, router]);

  return null;
}
