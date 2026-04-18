/* 这个文件负责把首页里的研究、执行、异常和工具入口收成唯一主动作区。 */

import Link from "next/link";

import { DetailDrawer } from "./detail-drawer";
import { FormSubmitButton } from "./form-submit-button";
import { SectionShell } from "./section-shell";
import { SummaryCard } from "./summary-card";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

type HomePrimaryActionSectionProps = {
  successValue: string;
  successDetail: string;
  executionValue: string;
  executionDetail: string;
  exceptionValue: string;
  exceptionDetail: string;
  nextStepValue: string;
  nextStepDetail: string;
  researchHref: string;
  evaluationHref: string;
  strategiesHref: string;
  riskHref: string;
  tasksHref: string;
};

/* 渲染首页唯一保留的主动作区。 */
export function HomePrimaryActionSection({
  successValue,
  successDetail,
  executionValue,
  executionDetail,
  exceptionValue,
  exceptionDetail,
  nextStepValue,
  nextStepDetail,
  researchHref,
  evaluationHref,
  strategiesHref,
  riskHref,
  tasksHref,
}: HomePrimaryActionSectionProps) {
  return (
    <SectionShell
      eyebrow="首页主线"
      title="首页主动作区"
      description="首页首屏只保留一组主动作。研究启动、执行入口、异常入口和工具跳转都统一从这里展开。"
    >
      <SummaryCard
        eyebrow="首页主动作区"
        title="推荐下一步"
        summary="先判断研究有没有新候选，再决定是否进入执行链；如果要处理失败或跳转其他页面，也都从这里展开。"
        detail="首页不再把成功链路、执行入口和异常链路拆成多个并列按钮区，默认只给摘要，细节按需展开。"
        actions={(
          <>
            <DetailDrawer
              triggerLabel="运行研究动作"
              title="运行研究动作"
              description="研究链的启动、重跑和报告入口统一收在这里。"
              triggerVariant="terminal"
            >
              <div className="grid gap-3 md:grid-cols-2">
                <ActionFormCard action="run_pipeline" label="运行 Qlib 信号流水线" detail="先生成最新研究候选。" returnTo="/" terminal />
                <ActionFormCard action="run_mock_pipeline" label="运行演示信号流水线" detail="快速重复验证稳定链路。" returnTo="/" />
                <ActionLinkCard href="/signals" label="查看统一研究报告" detail="先确认当前最佳候选和筛选通过率。" />
              </div>
            </DetailDrawer>

            <DetailDrawer
              triggerLabel="查看执行入口"
              title="查看执行入口"
              description="研究确认后，再从这里进入策略控制和信号派发。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  先确认研究有没有产出明确候选，再决定是否启动策略、派发信号或回图表继续复核。
                </p>
                <div className="grid gap-3 md:grid-cols-2">
                  <ActionFormCard action="start_strategy" label="启动策略" detail="让执行器进入可派发状态。" returnTo="/" strategyId="1" />
                  <ActionFormCard action="dispatch_latest_signal" label="派发最新信号" detail="把研究结果送进执行链。" returnTo="/" strategyId="1" terminal />
                  <ActionLinkCard href={strategiesHref} label="去策略页确认执行" detail="进入执行工作台看当前候选、执行器和结果页入口。" />
                  <ActionLinkCard href="/market" label="去市场页筛选目标" detail="先回图表和市场页继续判断候选。" />
                </div>
              </div>
            </DetailDrawer>

            <DetailDrawer
              triggerLabel="查看异常入口"
              title="查看异常入口"
              description="失败任务、风险事件和最近任务统一从这里进入。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  如果你要验证失败链路，直接从这里制造失败任务，或者去风险页、任务页看当前阻塞。
                </p>
                <div className="grid gap-3 md:grid-cols-2">
                  <ActionFormCard
                    action="trigger_reconcile_failure"
                    label="制造失败任务"
                    detail="确认任务失败能否被清楚看见。"
                    returnTo="/"
                    danger
                  />
                  <ActionLinkCard href={riskHref} label="查看风险事件" detail="先看最近风险规则和当前告警。" />
                  <ActionLinkCard href={tasksHref} label="查看最近任务" detail="回到任务页看最新时间线和恢复建议。" />
                </div>
              </div>
            </DetailDrawer>

            <DetailDrawer
              triggerLabel="查看详情页跳转"
              title="查看详情页跳转"
              description="主工作台做完判断后，市场、账户和风险明细都统一从这里进入。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  首页只负责先判断下一步，这里再统一去看市场、余额、订单、持仓和风险明细。
                </p>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <ToolLink href="/market" label="查看市场详情" />
                  <ToolLink href="/balances" label="查看余额详情" />
                  <ToolLink href="/orders" label="查看订单详情" />
                  <ToolLink href="/positions" label="查看持仓详情" />
                  <ToolLink href={riskHref} label="查看风险详情" />
                  <ToolLink href="/signals" label="查看统一研究报告" />
                  <ToolLink href={researchHref} label="回到研究工作台" />
                  <ToolLink href={evaluationHref} label="去评估与实验中心" />
                  <ToolLink href={strategiesHref} label="去策略页确认执行" />
                  <ToolLink href={tasksHref} label="去任务页看自动化" />
                </div>
              </div>
            </DetailDrawer>
          </>
        )}
        footer="成功链路、执行入口和异常链路都变成摘要入口；详细动作统一下沉到抽屉。"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PrimaryDigest label="成功链路" value={successValue} detail={successDetail} />
          <PrimaryDigest label="执行入口" value={executionValue} detail={executionDetail} />
          <PrimaryDigest label="异常链路" value={exceptionValue} detail={exceptionDetail} />
          <PrimaryDigest label="驾驶舱判断" value={nextStepValue} detail={nextStepDetail} />
        </div>
      </SummaryCard>
    </SectionShell>
  );
}

/* 渲染首页主动作区里的摘要块。 */
function PrimaryDigest({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}

/* 渲染首页抽屉里的动作表单卡。 */
function ActionFormCard({
  action,
  label,
  detail,
  returnTo,
  strategyId = "",
  danger = false,
  terminal = false,
}: {
  action: string;
  label: string;
  detail: string;
  returnTo: string;
  strategyId?: string;
  danger?: boolean;
  terminal?: boolean;
}) {
  return (
    <Card className={danger ? "border-rose-500/30 bg-rose-500/10" : "bg-[color:var(--panel-strong)]/80"}>
      <CardContent className="p-4">
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value={action} />
          {strategyId ? <input type="hidden" name="strategyId" value={strategyId} /> : null}
          <input type="hidden" name="returnTo" value={returnTo} />
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
          <FormSubmitButton
            type="submit"
            variant={danger ? "danger" : terminal ? "terminal" : "outline"}
            size="sm"
            idleLabel={label}
            pendingLabel={`${label}运行中…`}
            pendingHint="控制平面正在处理这次动作，页面会在完成后刷新。"
          />
        </form>
      </CardContent>
    </Card>
  );
}

/* 渲染首页抽屉里的跳转卡。 */
function ActionLinkCard({ href, label, detail }: { href: string; label: string; detail: string }) {
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

/* 渲染工具跳转按钮。 */
function ToolLink({ href, label }: { href: string; label: string }) {
  return (
    <Button asChild variant="outline" size="sm">
      <Link href={href}>{label}</Link>
    </Button>
  );
}
