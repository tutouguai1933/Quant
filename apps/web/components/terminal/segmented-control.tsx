/**
 * 分段控制组件
 * 用于 tabs/chip 式开关选择
 */
"use client";

import type { ReactNode } from "react";

/* 分段控制属性 */
export type SegmentedControlProps = {
  /** 当前值 */
  value: string;
  /** 值变化回调 */
  onChange: (value: string) => void;
  /** 选项列表 */
  options: Array<{ value: string; label: string; icon?: ReactNode }>;
  /** 是否禁用 */
  disabled?: boolean;
  /** 尺寸：small=紧凑, medium=默认 */
  size?: "small" | "medium";
  /** 额外的类名 */
  className?: string;
};

/* 分段控制组件 */
export function SegmentedControl({
  value,
  onChange,
  options,
  disabled = false,
  size = "medium",
  className = "",
}: SegmentedControlProps) {
  const sizeClasses = {
    small: "text-[11px] py-1.5 px-2",
    medium: "text-[12px] py-2 px-3",
  };

  return (
    <div
      className={`inline-flex rounded-md border border-[var(--terminal-border)] bg-[var(--terminal-panel-deep)] ${className}`}
    >
      {options.map((option) => {
        const isActive = value === option.value;

        return (
          <button
            key={option.value}
            type="button"
            onClick={() => !disabled && onChange(option.value)}
            disabled={disabled}
            className={`
              ${sizeClasses[size]}
              font-medium
              transition-all
              duration-150
              ${isActive
                ? "bg-[var(--terminal-cyan)] text-[var(--terminal-bg)]"
                : "text-[var(--terminal-muted)] hover:text-[var(--terminal-text)]"
              }
              ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
              first:rounded-l-md
              last:rounded-r-md
            `}
          >
            {option.icon && <span className="mr-1">{option.icon}</span>}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

/* Tabs 组件变体 - 带边框底部分割 */
export type TerminalTabsProps = {
  /** 当前值 */
  value: string;
  /** 值变化回调 */
  onChange: (value: string) => void;
  /** 选项列表 */
  options: Array<{ value: string; label: string }>;
  /** 额外的类名 */
  className?: string;
};

/* 终端 Tabs 组件 */
export function TerminalTabs({
  value,
  onChange,
  options,
  className = "",
}: TerminalTabsProps) {
  return (
    <div className={`flex border-b border-[var(--terminal-border)] ${className}`}>
      {options.map((option) => {
        const isActive = value === option.value;

        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`
              px-4 py-2.5
              text-[13px] font-medium
              transition-colors
              duration-150
              border-b-2
              -mb-px
              ${isActive
                ? "border-[var(--terminal-cyan)] text-[var(--terminal-cyan)]"
                : "border-transparent text-[var(--terminal-muted)] hover:text-[var(--terminal-text)]"
              }
            `}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
