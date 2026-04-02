/* 这个文件负责渲染市场页顶部的筛选入口提示。 */

/* 渲染市场页的静态筛选条。 */
export function MarketFilterBar() {
  return (
    <section className="panel">
      <p className="eyebrow">筛选入口</p>
      <h3>先缩小目标，再进入单币页看图</h3>
      <div className="action-grid">
        <article className="action-card">
          <strong>优先关注</strong>
          <p>先点有明确策略方向的币，减少来回切换。</p>
        </article>
        <article className="action-card">
          <strong>高信心</strong>
          <p>优先看研究信心更高的目标，先完成第一轮筛选。</p>
        </article>
        <article className="action-card">
          <strong>多周期状态</strong>
          <p>先看趋势是在上行、回调还是中性，再决定下一步。</p>
        </article>
      </div>
    </section>
  );
}
