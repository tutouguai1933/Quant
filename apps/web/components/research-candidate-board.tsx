/* 这个文件负责统一展示研究候选、dry-run 准入和下一步动作。 */

"use client";

import type { ResearchCandidateItem } from "../lib/api";
import { StatusBadge } from "./status-badge";

type ResearchCandidateBoardProps = {
  title?: string;
  description?: string;
  summary: {
    candidate_count: number;
    ready_count: number;
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
  const visibleItems = normalizedFocusSymbol
    ? items.filter((item) => item.symbol === normalizedFocusSymbol)
    : items;
  const primaryItem = visibleItems[0] ?? items[0] ?? null;

  return (
    <section className="panel">
      <p className="eyebrow">研究候选</p>
      <h3>{title}</h3>
      <p>{description}</p>
      <p>
        候选总数：{summary.candidate_count}
        {"，可进入 dry-run："}
        {summary.ready_count}
      </p>

      {primaryItem ? (
        <>
          <p>
            是否允许进入 dry-run：
            {" "}
            <StatusBadge value={primaryItem.allowed_to_dry_run ? "passed" : primaryItem.dry_run_gate.status} />
          </p>
          <p>下一步动作：{formatNextStep(primaryItem, nextStep)}</p>
          <div className="stack-xs">
            {visibleItems.map((item) => (
              <article key={`${item.symbol}-${item.rank}`} className="action-card">
                <p className="eyebrow">{item.symbol}</p>
                <h4>{item.strategy_template}</h4>
                <p>分数：{item.score}</p>
                <p>是否允许进入 dry-run：{item.allowed_to_dry_run ? "是" : "否"}</p>
                <p>研究门：{item.dry_run_gate.status}</p>
              </article>
            ))}
          </div>
        </>
      ) : (
        <>
          <p>
            是否允许进入 dry-run：
            {" "}
            <StatusBadge value="unavailable" />
          </p>
          <p>下一步动作：{nextStep || "先运行研究训练和研究推理，再决定是否进入策略中心。"}</p>
          <p>当前还没有候选结果，先运行研究训练和研究推理。</p>
        </>
      )}
    </section>
  );
}

function formatNextStep(item: ResearchCandidateItem, fallback: string): string {
  if (item.allowed_to_dry_run) {
    return fallback || "进入策略中心确认执行，再决定是否派发。";
  }
  return fallback || "先继续观察或回到信号页重新运行研究。";
}
