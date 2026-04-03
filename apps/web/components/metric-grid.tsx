/* 这个文件负责统一展示页面关键指标卡。 */

import { Card, CardContent } from "./ui/card";

type MetricItem = {
  label: string;
  value: string;
  detail: string;
};

type MetricGridProps = {
  items: MetricItem[];
};

/* 渲染一组摘要指标。 */
export function MetricGrid({ items }: MetricGridProps) {
  return (
    <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <Card key={item.label} className="bg-card/80">
          <CardContent className="space-y-3 p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{item.label}</p>
            <strong className="block text-3xl font-semibold tracking-tight">{item.value}</strong>
            <p className="text-sm leading-6 text-muted-foreground">{item.detail}</p>
          </CardContent>
        </Card>
      ))}
    </section>
  );
}
