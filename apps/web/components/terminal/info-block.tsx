/**
 * 信息块组件
 * 用于显示标签和值的组合
 */

export interface InfoBlockProps {
  label: string;
  value: string;
  className?: string;
}

export function InfoBlock({ label, value, className = "" }: InfoBlockProps) {
  return (
    <div className={`rounded border border-[var(--terminal-border)]/60 bg-[var(--terminal-bg)]/30 p-3 ${className}`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">{label}</p>
      <p className="mt-2 text-sm text-[var(--terminal-text)] break-all">{value || "n/a"}</p>
    </div>
  );
}
