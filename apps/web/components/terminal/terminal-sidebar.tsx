/**
 * 终端侧边栏组件
 * 窄导航栏，包含分组导航和底部系统状态
 * 宽度约 144-160px
 */
"use client";

import Link from "next/link";
import type { ReactNode } from "react";

/* 导航项定义 */
type NavItem = {
  href: string;
  label: string;
  icon?: ReactNode;
  protected?: boolean;
  badge?: string | number;
};

/* 导航分组定义 */
type NavGroup = {
  title: string;
  items: NavItem[];
};

/* 侧边栏属性 */
export type TerminalSidebarProps = {
  currentPath: string;
  isAuthenticated: boolean;
};

/* 导航分组配置 */
const NAV_GROUPS: NavGroup[] = [
  {
    title: "研究",
    items: [
      { href: "/", label: "工作台" },
      { href: "/research", label: "模型训练", protected: true },
      { href: "/backtest", label: "回测训练", protected: true },
      { href: "/evaluation", label: "选币回测", protected: true },
      { href: "/features", label: "因子研究", protected: true },
      { href: "/signals", label: "信号" },
      { href: "/hyperopt", label: "参数优化", protected: true },
      { href: "/analytics", label: "数据分析" },
    ],
  },
  {
    title: "数据与知识",
    items: [
      { href: "/data", label: "数据管理" },
      { href: "/factor-knowledge", label: "因子知识库" },
      { href: "/config", label: "配置管理" },
    ],
  },
  {
    title: "运营",
    items: [
      { href: "/strategies", label: "策略中心", protected: true },
      { href: "/ops", label: "运维监控" },
      { href: "/tasks", label: "任务", protected: true },
    ],
  },
  {
    title: "工具",
    items: [
      { href: "/market", label: "市场" },
      { href: "/balances", label: "余额" },
      { href: "/positions", label: "持仓" },
      { href: "/orders", label: "订单" },
      { href: "/risk", label: "风险", protected: true },
    ],
  },
];

/* 系统状态项 */
const SYSTEM_STATUS = [
  { label: "数据更新", value: "正常", status: "online" as const },
  { label: "控程引擎", value: "3 运行中", status: "online" as const },
  { label: "实盘连接", value: "已连接", status: "online" as const },
  { label: "GPU 使用", value: "--", status: "offline" as const },
];

/* 终端侧边栏组件 */
export function TerminalSidebar({
  currentPath,
  isAuthenticated,
}: TerminalSidebarProps) {
  return (
    <aside className="terminal-sidebar-root hidden lg:flex flex-col h-screen sticky top-0">
      {/* Logo 区域 */}
      <div className="p-4 border-b border-[var(--terminal-border)]">
        <div className="text-[var(--terminal-cyan)] font-semibold text-sm">
          Quant
        </div>
        <div className="text-[var(--terminal-dim)] text-[10px] mt-0.5">
          v0.1
        </div>
      </div>

      {/* 导航区域 */}
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV_GROUPS.map((group) => (
          <div key={group.title} className="mb-2">
            {/* 分组标题 */}
            <div className="terminal-nav-group-title">
              {group.title}
            </div>
            {/* 分组导航项 */}
            {group.items.map((item) => {
              const isActive = currentPath === item.href;
              const isProtected = item.protected && !isAuthenticated;
              const targetHref = isProtected
                ? `/login?next=${encodeURIComponent(item.href)}`
                : item.href;

              return (
                <Link
                  key={item.href}
                  href={targetHref}
                  prefetch={false}
                  className={`terminal-nav-item ${isActive ? "active" : ""}`}
                >
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ml-auto text-[10px] text-[var(--terminal-cyan)]">
                      {item.badge}
                    </span>
                  )}
                  {item.protected && (
                    <span className="ml-auto text-[10px] text-[var(--terminal-dim)]">
                      {isAuthenticated ? "✓" : "🔒"}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* 底部系统状态 */}
      <div className="border-t border-[var(--terminal-border)] p-3">
        {SYSTEM_STATUS.map((status) => (
          <div
            key={status.label}
            className="flex items-center justify-between py-1.5 text-[11px]"
          >
            <span className="text-[var(--terminal-dim)]">{status.label}</span>
            <div className="flex items-center gap-1.5">
              <span className={`terminal-status-dot ${status.status}`} />
              <span className="text-[var(--terminal-muted)]">{status.value}</span>
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
