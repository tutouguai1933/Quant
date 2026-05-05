/**
 * 持仓页面
 * 终端风格重构
 */
"use client";

import { useEffect, useState } from "react";

import {
  TerminalShell,
  TerminalCard,
  MetricCard,
} from "../../components/terminal";
import { listPositions } from "../../lib/api";
import { LoadingBanner } from "../../components/loading-banner";

type PositionItem = {
  id: string;
  symbol: string;
  side: string;
  quantity: string;
  unrealizedPnl: string;
};

type PositionsPageModel = {
  source: string;
  truthSource: string;
  items: PositionItem[];
};

export default function PositionsPage() {
  const [session, setSession] = useState<{ isAuthenticated: boolean }>({
    isAuthenticated: false,
  });
  const [model, setModel] = useState<PositionsPageModel>({ source: "unknown", truthSource: "unknown", items: [] });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    listPositions(controller.signal)
      .then((response) => {
        if (!response.error) {
          setModel(response.data);
        }
      })
      .catch(() => {})
      .finally(() => {
        clearTimeout(timeoutId);
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  return (
    <TerminalShell
      breadcrumb="资产 / 持仓"
      title="持仓"
      subtitle="当前仓位与浮盈亏"
      currentPath="/positions"
      isAuthenticated={session.isAuthenticated}
    >
      {isLoading && <LoadingBanner />}

      {/* 指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          label="持仓数量"
          value={String(model.items.length)}
          colorType="neutral"
        />
        <MetricCard
          label="最新方向"
          value={model.items[0]?.side ?? "--"}
          colorType={model.items[0]?.side === "long" ? "positive" : model.items[0]?.side === "short" ? "negative" : "neutral"}
        />
        <MetricCard
          label="最新品种"
          value={model.items[0]?.symbol ?? "--"}
          colorType="neutral"
        />
      </div>

      {/* 同步来源 */}
      <TerminalCard title="同步来源">
        <div className="space-y-2 text-[12px]">
          <div className="flex justify-between">
            <span className="text-[var(--terminal-muted)]">source</span>
            <span className="text-[var(--terminal-text)]">{model.source}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[var(--terminal-muted)]">truth source</span>
            <span className="text-[var(--terminal-text)]">{model.truthSource}</span>
          </div>
        </div>
      </TerminalCard>

      {/* 持仓表格 */}
      <TerminalCard title="持仓列表">
        {model.items.length === 0 ? (
          <div className="text-center py-10 text-[var(--terminal-muted)]">
            暂无持仓数据
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--terminal-border)]">
                  <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">品种</th>
                  <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">方向</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">数量</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">浮盈亏</th>
                </tr>
              </thead>
              <tbody>
                {model.items.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-bg-hover)]">
                    <td className="py-2 px-3 text-[var(--terminal-text)] font-medium">{item.symbol}</td>
                    <td className="py-2 px-3 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] ${
                        item.side === "long"
                          ? "bg-[var(--terminal-green)]/20 text-[var(--terminal-green)]"
                          : item.side === "short"
                          ? "bg-[var(--terminal-red)]/20 text-[var(--terminal-red)]"
                          : "bg-[var(--terminal-border)] text-[var(--terminal-dim)]"
                      }`}>
                        {item.side}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)]">{item.quantity}</td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)]">{item.unrealizedPnl}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </TerminalCard>
    </TerminalShell>
  );
}
