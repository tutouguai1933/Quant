/* 这个文件负责把评估页里的阶段筛选、实验对比和下一步跳转收成唯一主动作区。 */

import Link from "next/link";
import type { ReactNode } from "react";

import { DetailDialog } from "./detail-dialog";
import { DetailDrawer } from "./detail-drawer";
import { FormSubmitButton } from "./form-submit-button";
import { SectionShell } from "./section-shell";
import { SummaryCard } from "./summary-card";
import { Button } from "./ui/button";

type CompareOption = {
  id: string;
  label: string;
};

type AlignmentAction = {
  label: string;
  detail: string;
};

type EvaluationPrimaryActionSectionProps = {
  primaryActionLabel: string;
  primaryActionHref: string;
  targetPageLabel: string;
  stageView: string;
  stageCurrentLabel: string;
  stageDetail: string;
  filteredCount: number;
  researchCount: number;
  dryRunCount: number;
  liveCount: number;
  compareOptions: CompareOption[];
  compareA: string;
  compareB: string;
  compareReadiness: string;
  compareNote: string;
  comparePreferredRun: string;
  compareNextAction: string;
  alignmentActions: AlignmentAction[];
  configContent?: ReactNode;
  experimentContent?: ReactNode;
  alignmentContent?: ReactNode;
};

