/* 这个文件负责渲染任务与自动化控制台。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { readFeedback } from "../../lib/feedback";
import { getAutomationStatus, getAutomationStatusFallback, getValidationReview, getTasksPageModel, listTasks } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function TasksPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { isAuthenticated, token } = session;
  const feedback = readFeedback(params);
  let items = getTasksPageModel().items;
  let automation = getAutomationStatusFallback().item;
  let review: Record<string, unknown> = {};

  if (token) {
    const [tasksResponse, automationResponse, reviewResponse] = await Promise.allSettled([
      listTasks(token),
      getAutomationStatus(token),
      getValidationReview(token),
    ]);
    if (tasksResponse.status === "fulfilled" && !tasksResponse.value.error) {
      items = tasksResponse.value.data.items;
    }
    if (automationResponse.status === "fulfilled" && !automationResponse.value.error) {
      automation = automationResponse.value.data.item;
    }
    if (reviewResponse.status === "fulfilled" && !reviewResponse.value.error) {
      review = reviewResponse.value.data.item;
    }
  }

  const latestAlert = automation.alerts[0];
  const reviewOverview = asRecord(review.overview);
  const executionHealth = asRecord(automation.executionHealth);

  return (
    <AppShell
      title="任务"
      subtitle="任务页现在先回答自动化有没有开、是否暂停、最近一轮做到哪里，再看底部任务列表。"
      currentPath="/tasks"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} fallbackTitle="任务反馈" />

      <PageHero
        badge="自动化控制台"
        title="先确认自动化模式，再决定要不要触发下一轮工作流。"
        description="这页把自动化模式、停机入口、健康摘要和统一复盘放到一起，避免训练、推理、执行和复盘分散在不同页面里。"
      />

      {!isAuthenticated ? (
        <Card>
          <CardHeader>
            <p className="eyebrow">任务反馈</p>
            <CardTitle>任务页需要管理员登录</CardTitle>
            <CardDescription>登录后才能切换自动化模式、暂停自动化、手动触发一轮工作流和查看复盘。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="terminal">
              <a href="/login?next=%2Ftasks">前往登录</a>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <MetricGrid
            items={[
              { label: "自动化模式", value: formatMode(automation.mode), detail: automation.paused ? "当前已暂停" : "当前允许继续推进" },
              { label: "最近工作流", value: String(asRecord(automation.lastCycle).status ?? "waiting"), detail: "看最近一轮有没有真正推进到执行和复盘" },
              { label: "最近同步", value: String(executionHealth.latest_sync_status ?? "unknown"), detail: "自动化执行后先看同步有没有成功" },
              { label: "推荐动作", value: String(reviewOverview.recommended_action ?? automation.researchOverview.recommended_action ?? "n/a"), detail: "统一复盘会告诉你下一步该继续研究、dry-run 还是 live" },
            ]}
          />

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.9fr)]">
            <section className="grid gap-5">
              <Card>
                <CardHeader>
                  <p className="eyebrow">自动化模式</p>
                  <CardTitle>三种模式和一个停机开关</CardTitle>
                  <CardDescription>先决定是手动、自动 dry-run 还是自动小额 live；真正有风险时，直接暂停自动化。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-3">
                  <ActionCard action="automation_mode_manual" label="手动模式" detail="只保留人工操作，不再自动推进。" />
                  <ActionCard action="automation_mode_auto_dry_run" label="自动 dry-run" detail="研究通过后自动进入 dry-run，先不碰真实资金。" />
                  <ActionCard action="automation_mode_auto_live" label="自动小额 live" detail="在保留安全门的前提下自动进入小额 live。" />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">统一调度入口</p>
                  <CardTitle>一键跑完整一轮自动化工作流</CardTitle>
                  <CardDescription>这轮会统一串起训练、推理、筛选、执行和复盘，不再靠你一页页点。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-3">
                  <ActionCard action="automation_run_cycle" label="运行自动化工作流" detail="按当前模式推进一轮训练、推理、执行和复盘。" />
                  <ActionCard action="automation_pause" label="暂停自动化" detail="停止后续自动推进，切回人工接管。" danger />
                  <ActionCard action="automation_resume" label="恢复自动化" detail="恢复当前模式，让系统继续自动推进。" />
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">统一复盘</p>
                  <CardTitle>这轮工作流做到哪里了</CardTitle>
                  <CardDescription>先看训练、推理、筛选、dry-run、live、复盘六个阶段，再决定下一步。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  {buildReviewSteps(review).map((step) => (
                    <div key={step.key} className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold text-foreground">{step.label}</p>
                        <StatusBadge value={step.status} />
                      </div>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.detail}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </section>

            <aside className="grid gap-5">
              <Card>
                <CardHeader>
                  <p className="eyebrow">健康摘要</p>
                  <CardTitle>先看自动化是不是健康</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>当前模式：{formatMode(automation.mode)}，暂停：{automation.paused ? "是" : "否"}</p>
                  <p>人工接管：{automation.manualTakeover ? "是" : "否"}</p>
                  <p>最近 armed 候选：{automation.armedSymbol || "n/a"}</p>
                  <p>最近同步：{String(executionHealth.latest_sync_status ?? "unknown")}</p>
                  <p>最近复盘：{String(executionHealth.latest_review_status ?? "unknown")}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">最近告警</p>
                  <CardTitle>{latestAlert ? latestAlert.code : "当前没有新告警"}</CardTitle>
                  <CardDescription>{latestAlert ? latestAlert.message : "训练失败、推理失败、执行失败和同步失败都会显示在这里。"}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/70 px-4 py-4">
                    <span className="text-sm text-muted-foreground">告警级别</span>
                    <StatusBadge value={latestAlert?.level || "ok"} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">研究与执行对齐</p>
                  <CardTitle>当前推荐和下一步动作</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>推荐标的：{String(reviewOverview.recommended_symbol ?? automation.researchOverview.recommended_symbol ?? "n/a")}</p>
                  <p>推荐动作：{String(reviewOverview.recommended_action ?? automation.researchOverview.recommended_action ?? "n/a")}</p>
                  <p>候选数量：{String(reviewOverview.candidate_count ?? automation.researchOverview.candidate_count ?? 0)}</p>
                  <p>可进 dry-run：{String(reviewOverview.ready_count ?? automation.researchOverview.ready_count ?? 0)}</p>
                </CardContent>
              </Card>
            </aside>
          </section>

          <DataTable
            columns={["Task", "Source", "Status"]}
            rows={items.map((item) => ({
              id: item.id,
              cells: [item.taskType, item.source, <StatusBadge key={item.id} value={item.status} />],
            }))}
            emptyTitle="当前没有任务记录"
            emptyDetail="先运行一轮自动化工作流，再回到这里确认训练、同步、复盘是不是已经留下记录。"
          />
        </>
      )}
    </AppShell>
  );
}

function ActionCard({
  action,
  label,
  detail,
  danger = false,
}: {
  action: string;
  label: string;
  detail: string;
  danger?: boolean;
}) {
  return (
    <Card className={danger ? "border-rose-500/30 bg-rose-500/10" : "bg-[color:var(--panel-strong)]/80"}>
      <CardContent className="p-4">
        <form action="/actions" method="post" className="space-y-4">
          <input type="hidden" name="action" value={action} />
          <input type="hidden" name="returnTo" value="/tasks" />
          <div className="space-y-2">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
          <FormSubmitButton
            type="submit"
            variant={danger ? "danger" : "terminal"}
            size="sm"
            idleLabel={label}
            pendingLabel={`${label}运行中…`}
            pendingHint="自动化动作已提交，页面会在状态更新后自动刷新。"
          />
        </form>
      </CardContent>
    </Card>
  );
}

function buildReviewSteps(review: Record<string, unknown>) {
  const rawSteps = Array.isArray(review.steps) ? review.steps : [];
  const labelMap: Record<string, string> = {
    training: "研究训练",
    inference: "研究推理",
    screening: "研究筛选",
    dry_run: "dry-run",
    live: "小额 live",
    review: "统一复盘",
  };
  return rawSteps.map((item) => {
    const row = asRecord(item);
    const key = String(row.key ?? "");
    return {
      key,
      label: labelMap[key] || key || "步骤",
      status: String(row.status ?? "waiting"),
      detail: String(row.detail ?? ""),
    };
  });
}

function formatMode(mode: string) {
  if (mode === "auto_dry_run") {
    return "自动 dry-run";
  }
  if (mode === "auto_live") {
    return "自动小额 live";
  }
  return "手动";
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}
