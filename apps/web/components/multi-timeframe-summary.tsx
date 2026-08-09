/* 这个文件负责渲染单币页的多周期摘要。 */

import { StatusBadge } from "./status-badge";
import type { MultiTimeframeSummaryItem } from "../lib/api";

type MultiTimeframeSummaryProps = {
  items: MultiTimeframeSummaryItem[];
};

/* 渲染固定周期列表的轻量摘要。 */
export function MultiTimeframeSummary({ items }: MultiTimeframeSummaryProps) {
  if (!items.length) {
    return (
      <div className="terminal-card p-4">
        <div className="mb-4">
          <p className="eyebrow">多周期摘要</p>
          <h3 className="text-lg font-semibold tracking-tight text-[var(--terminal-text)]">当前还没有可展示的多周期判断</h3>
        </div>
        <p className="text-sm leading-6 text-[var(--terminal-muted)]">先确认市场接口已经返回周期摘要，再继续进入更细的图表分析。</p>
      </div>
    );
  }

  return (
    <div className="terminal-card p-4">
      <div className="mb-4">
        <p className="eyebrow">多周期摘要</p>
        <h3 className="text-lg font-semibold tracking-tight text-[var(--terminal-text)]">同一个币，先横向看几个关键周期</h3>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {items.map((item) => (
          <article key={item.interval} className="rounded border border-[var(--terminal-border)] bg-[var(--terminal-panel-deep)] p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <strong className="text-base">{item.interval}</strong>
              <StatusBadge value={item.confidence} />
            </div>
            <div className="space-y-2 text-sm text-[var(--terminal-muted)]">
              <p>趋势：<span className="text-[var(--terminal-text)]">{item.trend_state}</span></p>
              <p>研究：<span className="text-[var(--terminal-text)]">{item.research_bias}</span></p>
              <p>策略：<span className="text-[var(--terminal-text)]">{item.recommended_strategy}</span></p>
              <p>主判断：<span className="text-[var(--terminal-text)]">{formatText(item.primary_reason, "n/a")}</span></p>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
