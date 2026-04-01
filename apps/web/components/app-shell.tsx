/* 这个文件负责统一的控制面外壳和主导航。 */

import type { ReactNode } from "react";


type AppShellProps = {
  title: string;
  subtitle: string;
  currentPath: string;
  isAuthenticated: boolean;
  children: ReactNode;
};

const NAV_ITEMS = [
  { href: "/", label: "驾驶舱", protected: false },
  { href: "/signals", label: "信号", protected: false },
  { href: "/market", label: "市场", protected: false },
  { href: "/strategies", label: "策略", protected: true },
  { href: "/balances", label: "余额", protected: false },
  { href: "/positions", label: "持仓", protected: false },
  { href: "/orders", label: "订单", protected: false },
  { href: "/risk", label: "风险", protected: true },
  { href: "/tasks", label: "任务", protected: true },
  { href: "/login", label: "登录", protected: false },
];

/* 渲染统一页面壳层。 */
export function AppShell({ title, subtitle, currentPath, isAuthenticated, children }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-block">
          <p className="eyebrow">Quant Control Plane</p>
          <h1>单用户运维驾驶舱</h1>
          <p>把信号、执行、风险和任务收敛到一条清晰的控制动线。</p>
        </div>

        <nav className="app-nav" aria-label="主导航">
          {NAV_ITEMS.map((item) => {
            const isActive = currentPath === item.href;
            const target = item.protected && !isAuthenticated ? `/login?next=${encodeURIComponent(item.href)}` : item.href;

            return (
              <a
                key={item.href}
                href={target}
                className={isActive ? "nav-link nav-link-active" : "nav-link"}
              >
                <span>{item.label}</span>
                {item.protected ? <span className="nav-tag">{isAuthenticated ? "已解锁" : "需登录"}</span> : null}
              </a>
            );
          })}
        </nav>

        <div className="sidebar-note">
          <p className="eyebrow">当前模式</p>
          <p>{isAuthenticated ? "已登录，可直接执行受保护操作。" : "未登录，先进入 Login 完成管理员认证。"}</p>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div>
            <p className="eyebrow">当前页面</p>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>

          <div className="topbar-actions">
            <span className={isAuthenticated ? "session-pill session-pill-live" : "session-pill"}>
              {isAuthenticated ? "会话已就绪" : "需要登录"}
            </span>

            {isAuthenticated ? (
              <form action="/logout" method="post">
                <button type="submit" className="secondary-button">
                  退出登录
                </button>
              </form>
            ) : (
              <a className="secondary-button button-link" href="/login">
                前往登录
              </a>
            )}
          </div>
        </header>

        <main className="page-stack">{children}</main>
      </div>
    </div>
  );
}
