/**
 * 订单页面
 * 终端风格重构
 */
"use client";

import { useEffect, useState } from "react";

import {
  TerminalShell,
  TerminalCard,
  MetricCard,
} from "../../components/terminal";
import { DEFAULT_API_TIMEOUT, getOrdersPageModel, listOrders } from "../../lib/api";
import { LoadingBanner } from "../../components/loading-banner";

type OrdersPageModel = {
  source: string;
  truthSource: string;
  items: Array<{ id: string; symbol: string; side: string; orderType: string; status: string }>;
};

export default function OrdersPage() {
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [model, setModel] = useState<OrdersPageModel>(getOrdersPageModel());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!session.token) {
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_API_TIMEOUT);

    listOrders(controller.signal)
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
  }, [session.token]);

  return (
    <TerminalShell
      breadcrumb="资产 / 订单"
      title="订单"
      subtitle="订单核对与执行回报"
      currentPath="/orders"
      isAuthenticated={session.isAuthenticated}
    >
      {isLoading && <LoadingBanner />}

      {/* 指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          label="订单数量"
          value={String(model.items.length)}
          colorType="neutral"
        />
        <MetricCard
          label="最新品种"
          value={model.items[0]?.symbol ?? "--"}
          colorType="neutral"
        />
        <MetricCard
          label="最新状态"
          value={model.items[0]?.status ?? "waiting"}
          colorType={model.items[0]?.status === "filled" || model.items[0]?.status === "closed" ? "positive" : "neutral"}
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
          <div className="flex justify-between">
            <span className="text-[var(--terminal-muted)]">最新订单</span>
            <span className="text-[var(--terminal-text)]">
              {model.items[0]?.symbol ?? "n/a"} / {model.items[0]?.status ?? "waiting"}
            </span>
          </div>
        </div>
      </TerminalCard>

      {/* 订单表格 */}
      <TerminalCard title="订单列表">
        {model.items.length === 0 ? (
          <div className="text-center py-10 space-y-4">
            <div className="text-[var(--terminal-muted)]">
              <p className="text-lg mb-2">暂无订单数据</p>
              <p className="text-sm">当前没有订单记录，可能原因：</p>
              <ul className="text-sm mt-2 space-y-1 text-[var(--terminal-dim)]">
                <li>• 策略尚未触发入场信号</li>
                <li>• 订单已全部成交并从列表中移除</li>
                <li>• 执行器连接未建立</li>
              </ul>
            </div>
            <div className="flex justify-center gap-3">
              <button
                onClick={() => window.location.reload()}
                className="inline-flex items-center gap-2 rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-4 py-2 text-sm text-[var(--terminal-text)] hover:bg-[var(--terminal-bg-hover)]"
              >
                刷新页面
              </button>
              <a
                href="/signals"
                className="inline-flex items-center gap-2 rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-4 py-2 text-sm text-[var(--terminal-text)] hover:bg-[var(--terminal-bg-hover)]"
              >
                查看策略状态
              </a>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--terminal-border)]">
                  <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">品种</th>
                  <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">方向</th>
                  <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">类型</th>
                  <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">状态</th>
                </tr>
              </thead>
              <tbody>
                {model.items.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-bg-hover)]">
                    <td className="py-2 px-3 text-[var(--terminal-text)] font-medium">{item.symbol}</td>
                    <td className="py-2 px-3 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] ${
                        item.side === "buy"
                          ? "bg-[var(--terminal-green)]/20 text-[var(--terminal-green)]"
                          : item.side === "sell"
                          ? "bg-[var(--terminal-red)]/20 text-[var(--terminal-red)]"
                          : "bg-[var(--terminal-border)] text-[var(--terminal-dim)]"
                      }`}>
                        {item.side}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-center text-[var(--terminal-text)]">{item.orderType}</td>
                    <td className="py-2 px-3 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded text-[11px] ${
                        item.status === "filled" || item.status === "closed"
                          ? "bg-[var(--terminal-green)]/20 text-[var(--terminal-green)]"
                          : item.status === "canceled" || item.status === "rejected"
                          ? "bg-[var(--terminal-red)]/20 text-[var(--terminal-red)]"
                          : "bg-[var(--terminal-yellow)]/20 text-[var(--terminal-yellow)]"
                      }`}>
                        {item.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </TerminalCard>

      {/* 结果判断 */}
      <TerminalCard title="结果判断">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded border border-[var(--terminal-border)]/60 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">有订单时</p>
            <p className="mt-2 text-sm text-[var(--terminal-text)]">先看最新品种和状态，确认是不是你刚刚派发的目标。</p>
          </div>
          <div className="rounded border border-[var(--terminal-border)]/60 p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">没订单时</p>
            <p className="mt-2 text-sm text-[var(--terminal-text)]">如果余额页还剩少量币，通常说明执行已结束，只留下交易所零头。</p>
          </div>
        </div>
      </TerminalCard>
    </TerminalShell>
  );
}
