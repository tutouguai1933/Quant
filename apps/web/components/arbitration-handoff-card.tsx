/* 这个文件负责在策略页和任务页复用当前仲裁动作承接卡片。 */

import Link from "next/link";

import { StatusBadge } from "./status-badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type ArbitrationHandoffCardProps = {
  arbitration: Record<string, unknown>;
  isAuthenticated: boolean;
  surfaceLabel: string;
  showActions?: boolean;
};

/* 渲染策略页和任务页统一的仲裁动作承接入口。 */
export function ArbitrationHandoffCard({
  arbitration,
  isAuthenticated,
  surfaceLabel,
  showActions = true,
}: ArbitrationHandoffCardProps) {
  const status = readText(arbitration.status, "continue_research");
  const symbol = readText(arbitration.symbol, "当前还没有推荐标的");
  const suggestedAction = asRecord(arbitration.suggested_action);
  const blockingItems = Array.isArray(arbitration.blocking_items)
    ? arbitration.blocking_items.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
  const primaryBlocker = asRecord(blockingItems[0]);
  const targetPage = readText(suggestedAction.target_page, "/research");
  const targetHref = isAuthenticated ? targetPage : `/login?next=${encodeURIComponent(targetPage)}`;
  const actionLabel = readText(suggestedAction.label, "去研究页继续训练和推理");
  const recommendedStage = normalizeStage(readText(arbitration.recommended_stage, "research"));

  return (
    <Card className="border-emerald-500/25 bg-[color:var(--panel-strong)]/90">
      <CardHeader>
        <p className="eyebrow">当前仲裁动作</p>
        <CardTitle>{readText(arbitration.headline, "当前还没有仲裁动作")}</CardTitle>
        <CardDescription>
          这一步和评估页顶部的当前仲裁结论保持一致，策略页和任务页不再各自猜下一步动作。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge value={status} />
          <StatusBadge value={recommendedStage} />
          <StatusBadge value={surfaceLabel} />
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <ArbitrationInfoBlock label="现在先推进哪一层" value={formatStageLabel(recommendedStage)} />
          <ArbitrationInfoBlock label="现在该去哪一页" value={formatTargetPage(targetPage)} />
          <ArbitrationInfoBlock label="当前建议标的" value={symbol} />
          <ArbitrationInfoBlock label="当前页面" value={surfaceLabel} />
        </div>

        <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
          <p className="eyebrow">当前为什么这样</p>
          <p className="mt-2 text-sm leading-6 text-foreground">
            {readText(arbitration.detail, "当前还没有可用仲裁说明。")}
          </p>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {readText(
              primaryBlocker.detail,
              "当前没有额外阻塞，优先按这一块给出的主入口继续推进。",
            )}
          </p>
        </div>

        {!isAuthenticated ? (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm leading-6 text-muted-foreground">
            <p>当前还没登录，所以这里只保留安全导航，不直接开放执行动作。</p>
            <p>登录后会继续沿用同一份仲裁动作，不需要重新猜下一步。</p>
          </div>
        ) : null}

        {showActions ? (
          <div className="flex flex-wrap items-center gap-3">
            <Button asChild variant={resolveActionVariant(status)}>
              <Link href={targetHref}>{actionLabel}</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/evaluation">去评估页看完整仲裁</Link>
            </Button>
          </div>
        ) : (
          <p className="text-sm leading-6 text-muted-foreground">具体动作已收口到当前页面的主动作区，这里只保留仲裁摘要。</p>
        )}
      </CardContent>
    </Card>
  );
}

/* 渲染仲裁卡片里的小信息块。 */
function ArbitrationInfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-foreground break-all">{value}</p>
    </div>
  );
}

/* 安全读取文本字段。 */
function readText(value: unknown, fallback: string): string {
  const normalized = String(value ?? "").trim();
  return normalized || fallback;
}

/* 把未知值安全压成对象。 */
function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

/* 统一格式化阶段标签。 */
function formatStageLabel(stage: string): string {
  if (stage === "live") {
    return "进入 live";
  }
  if (stage === "dry_run") {
    return "进入 dry-run";
  }
  return "继续研究";
}

/* 统一格式化目标页面名称。 */
function formatTargetPage(targetPage: string): string {
  const labels: Record<string, string> = {
    "/research": "研究页",
    "/tasks": "任务页",
    "/strategies": "策略页",
    "/evaluation": "评估页",
  };
  return labels[targetPage] ?? targetPage;
}

/* 根据仲裁状态选择主按钮视觉。 */
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
