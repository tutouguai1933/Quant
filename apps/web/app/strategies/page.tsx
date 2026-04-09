/* 这个文件负责渲染策略中心页面，统一展示策略判断和执行动作。 */

import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ResearchCandidateBoard } from "../../components/research-candidate-board";
import { ConfigCheckboxGrid, ConfigField, ConfigInput, WorkbenchConfigCard } from "../../components/workbench-config-card";
import { StatusBadge } from "../../components/status-badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { readFeedback } from "../../lib/feedback";
import {
  getAutomationStatus,
  getAutomationStatusFallback,
  getEvaluationWorkspace,
  getEvaluationWorkspaceFallback,
  getResearchCandidate,
  getResearchCandidates,
  getResearchCandidatesFallback,
  getStrategyWorkspace,
  getStrategyWorkspaceFallback,
  type StrategyWorkspaceCard,
  type WorkspaceAccountState,
} from "../../lib/api";
import { getControlSessionState } from "../../lib/session";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function StrategiesPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const focusSymbol = readQueryText(params.symbol).toUpperCase();
  const session = await getControlSessionState();
  const { token, isAuthenticated } = session;
  const feedback = readFeedback(params);
  let workspace = getStrategyWorkspaceFallback();
  let candidateSnapshot = getResearchCandidatesFallback();
  let automation = getAutomationStatusFallback().item;
  let evaluation = getEvaluationWorkspaceFallback();
  const [workspaceResult, candidateResult, automationResult, evaluationResult] = await Promise.allSettled([
    token ? getStrategyWorkspace(token) : Promise.resolve(null),
    focusSymbol ? getResearchCandidate(focusSymbol) : getResearchCandidates(),
    token ? getAutomationStatus(token) : Promise.resolve(null),
    getEvaluationWorkspace(),
  ]);

  if (workspaceResult.status === "fulfilled" && workspaceResult.value && !workspaceResult.value.error) {
    workspace = workspaceResult.value.data;
  }

  if (candidateResult.status === "fulfilled") {
    const response = candidateResult.value;
    if (!response.error) {
      if (focusSymbol && "item" in response.data && response.data.item) {
        candidateSnapshot = {
          items: [response.data.item],
          summary: {
            candidate_count: 1,
            ready_count: response.data.item.allowed_to_dry_run ? 1 : 0,
            blocked_count: response.data.item.allowed_to_dry_run ? 0 : 1,
            pass_rate_pct: response.data.item.allowed_to_dry_run ? "100.00" : "0.00",
            top_candidate_symbol: response.data.item.symbol,
            top_candidate_score: response.data.item.score,
          },
        };
      } else if ("items" in response.data) {
        candidateSnapshot = response.data;
      }
    }
  }
  if (automationResult.status === "fulfilled" && automationResult.value && !automationResult.value.error) {
    automation = automationResult.value.data.item;
  }
  if (evaluationResult.status === "fulfilled" && !evaluationResult.value.error) {
    evaluation = evaluationResult.value.data.item;
  }
  const automationCycle = asRecord(automation.lastCycle);
  const evaluationReview = asRecord(asRecord(evaluation.reviews).research);
  const configuration = asRecord(workspace.configuration);
  const executionPolicy = asRecord(automation.executionPolicy);
  const candidateSymbols = toStringArray(executionPolicy.candidate_symbols);
  const executionAllowedSymbols = toStringArray(executionPolicy.live_allowed_symbols);
  const executionSymbolOptions = Array.from(
    new Set([...(candidateSymbols.length ? candidateSymbols : workspace.whitelist), ...executionAllowedSymbols]),
  ).map((item) => ({
    value: item,
    label: item,
    checked: executionAllowedSymbols.includes(item),
  }));

  return (
    <AppShell
      title="策略"
      subtitle="策略中心先回答三件事：哪套策略在运行、它现在怎么看市场、最近有没有真正走到执行。"
      currentPath="/strategies"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="策略中心"
        title="先看判断，再决定要不要派发"
        description="左侧先看推荐执行、研究候选和下一步动作，右侧只看执行器状态、账户收口和执行动作。"
      />

      {focusSymbol ? (
        <Card>
          <CardHeader>
            <p className="eyebrow">当前跟进对象</p>
            <CardTitle>{focusSymbol}</CardTitle>
            <CardDescription>你是带着这个币种从市场页或图表页进入策略中心的，先围绕它确认判断，再决定要不要继续派发。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline">
              <Link href={`/market/${encodeURIComponent(focusSymbol)}`}>返回这个币种的图表页</Link>
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {!isAuthenticated ? (
        <Card>
          <CardHeader>
            <p className="eyebrow">动作反馈</p>
            <CardTitle>当前页面需要登录</CardTitle>
            <CardDescription>登录后才能看到真实策略状态、当前判断和最近执行结果，也才能继续启动、暂停、停止和派发。</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="terminal">
              <Link href="/login?next=%2Fstrategies">先去登录</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <p className="eyebrow">双栏布局</p>
              <CardTitle>左边看判断，右边看执行</CardTitle>
              <CardDescription>这页把判断和执行分开，避免一整屏连续往下扫。</CardDescription>
            </CardHeader>
          </Card>

          <MetricGrid
            items={[
              { label: "策略数量", value: String(workspace.overview.strategy_count), detail: "当前阶段固定只做两套首批波段策略" },
              { label: "运行中", value: String(workspace.overview.running_count), detail: "running 才能继续派发最新信号" },
              { label: "白名单", value: String(workspace.overview.whitelist_count), detail: "只在固定币种池里做最小 dry-run" },
              { label: "最近执行", value: String(workspace.overview.order_count), detail: "方便快速确认链路有没有真正走通" },
            ]}
          />

          {automation.paused || automation.manualTakeover ? (
            <Card>
              <CardHeader>
                <p className="eyebrow">当前自动化状态</p>
                <CardTitle>{automation.manualTakeover ? "当前已人工接管" : "当前已暂停自动化"}</CardTitle>
                <CardDescription>
                  {automation.manualTakeover
                    ? "这意味着当前不应该继续自动推进，先去任务页看接管原因、恢复步骤和最近失败。"
                    : "这意味着当前不应该继续自动推进，先去任务页确认为什么暂停、什么时候恢复。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-3">
                <AutomationInfo label="当前模式" value={readText(automation.mode, "manual")} />
                <AutomationInfo label="暂停原因" value={readText(automation.pauseReason, "当前没有暂停原因")} />
                <AutomationInfo label="最近失败时间" value={readText(automation.lastFailureAt, "当前没有失败记录")} />
                <Button asChild variant="outline">
                  <Link href="/tasks">去任务页处理接管与恢复</Link>
                </Button>
              </CardContent>
            </Card>
          ) : null}

          <section className="grid gap-5 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)] xl:items-start">
            <section className="grid gap-5">
              {workspace.research_recommendation ? (
                <Card>
                  <CardHeader>
                    <p className="eyebrow">当前推荐执行候选</p>
                    <CardTitle>{workspace.research_recommendation.symbol}</CardTitle>
                    <CardDescription>
                      研究门：{workspace.research_recommendation.dry_run_gate.status}
                      {"，下一步动作："}
                      {workspace.research_recommendation.next_action || "先进入 dry-run 观察。"}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="action-grid">
                    <Button asChild variant="outline">
                      <Link href={`/market/${encodeURIComponent(workspace.research_recommendation.symbol)}`}>去这个币的图表页</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/research">去研究工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/backtest">去回测工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/evaluation">去评估与实验中心</Link>
                    </Button>
                    <Button asChild variant="terminal">
                      <Link href={`/strategies?symbol=${encodeURIComponent(workspace.research_recommendation.symbol)}`}>围绕这个币继续执行</Link>
                    </Button>
                  </CardContent>
                </Card>
              ) : null}

              <Card>
                <CardHeader>
                  <p className="eyebrow">候选池摘要</p>
                  <CardTitle>为什么现在先推进这个币</CardTitle>
                  <CardDescription>先把共享候选池、评估门和 live 子集讲清楚，再决定这一轮先推进谁。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <AutomationInfo
                    label="候选池先筛，live 子集后放"
                    value={readText(configuration.candidate_pool_preset, "研究和 dry-run 先共用候选池，再由更严格的 live 子集继续放行。")}
                  />
                  <AutomationInfo
                    label="这一轮先推进谁"
                    value={workspace.research_recommendation?.symbol || readText(evaluation.overview.recommended_symbol, "当前还没有推荐标的")}
                  />
                  <AutomationInfo
                    label="为什么先推进"
                    value={workspace.research_recommendation?.next_action || readText(evaluationReview.next_action, "先继续研究，确认门控和执行差异")}
                  />
                  <AutomationInfo
                    label="还差什么"
                    value={readText(configuration.live_subset_preset, "先通过候选池和评估门，再进入更严格的 live 子集")}
                  />
                </CardContent>
              </Card>

              <ResearchCandidateBoard
                title="研究候选"
                summary={candidateSnapshot.summary}
                items={candidateSnapshot.items}
                focusSymbol={focusSymbol}
                nextStep={focusSymbol ? `下一步动作：先围绕 ${focusSymbol} 确认是否允许进入 dry-run，再决定是否派发。` : "下一步动作：优先看是否允许进入 dry-run，再决定要不要派发。"}
              />

              <Card>
                <CardHeader>
                  <p className="eyebrow">自动化判断</p>
                  <CardTitle>这一轮会不会继续走到 dry-run 或 live</CardTitle>
                  <CardDescription>策略页不只看执行器状态，也直接告诉你当前自动化模式、最近一轮结果和下一步动作。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-2">
                  <AutomationInfo label="当前模式" value={readText(automation.mode, "manual")} />
                  <AutomationInfo label="最近一轮" value={readText(automationCycle.status, "waiting")} />
                  <AutomationInfo label="自动化推荐" value={readText(automationCycle.recommended_symbol, "n/a")} />
                  <AutomationInfo label="下一步动作" value={readText(automationCycle.next_action, "continue_research")} />
                  <AutomationInfo label="是否暂停" value={automation.paused ? "已暂停" : "正常运行"} />
                  <AutomationInfo label="人工接管" value={automation.manualTakeover ? "人工接管中" : "当前未接管"} />
                  <AutomationInfo label="暂停原因" value={readText(automation.pauseReason, "当前没有暂停原因")} />
                  <AutomationInfo label="上次失败时间" value={readText(automation.lastFailureAt, "当前没有失败记录")} />
                </CardContent>
              </Card>

              <MetricGrid
                items={[
                  { label: "研究状态", value: workspace.research.status, detail: workspace.research.detail },
                  { label: "模型版本", value: workspace.research.model_version || "n/a", detail: "最近训练产物已经回到策略工作台" },
                  { label: "研究信号", value: String(workspace.research.signal_count), detail: "最近推理结果中可用的信号数量" },
                ]}
              />

              <Card>
                <CardHeader>
                  <p className="eyebrow">下一步动作</p>
                  <CardTitle>把判断收口到可以执行的动作</CardTitle>
                  <CardDescription>先确认研究候选是否允许进入 dry-run，再决定要不要围绕这个币继续派发。</CardDescription>
                </CardHeader>
                <CardContent className="action-grid">
                  <Button asChild variant="outline">
                    <Link href={focusSymbol ? `/market/${encodeURIComponent(focusSymbol)}` : "/signals"}>去图表页确认</Link>
                  </Button>
                  <Button asChild variant="terminal">
                    <Link href={focusSymbol ? `/strategies?symbol=${encodeURIComponent(focusSymbol)}` : "/strategies"}>围绕这个币继续执行</Link>
                  </Button>
                  <Button asChild variant="secondary">
                    <Link href="/signals">回到信号页复核</Link>
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">研究链入口</p>
                  <CardTitle>先看研究工作台、回测工作台和评估与实验中心</CardTitle>
                  <CardDescription>执行页继续承接研究链，而不是让你自己在多个页面之间拼结论。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>评估中心推荐：{readText(evaluation.overview.recommended_symbol, "n/a")}</p>
                  <p>推荐原因：{readText(evaluationReview.result, "未生成")}</p>
                  <div className="flex flex-wrap gap-3">
                    <Button asChild variant="outline">
                      <Link href="/research">研究工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/backtest">回测工作台</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/evaluation">评估与实验中心</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-card/90">
                <CardHeader>
                  <p className="eyebrow">策略判断</p>
                  <CardTitle>两套首批波段策略</CardTitle>
                  <CardDescription>只保留当前判断和执行建议，不再把页面往纵向拉长。</CardDescription>
                </CardHeader>
                <CardContent className="grid gap-4 xl:grid-cols-2">
                  {workspace.strategies.map((item) => (
                    <StrategyCard key={item.key} item={item} />
                  ))}
                </CardContent>
              </Card>
            </section>

            <aside className="grid gap-5">
              <Card>
                <CardHeader>
                  <p className="eyebrow">执行器状态</p>
                  <CardTitle>先确认当前连的是谁</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>
                    当前执行器：
                    {" "}
                    {workspace.executor_runtime.executor}
                    {" / "}
                    {workspace.executor_runtime.backend}
                    {" / "}
                    {workspace.executor_runtime.mode}
                  </p>
                  <p>连接状态：{workspace.executor_runtime.connection_status}</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">当前配置摘要</p>
                  <CardTitle>先确认这轮研究和执行到底按什么口径在跑</CardTitle>
                  <CardDescription>把研究模板、验证门、执行安全门和自动化策略压成一块，避免你只看到推荐结果，却不知道它是按什么规则得出来的。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>研究范围：{readText(configuration.research_scope, "当前还没有研究范围摘要")}</p>
                  <p>研究 / dry-run 候选池：{readText(configuration.candidate_pool, workspace.whitelist.join(" / ") || "当前未设置")}</p>
                  <p>验证策略：{readText(configuration.validation_policy, "当前还没有验证策略摘要")}</p>
                  <p>live 子集：{executionAllowedSymbols.length ? executionAllowedSymbols.join(" / ") : "当前未设置"}</p>
                  <p>执行策略：{readText(configuration.execution_policy, "当前还没有执行策略摘要")}</p>
                  <p>门槛策略：{readText(configuration.threshold_policy, "当前还没有门槛策略摘要")}</p>
                  <p>自动化策略：{readText(configuration.automation_policy, "当前还没有自动化策略摘要")}</p>
                </CardContent>
              </Card>

              <WorkbenchConfigCard
                title="执行安全门配置"
                description="研究推荐出来的币会先走研究 / dry-run 候选池；这里只有更严格的 live 子集、单笔金额和最大开仓数。"
                scope="execution"
                returnTo={focusSymbol ? `/strategies?symbol=${encodeURIComponent(focusSymbol)}` : "/strategies"}
              >
                <ConfigField label="live_allowed_symbols" hint="只有这里勾选的币，才允许继续自动小额 live。">
                  <ConfigCheckboxGrid name="live_allowed_symbols" options={executionSymbolOptions} />
                </ConfigField>
                <ConfigField label="单笔 live 金额" hint="这里控制单次自动小额 live 最多能下多少 USDT。">
                  <ConfigInput
                    name="live_max_stake_usdt"
                    type="number"
                    min={0.1}
                    step={0.1}
                    defaultValue={readText(executionPolicy.live_max_stake_usdt, "6")}
                  />
                </ConfigField>
                <ConfigField label="最大同时开仓数" hint="这里控制自动 live 同时最多保留多少个打开中的仓位。">
                  <ConfigInput
                    name="live_max_open_trades"
                    type="number"
                    min={1}
                    max={20}
                    step={1}
                    defaultValue={readText(executionPolicy.live_max_open_trades, "1")}
                  />
                </ConfigField>
              </WorkbenchConfigCard>

              <Card>
                <CardHeader>
                  <p className="eyebrow">账户收口</p>
                  <CardTitle>执行之后，回到同一套真实来源上看结果</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>source: {workspace.account_state.source} / truth source: {workspace.account_state.truth_source}</p>
                  <p>余额：{workspace.account_state.summary.balance_count}，可交易：{workspace.account_state.summary.tradable_balance_count}，零头：{workspace.account_state.summary.dust_count}</p>
                  <p>订单：{workspace.account_state.summary.order_count}，持仓：{workspace.account_state.summary.position_count}</p>
                  <p>
                    最近余额：{formatLatestBalance(workspace.account_state.latest_balance)}
                    {"，最近订单："}
                    {formatLatestOrder(workspace.account_state.latest_order)}
                    {"，最近持仓："}
                    {formatLatestPosition(workspace.account_state.latest_position)}
                  </p>
                  <div className="action-grid">
                    <Button asChild variant="outline">
                      <Link href="/balances">去余额页</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/orders">去订单页</Link>
                    </Button>
                    <Button asChild variant="outline">
                      <Link href="/positions">去持仓页</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">执行动作</p>
                  <CardTitle>这些动作控制的是整台执行器</CardTitle>
                  <CardDescription>推荐顺序：先启动，再派发。当前阶段固定控制整台 Freqtrade 执行器。</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="action-grid">
                    <ActionForm action="start_strategy" label="启动策略" focusSymbol={focusSymbol} />
                    <ActionForm action="pause_strategy" label="暂停策略" focusSymbol={focusSymbol} />
                    <ActionForm action="stop_strategy" label="停止策略" focusSymbol={focusSymbol} />
                    <ActionForm action="dispatch_latest_signal" label="派发最新信号" focusSymbol={focusSymbol} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <p className="eyebrow">候选池摘要</p>
                  <CardTitle>研究 / dry-run 和 live 用的是两层口径</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>研究 / dry-run 候选池：{(candidateSymbols.length ? candidateSymbols : workspace.whitelist).join(" / ")}</p>
                  <p>live 子集：{executionAllowedSymbols.length ? executionAllowedSymbols.join(" / ") : "当前未设置"}</p>
                </CardContent>
              </Card>
            </aside>
          </section>

          <section className="grid gap-5 lg:grid-cols-2 lg:items-start">
            <DataTable
              columns={["Strategy", "Symbol", "Status", "Generated"]}
              rows={workspace.recent_signals.map((item, index) => ({
                id: String(item.signal_id ?? index),
                cells: [
                  String(item.strategy_id ?? "n/a"),
                  String(item.symbol ?? ""),
                  <StatusBadge key={String(item.signal_id ?? index)} value={String(item.status ?? "")} />,
                  String(item.generated_at ?? ""),
                ],
              }))}
              emptyTitle="最近信号"
              emptyDetail="还没有新的持久化 signal 时，可以先看上面的当前判断卡片。"
            />

            <DataTable
              columns={["Symbol", "Side", "Type", "Status"]}
              rows={workspace.recent_orders.map((item, index) => ({
                id: String(item.id ?? index),
                cells: [
                  String(item.symbol ?? ""),
                  String(item.side ?? ""),
                  String(item.orderType ?? item.order_type ?? ""),
                  <StatusBadge key={String(item.id ?? index)} value={String(item.status ?? "")} />,
                ],
              }))}
              emptyTitle="最近执行结果"
              emptyDetail="先启动策略并派发最新信号，再回到这里确认执行链路有没有真正走通。"
            />
          </section>
        </>
      )}
    </AppShell>
  );
}

type ActionFormProps = {
  action: string;
  label: string;
  focusSymbol: string;
};

function ActionForm({ action, label, focusSymbol }: ActionFormProps) {
  const returnTo = focusSymbol ? `/strategies?symbol=${encodeURIComponent(focusSymbol)}` : "/strategies";

  return (
    <form action="/actions" method="post" className="action-card">
      <input type="hidden" name="action" value={action} />
      <input type="hidden" name="strategyId" value="1" />
      <input type="hidden" name="returnTo" value={returnTo} />
      <FormSubmitButton
        type="submit"
        variant={action === "dispatch_latest_signal" ? "terminal" : "outline"}
        idleLabel={label}
        pendingLabel={`${label}运行中…`}
        pendingHint="执行动作已提交，页面会在状态返回后自动刷新。"
      />
      <p>{focusSymbol ? `当前跟进对象：${focusSymbol}。` : ""}把控制动作统一走控制平面，当前阶段固定控制整台执行器。</p>
    </form>
  );
}

function readQueryText(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return String(value[0] ?? "").trim();
  }
  return String(value ?? "").trim();
}

function readText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

function AutomationInfo({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-[color:var(--panel-strong)]/80 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-3 text-sm font-medium leading-6 text-foreground">{value}</p>
    </div>
  );
}

function StrategyCard({ item }: { item: StrategyWorkspaceCard }) {
  const executionHint = formatExecutionHint(item.current_evaluation);
  return (
    <article className="action-card strategy-card">
      <div className="stack-xs">
        <p className="eyebrow">{item.key}</p>
        <h4>{item.display_name}</h4>
        <p>{item.description}</p>
      </div>
      <div className="stack-xs">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>运行状态：</span>
          <StatusBadge value={item.runtime_status} />
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>当前判断：</span>
          <StatusBadge value={String(item.current_evaluation.decision ?? "unknown")} />
        </div>
        <p>研究分数：{formatResearchScore(item.research_summary.score)}</p>
        <p>模型版本：{item.research_summary.model_version || "暂无训练产物"}</p>
        <p>研究解释：{item.research_summary.explanation || "暂无研究解释"}</p>
        <p>推荐策略：{formatPreferredStrategy(item.research_cockpit.recommended_strategy)}</p>
        <p>执行建议：{executionHint}</p>
        <p>观察币种：{item.symbols.join(" / ")}</p>
        <p>参数摘要：{formatParamSummary(item.default_params)}</p>
        <p>最近信号：{formatLatestSignal(item.latest_signal)}</p>
      </div>
    </article>
  );
}

function formatParamSummary(params: Record<string, unknown>): string {
  return Object.entries(params)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" · ");
}

