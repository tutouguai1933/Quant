/**
 * 余额页面
 * 终端风格重构
 */
"use client";

import { useEffect, useState } from "react";

import {
  TerminalShell,
  TerminalCard,
  MetricCard,
} from "../../components/terminal";
import { listBalances } from "../../lib/api";
import { LoadingBanner } from "../../components/loading-banner";

interface BalanceItem {
  id: string;
  asset: string;
  available: string;
  locked: string;
  tradeStatus: string;
  sellableQuantity: string;
  tradeHint: string;
}

interface BalancesModel {
  items: BalanceItem[];
  source: string;
  truthSource: string;
}

export default function BalancesPage() {
  const [session, setSession] = useState<{ isAuthenticated: boolean }>({
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [model, setModel] = useState<BalancesModel>({ items: [], source: "unknown", truthSource: "unknown" });

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

    listBalances(controller.signal)
      .then((response) => {
        clearTimeout(timeoutId);
        if (!response.error) {
          setModel(response.data);
        }
        setIsLoading(false);
      })
      .catch(() => {
        clearTimeout(timeoutId);
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  const items = model.items;
  const dustItems = items.filter((item) => item.tradeStatus === "dust");
  const tradableItems = items.filter((item) => item.tradeStatus === "tradable");

  return (
    <TerminalShell
      breadcrumb="资产 / 余额"
      title="余额"
      subtitle="账户资产明细与可交易状态"
      currentPath="/balances"
      isAuthenticated={session.isAuthenticated}
    >
      {isLoading && <LoadingBanner />}

      {/* 指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          label="资产数量"
          value={String(items.length)}
          colorType="neutral"
        />
        <MetricCard
          label="可交易资产"
          value={String(tradableItems.length)}
          colorType="positive"
        />
        <MetricCard
          label="零头资产"
          value={String(dustItems.length)}
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

      {/* 余额表格 */}
      <TerminalCard title="资产列表">
        {items.length === 0 ? (
          <div className="text-center py-10 text-[var(--terminal-muted)]">
            暂无余额数据，请先连接交易所账户
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--terminal-border)]">
                  <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">资产</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">可用</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">锁定</th>
                  <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">状态</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">可卖</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-bg-hover)]">
                    <td className="py-2 px-3 text-[var(--terminal-text)] font-medium">{item.asset}</td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)]">{item.available}</td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)]">{item.locked}</td>
                    <td className="py-2 px-3 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] ${
                        item.tradeStatus === "tradable"
                          ? "bg-[var(--terminal-green)]/20 text-[var(--terminal-green)]"
                          : item.tradeStatus === "dust"
                          ? "bg-[var(--terminal-yellow)]/20 text-[var(--terminal-yellow)]"
                          : "bg-[var(--terminal-border)] text-[var(--terminal-dim)]"
                      }`}>
                        {item.tradeStatus}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)]">{item.sellableQuantity}</td>
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
