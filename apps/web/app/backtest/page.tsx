/* 这个文件负责渲染回测工作台，让成本模型、净收益、回撤和动作段直接可见。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { getBacktestWorkspace } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";

export default async function BacktestPage() {
  const session = await getControlSessionState();
  const response = await getBacktestWorkspace();
  const workspace = response.data.item;
  const metrics = workspace.training_backtest.metrics;

  return (
    <AppShell
      title="回测工作台"
      subtitle="把回测结果拆开讲清楚：成本模型是什么，净收益是多少，成本影响、回撤和动作段又分别代表什么。"
      currentPath="/backtest"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="回测工作台"
        title="先确认净收益、成本影响和动作段，再决定这套研究结果值不值得进入验证。"
        description="这里不会只给一个回测分数，而是直接把成本模型、净收益、回撤、Sharpe 和动作段统计摊开，方便你判断这次回测到底靠不靠谱。"
      />

      <MetricGrid
        items={[
          { label: "净收益", value: metric(metrics, "net_return_pct"), detail: `${workspace.overview.holding_window || "未写入"} / ${workspace.backend}` },
          { label: "成本影响", value: metric(metrics, "cost_impact_pct"), detail: "把手续费和滑点单独摊开看" },
          { label: "最大回撤", value: metric(metrics, "max_drawdown_pct"), detail: "亏损最深的那一段" },
          { label: "动作段统计", value: metric(metrics, "action_segment_count"), detail: `方向切换 ${metric(metrics, "direction_switch_count")}` },
        ]}
      />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_380px]">
        <div className="space-y-5">
          <DataTable
            columns={["标的", "模板", "净收益", "成本影响", "最大回撤", "Sharpe"]}
            rows={workspace.leaderboard.map((item) => ({
              id: item.symbol,
              cells: [
                item.symbol,
                item.strategy_template || "未标注",
                valueOrFallback(item.backtest.net_return_pct),
                valueOrFallback(item.backtest.cost_impact_pct),
                valueOrFallback(item.backtest.max_drawdown_pct),
                valueOrFallback(item.backtest.sharpe),
              ],
            }))}
            emptyTitle="还没有候选回测"
            emptyDetail="先运行研究训练和推理，再回到这里比较候选回测。"
          />

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>交易明细</CardTitle>
              <CardDescription>当前最小回测先展示动作段和切换统计，逐笔明细后续再继续补齐。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="动作段统计" value={metric(metrics, "action_segment_count")} />
              <InfoBlock label="方向切换" value={metric(metrics, "direction_switch_count")} />
              <InfoBlock label="胜率" value={metric(metrics, "win_rate")} />
              <InfoBlock label="连续亏损段" value={metric(metrics, "max_loss_streak")} />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-5">
          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>成本模型</CardTitle>
              <CardDescription>先确认手续费、滑点和回合成本是怎么算的。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="手续费" value={valueOrFallback(workspace.assumptions.fee_bps)} />
              <InfoBlock label="滑点" value={valueOrFallback(workspace.assumptions.slippage_bps)} />
              <InfoBlock label="回合成本" value={valueOrFallback(workspace.assumptions.round_trip_cost_pct)} />
              <InfoBlock label="成本模型" value={valueOrFallback(workspace.assumptions.cost_model)} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>回测摘要</CardTitle>
              <CardDescription>把关键结果压成一眼能看懂的最小摘要。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoBlock label="总收益" value={metric(metrics, "total_return_pct")} />
              <InfoBlock label="毛收益" value={metric(metrics, "gross_return_pct")} />
              <InfoBlock label="净收益" value={metric(metrics, "net_return_pct")} />
              <InfoBlock label="Sharpe" value={metric(metrics, "sharpe")} />
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-foreground break-all">{value}</p>
    </div>
  );
}

function metric(metrics: Record<string, string>, key: string) {
  return valueOrFallback(metrics[key]);
}

function valueOrFallback(value: string | undefined) {
  return value && value.length > 0 ? value : "n/a";
}
