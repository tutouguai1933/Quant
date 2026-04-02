/* 这个文件负责渲染单币页贴边的周期切换条。 */

"use client";

type TimeframeTabsProps = {
  symbol: string;
  activeInterval: string;
  supportedIntervals: string[];
  onSelect: (interval: string) => void;
  pendingInterval?: string;
  align?: "left" | "right";
};

/* 渲染贴在图表左右两侧的轻量周期切换条。 */
export function TimeframeTabs({
  symbol,
  activeInterval,
  supportedIntervals,
  onSelect,
  pendingInterval = "",
  align = "left",
}: TimeframeTabsProps) {
  const intervals = supportedIntervals.length ? supportedIntervals : ["1m", "5m", "15m", "1h", "4h", "1d"];

  return (
    <section
      className={align === "right" ? "timeframe-rail timeframe-rail-right" : "timeframe-rail"}
      aria-label={`${symbol} 周期切换`}
    >
      <p className="eyebrow">{align === "right" ? "高周期" : "快周期"}</p>
      <div className="timeframe-stack">
        {intervals.map((interval) => {
          const isActive = interval === activeInterval;
          const isPending = pendingInterval === interval;

          return (
            <button
              key={interval}
              type="button"
              className={isActive ? "timeframe-pill timeframe-pill-active" : "timeframe-pill"}
              onClick={() => onSelect(interval)}
              disabled={isPending}
              aria-pressed={isActive}
              style={{ textAlign: align === "right" ? "right" : "left" }}
            >
              <strong>{interval}</strong>
              <span>{isActive ? "当前" : isPending ? "切换中" : "切换"}</span>
            </button>
          );
        })}
      </div>
      <p className="timeframe-caption">{symbol}</p>
    </section>
  );
}
