/* 这个文件负责把任务页里的模式切换、调度、告警和跳转入口收成唯一主动作区。 */

import Link from "next/link";

import { AutomationControlCard } from "./automation-control-card";
import { DetailDrawer } from "./detail-drawer";
import { SectionShell } from "./section-shell";
import { SummaryCard } from "./summary-card";
import { Button } from "./ui/button";

type DrawerControlAction = {
  action: string;
  label: string;
  detail: string;
  danger?: boolean;
  disabled?: boolean;
  disabledHint?: string;
};

type TasksPrimaryActionSectionProps = {
  modeLabel: string;
  modeDetail: string;
  restoreActionLabel: string;
  restoreSummary: string;
  restoreDetail: string;
  targetActionLabel: string;
  targetActionHref: string;
  targetPageLabel: string;
  latestAlertValue: string;
  latestAlertDetail: string;
  runtimeHeadline: string;
  runtimeDetail: string;
  latestAlertIdValue: string;
  hasClearableAlerts: boolean;
  controlActions: DrawerControlAction[];
};

/* 渲染任务页唯一保留的主动作区。 */
export function TasksPrimaryActionSection({
  modeLabel,
  modeDetail,
  restoreActionLabel,
  restoreSummary,
  restoreDetail,
  targetActionLabel,
  targetActionHref,
  targetPageLabel,
  latestAlertValue,
  latestAlertDetail,
  runtimeHeadline,
  runtimeDetail,
  latestAlertIdValue,
  hasClearableAlerts,
  controlActions,
}: TasksPrimaryActionSectionProps) {
  const additionalControlActions = controlActions.filter((item) => !["automation_run_cycle", "automation_pause"].includes(item.action));

  return (
    <SectionShell
      eyebrow="任务主线"
      title="任务主动作区"
      description="首屏只保留一组主动作。先决定要不要继续自动化，再按需展开模式、告警和跨页入口。"
    >
      <SummaryCard
        eyebrow="任务主动作区"
        title={restoreActionLabel}
        summary={restoreSummary}
        detail={restoreDetail}
        actions={(
          <>
            <form action="/actions" method="post">
              <input type="hidden" name="action" value="automation_run_cycle" />
              <input type="hidden" name="returnTo" value="/tasks" />
              <button
                type="submit"
                className="px-4 py-2 text-sm rounded font-medium bg-[var(--terminal-cyan)]/20 text-[var(--terminal-cyan)] border border-[var(--terminal-cyan)]/30 hover:bg-[var(--terminal-cyan)]/30 transition-colors"
              >
                运行自动化工作流
              </button>
            </form>

            <Button asChild variant="outline" size="sm">
              <Link href={targetActionHref}>{targetActionLabel}</Link>
            </Button>

            <DetailDrawer
              triggerLabel="切换自动化模式"
              title="切换自动化模式"
              description="手动、自动 dry-run 和自动小额 live 只保留这一处切换入口。"
            >
              <div className="grid gap-3 md:grid-cols-3">
                <AutomationControlCard action="automation_mode_manual" label="手动模式" detail="只保留人工操作，不再自动推进。" returnTo="/tasks" />
                <AutomationControlCard action="automation_mode_auto_dry_run" label="自动 dry-run" detail="研究通过后自动进入 dry-run，先不碰真实资金。" returnTo="/tasks" />
                <AutomationControlCard action="automation_mode_auto_live" label="自动小额 live" detail="在保留安全门的前提下自动进入小额 live。" returnTo="/tasks" />
              </div>
            </DetailDrawer>

            <DetailDrawer
              triggerLabel="执行调度动作"
              title="执行调度动作"
              description="运行、暂停、人工接管和 Kill Switch 统一放到这里，避免任务页首屏出现多个同级按钮组。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  当前建议先做：{restoreActionLabel}。如果要直接干预自动化，就在这里执行。
                </p>

                <div className="grid gap-3 md:grid-cols-2">
                  <AutomationControlCard action="automation_run_cycle" label="运行自动化工作流" detail="按当前模式推进一轮训练、推理、执行和复盘。" returnTo="/tasks" />
                  <AutomationControlCard action="automation_pause" label="暂停自动化" detail="先停住后续自动推进，回到人工判断。" returnTo="/tasks" />
                  {additionalControlActions.map((item, index) => (
                    <AutomationControlCard
                      key={`${item.action}-${index}`}
                      action={item.action}
                      label={item.label}
                      detail={item.detail}
                      returnTo="/tasks"
                      danger={Boolean(item.danger)}
                      disabled={Boolean(item.disabled)}
                      disabledHint={item.disabledHint}
                    />
                  ))}
                </div>
              </div>
            </DetailDrawer>

            <DetailDrawer
              triggerLabel="处理告警动作"
              title="处理告警动作"
              description="错误告警先人工处理；需要确认或清理时，再从这里打开二级动作。"
            >
              <div className="space-y-4">
                <p className="text-sm leading-6 text-muted-foreground">
                  当前头号告警：{latestAlertValue}。先确认这条告警会不会继续挡住下一轮自动化。
                </p>

                <div className="grid gap-3 md:grid-cols-2">
                  <AutomationControlCard
                    action="automation_confirm_alert"
                    label="确认头号告警"
                    detail="把当前最靠前那条告警标记为已处理，适合告警已经人工确认、不需要继续占住头号位置的时候使用。"
                    returnTo="/tasks"
                    hiddenFields={{ alert_id: latestAlertIdValue }}
                    disabled={!latestAlertIdValue}
                    disabledHint="当前没有可确认的头号告警。"
                  />
                  <AutomationControlCard
                    action="automation_clear_non_error_alerts"
                    label="清理非错误告警"
                    detail="批量清掉 info 和 warning，只把真正需要人工处理的 error 留在列表里。"
                    returnTo="/tasks"
                    hiddenFields={{ levels: "info,warning" }}
                    disabled={!hasClearableAlerts}
                    disabledHint="当前没有可清理的 info / warning 告警。"
                  />
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
                  当前仲裁建议先去 {targetPageLabel}。如果还要查市场、账户和风险明细，也统一从这里展开。
                </p>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  <Button asChild variant="terminal" size="sm">
                    <Link href={targetActionHref}>{targetActionLabel}</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/market">查看市场详情</Link>
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
                  <Button asChild variant="outline" size="sm">
                    <Link href="/research">回到研究链</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/evaluation">去评估与实验中心</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/strategies">去策略页确认执行</Link>
                  </Button>
                  <Button asChild variant="outline" size="sm">
                    <Link href="/backtest">去回测工作台</Link>
                  </Button>
                </div>
              </div>
            </DetailDrawer>
          </>
        )}
        footer="首屏只保留这一组动作；模式切换、告警处理和跨页跳转都下沉到抽屉里。"
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <PrimaryDigest label="当前模式" value={modeLabel} detail={modeDetail} />
          <PrimaryDigest label="当前建议动作" value={restoreActionLabel} detail={restoreSummary} />
          <PrimaryDigest label="头号告警" value={latestAlertValue} detail={latestAlertDetail} />
          <PrimaryDigest label="调度窗口" value={runtimeHeadline} detail={runtimeDetail} />
        </div>
      </SummaryCard>
    </SectionShell>
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
