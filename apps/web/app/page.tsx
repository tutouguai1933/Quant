/* 这个文件负责渲染首页驾驶舱，并给出成功链路和异常链路指引。 */

import Link from "next/link";
import { ArrowRight, Radar, ShieldAlert, Zap } from "lucide-react";

import { AppShell } from "../components/app-shell";
import { FeedbackBanner } from "../components/feedback-banner";
import { MetricGrid } from "../components/metric-grid";
import { PageHero } from "../components/page-hero";
import { StatusBadge } from "../components/status-badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { readFeedback } from "../lib/feedback";
import { listOrders, listPositions, listRiskEvents, listSignals, listStrategies, listTasks } from "../lib/api";
import { getControlSessionState } from "../lib/session";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

/* 渲染首页驾驶舱。 */
export default async function HomePage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { token, isAuthenticated } = session;
  const feedback = readFeedback(params);
  const [signals, orders, positions, strategies, tasks, riskEvents] = await Promise.all([
    safeLoad(() => listSignals(), []),
    safeLoad(() => listOrders(), []),
    safeLoad(() => listPositions(), []),
    isAuthenticated ? safeLoad(() => listStrategies(token), []) : Promise.resolve([]),
    isAuthenticated ? safeLoad(() => listTasks(token), []) : Promise.resolve([]),
    isAuthenticated ? safeLoad(() => listRiskEvents(token), []) : Promise.resolve([]),
  ]);

  const latestSignal = signals[0];
  const latestTask = tasks[0];
  const latestRisk = riskEvents[0];

  return (
    <AppShell
      title="驾驶舱"
      subtitle="先看当前最佳判断，再决定是否进入图表、策略和执行。首页只保留最短的决策链。"
      currentPath="/"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="决策优先"
        title="先决定该跟哪个候选，再进入图表、策略和执行。"
        description="现在首页作为系统总览，不再堆很多说明卡，而是先告诉你研究有没有出结果、执行器是否可用、异常入口在哪里。"
        aside={
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <span className="text-sm font-medium text-foreground">市场：crypto</span>
              <span className="text-sm text-muted-foreground">研究：Qlib</span>
              <span className="text-sm text-muted-foreground">执行：Freqtrade</span>
            </div>
            <div className="grid gap-2">
              <ActionLink href="/signals" label="查看统一研究报告" detail="先确认当前最佳候选和筛选通过率。" />
              <ActionLink href="/market" label="去市场页筛选目标" detail="从市场总览进入单币图表页。" />
            </div>
          </div>
        }
      />

      <MetricGrid
        items={[
          {
            label: "Signals",
            value: String(signals.length),
            detail: latestSignal ? `最新候选：${latestSignal.symbol}` : "还没有研究信号",
          },
          {
            label: "Execution",
            value: strategies[0]?.status ?? "idle",
            detail: strategies[0] ? "执行器状态已回到首页" : "登录后查看执行器状态",
          },
          {
            label: "Orders",
            value: String(orders.length),
            detail: orders[0] ? `最新反馈：${orders[0].status}` : "还没有执行反馈",
          },
          {
            label: "Risk",
            value: String(riskEvents.length),
            detail: latestRisk ? `最近规则：${latestRisk.ruleName}` : "当前没有新风险事件",
          },
        ]}
      />

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.9fr)]">
        <div className="space-y-6">
          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Zap className="size-4 text-primary" />
                <p className="eyebrow">成功链路</p>
              </div>
              <CardTitle>推荐下一步</CardTitle>
              <CardDescription>先把研究结果拉出来，再去图表页和策略页确认是否继续推进。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <ActionFormCard action="run_pipeline" label="运行 Qlib 信号流水线" detail="先生成最新研究候选。" returnTo="/" />
              <ActionFormCard action="run_mock_pipeline" label="运行演示信号流水线" detail="快速重复验证稳定链路。" returnTo="/" />
              <ActionLink href="/signals" label="查看统一研究报告" detail="先确认当前最佳候选和筛选通过率。" />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <Radar className="size-4 text-primary" />
                <p className="eyebrow">执行入口</p>
              </div>
              <CardTitle>研究确认后，再进入策略控制</CardTitle>
              <CardDescription>如果已经确认候选，可以继续启动策略并派发最新信号；如果还没确认，先去市场页和单币页看图表细节。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <ActionFormCard action="start_strategy" label="启动策略" detail="让执行器进入可派发状态。" returnTo="/" strategyId="1" />
              <ActionFormCard action="dispatch_latest_signal" label="派发最新信号" detail="把研究结果送进执行链。" returnTo="/" strategyId="1" />
              <ActionLink href="/market" label="先去市场页看候选" detail="按单币顺序继续判断。" />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">当前决策板</p>
              <CardTitle>你现在最应该先确认的 4 个状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <DecisionRow
                title="研究信号"
                detail={latestSignal ? `当前最新候选：${latestSignal.symbol}` : "还没有研究信号。"}
                status={latestSignal?.status ?? "waiting"}
              />
              <DecisionRow
                title="执行器状态"
                detail={strategies[0] ? "策略页已可直接接着执行。" : "登录后查看执行器状态。"}
                status={strategies[0]?.status ?? "login required"}
              />
              <DecisionRow
                title="订单反馈"
                detail={orders[0] ? "执行链已有返回。" : "当前还没有新订单反馈。"}
                status={orders[0]?.status ?? "waiting"}
              />
              <DecisionRow
                title="持仓状态"
                detail={positions[0] ? "持仓页已有状态可读。" : "当前没有新持仓状态。"}
                status={positions[0]?.side ?? "waiting"}
              />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <div className="flex items-center gap-3">
                <ShieldAlert className="size-4 text-[color:var(--warning)]" />
                <p className="eyebrow">异常链路</p>
              </div>
              <CardTitle>失败入口保留在右侧</CardTitle>
              <CardDescription>如果你要验证异常链路，直接从这里制造失败任务或查看风险事件，不需要翻到页面底部。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <ActionFormCard
                action="trigger_reconcile_failure"
                label="制造失败任务"
                detail="确认任务失败能否被清楚看见。"
                returnTo="/"
                danger
              />
              <ActionLink
                href={isAuthenticated ? "/risk" : "/login?next=%2Frisk"}
                label="查看风险事件"
                detail={latestRisk ? `最近规则：${latestRisk.ruleName}` : "当前没有新风险事件。"}
              />
              <ActionLink
                href={isAuthenticated ? "/tasks" : "/login?next=%2Ftasks"}
                label="查看最近任务"
                detail={latestTask ? `最近任务：${latestTask.taskType}` : "当前没有新任务。"}
              />
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}

