/* 首页账户余额卡：复用完整权益接口，独立刷新，不等待其他策略卡片。 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { TerminalCard } from "./terminal";
import { Button } from "./ui/button";
import { DEFAULT_API_TIMEOUT, getBalanceEquitySummary, type BalanceEquitySummary } from "../lib/api";

/* 未知或异常金额显示不可用，避免把未取得的余额显示为零。 */
function amountText(value?: string | null): string {
  if (value == null || value === "") return "暂不可用";
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toFixed(2) + " USDT" : "暂不可用";
}

/* 已登录后才读取完整账户；同一时刻只允许一次刷新。 */
export function HomeAccountEquityCard({ authenticated }: { authenticated: boolean }) {
  const [equity, setEquity] = useState<BalanceEquitySummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [reason, setReason] = useState("");
  const [updatedAt, setUpdatedAt] = useState("");
  const pending = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    if (!authenticated || pending.current) return;
    const controller = new AbortController();
    pending.current = controller;
    setLoading(true);
    const timeout = window.setTimeout(() => controller.abort(), DEFAULT_API_TIMEOUT);
    try {
      const response = await getBalanceEquitySummary(controller.signal);
      if (controller.signal.aborted) {
        if (pending.current === controller) {
          setEquity(null);
          setReason("账户余额读取超时，请刷新或稍后再试");
        }
        return;
      }
      if (response.error) {
        setEquity(null);
        setReason(response.error.message);
      } else {
        setEquity(response.data);
        setReason(response.data.issues.join("；"));
        setUpdatedAt(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
      }
    } catch {
      if (pending.current === controller) {
        setEquity(null);
        setReason("账户余额读取失败，请刷新或稍后再试");
      }
    } finally {
      window.clearTimeout(timeout);
      if (pending.current === controller) {
        pending.current = null;
        setLoading(false);
      }
    }
  }, [authenticated]);

  useEffect(() => {
    if (!authenticated) {
      setEquity(null);
      setReason("");
      return;
    }
    void refresh();
    // 隐藏标签页不刷新，减少账户接口负载。
    const interval = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 60_000);
    return () => {
      window.clearInterval(interval);
      const controller = pending.current;
      pending.current = null;
      controller?.abort();
    };
  }, [authenticated, refresh]);

  return (
    <div data-testid="home-account-equity">
      <TerminalCard title="账户总余额">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div data-testid="home-equity-total" className="font-mono text-3xl font-semibold text-[var(--terminal-text)]">
              {!authenticated ? "登录后查看" : loading && !equity && !reason ? "读取中…" : amountText(equity?.total_equity)}
            </div>
            <div data-testid="home-equity-breakdown" className="mt-2 text-xs text-[var(--terminal-muted)]">
              现货：{authenticated ? amountText(equity?.spot_equity) : "—"} · 合约：{authenticated ? amountText(equity?.futures_equity) : "—"}
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <Link href={authenticated ? "/balances" : "/login?next=%2Fbalances"} className="text-[var(--terminal-cyan)]">余额明细</Link>
            <Button variant="outline" size="sm" disabled={!authenticated || loading} onClick={() => void refresh()}>
              {loading ? "刷新中…" : "刷新余额"}
            </Button>
          </div>
        </div>
        <p data-testid="home-equity-status" className="mt-3 text-xs text-[var(--terminal-muted)]">
          {!authenticated ? "登录后显示完整账户权益" : reason || `总额含现货零头及USDT合约权益${updatedAt ? " · 更新于 " + updatedAt : ""}`}
        </p>
      </TerminalCard>
    </div>
  );
}
