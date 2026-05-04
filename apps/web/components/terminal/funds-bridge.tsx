/**
 * 资金对比组件
 * 展示初始资金、收益、最终资金
 */
"use client";

/* 资金对比属性 */
export type FundsBridgeProps = {
  /** 初始资金 */
  initialFunds: string | number;
  /** 收益百分比 */
  returnPct: string | number;
  /** 最终资金 */
  finalFunds: string | number;
  /** 基准资金（Buy & Hold） */
  benchmarkFunds?: string | number;
  /** 超额收益 */
  excessReturn?: string | number;
  /** 货币单位 */
  currency?: string;
  /** 额外的类名 */
  className?: string;
};

/* 资金对比组件 */
export function FundsBridge({
  initialFunds,
  returnPct,
  finalFunds,
  benchmarkFunds,
  excessReturn,
  currency = "USDT",
  className = "",
}: FundsBridgeProps) {
  // 解析收益率，判断正负
  const returnNum = typeof returnPct === "string" ? parseFloat(returnPct) : returnPct;
  const isPositive = !isNaN(returnNum) && returnNum >= 0;
  const returnColor = isPositive ? "var(--terminal-green)" : "var(--terminal-red)";
  const returnSign = isPositive ? "+" : "";

  return (
    <div className={`terminal-card p-4 ${className}`}>
      <div className="grid grid-cols-3 gap-4 items-center">
        {/* 初始资金 */}
        <div className="text-center">
          <div className="text-[var(--terminal-dim)] text-[11px]">初始资金</div>
          <div className="text-[var(--terminal-text)] text-lg font-bold mt-1">
            {typeof initialFunds === "number" ? initialFunds.toLocaleString() : initialFunds}
          </div>
          <div className="text-[var(--terminal-dim)] text-[10px]">{currency}</div>
        </div>

        {/* 中间箭头和收益 */}
        <div className="text-center">
          <div className="flex items-center justify-center gap-2">
            <span className="text-[var(--terminal-border)]">→</span>
            <span style={{ color: returnColor }} className="text-lg font-bold">
              {returnSign}{typeof returnPct === "number" ? returnPct.toFixed(2) : returnPct}%
            </span>
            <span className="text-[var(--terminal-border)]">→</span>
          </div>
        </div>

        {/* 最终资金 */}
        <div className="text-center">
          <div className="text-[var(--terminal-dim)] text-[11px]">最终资金</div>
          <div className="text-[var(--terminal-text)] text-lg font-bold mt-1">
            {typeof finalFunds === "number" ? finalFunds.toLocaleString() : finalFunds}
          </div>
          <div className="text-[var(--terminal-dim)] text-[10px]">{currency}</div>
        </div>
      </div>

      {/* 基准对比 */}
      {benchmarkFunds !== undefined && (
        <div className="mt-4 pt-4 border-t border-[var(--terminal-border)]">
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center">
              <div className="text-[var(--terminal-dim)] text-[11px]">同期 Buy & Hold</div>
              <div className="text-[var(--terminal-muted)] text-sm font-medium mt-1">
                {typeof benchmarkFunds === "number" ? benchmarkFunds.toLocaleString() : benchmarkFunds} {currency}
              </div>
            </div>
            <div className="text-center">
              <div className="text-[var(--terminal-dim)] text-[11px]">超额收益</div>
              <div
                className="text-sm font-medium mt-1"
                style={{
                  color: excessReturn !== undefined && parseFloat(String(excessReturn)) >= 0
                    ? "var(--terminal-green)"
                    : "var(--terminal-red)"
                }}
              >
                {excessReturn !== undefined ? `${excessReturn}%` : "--"}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
