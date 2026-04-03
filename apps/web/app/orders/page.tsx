/* 这个文件负责渲染订单页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
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
          { label: "最新状态", value: model.items[0]?.status ?? "waiting", detail: "看到 closed 或 filled，说明执行已经落地" },
        ]}
      />

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <DataTable
          columns={["Symbol", "Side", "Type", "Status"]}
          rows={model.items.map((item) => ({
            id: item.id,
            cells: [item.symbol, item.side, item.orderType, <StatusBadge key={item.id} value={item.status} />],
          }))}
          emptyTitle="还没有订单"
          emptyDetail="先去策略页派发最新信号；如果这里已经清空，但余额页还有少量币，优先按余额页提示判断是不是交易所零头。"
        />

        <div className="space-y-6">
          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">同步来源</p>
              <CardTitle>先确认订单数据来自哪里</CardTitle>
              <CardDescription>右侧只保留结果解释，不再在主区重复堆说明文字。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              <p>source：<span className="text-foreground">{model.source}</span></p>
              <p>truth source：<span className="text-foreground">{model.truthSource}</span></p>
              <p>最新订单：<span className="text-foreground">{model.items[0]?.symbol ?? "n/a"} / {model.items[0]?.status ?? "waiting"}</span></p>
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">结果判断</p>
              <CardTitle>执行是否真正落地</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoTile title="有订单时" detail="先看最新品种和状态，确认是不是你刚刚派发的目标。" />
              <InfoTile title="没订单时" detail="如果余额页还剩少量币，通常说明执行已结束，只留下交易所零头。" />
            </CardContent>
          </Card>
        </div>
      </section>
    </AppShell>
  );
}

function InfoTile({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-border/70 bg-background/50 p-4">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