/* 渲染评估页唯一保留的主动作区。 */
export function EvaluationPrimaryActionSection({
  primaryActionLabel,
  primaryActionHref,
  targetPageLabel,
  stageView,
  stageCurrentLabel,
  stageDetail,
  filteredCount,
  researchCount,
  dryRunCount,
  liveCount,
  compareOptions,
  compareA,
  compareB,
  compareReadiness,
  compareNote,
  comparePreferredRun,
  compareNextAction,
  alignmentActions,
  configContent,
  experimentContent,
  alignmentContent,
}: EvaluationPrimaryActionSectionProps) {
  const currentCompareLabel = buildCurrentCompareLabel({ compareOptions, compareA, compareB });

  return (
    <SectionShell
      eyebrow="评估主线"
      title="评估主动作区"
      description="首屏只保留一组评估动作。阶段筛选、实验对比和跨页跳转都统一从这里展开。"
    >
      <SummaryCard
        eyebrow="评估主动作区"
        title={primaryActionLabel}
        summary={`当前仲裁建议先去 ${targetPageLabel}，评估页不再把阶段筛选、实验对比和导航拆成多块主动作区。`}
        detail={compareNote}
        actions={(
          <>
            <Button asChild variant="terminal" size="sm">
              <Link href={primaryActionHref}>{primaryActionLabel}</Link>
            </Button>

            <DetailDrawer
              triggerLabel="更新阶段视图"
              title="更新阶段视图"
              description="把候选过滤层级收进这里，避免筛选表单和主结论抢同一层注意力。"
            >
              <form method="get" action="/evaluation" className="space-y-4">
                <div className="space-y-2">
                  <p className="eyebrow">当前只看哪一层</p>
                  <select
                    name="stageView"
                    defaultValue={stageView}
                    className="flex h-11 w-full rounded-xl border border-border/70 bg-background px-3 text-sm text-foreground shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                  >
                    <option value="all">全部候选</option>
                    <option value="research">继续研究</option>
                    <option value="dry_run">可进 dry-run</option>
                    <option value="live">可进 live</option>
                  </select>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <PrimaryDigest label="当前阶段视图" value={stageCurrentLabel} detail={stageDetail} compact />
                  <PrimaryDigest label="当前视图候选数" value={String(filteredCount)} detail="当前按这组候选继续往下看。" compact />
                  <PrimaryDigest label="继续研究" value={String(researchCount)} detail="还没过门的候选数量。" compact />
                  <PrimaryDigest label="可进 dry-run" value={String(dryRunCount)} detail="已经够格进入 dry-run 的候选数量。" compact />
                  <PrimaryDigest label="可进 live" value={String(liveCount)} detail="已经够格进入小额 live 的候选数量。" compact />
                </div>
                <FormSubmitButton
                  type="submit"
                  variant="terminal"
                  size="sm"
                  idleLabel="更新阶段视图"
                  pendingLabel="更新阶段视图中…"
                  pendingHint="页面会按你选的阶段重新整理候选、门控和推进板。"
                />
              </form>
            </DetailDrawer>

            <DetailDialog
              triggerLabel="更新实验对比"
              title="实验对比详情"
              description="把手动实验对比和实验账本收进这一处，默认页不再直接铺大块实验表格。"
            >
              <div className="space-y-5">
                <form method="get" action="/evaluation" className="space-y-4">
                  <input type="hidden" name="stageView" value={stageView} />
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <p className="eyebrow">对比对象 A</p>
                      <select
                        name="compareA"
                        defaultValue={compareA}
                        className="flex h-11 w-full rounded-xl border border-border/70 bg-background px-3 text-sm text-foreground shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                      >
                        {compareOptions.map((item) => (
                          <option key={item.id} value={item.id}>{item.label}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <p className="eyebrow">对比对象 B</p>
                      <select
                        name="compareB"
                        defaultValue={compareB}
                        className="flex h-11 w-full rounded-xl border border-border/70 bg-background px-3 text-sm text-foreground shadow-sm outline-none transition focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30"
                      >
                        {compareOptions.map((item) => (
                          <option key={item.id} value={item.id}>{item.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <PrimaryDigest label="当前对比" value={currentCompareLabel} detail={compareNote} compact />
                    <PrimaryDigest label="可比性判断" value={compareReadiness} detail={compareNextAction} compact />
                    <PrimaryDigest label="当前更值得看谁" value={comparePreferredRun} detail="这里只给你手动对比后的当前偏向。" compact />
                  </div>
                  <FormSubmitButton
                    type="submit"
                    variant="terminal"
                    size="sm"
                    idleLabel="更新对比"
                    pendingLabel="更新对比中…"
                    pendingHint="页面会按你选的两轮实验重新整理自选对比表。"
                  />
                </form>
                {experimentContent ? <div className="border-t border-border/60 pt-4">{experimentContent}</div> : null}
              </div>
            </DetailDialog>

            {configContent ? (
              <DetailDrawer
                triggerLabel="查看评估配置"
                title="评估配置详情"
                description="准入门槛、实验窗口和配置目录都下沉到这里，默认页不再直接铺开。"
              >
                {configContent}
              </DetailDrawer>
            ) : null}

            {alignmentContent ? (
              <DetailDrawer
                triggerLabel="查看研究执行差异"
                title="研究执行差异详情"
                description="研究与执行的差异账本和修复动作统一收在这里。"
              >
                {alignmentContent}
              </DetailDrawer>
            ) : null}

            <DetailDrawer
              triggerLabel="查看下一步跳转"
              title="查看下一步跳转"
              description="跨页导航统一收在这里，避免评估页尾部再单独摆一排主按钮。"
            >
              <div className="space-y-4">
                <div className="space-y-3 text-sm leading-6 text-muted-foreground">
                  {alignmentActions.length ? alignmentActions.map((item, index) => (
                    <p key={`${item.label}-${index}`}>
                      {index + 1}. {item.label}：{item.detail}
                    </p>
                  )) : <p>当前还没有明确下一步动作。</p>}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Button asChild variant="terminal" size="sm">
                    <Link href={primaryActionHref}>{primaryActionLabel}</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/research">回到研究工作台</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/backtest">去回测工作台</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/strategies">去策略页看执行</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/tasks">去任务页看自动化</Link>
                  </Button>
                </div>
              </div>
            </DetailDrawer>
          </>
        )}
        footer="阶段筛选、实验对比和跨页跳转都下沉到抽屉；首屏只保留一组评估动作。"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PrimaryDigest label="当前阶段视图" value={stageCurrentLabel} detail={stageDetail} />
          <PrimaryDigest label="当前视图候选数" value={String(filteredCount)} detail={`继续研究 ${researchCount} / dry-run ${dryRunCount} / live ${liveCount}`} />
          <PrimaryDigest label="当前实验对比" value={currentCompareLabel} detail={compareReadiness} />
          <PrimaryDigest label="当前下一步" value={primaryActionLabel} detail={compareNextAction} />
        </div>
      </SummaryCard>
    </SectionShell>
  );
}

/* 生成当前手动对比摘要。 */
function buildCurrentCompareLabel({
  compareOptions,
  compareA,
  compareB,
}: {
  compareOptions: CompareOption[];
  compareA: string;
  compareB: string;
}) {
  const left = compareOptions.find((item) => item.id === compareA)?.label ?? "未选择 A";
  const right = compareOptions.find((item) => item.id === compareB)?.label ?? "未选择 B";
  return `${left} vs ${right}`;
}

/* 渲染主动作区里的摘要块。 */
function PrimaryDigest({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
  compact?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
