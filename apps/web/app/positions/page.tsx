/* 这个文件负责渲染持仓页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { ToolDetailHub } from "../../components/tool-detail-hub";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
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
      subtitle="持仓页现在只负责核对仓位结果，不再承担主流程判断。"
      currentPath="/positions"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="持仓详情"
        title="持仓详情页"
        description="先在执行页或任务页确认要不要看结果，再回到这里核对仓位有没有真的形成。"
      />

      <ToolDetailHub
        summary="持仓页只负责回答“执行后的仓位有没有真的形成”，不再承担主链推进。"
        detail="这里保留最新方向、数量和浮盈亏，帮助你核对目标品种有没有真正建仓，但不再让持仓页自己承担判断职责。"
        mainHint="首页先决定要不要继续看执行结果，需要核对仓位时再回持仓页。"
        strategiesHint="策略页负责继续推进或暂停，这里只用来对照仓位结果。"
        tasksHint="任务页提示同步或恢复问题时，再回持仓页确认是不是仓位层异常。"
      />

      <MetricGrid
        items={[
          { label: "持仓数量", value: String(model.items.length), detail: "执行后应该能在这里看到最新仓位" },
          { label: "最新方向", value: model.items[0]?.side ?? "waiting", detail: "long / short / flat 是最先要确认的信号" },
          { label: "最新品种", value: model.items[0]?.symbol ?? "n/a", detail: "确认是不是你刚刚派发的目标品种" },
        ]}
      />

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <DataTable
          columns={["Symbol", "Side", "Quantity", "PnL"]}
          rows={model.items.map((item) => ({
            id: item.id,
            cells: [item.symbol, <StatusBadge key={item.id} value={item.side} />, item.quantity, item.unrealizedPnl],
          }))}
          emptyTitle="还没有持仓"
          emptyDetail="当订单已经成交后，再回到这里确认是否形成最新仓位；如果这里只显示空列表，记得去余额页看看是否只剩交易所零头。"
        />

        <div className="space-y-6">
          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">同步来源</p>
              <CardTitle>先确认仓位数据来自哪里</CardTitle>
              <CardDescription>这里只解释结果，不和主表抢空间。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              <p>source：<span className="text-foreground">{model.source}</span></p>
              <p>truth source：<span className="text-foreground">{model.truthSource}</span></p>
              <p>最新仓位：<span className="text-foreground">{model.items[0]?.symbol ?? "n/a"} / {model.items[0]?.side ?? "waiting"}</span></p>
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">仓位判断</p>
              <CardTitle>先看有没有真的形成仓位</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <InfoTile title="有持仓时" detail="优先确认目标品种、方向和数量，再判断是否符合预期。" />
              <InfoTile title="空列表时" detail="如果余额页还剩少量币，先把它当成交易所零头，而不是系统卡着持仓。" />
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
