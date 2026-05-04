/**
 * 表单行组件
 * 统一的表单标签和输入框布局
 */
"use client";

import type { ReactNode } from "react";

/* 表单行属性 */
export type FieldRowProps = {
  /** 字段标签 */
  label: string;
  /** 字段内容（输入框、选择器等） */
  children: ReactNode;
  /** 是否必填 */
  required?: boolean;
  /** 额外的类名 */
  className?: string;
};

/* 表单行组件 */
export function FieldRow({
  label,
  children,
  required = false,
  className = "",
}: FieldRowProps) {
  return (
    <div className={`terminal-field-row ${className}`}>
      {/* 标签 */}
      <label className="terminal-field-label">
        {label}
        {required && (
          <span className="text-[var(--terminal-red)] ml-1">*</span>
        )}
      </label>

      {/* 内容 */}
      {children}
    </div>
  );
}

/* 输入框属性 */
export type TerminalInputProps = {
  /** 输入值 */
  value: string | number;
  /** 值变化回调 */
  onChange: (value: string) => void;
  /** 占位符 */
  placeholder?: string;
  /** 类型 */
  type?: "text" | "number" | "date";
  /** 是否禁用 */
  disabled?: boolean;
  /** 额外的类名 */
  className?: string;
};

/* 终端风格输入框组件 */
export function TerminalInput({
  value,
  onChange,
  placeholder,
  type = "text",
  disabled = false,
  className = "",
}: TerminalInputProps) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled}
      className={`terminal-input w-full ${disabled ? "opacity-50 cursor-not-allowed" : ""} ${className}`}
    />
  );
}

/* 选择器属性 */
export type TerminalSelectProps = {
  /** 当前值 */
  value: string;
  /** 值变化回调 */
  onChange: (value: string) => void;
  /** 选项列表 */
  options: Array<{ value: string; label: string }>;
  /** 是否禁用 */
  disabled?: boolean;
  /** 额外的类名 */
  className?: string;
};

/* 终端风格选择器组件 */
export function TerminalSelect({
  value,
  onChange,
  options,
  disabled = false,
  className = "",
}: TerminalSelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className={`terminal-input w-full appearance-none ${disabled ? "opacity-50 cursor-not-allowed" : ""} ${className}`}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  );
}
