/* 这个文件负责渲染单币页右侧研究侧卡。 */

import { ArrowUpRight, ShieldCheck, Sparkles } from "lucide-react";

import type { ResearchCockpitSummary } from "../lib/api";
import { StatusBadge } from "./status-badge";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Separator } from "./ui/separator";

type ResearchSidecardProps = {
  cockpit: ResearchCockpitSummary;
  nextStep: string;
};

/* 渲染研究解释和下一步动作侧卡。 */
export function ResearchSidecard({ cockpit, nextStep }: ResearchSidecardProps) {
  const gateStatus = String(cockpit.research_gate.status ?? "unavailable");

  return (
    <Card className="bg-card/90">
      <CardHeader className="gap-3">
        <Badge variant="neutral">研究侧卡</Badge>
        <CardTitle>先看研究解释，再决定是否切到策略页</CardTitle>
        <CardDescription>把研究倾向、准入状态和下一步动作收在一张卡里，不再向下堆叠。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="rounded-2xl border border-primary/20 bg-primary/10 p-4">
          <div className="flex items-start gap-3">
            <Sparkles className="mt-0.5 size-4 text-primary" />
            <div className="space-y-2">
              <strong className="block text-base text-foreground">{formatText(cockpit.overlay_summary, "暂无可用信号")}</strong>
              <p className="text-sm leading-6 text-muted-foreground">
                {formatText(cockpit.research_explanation, "研究解释暂时为空。")}
              </p>
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <InfoTile label="研究倾向" value={formatText(cockpit.research_bias, "unavailable")} />
          <InfoTile label="推荐策略" value={formatText(cockpit.recommended_strategy, "none")} />
          <InfoTile label="判断信心" value={formatText(cockpit.confidence, "low")} />
          <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">研究门控</p>
            <div className="mt-3">
              <StatusBadge value={gateStatus} />
            </div>
          </div>
        </div>

        <Separator />

        <div className="grid gap-3 sm:grid-cols-2">
          <MetaLine icon={ShieldCheck} label="模型版本" value={formatText(cockpit.model_version, "n/a")} />
          <MetaLine icon={ArrowUpRight} label="生成时间" value={formatText(cockpit.generated_at, "n/a")} />
          <MetaLine icon={Sparkles} label="信号点" value={String(cockpit.signal_count ?? 0)} />
          <MetaLine icon={ArrowUpRight} label="入场 / 止损" value={`${formatText(cockpit.entry_hint, "n/a")} / ${formatText(cockpit.stop_hint, "n/a")}`} />
        </div>

        <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">下一步动作</p>
          <p className="mt-2 text-sm leading-6 text-foreground">{formatText(nextStep, "先继续观察。")}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-3 text-base font-semibold text-foreground">{value}</p>
    </div>
  );
}

function MetaLine({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof ArrowUpRight;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/30 p-4">
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <p className="mt-3 text-sm font-medium leading-6 text-foreground">{value}</p>
    </div>
  );
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
