/* 这个文件负责渲染首页驾驶舱，并给出成功链路和异常链路指引。 */

import { AppShell } from "../components/app-shell";
import { FeedbackBanner } from "../components/feedback-banner";
import { MetricGrid } from "../components/metric-grid";
import { PageHero } from "../components/page-hero";
import { StatusBadge } from "../components/status-badge";
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

  const signals = await safeLoad(() => listSignals(), []);
  const orders = await safeLoad(() => listOrders(), []);
  const positions = await safeLoad(() => listPositions(), []);
  const strategies = isAuthenticated ? await safeLoad(() => listStrategies(token), []) : [];
  const tasks = isAuthenticated ? await safeLoad(() => listTasks(token), []) : [];
  const riskEvents = isAuthenticated ? await safeLoad(() => listRiskEvents(token), []) : [];

  const latestSignal = signals[0];
  const latestTask = tasks[0];
  const latestRisk = riskEvents[0];

  return (
    <AppShell
      title="驾驶舱"
      subtitle="用一条清晰的控制动线，把信号、执行、风险与任务收在同一视图里。"
      currentPath="/"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="驾驶舱"
        title="系统总览放在最前面，从登录到执行，再到异常可见，都有明确下一步。"
        description="这里优先展示当前系统状态、推荐动作和演示链路，让第一次进入系统的人也能快速知道该点哪里、先看什么。"
        aside={
          <div className="hero-stack">
            <div className="info-chip">市场：crypto</div>
            <div className="info-chip">交易所：Binance</div>
            <div className="info-chip">执行器：Freqtrade</div>
          </div>
        }
      />

      <MetricGrid
        items={[
          {
            label: "Signals",
            value: String(signals.length),
            detail: latestSignal ? `最新：${latestSignal.symbol}` : "还没有信号",
          },
          {
            label: "Strategies",
            value: String(strategies.length),
            detail: strategies[0] ? `当前状态：${strategies[0].status}` : "登录后查看策略控制",
          },
          {
            label: "Orders",
            value: String(orders.length),
            detail: orders[0] ? `最新订单：${orders[0].status}` : "还没有订单反馈",
          },
          {
            label: "Tasks",
            value: String(tasks.length),
            detail: latestTask ? `最近任务：${latestTask.taskType}` : "登录后查看任务反馈",
          },
        ]}
      />

      <section className="content-grid">
        <article className="panel">
          <p className="eyebrow">推荐下一步</p>
          <h3>先跑成功链路，再观察异常链路</h3>
          <p>如果你已经登录，就先运行信号流水线、启动策略、派发最新信号。之后再切到风险和任务页观察异常路径。</p>

	          <div className="action-grid">
	            <form action="/actions" method="post" className="action-card">
	              <input type="hidden" name="action" value="run_pipeline" />
	              <input type="hidden" name="returnTo" value="/" />
	              <button type="submit">运行 Qlib 信号流水线</button>
	              <p>先生成最新研究信号，让后面的执行链路有输入。</p>
	            </form>

	            <form action="/actions" method="post" className="action-card">
	              <input type="hidden" name="action" value="run_mock_pipeline" />
	              <input type="hidden" name="returnTo" value="/" />
	              <button type="submit">运行演示信号流水线</button>
	              <p>如果要重复验证 dry-run 成功链路，就用这条稳定的演示输入。</p>
	            </form>

	            <form action="/actions" method="post" className="action-card">
              <input type="hidden" name="action" value="start_strategy" />
              <input type="hidden" name="strategyId" value="1" />
              <input type="hidden" name="returnTo" value="/" />
              <button type="submit">启动策略</button>
              <p>让控制面进入可执行状态，为派发最新信号做准备。</p>
            </form>

            <form action="/actions" method="post" className="action-card">
              <input type="hidden" name="action" value="dispatch_latest_signal" />
              <input type="hidden" name="strategyId" value="1" />
              <input type="hidden" name="returnTo" value="/" />
              <button type="submit">派发最新信号</button>
              <p>把研究结果送进执行和同步链路，直接看订单与持仓反馈。</p>
            </form>
          </div>
        </article>

        <article className="panel">
          <p className="eyebrow">成功链路</p>
          <h3>你现在最应该先确认的 4 个状态</h3>
          <ul className="flow-list">
            <li>
              <span>信号准备完成</span>
              <StatusBadge value={latestSignal?.status ?? "waiting"} />
            </li>
            <li>
              <span>策略可以执行</span>
              <StatusBadge value={strategies[0]?.status ?? "login required"} />
            </li>
            <li>
              <span>订单反馈可见</span>
              <StatusBadge value={orders[0]?.status ?? "waiting"} />
            </li>
            <li>
              <span>持仓状态可见</span>
              <StatusBadge value={positions[0]?.side ?? "waiting"} />
            </li>
          </ul>
        </article>

        <article className="panel">
          <p className="eyebrow">异常链路</p>
          <h3>把失败做成可见，而不是事后猜测</h3>
          <p>你可以主动制造一个失败任务，或者先停掉策略再派发信号，系统会把风险和任务状态直接回写到页面。</p>
          <div className="action-grid">
            <form action="/actions" method="post" className="action-card action-card-danger">
              <input type="hidden" name="action" value="trigger_reconcile_failure" />
              <input type="hidden" name="returnTo" value="/" />
              <button type="submit">制造失败任务</button>
              <p>触发一个失败的对账任务，确认异常路径对用户是可见的。</p>
            </form>

            <a className="action-card button-link" href={isAuthenticated ? "/risk" : "/login?next=%2Frisk"}>
              <strong>查看风险事件</strong>
              <p>{latestRisk ? `最新规则：${latestRisk.ruleName}` : "当前还没有风险事件，先停策略再派发信号。"} </p>
            </a>
          </div>
        </article>
      </section>
    </AppShell>
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
