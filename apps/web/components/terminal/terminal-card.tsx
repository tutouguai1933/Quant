/**
 * 终端卡片组件
 * 所有深色卡片的基础外观
 * 统一圆角、边框、背景
 */

import type { ReactNode } from "react";

/* 终端卡片属性 */
export type TerminalCardProps = {
  /** 卡片标题 */
  title?: string;
  /** 额外操作区 */
  actions?: ReactNode;
  /** 卡片内容 */
  children: ReactNode;
  /** 额外的类名 */
  className?: string;
};

/* 终端卡片组件 */
export function TerminalCard({
  title,
  actions,
  children,
  className = "",
}: TerminalCardProps) {
  return (
    <div className={`terminal-card ${className}`}>
      {/* 卡片头部 */}
      {(title || actions) && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--terminal-border)]">
          {title && (
            <h3 className="text-[14px] font-bold text-[var(--terminal-text)]">
              {title}
            </h3>
          )}
          {actions && (
            <div className="flex items-center gap-2">
              {actions}
            </div>
          )}
        </div>
      )}

      {/* 卡片内容 */}
      <div className="p-4">
        {children}
      </div>
    </div>
  );
}

/* 紧凑卡片变体 - 无边框标题 */
export type TerminalCardCompactProps = {
  children: ReactNode;
  className?: string;
};

/* 紧凑卡片组件 */
export function TerminalCardCompact({
  children,
  className = "",
}: TerminalCardCompactProps) {
  return (
    <div className={`terminal-card p-3 ${className}`}>
      {children}
    </div>
  );
}
