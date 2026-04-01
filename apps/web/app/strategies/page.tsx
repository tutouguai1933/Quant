/* 这个文件负责渲染策略中心页面，统一展示策略卡片、白名单、最近信号和执行结果。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { readFeedback } from "../../lib/feedback";
import { getStrategyWorkspace, getStrategyWorkspaceFallback, type StrategyWorkspaceCard } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function StrategiesPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { token, isAuthenticated } = session;
  const feedback = readFeedback(params);
  let workspace = getStrategyWorkspaceFallback();

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
        description="这个页面把两套首批波段策略、白名单、最近信号和最近执行结果放到一条清晰动线上。"
      />

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
          <MetricGrid
            items={[
              { label: "策略数量", value: String(workspace.overview.strategy_count), detail: "当前阶段固定只做两套首批波段策略" },
              { label: "运行中", value: String(workspace.overview.running_count), detail: "running 才能继续派发最新信号" },
              { label: "白名单", value: String(workspace.overview.whitelist_count), detail: "只在固定币种池里做最小 dry-run" },
              { label: "最近执行", value: String(workspace.overview.order_count), detail: "方便快速确认链路有没有真正走通" },
            ]}
          />

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

          <MetricGrid
            items={[
              { label: "研究状态", value: workspace.research.status, detail: workspace.research.detail },
              { label: "模型版本", value: workspace.research.model_version || "n/a", detail: "最近训练产物已经回到策略工作台" },
              { label: "研究信号", value: String(workspace.research.signal_count), detail: "最近推理结果中可用的信号数量" },
            ]}
          />

          <section className="panel">
            <p className="eyebrow">两套首批波段策略</p>
            <h3>策略中心</h3>
            <p>先看每套策略现在的判断，再决定是继续观察，还是把最新信号派发给执行器。</p>

            <div className="strategy-grid">
              {workspace.strategies.map((item) => (
                <StrategyCard key={item.key} item={item} />
              ))}
            </div>
          </section>

          <section className="panel">
            <p className="eyebrow">白名单摘要</p>
            <h3>当前只在固定币种池里做 dry-run</h3>
            <p>{workspace.whitelist.join(" / ")}</p>
          </section>

          <section className="panel">
            <p className="eyebrow">动作反馈</p>
            <h3>执行器控制</h3>
            <p>这些动作控制的是整台 Freqtrade 执行器，不是单张策略卡。推荐顺序：先启动，再派发。</p>

            <div className="action-grid">
              <ActionForm action="start_strategy" label="启动策略" />
              <ActionForm action="pause_strategy" label="暂停策略" />
              <ActionForm action="stop_strategy" label="停止策略" />
              <ActionForm action="dispatch_latest_signal" label="派发最新信号" />
            </div>
          </section>

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
        </>
      )}
    </AppShell>
  );
}

type ActionFormProps = {
  action: string;
  label: string;
};

function ActionForm({ action, label }: ActionFormProps) {
  return (
    <form action="/actions" method="post" className="action-card">
      <input type="hidden" name="action" value={action} />
      <input type="hidden" name="strategyId" value="1" />
      <input type="hidden" name="returnTo" value="/strategies" />
      <button type="submit">{label}</button>
      <p>把控制动作统一走控制平面，当前阶段固定控制整台执行器。</p>
    </form>
  );
}

function StrategyCard({ item }: { item: StrategyWorkspaceCard }) {
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
        <p>判断原因：{String(item.current_evaluation.reason ?? "n/a")}</p>
        <p>判断信心：{formatValue(item.current_evaluation.confidence, "n/a")}</p>
        <p>研究门控：{formatValue(asResearchGate(item.current_evaluation).status, "n/a")}</p>
        <p>研究分数：{formatValue(item.research_summary.score, "n/a")}</p>
        <p>模型版本：{formatValue(item.research_summary.model_version, "n/a")}</p>
        <p>研究解释：{formatValue(item.research_summary.explanation, "暂无研究结果")}</p>
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

function formatValue(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}

function formatLatestSignal(item: Record<string, unknown> | null): string {
  if (!item) {
    return "暂无持久化信号";
  }
  return `${String(item.symbol ?? "")} / ${String(item.status ?? "")}`;
}

function asResearchGate(evaluation: Record<string, unknown>): Record<string, unknown> {
  const gate = evaluation.research_gate;
  if (gate && typeof gate === "object" && !Array.isArray(gate)) {
    return gate as Record<string, unknown>;
  }
  return {};
}
