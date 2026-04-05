/* 这个文件负责统一的控制面外壳和主导航。 */

import Link from "next/link";
import type { ReactNode } from "react";

import { FormSubmitButton } from "./form-submit-button";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Separator } from "./ui/separator";

type AppShellProps = {
  title: string;
  subtitle: string;
  currentPath: string;
  isAuthenticated: boolean;
  children: ReactNode;
};

const NAV_ITEMS = [
  { href: "/", label: "驾驶舱", protected: false },
  { href: "/data", label: "数据", protected: false },
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
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto grid min-h-screen max-w-[1680px] grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="border-b border-border/60 bg-card/60 px-5 py-6 backdrop-blur lg:border-b-0 lg:border-r">
          <div className="rounded-2xl border border-border/70 bg-card/90 p-5 shadow-[0_20px_40px_rgba(2,6,23,0.28)]">
            <p className="eyebrow">Quant Terminal</p>
            <h1 className="text-xl font-semibold tracking-tight">研究执行终端</h1>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              先看研究结论，再决定下一步动作，把判断、执行和结果收在同一条终端动线里。
            </p>
          </div>

          <nav className="mt-5 grid gap-2" aria-label="主导航">
            {NAV_ITEMS.map((item) => {
              const isActive = currentPath === item.href;
              const target = item.protected && !isAuthenticated ? `/login?next=${encodeURIComponent(item.href)}` : item.href;

              return (
                <Link
                  key={item.href}
                  href={target}
                  className={[
                    "flex items-center justify-between rounded-xl border px-3 py-3 text-sm transition-colors",
                    isActive
                      ? "border-primary/40 bg-primary/10 text-foreground"
                      : "border-border/60 bg-muted/25 text-muted-foreground hover:border-border hover:bg-accent hover:text-accent-foreground",
                  ].join(" ")}
                >
                  <span>{item.label}</span>
                  {item.protected ? (
                    <Badge variant={isAuthenticated ? "success" : "outline"}>
                      {isAuthenticated ? "已解锁" : "需登录"}
                    </Badge>
                  ) : null}
                </Link>
              );
            })}
          </nav>

          <Separator className="my-5" />

          <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
            <p className="eyebrow">当前模式</p>
            <p className="text-sm leading-6 text-muted-foreground">
              {isAuthenticated ? "已登录，优先看左侧决策区，再去右侧执行区确认动作。" : "未登录，先进入登录页解锁策略、风险和任务控制区。"}
            </p>
          </div>
        </aside>

        <div className="px-4 py-5 sm:px-6 lg:px-8">
          <header className="mb-6 rounded-2xl border border-border/70 bg-card/85 px-5 py-5 shadow-[0_18px_44px_rgba(2,6,23,0.24)] backdrop-blur">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="space-y-2">
                <p className="eyebrow">当前工作区</p>
                <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
                <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{subtitle}</p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Badge variant={isAuthenticated ? "success" : "warning"} className="px-3 py-1 text-[11px]">
                  {isAuthenticated ? "会话已就绪 / 7 天保持" : "需要登录"}
                </Badge>

                {isAuthenticated ? (
                  <form action="/logout" method="post">
                    <FormSubmitButton
                      type="submit"
                      variant="outline"
                      idleLabel="退出登录"
                      pendingLabel="退出中…"
                      pendingHint="会话正在清理，页面会自动返回未登录状态。"
                    />
                  </form>
                ) : (
                  <Button asChild variant="outline">
                    <Link href="/login">前往登录</Link>
                  </Button>
                )}
              </div>
            </div>
          </header>

          <main className="space-y-5">{children}</main>
        </div>
      </div>
    </div>
  );
}
