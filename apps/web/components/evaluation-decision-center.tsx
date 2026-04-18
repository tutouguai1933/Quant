/* 这个文件负责渲染评估页顶部的当前仲裁决策中心。 */

import Link from "next/link";
import type { ReactNode } from "react";

import { DetailDialog } from "./detail-dialog";
import { DetailDrawer } from "./detail-drawer";
import { SectionShell } from "./section-shell";
import { SummaryCard } from "./summary-card";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { StatusBadge } from "./status-badge";

type DecisionCenterProps = {
  arbitration: Record<string, unknown>;
  decisionBoard: Record<string, unknown>;
  stageDecisionSummary: Record<string, unknown>;
  bestExperiment: Record<string, unknown>;
  recommendationExplanation: Record<string, unknown>;
  showPrimaryAction?: boolean;
};

/* 渲染评估页顶部的当前仲裁结论和历史证据分区。 */
export function EvaluationDecisionCenter({
  arbitration,
  decisionBoard,
  stageDecisionSummary,
  bestExperiment,
  recommendationExplanation,
  showPrimaryAction = true,
}: DecisionCenterProps) {
  const status = readText(arbitration.status, "continue_research");
  const symbol = readText(arbitration.symbol, "当前还没有推荐标的");
  const recommendedStage = normalizeStage(readText(arbitration.recommended_stage, "research"));
  const suggestedAction = asRecord(arbitration.suggested_action);
  const inputs = asRecord(arbitration.inputs);
  const blockingItems = Array.isArray(arbitration.blocking_items)
    ? arbitration.blocking_items.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const reasonItems = Array.isArray(arbitration.reason_items) ? arbitration.reason_items.map(String).filter(Boolean) : [];
  const targetPage = readText(suggestedAction.target_page, "/research");

  return (
    <SectionShell
      eyebrow="三层结构"
      title="先看当前判断，需要时再展开证据细节"
      description="顶部先只保留结论和一句解释，门控细节进右侧抽屉，实验与历史证据进集中弹窗。"
      contentClassName="xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]"
    >
      <SummaryCard
        eyebrow="当前仲裁结论"
        title={readText(arbitration.headline, "当前还没有仲裁结论")}
        summary="这一块才回答现在该先做什么，不再把研究证据、执行差异和历史实验混成同一层结论。"
        detail={readText(arbitration.detail, "当前还没有可用仲裁说明。")}
        status={
          <>
            <StatusBadge value={status} />
            <StatusBadge value={recommendedStage} />
            <StatusBadge value={readText(inputs.mode, "manual")} />
          </>
        }
        actions={
          <>
            {showPrimaryAction ? (
              <Button asChild variant={resolveActionVariant(status)} size="sm">
                <Link href={targetPage}>{readText(suggestedAction.label, "去下一页继续处理")}</Link>
              </Button>
            ) : null}
            <DetailDrawer
              triggerLabel="查看门控详情"
              title="门控详情"
              description="这里展开当前为什么这样判断、还差什么，以及现在这一层到底要去哪。"
              closeLabel="关闭门控详情"
              footer="当前动作只跟摘要卡走；这里的细节只负责解释为什么。"
            >
              <div className="space-y-5">
                <div className="grid gap-3 md:grid-cols-2">
                  <DecisionInfoBlock label="现在先推进哪一层" value={formatStageLabel(recommendedStage)} />
                  <DecisionInfoBlock label="现在该去哪一页" value={formatTargetPage(targetPage)} />
                  <DecisionInfoBlock label="当前建议标的" value={symbol} />
                  <DecisionInfoBlock label="当前下一步动作" value={formatActionLabel(readText(suggestedAction.action, "continue_research"))} />
                </div>

                <OverlaySection title="当前为什么这么判断">
                  <p className="text-sm leading-6 text-foreground">{readText(arbitration.detail, "当前还没有可用仲裁说明。")}</p>
                  <div className="space-y-2 text-sm leading-6 text-muted-foreground">
                    {reasonItems.length ? reasonItems.map((item, index) => <p key={`reason-${index}`}>{item}</p>) : <p>当前还没有额外判断依据。</p>}
                  </div>
                </OverlaySection>

                <OverlaySection title="还差什么">
                  <div className="space-y-3 text-sm leading-6 text-muted-foreground">
                    {blockingItems.length ? blockingItems.map((item, index) => (
                      <div key={`blocking-${index}`} className="rounded-2xl border border-border/60 bg-background/40 p-3">
                        <p className="font-medium text-foreground">{readText(item.label, "当前阻塞")}</p>
                        <p className="mt-1">{readText(item.detail, "当前还没有阻塞说明。")}</p>
                      </div>
                    )) : <p>当前没有明显阻塞，可以按这块给出的下一步继续推进。</p>}
                  </div>
                </OverlaySection>
              </div>
            </DetailDrawer>
          </>
        }
        footer="当前动作只跟这一块走；下面的实验、对比和时间线只负责解释为什么。"
        className="border-emerald-500/25 bg-[color:var(--panel-strong)]/90"
      >
        <div className="grid gap-3 md:grid-cols-2">
          <DecisionInfoBlock label="现在先推进哪一层" value={formatStageLabel(recommendedStage)} />
          <DecisionInfoBlock label="现在该去哪一页" value={formatTargetPage(targetPage)} />
          <DecisionInfoBlock label="当前建议标的" value={symbol} />
          <DecisionInfoBlock label="当前下一步动作" value={formatActionLabel(readText(suggestedAction.action, "continue_research"))} />
        </div>
      </SummaryCard>

      <SummaryCard
        eyebrow="历史判断只做参考"
        title={readText(decisionBoard.headline, "当前还没有历史阶段判断")}
        summary="这里保留研究侧阶段判断、最佳实验和推荐证据，帮你理解当前结论为什么成立，但它们不等于现在要执行的动作。"
        detail={readText(stageDecisionSummary.why_recommended, readText(recommendationExplanation.detail, "当前还没有推荐原因"))}
        status={<Badge variant="outline">历史证据层</Badge>}
        actions={
          <DetailDialog
            triggerLabel="打开实验对比弹窗"
            title="实验对比弹窗"
            description="这里集中展示研究侧判断、最佳实验和推荐证据，避免它们和当前动作争抢同一层注意力。"
            closeLabel="关闭实验对比弹窗"
            footer="实验和历史证据只负责解释当前结论，不直接代替当前动作。"
          >
            <div className="space-y-5">
              <div className="grid gap-3 md:grid-cols-2">
                <DecisionInfoBlock label="研究侧阶段判断" value={readText(stageDecisionSummary.headline, "当前还没有阶段判断")} />
                <DecisionInfoBlock label="研究侧当前下一步" value={formatActionLabel(readText(stageDecisionSummary.next_step, "continue_research"))} />
                <DecisionInfoBlock label="研究侧最佳实验" value={readText(bestExperiment.symbol, "当前还没有最佳实验")} />
                <DecisionInfoBlock
                  label="研究侧推荐原因"
                  value={readText(stageDecisionSummary.why_recommended, readText(recommendationExplanation.detail, "当前还没有推荐原因"))}
                />
                <DecisionInfoBlock label="研究与执行差异" value={readText(stageDecisionSummary.execution_gap, "当前还没有差异摘要")} />
                <DecisionInfoBlock label="当前主要阻塞" value={readText(stageDecisionSummary.why_blocked, "当前没有明显阻塞")} />
              </div>

              <OverlaySection title="为什么历史判断只做参考">
                <p className="text-sm leading-6 text-muted-foreground">
                  当前要不要继续推进，仍然以上面的仲裁摘要卡为准；这里保留的是研究侧证据和实验结论，方便回看为什么会形成当前建议。
                </p>
              </OverlaySection>
            </div>
          </DetailDialog>
        }
        footer="历史证据只负责解释当前结论，不单独下动作。"
      >
        <div className="grid gap-3">
          <DecisionInfoBlock label="研究侧阶段判断" value={readText(stageDecisionSummary.headline, "当前还没有阶段判断")} />
          <DecisionInfoBlock label="研究侧当前下一步" value={formatActionLabel(readText(stageDecisionSummary.next_step, "continue_research"))} />
          <DecisionInfoBlock label="研究侧最佳实验" value={readText(bestExperiment.symbol, "当前还没有最佳实验")} />
        </div>
      </SummaryCard>
    </SectionShell>
  );
}

