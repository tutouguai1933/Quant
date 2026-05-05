/**
 * 风险页面
 * 终端风格重构
 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

import {
  TerminalShell,
  TerminalCard,
  MetricCard,
} from "../../components/terminal";
import { FeedbackBanner } from "../../components/feedback-banner";
import { LoadingBanner } from "../../components/loading-banner";
import { readFeedback } from "../../lib/feedback";
import { getRiskPageModel, listRiskEvents } from "../../lib/api";

type RiskItem = { id: string; level: string; ruleName: string; decision: string };

export default function RiskPage() {
  const searchParams = useSearchParams();
  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [items, setItems] = useState<RiskItem[]>(getRiskPageModel().items);
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
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    listRiskEvents(session.token, controller.signal)
      .then((response) => {
        if (!response.error) {
          setItems(response.data.items);
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
      breadcrumb="工具 / 风险"
      title="风险"
      subtitle="风险告警与规则明细"
      currentPath="/risk"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      {isLoading && <LoadingBanner />}

      {!session.isAuthenticated ? (
        <TerminalCard title="需要登录">
          <div className="space-y-3">
            <p className="text-sm text-[var(--terminal-muted)]">登录后才能查看真实风控事件和规则名称。</p>
            <Link
              className="inline-flex items-center justify-center rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-4 py-2 text-sm text-[var(--terminal-text)] hover:bg-[var(--terminal-bg-hover)]"
              href="/login?next=%2Frisk"
            >
              前往登录
            </Link>
          </div>
        </TerminalCard>
      ) : (
        <>
          {/* 指标卡 */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <MetricCard
              label="风险事件数"
              value={String(items.length)}
              colorType="neutral"
            />
            <MetricCard
              label="最新规则"
              value={items[0]?.ruleName ?? "--"}
              colorType="neutral"
            />
            <MetricCard
              label="最新决定"
              value={items[0]?.decision ?? "waiting"}
              colorType={items[0]?.decision === "block" ? "negative" : items[0]?.decision === "warn" ? "neutral" : "neutral"}
            />
          </div>

          {/* 风险表格 */}
          <TerminalCard title="风险事件列表">
            {items.length === 0 ? (
              <div className="text-center py-10 text-[var(--terminal-muted)]">
                当前没有风险事件
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-[var(--terminal-border)]">
                      <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">级别</th>
                      <th className="text-left py-2 px-3 text-[var(--terminal-dim)]">规则</th>
                      <th className="text-center py-2 px-3 text-[var(--terminal-dim)]">决定</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <tr key={item.id} className="border-b border-[var(--terminal-border)]/50 hover:bg-[var(--terminal-bg-hover)]">
                        <td className="py-2 px-3 text-[var(--terminal-text)]">{item.level}</td>
                        <td className="py-2 px-3 text-[var(--terminal-text)]">{item.ruleName}</td>
                        <td className="py-2 px-3 text-center">
                          <span className={`inline-block px-2 py-0.5 rounded text-[11px] ${
                            item.decision === "block"
                              ? "bg-[var(--terminal-red)]/20 text-[var(--terminal-red)]"
                              : item.decision === "warn"
                              ? "bg-[var(--terminal-yellow)]/20 text-[var(--terminal-yellow)]"
                              : "bg-[var(--terminal-green)]/20 text-[var(--terminal-green)]"
                          }`}>
                            {item.decision}
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
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded border border-[var(--terminal-border)]/60 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">首页判断</p>
                <p className="mt-2 text-sm text-[var(--terminal-text)]">首页已经先告诉你有没有头号阻塞，再回风险页核对具体规则。</p>
              </div>
              <div className="rounded border border-[var(--terminal-border)]/60 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">策略页判断</p>
                <p className="mt-2 text-sm text-[var(--terminal-text)]">执行页先决定是否继续推进；如果被挡住，再回风险页看具体拒绝原因。</p>
              </div>
              <div className="rounded border border-[var(--terminal-border)]/60 p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">任务页判断</p>
                <p className="mt-2 text-sm text-[var(--terminal-text)]">任务页负责恢复和接管，这里只负责把告警和规则明细看清楚。</p>
              </div>
            </div>
          </TerminalCard>
        </>
      )}
    </TerminalShell>
  );
}