function formatLatestSignal(item: Record<string, unknown> | null): string {
  if (!item) {
    return "暂无持久化信号";
  }
  return `${String(item.symbol ?? "")} / ${String(item.status ?? "")}`;
}

function formatResearchScore(value: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : "暂无研究分数";
}

function formatExecutionHint(item: Record<string, unknown>): string {
  const decision = String(item.decision ?? "").trim();
  if (decision === "signal") {
    return "可以继续看最新信号并决定是否派发。";
  }
  if (decision === "watch") {
    return "先保持观察，暂时不要派发。";
  }
  if (decision === "block") {
    return "当前不适合执行，先不要派发。";
  }
  return "先确认执行器状态和最新信号。";
}

function formatPreferredStrategy(value: StrategyWorkspaceCard["research_cockpit"]["recommended_strategy"]): string {
  if (value === "trend_breakout") {
    return "趋势突破";
  }
  if (value === "trend_pullback") {
    return "趋势回调";
  }
  return "继续观察";
}

function formatLatestBalance(item: WorkspaceAccountState["latest_balance"]): string {
  if (!item) {
    return "暂无余额";
  }
  return `${String(item.asset ?? "")} / ${String(item.tradeStatus ?? "")}`;
}

function formatLatestOrder(item: WorkspaceAccountState["latest_order"]): string {
  if (!item) {
    return "暂无订单";
  }
  return `${String(item.symbol ?? "")} / ${String(item.status ?? "")}`;
}

function formatLatestPosition(item: WorkspaceAccountState["latest_position"]): string {
  if (!item) {
    return "暂无持仓";
  }
  return `${String(item.symbol ?? "")} / ${String(item.side ?? "")}`;
}
