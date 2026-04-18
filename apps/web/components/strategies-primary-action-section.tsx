/* 这个文件负责把策略页里的仲裁承接、自动化恢复、执行器控制和跨页入口收成唯一主动作区。 */

import Link from "next/link";

import { AutomationControlCard } from "./automation-control-card";
import { DetailDrawer } from "./detail-drawer";
import { FormSubmitButton } from "./form-submit-button";
import { SectionShell } from "./section-shell";
import { SummaryCard } from "./summary-card";
import { Button } from "./ui/button";

type StrategyControlAction = {
  action: string;
  label: string;
  detail: string;
  danger?: boolean;
  disabled?: boolean;
  disabledHint?: string;
};

type StrategiesPrimaryActionSectionProps = {
  primaryActionLabel: string;
  primaryActionHref: string;
  targetPageLabel: string;
  candidateLabel: string;
  candidateDetail: string;
  executorLabel: string;
  executorDetail: string;
  automationLabel: string;
  automationDetail: string;
  queueLabel: string;
  queueDetail: string;
  strategyReturnTo: string;
  focusMarketHref: string;
  focusMarketLabel: string;
  controlActions: StrategyControlAction[];
};

/* 渲染策略页唯一保留的主动作区。 */
export function StrategiesPrimaryActionSection({
  primaryActionLabel,
  primaryActionHref,
  targetPageLabel,
  candidateLabel,
  candidateDetail,
  executorLabel,
  executorDetail,
  automationLabel,
  automationDetail,
  queueLabel,
  queueDetail,
  strategyReturnTo,
  focusMarketHref,
  focusMarketLabel,
  controlActions,
}: StrategiesPrimaryActionSectionProps) {
  return (
    <SectionShell
      eyebrow="执行主线"
      title="策略主动作区"
      description="首屏只保留一组动作。先按当前仲裁承接下一步，再按需展开自动化恢复、执行器控制和相关页面入口。"
    >
      <SummaryCard
        eyebrow="策略主动作区"
        title={primaryActionLabel}
        summary={`当前仲裁建议先去 ${targetPageLabel}，策略页不再自己额外造一个平行动作区。`}
        detail={`当前候选：${candidateLabel}。${candidateDetail}`}
        actions={(
          <>
            <Button asChild variant="terminal" size="sm">
              <Link href={primaryActionHref}>{primaryActionLabel}</Link>
            </Button>

            <DetailDrawer
              triggerLabel="处理自动化动作"
              title="处理自动化动作"
              description="保持手动、恢复自动化、只回 dry-run 或停机，都统一从这里展开。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  当前自动化状态：{automationLabel}。如果要直接干预自动化链，就从这里处理。
                </p>
                <div className="grid gap-3 md:grid-cols-2">
                  {controlActions.map((item, index) => (
                    <AutomationControlCard
                      key={`${item.action}-${index}`}
                      action={item.action}
                      label={item.label}
                      detail={item.detail}
                      returnTo={strategyReturnTo}
                      danger={Boolean(item.danger)}
                      disabled={Boolean(item.disabled)}
                      disabledHint={item.disabledHint}
                    />
                  ))}
                </div>
              </div>
            </DetailDrawer>

            <DetailDrawer
              triggerLabel="查看执行器动作"
              title="查看执行器动作"
              description="启动、暂停、停止和派发最新信号都收进这一处，不再在侧栏单独摆一组控制卡。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  当前执行器状态：{executorLabel}。真正控制整台执行器的动作，都在这里。
                </p>
                <div className="grid gap-3 md:grid-cols-2">
                  <StrategyExecutorAction action="start_strategy" label="启动策略" returnTo={strategyReturnTo} />
                  <StrategyExecutorAction action="pause_strategy" label="暂停策略" returnTo={strategyReturnTo} />
                  <StrategyExecutorAction action="stop_strategy" label="停止策略" returnTo={strategyReturnTo} />
                  <StrategyExecutorAction action="dispatch_latest_signal" label="派发最新信号" returnTo={strategyReturnTo} terminal />
                </div>
              </div>
            </DetailDrawer>

            <DetailDrawer
              triggerLabel="查看研究链跳转"
              title="查看研究链跳转"
              description="图表、信号、研究、回测和评估入口统一收在这里，避免策略页首屏出现多组跳转按钮。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  当前要先去 {targetPageLabel}。如果要回图表或研究链其他页面，也统一从这里展开。
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Button asChild variant="terminal" size="sm">
                    <Link href={primaryActionHref}>{primaryActionLabel}</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href={focusMarketHref}>{focusMarketLabel}</Link>
                  </Button>
                  <Button asChild variant="secondary" size="sm">
                    <Link href="/signals">回到信号页复核</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/research">研究工作台</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/backtest">回测工作台</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/evaluation">评估与实验中心</Link>
                  </Button>
                </div>
              </div>
            </DetailDrawer>

            <DetailDrawer
              triggerLabel="查看工具详情"
              title="查看工具详情"
              description="主执行链做完判断后，市场、账户、风险和任务明细都统一从这里进入。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  策略页只保留执行判断，执行后的图表、账户和风险明细都统一放到这里按需展开。
                </p>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <Button asChild variant="outline" size="sm">
                    <Link href="/market">查看市场详情</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/tasks">去任务页看完整时间线</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/balances">查看余额详情</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/orders">查看订单详情</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/positions">查看持仓详情</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/risk">查看风险详情</Link>
                  </Button>
                </div>
              </div>
            </DetailDrawer>
          </>
        )}
        footer="首屏只保留这一组动作；自动化、执行器、研究链和结果页面入口都下沉到抽屉里。"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PrimaryDigest label="当前候选" value={candidateLabel} detail={candidateDetail} />
          <PrimaryDigest label="执行器状态" value={executorLabel} detail={executorDetail} />
          <PrimaryDigest label="自动化状态" value={automationLabel} detail={automationDetail} />
          <PrimaryDigest label="当前队列" value={queueLabel} detail={queueDetail} />
        </div>
      </SummaryCard>
    </SectionShell>
  );
}

/* 渲染执行器控制卡。 */
function StrategyExecutorAction({
  action,
  label,
  returnTo,
  terminal = false,
}: {
  action: string;
  label: string;
  returnTo: string;
  terminal?: boolean;
}) {
  return (
    <form action="/actions" method="post" className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-4">
      <input type="hidden" name="action" value={action} />
      <input type="hidden" name="strategyId" value="1" />
      <input type="hidden" name="returnTo" value={returnTo} />
      <div className="space-y-2">
        <p className="text-sm font-semibold text-foreground">{label}</p>
        <p className="text-sm leading-6 text-muted-foreground">把执行器控制动作统一走控制平面，当前阶段固定控制整台执行器。</p>
      </div>
      <div className="mt-4">
        <FormSubmitButton
          type="submit"
          variant={terminal ? "terminal" : "outline"}
          size="sm"
          idleLabel={label}
          pendingLabel={`${label}运行中…`}
          pendingHint="执行动作已提交，页面会在状态返回后自动刷新。"
        />
      </div>
    </form>
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
