/**
 * Chip 列表组件
 * 高密度标签列表，用于因子选择、策略标签等
 */
"use client";

/* Chip 类型样式映射 */
const CHIP_TYPE_CLASSES: Record<"default" | "ml" | "rule", string> = {
  default: "terminal-chip",
  ml: "terminal-chip terminal-chip-ml",
  rule: "terminal-chip terminal-chip-rule",
};

/* Chip 属性 */
export type ChipProps = {
  /** Chip 标签 */
  label: string;
  /** 是否选中 */
  active?: boolean;
  /** 点击回调 */
  onClick?: () => void;
  /** Chip 类型：ml=紫色ML标签, rule=青蓝规则标签 */
  type?: "default" | "ml" | "rule";
  /** 是否禁用 */
  disabled?: boolean;
  /** 额外的类名 */
  className?: string;
};

/* 单个 Chip 组件 */
export function Chip({
  label,
  active = false,
  onClick,
  type = "default",
  disabled = false,
  className = "",
}: ChipProps) {
  const baseClass = CHIP_TYPE_CLASSES[type];
  const activeClass = active && type === "default" ? "active" : "";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`${baseClass} ${activeClass} ${disabled ? "opacity-50 cursor-not-allowed" : ""} ${className}`}
    >
      {label}
    </button>
  );
}

/* Chip 列表属性 */
export type ChipListProps = {
  /** Chip 列表数据 */
  items: Array<{
    label: string;
    value: string;
    active?: boolean;
    type?: "default" | "ml" | "rule";
  }>;
  /** 点击回调，返回选中的 value */
  onChange?: (value: string) => void;
  /** 是否多选模式 */
  multiSelect?: boolean;
  /** 额外的类名 */
  className?: string;
};

/* Chip 列表组件 */
export function ChipList({
  items,
  onChange,
  multiSelect = false,
  className = "",
}: ChipListProps) {
  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {items.map((item) => (
        <Chip
          key={item.value}
          label={item.label}
          active={item.active}
          type={item.type}
          onClick={() => onChange?.(item.value)}
        />
      ))}
    </div>
  );
}

/* 带数量的 Chip 列表属性 */
export type ChipListWithCountProps = {
  /** 标题 */
  title?: string;
  /** Chip 列表数据 */
  items: Array<{
    label: string;
    value: string;
    active?: boolean;
    type?: "default" | "ml" | "rule";
  }>;
  /** 选中数量 */
  selectedCount?: number;
  /** 总数量 */
  totalCount?: number;
  /** 点击回调 */
  onChange?: (value: string) => void;
  /** 额外的类名 */
  className?: string;
};

/* 带数量统计的 Chip 列表组件 */
export function ChipListWithCount({
  title,
  items,
  selectedCount,
  totalCount,
  onChange,
  className = "",
}: ChipListWithCountProps) {
  return (
    <div className={className}>
      {/* 标题和数量 */}
      {(title || totalCount !== undefined) && (
        <div className="flex items-center justify-between mb-2">
          {title && (
            <span className="text-[12px] font-medium text-[var(--terminal-muted)]">
              {title}
            </span>
          )}
          {totalCount !== undefined && (
            <span className="text-[11px] text-[var(--terminal-dim)]">
              {selectedCount !== undefined ? `${selectedCount} / ` : ""}
              {totalCount}
            </span>
          )}
        </div>
      )}

      {/* Chip 列表 */}
      <ChipList items={items} onChange={onChange} />
    </div>
  );
}
