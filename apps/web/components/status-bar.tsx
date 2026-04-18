/* 统一的状态栏组件，显示系统关键状态指标 */

import { cn } from "../lib/utils";

type StatusType = "running" | "success" | "error" | "waiting" | "safe" | "active";

type StatusItem = {
  label: string;
  value: string;
  status: StatusType;
  detail?: string;
};

type StatusBarProps = {
  items: StatusItem[];
};

export function StatusBar({ items }: StatusBarProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item, index) => (
        <StatusIndicator key={index} {...item} />
      ))}
    </div>
  );
}

function StatusIndicator({ label, value, status, detail }: StatusItem) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
      <div className="flex items-center justify-between">
        <p className="eyebrow">{label}</p>
        <StatusBadge status={status} />
      </div>
      <p className="mt-2 text-lg font-semibold leading-6 text-foreground">{value}</p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </div>
  );
}

function StatusBadge({ status }: { status: StatusType }) {
  const variants: Record<StatusType, { bg: string; text: string; label: string }> = {
    running: { bg: "bg-blue-500/10", text: "text-blue-600 dark:text-blue-400", label: "运行中" },
    success: { bg: "bg-green-500/10", text: "text-green-600 dark:text-green-400", label: "成功" },
    error: { bg: "bg-red-500/10", text: "text-red-600 dark:text-red-400", label: "异常" },
    waiting: { bg: "bg-yellow-500/10", text: "text-yellow-600 dark:text-yellow-400", label: "等待" },
    safe: { bg: "bg-green-500/10", text: "text-green-600 dark:text-green-400", label: "正常" },
    active: { bg: "bg-blue-500/10", text: "text-blue-600 dark:text-blue-400", label: "活跃" },
  };

  const variant = variants[status];

  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-1 text-xs font-medium", variant.bg, variant.text)}>
      {variant.label}
    </span>
  );
}
