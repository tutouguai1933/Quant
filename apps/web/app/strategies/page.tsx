/* 这个文件负责渲染策略中心页面，统一展示策略判断和执行动作。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ResearchCandidateBoard } from "../../components/research-candidate-board";
import { StatusBadge } from "../../components/status-badge";
import { readFeedback } from "../../lib/feedback";
import {
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

  if (token) {
    try {
      const response = await getStrategyWorkspace(token);
      if (!response.error) {
        workspace = response.data;
      }
    } catch {
      // API 不可用时仍然保留占位数据。
    }
  }

  try {
    if (focusSymbol) {
      const response = await getResearchCandidate(focusSymbol);
      if (!response.error && response.data.item) {
        candidateSnapshot = {
          items: [response.data.item],
          summary: {
            candidate_count: 1,
            ready_count: response.data.item.allowed_to_dry_run ? 1 : 0,
          },
        };
      }
    } else {
      const response = await getResearchCandidates();
      if (!response.error) {
        candidateSnapshot = response.data;
      }
    }
  } catch {
    // API 不可用时仍然保留候选兜底数据。
  }

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
        <section className="panel">
          <p className="eyebrow">当前跟进对象</p>
          <h3>{focusSymbol}</h3>
          <p>你是带着这个币种从市场页或图表页进入策略中心的，先围绕它确认判断，再决定要不要继续派发。</p>
          <a className="button-link secondary-link" href={`/market/${encodeURIComponent(focusSymbol)}`}>
            返回这个币种的图表页
          </a>
        </section>
      ) : null}

      {!isAuthenticated ? (
        <section className="panel">
          <p className="eyebrow">动作反馈</p>
          <h3>当前页面需要登录</h3>
          <p>登录后才能看到真实策略状态、当前判断和最近执行结果，也才能继续启动、暂停、停止和派发。</p>
          <a className="button-link primary-link" href="/login?next=%2Fstrategies">
            先去登录
          </a>
        </section>
      ) : (
        <>
          <section className="panel">
            <p className="eyebrow">双栏布局</p>
            <h3>左边看判断，右边看执行</h3>
            <p>这页把判断和执行分开，避免一整屏连续往下扫。</p>
          </section>

          <MetricGrid
            items={[
              { label: "策略数量", value: String(workspace.overview.strategy_count), detail: "当前阶段固定只做两套首批波段策略" },
              { label: "运行中", value: String(workspace.overview.running_count), detail: "running 才能继续派发最新信号" },
              { label: "白名单", value: String(workspace.overview.whitelist_count), detail: "只在固定币种池里做最小 dry-run" },
              { label: "最近执行", value: String(workspace.overview.order_count), detail: "方便快速确认链路有没有真正走通" },
            ]}
          />

          <section
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0, 1.4fr) minmax(320px, 0.9fr)",
              gap: "clamp(16px, 2vw, 24px)",
              alignItems: "start",
            }}
          >
            <section style={{ display: "grid", gap: "clamp(16px, 1.5vw, 20px)" }}>
              {workspace.research_recommendation ? (
                <section className="panel">
                  <p className="eyebrow">当前推荐执行候选</p>
                  <h3>{workspace.research_recommendation.symbol}</h3>
                  <p>
                    研究门：
                    {" "}
                    {workspace.research_recommendation.dry_run_gate.status}
                    {"，下一步动作："}
                    {workspace.research_recommendation.next_action || "先进入 dry-run 观察。"}
                  </p>
                  <div className="action-grid">
                    <a className="button-link secondary-link" href={`/market/${encodeURIComponent(workspace.research_recommendation.symbol)}`}>
                      去这个币的图表页
                    </a>
                    <a className="button-link secondary-link" href={`/strategies?symbol=${encodeURIComponent(workspace.research_recommendation.symbol)}`}>
                      围绕这个币继续执行
                    </a>
                  </div>
                </section>
              ) : null}

              <ResearchCandidateBoard
                title="研究候选"
                summary={candidateSnapshot.summary}
                items={candidateSnapshot.items}
                focusSymbol={focusSymbol}
                nextStep={focusSymbol ? `下一步动作：先围绕 ${focusSymbol} 确认是否允许进入 dry-run，再决定是否派发。` : "下一步动作：优先看是否允许进入 dry-run，再决定要不要派发。"}
              />

              <MetricGrid
                items={[
                  { label: "研究状态", value: workspace.research.status, detail: workspace.research.detail },
                  { label: "模型版本", value: workspace.research.model_version || "n/a", detail: "最近训练产物已经回到策略工作台" },
                  { label: "研究信号", value: String(workspace.research.signal_count), detail: "最近推理结果中可用的信号数量" },
                ]}
              />

              <section className="panel">
                <p className="eyebrow">下一步动作</p>
                <h3>把判断收口到可以执行的动作</h3>
                <p>先确认研究候选是否允许进入 dry-run，再决定要不要围绕这个币继续派发。</p>
                <div className="action-grid">
                  <a className="button-link secondary-link" href={focusSymbol ? `/market/${encodeURIComponent(focusSymbol)}` : "/signals"}>
                    去图表页确认
                  </a>
                  <a className="button-link secondary-link" href={focusSymbol ? `/strategies?symbol=${encodeURIComponent(focusSymbol)}` : "/strategies"}>
                    围绕这个币继续执行
                  </a>
                  <a className="button-link secondary-link" href="/signals">
                    回到信号页复核
                  </a>
                </div>
              </section>

              <section className="panel">
                <p className="eyebrow">策略判断</p>
                <h3>两套首批波段策略</h3>
                <p>只保留当前判断和执行建议，不再把页面往纵向拉长。</p>

                <div className="strategy-grid">
                  {workspace.strategies.map((item) => (
                    <StrategyCard key={item.key} item={item} />
                  ))}
                </div>
              </section>
            </section>

            <aside style={{ display: "grid", gap: "clamp(16px, 1.5vw, 20px)" }}>
              <section className="panel">
                <p className="eyebrow">执行器状态</p>
                <h3>先确认当前连的是谁</h3>
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
              </section>

              <section className="panel">
                <p className="eyebrow">账户收口</p>
                <h3>执行之后，回到同一套真实来源上看结果</h3>
                <p>
                  source:
                  {" "}
                  {workspace.account_state.source}
                  {" / "}
                  truth source:
                  {" "}
                  {workspace.account_state.truth_source}
                </p>
                <p>
                  余额：
                  {" "}
                  {workspace.account_state.summary.balance_count}
                  {"，可交易："}
                  {workspace.account_state.summary.tradable_balance_count}
                  {"，零头："}
                  {workspace.account_state.summary.dust_count}
                </p>
                <p>
                  订单：
                  {" "}
                  {workspace.account_state.summary.order_count}
                  {"，持仓："}
                  {workspace.account_state.summary.position_count}
                </p>
                <p>
                  最近余额：
                  {" "}
                  {formatLatestBalance(workspace.account_state.latest_balance)}
                  {"，最近订单："}
                  {formatLatestOrder(workspace.account_state.latest_order)}
                  {"，最近持仓："}
                  {formatLatestPosition(workspace.account_state.latest_position)}
                </p>
                <div className="action-grid">
                  <a className="button-link secondary-link" href="/balances">
                    去余额页
                  </a>
                  <a className="button-link secondary-link" href="/orders">
                    去订单页
                  </a>
                  <a className="button-link secondary-link" href="/positions">
                    去持仓页
                  </a>
                </div>
              </section>

              <section className="panel">
                <p className="eyebrow">执行动作</p>
                <h3>这些动作控制的是整台执行器</h3>
                <p>推荐顺序：先启动，再派发。当前阶段固定控制整台 Freqtrade 执行器。</p>

                <div className="action-grid">
                  <ActionForm action="start_strategy" label="启动策略" focusSymbol={focusSymbol} />
                  <ActionForm action="pause_strategy" label="暂停策略" focusSymbol={focusSymbol} />
                  <ActionForm action="stop_strategy" label="停止策略" focusSymbol={focusSymbol} />
                  <ActionForm action="dispatch_latest_signal" label="派发最新信号" focusSymbol={focusSymbol} />
                </div>
              </section>

              <section className="panel">
                <p className="eyebrow">白名单摘要</p>
                <h3>当前只在固定币种池里做 dry-run</h3>
                <p>{workspace.whitelist.join(" / ")}</p>
              </section>
            </aside>
          </section>

          <section
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
              gap: "clamp(16px, 2vw, 24px)",
              alignItems: "start",
            }}
          >
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
      <button type="submit">{label}</button>
      <p>{focusSymbol ? `当前关注：${focusSymbol}。` : ""}把控制动作统一走控制平面，当前阶段固定控制整台执行器。</p>
    </form>
  );
}

function readQueryText(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return String(value[0] ?? "").trim();
  }
  return String(value ?? "").trim();
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
        <p>
          运行状态：
          {" "}
          <StatusBadge value={item.runtime_status} />
        </p>
        <p>
          当前判断：
          {" "}
          <StatusBadge value={String(item.current_evaluation.decision ?? "unknown")} />
        </p>
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
