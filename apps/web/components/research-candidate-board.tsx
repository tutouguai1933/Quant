/* 这个文件负责统一展示研究候选、dry-run 准入和下一步动作。 */

"use client";

import { useMemo, useState } from "react";

import type { ResearchCandidateItem } from "../lib/api";
import { StatusBadge } from "./status-badge";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { ScrollArea } from "./ui/scroll-area";
import { Separator } from "./ui/separator";

type ResearchCandidateBoardProps = {
  title?: string;
  description?: string;
  summary: {
    candidate_count: number;
    ready_count: number;
    blocked_count?: number;
    pass_rate_pct?: string;
    top_candidate_symbol?: string;
    top_candidate_score?: string;
  };
  items: ResearchCandidateItem[];
  focusSymbol?: string;
  nextStep?: string;
};

/* 渲染统一研究候选板。 */
export function ResearchCandidateBoard({
  title = "研究候选",
  description = "先看哪些候选已经通过研究门，再决定是否继续进入 dry-run 或策略执行。",
  summary,
  items,
  focusSymbol = "",
  nextStep = "",
}: ResearchCandidateBoardProps) {
  const normalizedFocusSymbol = focusSymbol.trim().toUpperCase();
  const [viewMode, setViewMode] = useState<"all" | "ready" | "continue" | "forced">("all");
  const [gateMode, setGateMode] = useState<"all" | "rule" | "backtest" | "validation">("all");
  const visibleItems = useMemo(() => {
    const scopedItems = normalizedFocusSymbol ? items.filter((item) => item.symbol === normalizedFocusSymbol) : items;
    return scopedItems.filter((item) => {
      if (viewMode === "ready" && !item.allowed_to_dry_run) {
        return false;
      }
      if (viewMode === "continue" && item.next_action !== "continue_research") {
        return false;
      }
      if (viewMode === "forced" && !item.forced_for_validation) {
        return false;
      }

      if (gateMode === "all") {
        return true;
      }
      return classifyGateBucket(item) === gateMode;
    });
  }, [gateMode, items, normalizedFocusSymbol, viewMode]);
  const primaryItem = visibleItems[0] ?? items[0] ?? null;

  return (
    <Card className="bg-card/95">
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-2">
            <p className="eyebrow">研究候选</p>
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
          {summary.top_candidate_symbol ? (
            <Badge variant="accent" className="px-3 py-1">
              当前最佳候选：{summary.top_candidate_symbol}
            </Badge>
          ) : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
          <SummaryStat label="候选总数" value={String(summary.candidate_count)} />
          <SummaryStat label="可进入 dry-run" value={String(summary.ready_count)} />
          <SummaryStat label="筛选通过率" value={`${summary.pass_rate_pct ?? "0.00"}%`} />
          <SummaryStat
            label="被拦下"
            value={String(summary.blocked_count ?? Math.max(summary.candidate_count - summary.ready_count, 0))}
          />
        </div>
        <div className="grid gap-3 rounded-2xl border border-border/70 bg-background/40 p-3 lg:grid-cols-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">流程开关</p>
            <FilterChip active={viewMode === "all"} onClick={() => setViewMode("all")}>全部</FilterChip>
            <FilterChip active={viewMode === "ready"} onClick={() => setViewMode("ready")}>可进 dry-run</FilterChip>
            <FilterChip active={viewMode === "continue"} onClick={() => setViewMode("continue")}>继续研究</FilterChip>
            <FilterChip active={viewMode === "forced"} onClick={() => setViewMode("forced")}>强制验证</FilterChip>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">门控视图</p>
            <FilterChip active={gateMode === "all"} onClick={() => setGateMode("all")}>全部门</FilterChip>
            <FilterChip active={gateMode === "rule"} onClick={() => setGateMode("rule")}>规则门</FilterChip>
            <FilterChip active={gateMode === "backtest"} onClick={() => setGateMode("backtest")}>回测门</FilterChip>
            <FilterChip active={gateMode === "validation"} onClick={() => setGateMode("validation")}>验证门</FilterChip>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {primaryItem ? (
          <>
            <div className="flex flex-col gap-3 rounded-2xl border border-border/70 bg-background/70 p-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">当前优先候选：{primaryItem.symbol}</p>
                <p className="text-sm leading-6 text-muted-foreground">下一步动作：{formatNextStep(primaryItem, nextStep)}</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Badge variant="outline">分数 {primaryItem.score}</Badge>
                <StatusBadge value={primaryItem.allowed_to_dry_run ? "passed" : primaryItem.dry_run_gate.status} />
              </div>
            </div>

            <ScrollArea className="max-h-[720px]">
              <div className="grid gap-3 xl:grid-cols-2">
                {visibleItems.map((item) => (
                  <article
                    key={`${item.symbol}-${item.rank}`}
                    className="rounded-2xl border border-border/70 bg-background/60 p-4 shadow-[0_14px_32px_rgba(2,6,23,0.18)]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="eyebrow">{item.symbol}</p>
                        <h4 className="text-base font-semibold text-foreground">{item.strategy_template}</h4>
                      </div>
                      <Badge variant={item.allowed_to_dry_run ? "success" : "neutral"}>
                        {item.allowed_to_dry_run ? "ready" : "watch"}
                      </Badge>
                    </div>
                    <Separator className="my-3" />
                    <div className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
                      <p>分数：<span className="text-foreground">{item.score}</span></p>
                      <p>研究门：<span className="text-foreground">{item.dry_run_gate.status}</span></p>
                      <p>复核状态：<span className="text-foreground">{formatReviewStatus(item.review_status)}</span></p>
                      <p>是否允许进入 dry-run：<span className="text-foreground">{item.allowed_to_dry_run ? "是" : "否"}</span></p>
                      <p>回测收益：<span className="text-foreground">{readMetric(item, "total_return_pct", "n/a")}%</span></p>
                      <p>最大回撤：<span className="text-foreground">{readMetric(item, "max_drawdown_pct", "n/a")}%</span></p>
                      <p>Sharpe：<span className="text-foreground">{readMetric(item, "sharpe", "n/a")}</span></p>
                    </div>
                    <div className="mt-3 rounded-xl border border-border/60 bg-muted/15 p-3 text-sm text-muted-foreground">
                      失败原因：<span className="text-foreground">{formatReasons(item.dry_run_gate.reasons)}</span>
                    </div>
                    {item.forced_for_validation ? (
                      <div className="mt-3 rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-sm text-amber-100">
                        强制验证：当前候选被临时放行进入验证链，原因是 {item.forced_reason || "force_top_candidate_for_validation"}。
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </ScrollArea>
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-border/70 bg-muted/15 p-5">
            <div className="mb-3 flex items-center justify-between gap-3">
              <p className="text-sm font-medium text-foreground">当前还没有候选结果</p>
              <StatusBadge value="unavailable" />
            </div>
            <p className="text-sm leading-6 text-muted-foreground">
              下一步动作：{nextStep || "先运行研究训练和研究推理，再决定是否进入策略中心。"}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <Button type="button" size="sm" variant={active ? "terminal" : "ghost"} onClick={onClick}>
      {children}
    </Button>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/60 p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

function formatNextStep(item: ResearchCandidateItem, fallback: string): string {
  if (item.forced_for_validation) {
    return "当前候选被临时放行进入验证链，先走 dry-run，再决定是否继续 live。";
  }
  if (item.allowed_to_dry_run) {
    return fallback || "进入策略中心确认执行，再决定是否派发。";
  }
  return fallback || "先继续观察或回到信号页重新运行研究。";
}

function readMetric(item: ResearchCandidateItem, key: string, fallback: string): string {
  const value = item.backtest.metrics[key];
  return String(value || "").trim() || fallback;
}

function formatReasons(reasons: string[]): string {
  if (!reasons.length) {
    return "无";
  }
  return reasons.join(" / ");
}

function formatReviewStatus(value: string): string {
  const normalized = value.trim();
  if (!normalized) {
    return "未标记";
  }
  if (normalized === "forced_validation") {
    return "强制验证";
  }
  if (normalized === "needs_research_iteration") {
    return "继续研究";
  }
  if (normalized === "ready_for_dry_run") {
    return "可进 dry-run";
  }
  return normalized.replaceAll("_", " ");
}

function classifyGateBucket(item: ResearchCandidateItem): "rule" | "backtest" | "validation" {
  const reasons = [item.review_status, ...item.dry_run_gate.reasons, item.forced_reason]
    .join(" ")
    .toLowerCase();

  if (
    reasons.includes("validation") ||
    reasons.includes("sample") ||
    reasons.includes("consistency") ||
    reasons.includes("drift")
  ) {
    return "validation";
  }
  if (
    reasons.includes("drawdown") ||
    reasons.includes("sharpe") ||
    reasons.includes("turnover") ||
    reasons.includes("backtest") ||
    reasons.includes("return")
  ) {
    return "backtest";
  }
  return "rule";
}