/* 渲染决策中心中的单个信息块。 */
function DecisionInfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-foreground break-all">{value}</p>
    </div>
  );
}

/* 渲染抽屉和弹窗里的细节分组。 */
function OverlaySection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">{title}</p>
      <div className="mt-3 space-y-3">{children}</div>
    </section>
  );
}

/* 读取对象里的文本字段。 */
function readText(value: unknown, fallback: string): string {
  const normalized = String(value ?? "").trim();
  return normalized || fallback;
}

/* 把未知值安全压成对象。 */
function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

/* 统一格式化当前阶段标签。 */
function formatStageLabel(stage: string): string {
  if (stage === "live") {
    return "进入 live";
  }
  if (stage === "dry_run") {
    return "进入 dry-run";
  }
  return "继续研究";
}

/* 统一格式化动作标签。 */
function formatActionLabel(action: string): string {
  const normalized = action.trim();
  const labels: Record<string, string> = {
    continue_research: "继续研究",
    run_training: "运行研究训练",
    run_inference: "运行研究推理",
    go_dry_run: "推进到 dry-run",
    enter_dry_run: "推进到 dry-run",
    go_live: "推进到 live",
    enter_live: "推进到 live",
    wait_cooldown: "等待冷却结束",
    wait_next_window: "等待下一日窗口",
    review_sync: "先处理同步和执行差异",
    review_takeover: "先处理人工接管",
    review_resume: "先完成恢复复核",
    switch_auto_mode: "先切回自动模式",
  };
  return labels[normalized] ?? (normalized || "继续研究");
}

/* 统一格式化目标页面标签。 */
function formatTargetPage(targetPage: string): string {
  const labels: Record<string, string> = {
    "/research": "研究页",
    "/tasks": "任务页",
    "/strategies": "策略页",
    "/evaluation": "评估页",
  };
  return labels[targetPage] ?? targetPage;
}

/* 给当前动作选择更贴切的按钮风格。 */
function resolveActionVariant(status: string): "terminal" | "warning" | "outline" {
  if (["manual_takeover", "manual_mode", "resume_review", "cooldown", "wait_window", "wait_sync"].includes(status)) {
    return "warning";
  }
  if (status === "continue_research") {
    return "outline";
  }
  return "terminal";
}

/* 统一阶段值，避免 dry-run 和 dry_run 混用。 */
function normalizeStage(stage: string): string {
  const normalized = stage.trim().toLowerCase().replaceAll("-", "_");
  if (normalized === "dry_run") {
    return "dry_run";
  }
  if (normalized === "live") {
    return "live";
  }
  return "research";
}