function DecisionRow({ title, detail, status }: { title: string; detail: string; status: string }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-2xl border border-border/70 bg-background/40 px-4 py-4">
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
      </div>
      <StatusBadge value={status} />
    </div>
  );
}

function ActionLink({ href, label, detail }: { href: string; label: string; detail: string }) {
  return (
    <Card className="bg-[color:var(--panel-strong)]/80">
      <CardContent className="space-y-4 p-4">
        <div className="space-y-2">
          <p className="text-sm font-semibold text-foreground">{label}</p>
          <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
        </div>
        <Button asChild variant="secondary" size="sm">
          <Link href={href}>
            继续
            <ArrowRight />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function ActionFormCard({
  action,
  label,
  detail,
  returnTo,
  strategyId = "",
  danger = false,
}: {
  action: string;
  label: string;
  detail: string;
  returnTo: string;
  strategyId?: string;
  danger?: boolean;
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
          <Button type="submit" variant={danger ? "danger" : "default"} size="sm">
            {label}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

/* 带容错地读取列表数据。 */
async function safeLoad<T>(
  loader: () => Promise<{ data: { items: T[] }; error: unknown }>,
  fallback: T[],
): Promise<T[]> {
  try {
    const response = await loader();
    return response.error ? fallback : response.data.items;
  } catch {
    return fallback;
  }
}
