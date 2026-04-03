/* 这个文件负责渲染单币页贴边的周期切换条。 */

"use client";

import { cn } from "../lib/utils";

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
    <div className={cn("rounded-2xl border border-border/60 bg-card/70 p-3", align === "right" ? "lg:order-last" : "")}>
      <p className="eyebrow">{align === "right" ? "高周期" : "快周期"}</p>
      <div className="grid gap-2">
        {intervals.map((interval) => {
          const isActive = interval === activeInterval;
          const isPending = pendingInterval === interval;

          return (
            <button
              key={interval}
              type="button"
              className={cn(
                "flex w-full items-center justify-between rounded-xl border px-3 py-2 text-sm transition-colors",
                isActive
                  ? "border-primary/40 bg-primary/12 text-foreground"
                  : "border-border/60 bg-background/70 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
              onClick={() => onSelect(interval)}
              disabled={isPending}
              aria-pressed={isActive}
            >
              <strong>{interval}</strong>
              <span>{isActive ? "当前" : isPending ? "切换中" : "切换"}</span>
            </button>
          );
        })}
      </div>
      <p className="mt-3 text-xs uppercase tracking-[0.12em] text-muted-foreground">{symbol}</p>
    </div>
  );
}
