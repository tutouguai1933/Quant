/* 这个文件负责把研究页里的训练、推理、配置摘要和跨页入口收成唯一主动作区。 */

import Link from "next/link";

import { FullScreenModal } from "./full-screen-modal";
import { FormSubmitButton } from "./form-submit-button";
import { SectionShell } from "./section-shell";
import { SummaryCard } from "./summary-card";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

type ResearchPrimaryActionSectionProps = {
  primaryActionLabel: string;
  primaryActionDetail: string;
  researchStatus: string;
  researchStatusDetail: string;
  trainReadinessLabel: string;
  inferReadinessLabel: string;
  configHeadline: string;
  configDetail: string;
  artifactHeadline: string;
  artifactDetail: string;
  modelExplanation: string;
  labelModeExplanation: string;
  triggerBasisExplanation: string;
  holdingWindowExplanation: string;
  signalsHref: string;
  evaluationHref: string;
  backtestHref: string;
  strategiesHref: string;
  tasksHref: string;
};

/* 渲染研究页唯一保留的主动作区。 */
export function ResearchPrimaryActionSection({
  primaryActionLabel,
  primaryActionDetail,
  researchStatus,
  researchStatusDetail,
  trainReadinessLabel,
  inferReadinessLabel,
  configHeadline,
  configDetail,
  artifactHeadline,
  artifactDetail,
  modelExplanation,
  labelModeExplanation,
  triggerBasisExplanation,
  holdingWindowExplanation,
  signalsHref,
  evaluationHref,
  backtestHref,
  strategiesHref,
  tasksHref,
}: ResearchPrimaryActionSectionProps) {
  return (
    <SectionShell
      eyebrow="研究主线"
      title="研究主动作区"
      description="首屏只保留一组研究动作。训练、推理、配置摘要和研究链跳转都统一从这里展开。"
    >
      <SummaryCard
        eyebrow="研究主动作区"
        title={primaryActionLabel}
        summary="研究页不再把训练、推理和跨页跳转拆成多组按钮。先看当前研究状态，再按需展开动作和说明。"
        detail={primaryActionDetail}
        actions={(
          <>
            <FullScreenModal
              triggerLabel="运行研究动作"
              title="运行研究动作"
              description="训练、推理和研究报告入口统一收在这里，避免研究页尾部再放一组动作卡。"
              triggerVariant="terminal"
            >
              <div className="grid gap-3 md:grid-cols-2">
                <ResearchActionCard action="run_research_training" label="研究训练" detail="先生成当前模板下的最新训练产物。" terminal />
                <ResearchActionCard action="run_research_inference" label="研究推理" detail="把最新训练结果继续推进到候选和研究报告。" />
                <ResearchLinkCard href={signalsHref} label="回到信号页看研究报告" detail="统一研究报告、候选排行榜和实验摘要继续从信号页回看。" />
              </div>
            </FullScreenModal>

            <FullScreenModal
              triggerLabel="查看配置摘要"
              title="查看配置摘要"
              description="把当前研究真正采用的预设、模板、模型和切分比例收成一屏，不用翻完整表单。"
            >
              <div className="grid gap-3 md:grid-cols-2">
                <PrimaryDigest label="当前组合" value={configHeadline} detail={configDetail} />
                <PrimaryDigest label="当前状态" value={researchStatus} detail={researchStatusDetail} />
                <PrimaryDigest label="训练是否可启动" value={trainReadinessLabel} detail="先确认训练入口现在是否已准备好。" />
                <PrimaryDigest label="推理是否可启动" value={inferReadinessLabel} detail="训练产物准备好后，再继续看推理是否可启动。" />
              </div>
            </FullScreenModal>

            <FullScreenModal
              triggerLabel="查看研究说明"
              title="查看研究说明"
              description="模型、标签方式、触发基础和持有窗口的解释统一放在这里，默认不再铺满整个研究页。"
            >
              <div className="grid gap-3 md:grid-cols-2">
                <PrimaryDigest label="模型怎么影响结果" value="当前模型说明" detail={modelExplanation} />
                <PrimaryDigest label="标签方式怎么记账" value="当前标签方式说明" detail={labelModeExplanation} />
                <PrimaryDigest label="触发基础" value="当前触发基础说明" detail={triggerBasisExplanation} />
                <PrimaryDigest label="持有窗口" value="当前持有窗口说明" detail={holdingWindowExplanation} />
                <PrimaryDigest label="当前产物" value={artifactHeadline} detail={artifactDetail} />
              </div>
            </FullScreenModal>

            <FullScreenModal
              triggerLabel="查看研究链跳转"
              title="查看研究链跳转"
              description="研究、评估、回测、执行和任务承接入口统一收在这里。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  研究动作完成后，通常先去信号页和评估页看结果；需要继续执行或回看自动化时，再去策略页和任务页。
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <ToolLink href={signalsHref} label="回到信号页看研究报告" terminal />
                  <ToolLink href={evaluationHref} label="去评估与实验中心" />
                  <ToolLink href={backtestHref} label="去回测工作台" />
                  <ToolLink href={strategiesHref} label="去策略页看执行承接" />
                  <ToolLink href={tasksHref} label="去任务页看自动化" />
                </div>
              </div>
            </FullScreenModal>
          </>
        )}
        footer="研究训练、研究推理和研究链跳转都已经下沉到弹窗；首屏只保留这一组研究动作。"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PrimaryDigest label="当前状态" value={researchStatus} detail={researchStatusDetail} />
          <PrimaryDigest label="训练 / 推理" value={`${trainReadinessLabel} / ${inferReadinessLabel}`} detail={primaryActionDetail} />
          <PrimaryDigest label="当前配置摘要" value={configHeadline} detail={configDetail} />
          <PrimaryDigest label="当前产物" value={artifactHeadline} detail={artifactDetail} />
        </div>
      </SummaryCard>
    </SectionShell>
  );
}

/* 渲染主动作区里的动作表单卡。 */
function ResearchActionCard({
  action,
  label,
  detail,
  terminal = false,
}: {
  action: string;
  label: string;
  detail: string;
  terminal?: boolean;
}) {
  return (
    <Card className="bg-[color:var(--panel-strong)]/80">
      <CardContent className="p-4">
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value={action} />
          <input type="hidden" name="returnTo" value="/research" />
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
          <FormSubmitButton
            type="submit"
            size="sm"
            variant={terminal ? "terminal" : "outline"}
            idleLabel={label}
            pendingLabel={`${label}运行中…`}
            pendingHint="研究动作已发出，页面返回后会更新最新研究状态。"
          />
        </form>
      </CardContent>
    </Card>
  );
}

/* 渲染主动作区里的跳转卡。 */
function ResearchLinkCard({ href, label, detail }: { href: string; label: string; detail: string }) {
  return (
    <Card className="bg-[color:var(--panel-strong)]/80">
      <CardContent className="space-y-4 p-4">
        <div className="space-y-2">
          <p className="text-sm font-semibold text-foreground">{label}</p>
          <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href={href}>{label}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

/* 渲染主动作区里的摘要块。 */
function PrimaryDigest({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}

/* 渲染研究链跳转按钮。 */
function ToolLink({ href, label, terminal = false }: { href: string; label: string; terminal?: boolean }) {
  return (
    <Button asChild variant={terminal ? "terminal" : "outline"} size="sm">
      <Link href={href}>{label}</Link>
    </Button>
  );
}
