/* 这个文件负责渲染持仓页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { getPositionsPageModel, listPositions } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


export default async function PositionsPage() {
  const session = await getControlSessionState();
  let model = getPositionsPageModel();

  try {
    const response = await listPositions();
    if (!response.error) {
      model = response.data;
    }
  } catch {
    // API 不可用时仍然保留演示数据。
  }

  return (
    <AppShell
      title="持仓"
      subtitle="持仓页的重点不是密度，而是让你快速判断执行后的仓位有没有真的形成。"
      currentPath="/positions"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="持仓"
        title="仓位变化是否符合你的预期"
        description="这里先看是否出现目标品种和方向，再看数量和浮盈亏。当前阶段不做主观交易终端。"
      />

      <MetricGrid
        items={[
          { label: "持仓数量", value: String(model.items.length), detail: "执行后应该能在这里看到最新仓位" },
          { label: "最新方向", value: model.items[0]?.side ?? "waiting", detail: "long / short / flat 是最先要确认的信号" },
          { label: "最新品种", value: model.items[0]?.symbol ?? "n/a", detail: "确认是不是你刚刚派发的目标品种" },
        ]}
      />

      <section className="panel">
        <p className="eyebrow">同步来源</p>
        <h3>先确认仓位数据来自哪里</h3>
        <p>
          source:
          {" "}
          {model.source}
        </p>
        <p>
          truth source:
          {" "}
          {model.truthSource}
        </p>
      </section>

      <DataTable
        columns={["Symbol", "Side", "Quantity", "PnL"]}
        rows={model.items.map((item) => ({
          id: item.id,
          cells: [item.symbol, <StatusBadge key={item.id} value={item.side} />, item.quantity, item.unrealizedPnl],
        }))}
        emptyTitle="还没有持仓"
        emptyDetail="当订单已经成交后，再回到这里确认是否形成最新仓位。"
      />
    </AppShell>
  );
}
