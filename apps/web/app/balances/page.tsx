/**
 * 余额页面
 * 终端风格重构
 * 显示资产USD估值
 */
"use client";

import { useEffect, useState } from "react";

import {
  TerminalShell,
  TerminalCard,
  MetricCard,
} from "../../components/terminal";
import { listBalances, getBalanceEquitySummary, type BalanceEquitySummary } from "../../lib/api";
import { LoadingBanner } from "../../components/loading-banner";

interface BalanceItem {
  id: string;
  asset: string;
  available: string;
  locked: string;
  tradeStatus: string;
  sellableQuantity: string;
  tradeHint: string;
  dustQuantity: string;
}

interface BalanceWithPrice extends BalanceItem {
  price: number;
  usdValue: number;
  totalQuantity: number;
}

interface BalancesModel {
  items: BalanceWithPrice[];
  source: string;
  truthSource: string;
  totalValue: number;
  tradableValue: number;
  dustValue: number;
}

export default function BalancesPage() {
  const [session, setSession] = useState<{ isAuthenticated: boolean }>({
    isAuthenticated: false,
  });
  const [classificationAvailable, setClassificationAvailable] = useState(false);
  const [equity, setEquity] = useState<BalanceEquitySummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [model, setModel] = useState<BalancesModel>({
    items: [],
    source: "unknown",
    truthSource: "unknown",
    totalValue: 0,
    tradableValue: 0,
    dustValue: 0,
  });

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
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    // 并行获取余额和市场价格
    Promise.allSettled([
      listBalances(controller.signal),
      getBalanceEquitySummary(controller.signal),
    ])
      .then(([balancesRes, equityRes]) => {
        clearTimeout(timeoutId);

        const summary = equityRes.status === "fulfilled" && !equityRes.value.error ? equityRes.value.data : null;
        setEquity(summary);
        // 估值取完整现货快照，不受策略行情列表或展示分页影响。
        const priceMap = new Map<string, number>();
        for (const item of summary?.assets ?? []) {
          if (item.price_usdt !== null) priceMap.set(item.asset, Number(item.price_usdt));
        }

        if (summary || (balancesRes.status === "fulfilled" && !balancesRes.value.error)) {
          const balances = balancesRes.status === "fulfilled" && !balancesRes.value.error ? balancesRes.value.data.items : [];
          const metadata = new Map(balances.map(item => [item.asset, item]));
          const rawItems = summary?.assets.length ? summary.assets.map(item => ({
            id: `balance-${item.asset.toLowerCase()}`, tradeStatus: "untracked", tradeHint: "完整账户余额",
            sellableQuantity: "0", dustQuantity: "0", ...metadata.get(item.asset), ...item,
          })) : balances;

          setClassificationAvailable(rawItems.every(item => ["tradable", "dust", "locked"].includes(item.tradeStatus)));
          // 计算每个资产的USD价值
          const itemsWithPrice: BalanceWithPrice[] = rawItems.map((item) => {
            const available = parseFloat(item.available) || 0;
            const locked = parseFloat(item.locked) || 0;
            const totalQuantity = available + locked;

            // 获取价格
            let price = priceMap.get(`${item.asset}USDT`) ||
                       priceMap.get(item.asset) || 0;

            // 特殊处理USDT
            if (item.asset === "USDT") {
              price = 1;
            }

            const usdValue = totalQuantity * price;

            return {
              ...item,
              price,
              usdValue,
              totalQuantity,
            };
          });

          // 按USD价值排序
          itemsWithPrice.sort((a, b) => b.usdValue - a.usdValue);

          // 计算总价值
          const totalValue = itemsWithPrice.reduce((sum, item) => sum + item.usdValue, 0);
          const tradableValue = itemsWithPrice
            .filter((item) => item.tradeStatus === "tradable")
            .reduce((sum, item) => sum + item.usdValue, 0);
          const dustValue = itemsWithPrice
            .filter((item) => item.tradeStatus === "dust")
            .reduce((sum, item) => sum + item.usdValue, 0);

          setModel({
            items: itemsWithPrice,
            source: "binance-account-equity",
            truthSource: "binance",
            totalValue,
            tradableValue,
            dustValue,
          });
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
  const nonZeroItems = items.filter((item) => item.totalQuantity > 0);

  return (
    <TerminalShell
      breadcrumb="资产 / 余额"
      title="余额"
      subtitle="账户资产明细与可交易状态"
      currentPath="/balances"
      isAuthenticated={session.isAuthenticated}
    >
      <div className="space-y-4">
      {isLoading && <LoadingBanner />}

      {/* 总价值概览 */}
      <TerminalCard title="资产总览">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div data-testid="balance-account-total"><MetricCard
            label="总资产价值"
            value={equity?.total_equity != null ? `${Number(equity.total_equity).toFixed(2)} USDT` : "暂不可用"}
            colorType={equity?.status === "available" ? "positive" : "neutral"}
          /></div>
          <MetricCard label="现货权益" value={equity?.spot_equity != null ? `${Number(equity.spot_equity).toFixed(2)} USDT` : "暂不可用"} colorType="neutral" />
          <MetricCard label="合约权益" value={equity?.futures_equity != null ? `${Number(equity.futures_equity).toFixed(2)} USDT` : "暂不可用"} colorType="neutral" />
          <MetricCard
            label="现货可交易价值"
            value={classificationAvailable && equity?.spot_equity != null ? `${model.tradableValue.toFixed(2)} USDT` : "暂不可用"}
            colorType="positive"
          />
          <MetricCard
            label="现货零头价值"
            value={classificationAvailable && equity?.spot_equity != null ? `${model.dustValue.toFixed(2)} USDT` : "暂不可用"}
            colorType="neutral"
          />
          <MetricCard
            label="现货资产数量"
            value={String(nonZeroItems.length)}
            colorType="neutral"
          />
        </div>

        <p data-testid="balance-equity-status" className="mt-3 text-xs text-[var(--terminal-muted)]">
          {equity?.status === "available" ? "总额包含完整现货和U本位合约权益（含合约浮盈），不含资金及理财账户。" : equity?.issues?.join("；") || "账户权益读取失败，总额暂不可用。"}
        </p>
        {/* 资产分布 */}
        {nonZeroItems.length > 0 && equity?.spot_equity != null && (
          <div className="mt-4 pt-4 border-t border-[var(--terminal-border)]/30">
            <div className="text-xs text-[var(--terminal-muted)] mb-2">现货资产分布</div>
            <div className="h-4 rounded-full bg-[var(--terminal-border)]/30 overflow-hidden flex">
              {nonZeroItems.map((item) => {
                const percentage = (item.usdValue / model.totalValue) * 100;
                const colors = [
                  "bg-[var(--terminal-cyan)]",
                  "bg-green-500",
                  "bg-yellow-500",
                  "bg-purple-500",
                  "bg-pink-500",
                  "bg-blue-500",
                ];
                const colorIndex = nonZeroItems.indexOf(item) % colors.length;
                return (
                  <div
                    key={item.asset}
                    className={`${colors[colorIndex]} h-full transition-all`}
                    style={{ width: `${percentage}%` }}
                    title={`${item.asset}: ${percentage.toFixed(1)}%`}
                  />
                );
              })}
            </div>
            <div className="flex flex-wrap gap-2 mt-2 text-xs">
              {nonZeroItems.slice(0, 6).map((item) => (
                <span key={item.asset} className="text-[var(--terminal-muted)]">
                  {item.asset}: {((item.usdValue / model.totalValue) * 100).toFixed(1)}%
                </span>
              ))}
            </div>
          </div>
        )}
      </TerminalCard>

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
        {nonZeroItems.length === 0 ? (
          <div className="text-center py-10 space-y-4">
            <div className="text-[var(--terminal-muted)]">
              <p className="text-lg mb-2">暂无余额数据</p>
              <p className="text-sm">请先连接交易所账户或查看执行器状态</p>
            </div>
            <a
              href="/strategies"
              className="inline-flex items-center gap-2 rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-4 py-2 text-sm text-[var(--terminal-text)] hover:bg-[var(--terminal-bg-hover)]"
            >
              查看执行器连接状态
            </a>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-[var(--terminal-border)]">
                  <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">资产</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">可用</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">锁定</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">单价</th>
                  <th className="text-right py-2 px-3 text-[var(--terminal-dim)]">USD价值</th>
                  <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">状态</th>
                </tr>
              </thead>
              <tbody>
                {nonZeroItems.map((item) => (
                  <tr key={item.id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-bg-hover)]">
                    <td className="py-2 px-3 text-[var(--terminal-text)] font-medium">{item.asset}</td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)] font-mono">{item.available}</td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)] font-mono">{item.locked}</td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)] font-mono">
                      {item.asset === "USDT" ? "$1.00" : item.price > 0 ? `$${item.price.toFixed(4)}` : "--"}
                    </td>
                    <td className="py-2 px-3 text-right text-[var(--terminal-text)] font-mono">
                      {item.price > 0 ? `${item.usdValue.toFixed(2)} USDT` : "--"}
                    </td>
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
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </TerminalCard>

    </div>
    </TerminalShell>
  );
}
