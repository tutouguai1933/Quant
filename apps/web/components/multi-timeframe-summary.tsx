/* 这个文件负责渲染单币页的多周期摘要。 */

import { StatusBadge } from "./status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import type { MultiTimeframeSummaryItem } from "../lib/api";

type MultiTimeframeSummaryProps = {
  items: MultiTimeframeSummaryItem[];
};

/* 渲染固定周期列表的轻量摘要。 */
export function MultiTimeframeSummary({ items }: MultiTimeframeSummaryProps) {
  if (!items.length) {
    return (
      <Card className="bg-card/80">
        <CardHeader>
          <p className="eyebrow">多周期摘要</p>
          <CardTitle>当前还没有可展示的多周期判断</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-6 text-muted-foreground">先确认市场接口已经返回周期摘要，再继续进入更细的图表分析。</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card/80">
      <CardHeader>
        <p className="eyebrow">多周期摘要</p>
        <CardTitle>同一个币，先横向看几个关键周期</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 lg:grid-cols-3">
        {items.map((item) => (
          <article key={item.interval} className="rounded-xl border border-border/60 bg-background/60 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <strong className="text-base">{item.interval}</strong>
              <StatusBadge value={item.confidence} />
            </div>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>趋势：<span className="text-foreground">{item.trend_state}</span></p>
              <p>研究：<span className="text-foreground">{item.research_bias}</span></p>
              <p>策略：<span className="text-foreground">{item.recommended_strategy}</span></p>
              <p>主判断：<span className="text-foreground">{formatText(item.primary_reason, "n/a")}</span></p>
            </div>
          </article>
        ))}
        </div>
      </CardContent>
    </Card>
  );
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
