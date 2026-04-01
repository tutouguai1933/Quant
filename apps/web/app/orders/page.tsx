/* 这个文件负责渲染订单页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { getOrdersPageModel, listOrders } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


export default async function OrdersPage() {
  const session = await getControlSessionState();
  let model = getOrdersPageModel();

  try {
    const response = await listOrders();
    if (!response.error) {
      model = response.data;
    }
  } catch {
    // API 不可用时仍然保留演示数据。
  }

  return (
    <AppShell
      title="订单"
      subtitle="订单页只回答一个问题：执行器到底回了什么。"
      currentPath="/orders"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="订单"
        title="订单反馈应该一眼能看懂"
        description="这里不再只是列出一串文本，而是先给出关键数量，再展开到表格，让你快速判断执行是否真的落地。"
      />

      <MetricGrid
        items={[
          { label: "订单数量", value: String(model.items.length), detail: "来自控制平面的聚合视图" },
          { label: "最新品种", value: model.items[0]?.symbol ?? "n/a", detail: "优先确认最新订单是不是你刚刚派发的品种" },
          { label: "最新状态", value: model.items[0]?.status ?? "waiting", detail: "filled 才说明执行已经完成" },
        ]}
      />

      <section className="panel">
        <p className="eyebrow">同步来源</p>
        <h3>先确认订单数据来自哪里</h3>
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
        columns={["Symbol", "Side", "Type", "Status"]}
        rows={model.items.map((item) => ({
          id: item.id,
          cells: [item.symbol, item.side, item.orderType, <StatusBadge key={item.id} value={item.status} />],
        }))}
        emptyTitle="还没有订单"
        emptyDetail="先去策略页派发最新信号，再回到这里确认执行反馈。"
      />
    </AppShell>
  );
}
