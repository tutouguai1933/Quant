/**
 * 参数面板组件
 * 左侧参数面板容器，用于表单参数展示
 */
"use client";

import type { ReactNode } from "react";

/* 参数面板属性 */
export type ControlPanelProps = {
  /** 面板标题 */
  title: string;
  /** 面板内容 */
  children: ReactNode;
  /** 底部操作区 */
  actions?: ReactNode;
  /** 额外的类名 */
  className?: string;
};

/* 参数面板组件 */
export function ControlPanel({
  title,
  children,
  actions,
  className = "",
}: ControlPanelProps) {
  return (
    <div className={`terminal-control-panel ${className}`}>
      {/* 标题 */}
      <div className="terminal-control-panel-title">
        {title}
      </div>

      {/* 内容区 */}
      <div className="space-y-3">
        {children}
      </div>

      {/* 底部操作区 */}
      {actions && (
        <div className="mt-4 pt-3 border-t border-[var(--terminal-border)]">
          {actions}
        </div>
      )}
    </div>
  );
}
