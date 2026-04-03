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
      subtitle="先看当前最佳判断，再决定是否进入图表、策略和执行，不先把你丢进一堆列表里。"
      currentPath="/"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="决策优先"
        title="先决定该跟哪个候选，再进入图表、策略和执行。"
        description="首页现在只做一件事：把当前最重要的判断、动作和异常入口压缩到一屏里。"
        aside={
          <div className="hero-stack">
            <div className="info-chip">市场：Crypto</div>
            <div className="info-chip">研究：Qlib</div>
            <div className="info-chip">执行：Freqtrade</div>
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

      <section className="terminal-layout">
        <div className="terminal-side">
          <article className="panel terminal-panel">
            <p className="eyebrow">推荐下一步</p>
            <h3>先跑研究，再决定是否进入执行</h3>
            <p>先把研究结果拉出来，再去图表页和策略页确认是否继续推进。首页只保留最短动作链。</p>
            <div className="terminal-action-stack">
              <form action="/actions" method="post" className="action-card">
                <input type="hidden" name="action" value="run_pipeline" />
                <input type="hidden" name="returnTo" value="/" />
                <button type="submit">运行 Qlib 信号流水线</button>
                <p>先生成最新研究候选。</p>
              </form>
              <form action="/actions" method="post" className="action-card">
                <input type="hidden" name="action" value="run_mock_pipeline" />
                <input type="hidden" name="returnTo" value="/" />
                <button type="submit">运行演示信号流水线</button>
                <p>快速重复验证稳定链路。</p>
              </form>
              <a className="action-card button-link" href="/signals">
                <strong>查看统一研究报告</strong>
                <p>先确认当前最佳候选和筛选通过率。</p>
              </a>
            </div>
          </article>

          <article className="panel terminal-panel">
            <p className="eyebrow">异常链路</p>
            <h3>把失败入口保留在左侧</h3>
            <p>如果你要验证异常链路，直接从这里制造失败任务或查看风险事件，不需要翻到页面底部。</p>
            <div className="terminal-action-stack">
              <form action="/actions" method="post" className="action-card action-card-danger">
                <input type="hidden" name="action" value="trigger_reconcile_failure" />
                <input type="hidden" name="returnTo" value="/" />
                <button type="submit">制造失败任务</button>
                <p>确认任务失败能否被清楚看见。</p>
              </form>
              <a className="action-card button-link" href={isAuthenticated ? "/risk" : "/login?next=%2Frisk"}>
                <strong>查看风险事件</strong>
                <p>{latestRisk ? `最近规则：${latestRisk.ruleName}` : "当前没有新风险事件。"} </p>
              </a>
            </div>
          </article>
        </div>

        <div className="terminal-main">
          <article className="panel terminal-panel terminal-panel-strong">
            <p className="eyebrow">当前决策板</p>
            <h3>你现在最应该先确认的 4 个状态</h3>
            <ul className="terminal-status-list">
              <li>
                <div>
                  <strong>研究信号</strong>
                  <p>{latestSignal ? `当前最新候选：${latestSignal.symbol}` : "还没有研究信号。"} </p>
                </div>
                <StatusBadge value={latestSignal?.status ?? "waiting"} />
              </li>
              <li>
                <div>
                  <strong>执行器状态</strong>
                  <p>{strategies[0] ? "策略页已可直接接着执行。" : "登录后查看执行器状态。"} </p>
                </div>
                <StatusBadge value={strategies[0]?.status ?? "login required"} />
              </li>
              <li>
                <div>
                  <strong>订单反馈</strong>
                  <p>{orders[0] ? "执行链已有返回。" : "当前还没有新订单反馈。"} </p>
                </div>
                <StatusBadge value={orders[0]?.status ?? "waiting"} />
              </li>
              <li>
                <div>
                  <strong>持仓状态</strong>
                  <p>{positions[0] ? "持仓页已有状态可读。" : "当前没有新持仓状态。"} </p>
                </div>
                <StatusBadge value={positions[0]?.side ?? "waiting"} />
              </li>
            </ul>
          </article>

          <article className="panel terminal-panel">
            <p className="eyebrow">执行入口</p>
            <h3>研究确认后，再进入策略控制</h3>
            <p>如果已经确认候选，可以继续启动策略并派发最新信号；如果还没确认，先去市场页和单币页看图表细节。</p>
            <div className="terminal-inline-actions">
              <form action="/actions" method="post" className="action-card">
                <input type="hidden" name="action" value="start_strategy" />
                <input type="hidden" name="strategyId" value="1" />
                <input type="hidden" name="returnTo" value="/" />
                <button type="submit">启动策略</button>
                <p>让执行器进入可派发状态。</p>
              </form>
              <form action="/actions" method="post" className="action-card">
                <input type="hidden" name="action" value="dispatch_latest_signal" />
                <input type="hidden" name="strategyId" value="1" />
                <input type="hidden" name="returnTo" value="/" />
                <button type="submit">派发最新信号</button>
                <p>把研究结果送进执行链。</p>
              </form>
              <a className="action-card button-link" href="/market">
                <strong>先去市场页看候选</strong>
                <p>按单币顺序继续判断。</p>
              </a>
            </div>
          </article>
        </div>
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
