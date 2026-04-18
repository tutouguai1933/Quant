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

type NavItem = {
  href: string;
  label: string;
  protected: boolean;
  hint: string;
};

const PRIMARY_NAV_ITEMS: NavItem[] = [
  { href: "/", label: "总览", protected: false, hint: "先看当前最该处理的事" },
  { href: "/features", label: "因子", protected: false, hint: "看因子体系和候选评分" },
  { href: "/research", label: "研究", protected: false, hint: "看当前研究状态和配置摘要" },
  { href: "/evaluation", label: "决策", protected: false, hint: "先确认该推进谁" },
  { href: "/strategies", label: "执行", protected: true, hint: "确认执行器和推进动作" },
  { href: "/tasks", label: "运维", protected: true, hint: "处理告警、接管和恢复" },
];

const TOOL_NAV_ITEMS: NavItem[] = [
  { href: "/market", label: "市场", protected: false, hint: "看行情和单币详情" },
  { href: "/balances", label: "余额", protected: false, hint: "查账户余额明细" },
  { href: "/positions", label: "持仓", protected: false, hint: "查当前仓位状态" },
  { href: "/orders", label: "订单", protected: false, hint: "查执行回报和历史" },
  { href: "/risk", label: "风险", protected: true, hint: "查告警事件和规则" },
];

const SUPPLEMENTAL_NAV_ITEMS: NavItem[] = [
  { href: "/data", label: "数据准备", protected: false, hint: "补看研究输入和准备状态" },
  { href: "/backtest", label: "回测验证", protected: false, hint: "补看回测成本和结果" },
  { href: "/signals", label: "信号报告", protected: false, hint: "补看统一研究产物" },
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

          <div className="mt-5 space-y-4">
            <NavSection
              title="主工作区"
              description="默认只保留主线页面，让你先看到判断、执行和风险。"
              ariaLabel="主工作区"
              items={PRIMARY_NAV_ITEMS}
              currentPath={currentPath}
              isAuthenticated={isAuthenticated}
            />

            <NavSection
              title="工具入口"
              description="查明细时再进入，不和主线页面抢第一眼注意力。"
              ariaLabel="工具入口"
              items={TOOL_NAV_ITEMS}
              currentPath={currentPath}
              isAuthenticated={isAuthenticated}
              compact
            />
          </div>

          <Separator className="my-5" />

          <div className="space-y-4">
            <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
              <p className="eyebrow">补充入口</p>
              <div className="mt-3 grid gap-2">
                {SUPPLEMENTAL_NAV_ITEMS.map((item) => {
                  const isActive = currentPath === item.href;

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      prefetch={false}
                      className={[
                        "rounded-xl border px-3 py-3 text-sm transition-colors",
                        isActive
                          ? "border-border bg-background text-foreground"
                          : "border-transparent bg-background/40 text-muted-foreground hover:border-border/70 hover:bg-background/70 hover:text-foreground",
                      ].join(" ")}
                    >
                      <p className="font-medium">{item.label}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.hint}</p>
                    </Link>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-border/60 bg-muted/20 p-4">
              <p className="eyebrow">当前模式</p>
              <p className="text-sm leading-6 text-muted-foreground">
                {isAuthenticated
                  ? "已登录，先在主工作区确认当前判断，再按需要进入工具页查看明细。"
                  : "未登录，先看总览、研究和决策摘要；执行、运维和风险入口会先带你去登录。"}
              </p>
            </div>
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
                  <form action="/logout/submit" method="post">
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
                    <Link href="/login" prefetch={false}>前往登录</Link>
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

type NavSectionProps = {
  title: string;
  description: string;
  ariaLabel: string;
  items: NavItem[];
  currentPath: string;
  isAuthenticated: boolean;
  compact?: boolean;
};

/* 渲染一组同层级导航。 */
function NavSection({
  title,
  description,
  ariaLabel,
  items,
  currentPath,
  isAuthenticated,
  compact = false,
}: NavSectionProps) {
  return (
    <section className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <div className="space-y-1">
        <p className="eyebrow">{title}</p>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>

      <nav className="mt-3 grid gap-2" aria-label={ariaLabel}>
        {items.map((item) => {
          const isActive = currentPath === item.href;
          const target = item.protected && !isAuthenticated ? `/login?next=${encodeURIComponent(item.href)}` : item.href;

          return (
            <Link
              key={item.href}
              href={target}
              prefetch={false}
              className={[
                "rounded-xl border px-3 py-3 transition-colors",
                compact ? "bg-background/70" : "bg-card/80",
                isActive
                  ? "border-primary/40 bg-primary/10 text-foreground"
                  : "border-border/60 text-muted-foreground hover:border-border hover:bg-accent hover:text-accent-foreground",
              ].join(" ")}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-current">{item.label}</p>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">{item.hint}</p>
                </div>
                {item.protected ? (
                  <Badge variant={isAuthenticated ? "success" : "outline"}>
                    {isAuthenticated ? "已解锁" : "需登录"}
                  </Badge>
                ) : null}
              </div>
            </Link>
          );
        })}
      </nav>
    </section>
  );
}
