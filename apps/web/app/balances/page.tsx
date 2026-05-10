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
import { listBalances, listMarketSnapshots } from "../../lib/api";
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
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    // 并行获取余额和市场价格
    Promise.allSettled([
      listBalances(controller.signal),
      listMarketSnapshots(),
    ])
      .then(([balancesRes, marketRes]) => {
        clearTimeout(timeoutId);

        // 构建价格映射
        const priceMap = new Map<string, number>();
        if (marketRes.status === "fulfilled" && !marketRes.value.error) {
          marketRes.value.data.items.forEach((item) => {
            priceMap.set(item.symbol, parseFloat(item.last_price) || 0);
          });
        }

        // USDT价格固定为1
        priceMap.set("USDT", 1);
        // BNB价格（如果没获取到）
        if (!priceMap.has("BNBUSDT")) {
          priceMap.set("BNB", priceMap.get("BNBUSDT") || 0);
        }

        if (balancesRes.status === "fulfilled" && !balancesRes.value.error) {
          const rawItems = balancesRes.value.data.items;

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
            source: balancesRes.value.data.source,
            truthSource: balancesRes.value.data.truthSource,
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
      {isLoading && <LoadingBanner />}

      {/* 总价值概览 */}
      <TerminalCard title="资产总览">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="总资产价值"
            value={`$${model.totalValue.toFixed(2)}`}
            colorType="positive"
          />
          <MetricCard
            label="可交易价值"
            value={`$${model.tradableValue.toFixed(2)}`}
            colorType="positive"
          />
          <MetricCard
            label="零头价值"
            value={`$${model.dustValue.toFixed(2)}`}
            colorType="neutral"
          />
          <MetricCard
            label="资产数量"
            value={String(nonZeroItems.length)}
            colorType="neutral"
          />
        </div>

        {/* 资产分布 */}
        {nonZeroItems.length > 0 && (
          <div className="mt-4 pt-4 border-t border-[var(--terminal-border)]/30">
            <div className="text-xs text-[var(--terminal-muted)] mb-2">资产分布</div>
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
                      ${item.usdValue.toFixed(2)}
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
    </TerminalShell>
  );
}
