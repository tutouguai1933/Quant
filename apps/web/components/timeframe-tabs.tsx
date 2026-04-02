/* 这个文件负责渲染单币页的周期切换骨架。 */

type TimeframeTabsProps = {
  symbol: string;
  activeInterval: string;
  supportedIntervals: string[];
};

/* 渲染 Binance 风格的轻量周期切换条。 */
export function TimeframeTabs({ symbol, activeInterval, supportedIntervals }: TimeframeTabsProps) {
  const intervals = supportedIntervals.length ? supportedIntervals : ["4h"];

  return (
    <section className="panel">
      <p className="eyebrow">周期切换</p>
      <div className="action-grid">
        {intervals.map((interval) => (
          <a
            key={interval}
            className="action-card"
            href={`/market/${encodeURIComponent(symbol)}?interval=${encodeURIComponent(interval)}`}
          >
            <strong>{interval}</strong>
            <p>{interval === activeInterval ? "当前主图周期" : "切到这个周期查看主图"}</p>
          </a>
        ))}
      </div>
    </section>
  );
}
