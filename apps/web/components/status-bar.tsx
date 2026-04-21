/* 统一的状态栏组件，显示系统关键状态指标 */

import { StatusBadge } from "./status-badge";

type StatusItem = {
  label: string;
  value: string;
  status: string;
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
        <StatusBadge value={status} />
      </div>
      <p className="mt-2 text-lg font-semibold leading-6 text-foreground">{value}</p>
      {detail && <p className="mt-1 text-xs text-muted-foreground">{detail}</p>}
    </div>
  );
}
