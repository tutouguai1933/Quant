/**
 * 终端外壳组件
 * 提供窄侧栏、顶部标题、主体区域的统一布局
 * 替代现有的大 AppShell，更接近参考图的紧凑风格
 */
"use client";

import type { ReactNode } from "react";
import { TerminalSidebar } from "./terminal-sidebar";
import { TerminalPageHeader } from "./terminal-page-header";
import { useWebSocket } from "../../lib/websocket-context";

/* 终端外壳属性 */
export type TerminalShellProps = {
  /** 面包屑路径，如 "研究 / 模型训练" */
  breadcrumb: string;
  /** 页面标题 */
  title: string;
  /** 页面副标题 */
  subtitle: string;
  /** 当前路由路径 */
  currentPath: string;
  /** 是否已登录 */
  isAuthenticated: boolean;
  /** 页面内容 */
  children: ReactNode;
};

/* 终端外壳组件 - 提供统一的终端布局 */
export function TerminalShell({
  breadcrumb,
  title,
  subtitle,
  currentPath,
  isAuthenticated,
  children,
}: TerminalShellProps) {
  const { status: wsStatus } = useWebSocket();

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] text-[var(--terminal-text)]">
      {/* WebSocket 连接状态横幅 */}
      {wsStatus !== "connected" && (
        <div className="fixed top-0 left-0 right-0 z-[9998] bg-amber-500/90 px-4 py-2 text-center text-sm text-white">
          {wsStatus === "connecting" ? "实时推送正在连接..." : "实时推送已断开，正在重连..."}
        </div>
      )}

      {/* 主布局：左侧导航 + 右侧内容 */}
      <div className="grid min-h-screen lg:grid-cols-[160px_minmax(0,1fr)]">
        {/* 左侧导航 */}
        <TerminalSidebar
          currentPath={currentPath}
          isAuthenticated={isAuthenticated}
        />

        {/* 右侧内容区 */}
        <div className="flex flex-col">
          {/* 顶部页面头 */}
          <TerminalPageHeader
            breadcrumb={breadcrumb}
            title={title}
            subtitle={subtitle}
          />

          {/* 主内容区 */}
          <main className="flex-1 p-4 lg:p-5">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
