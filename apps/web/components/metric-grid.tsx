/* 这个文件负责统一展示页面关键指标卡。 */

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
    <section className="metric-grid">
      {items.map((item) => (
        <article key={item.label} className="metric-card">
          <p className="metric-label">{item.label}</p>
          <strong className="metric-value">{item.value}</strong>
          <p className="metric-detail">{item.detail}</p>
        </article>
      ))}
    </section>
  );
}
