/* 这个文件负责渲染订单页。 */
"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { ToolDetailHub } from "../../components/tool-detail-hub";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Skeleton } from "../../components/ui/skeleton";
import { DEFAULT_API_TIMEOUT, getOrdersPageModel, listOrders } from "../../lib/api";

type OrdersPageModel = {
  source: string;
  truthSource: string;
  items: Array<{ id: string; symbol: string; side: string; orderType: string; status: string }>;
};

export default function OrdersPage() {
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });
  const [model, setModel] = useState<OrdersPageModel>(getOrdersPageModel());
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {
        // Keep default session state
      });
  }, []);

  useEffect(() => {
    if (!session.token) {
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), DEFAULT_API_TIMEOUT);

    listOrders(controller.signal)
      .then((response) => {
        if (!response.error) {
          setModel(response.data);
        }
      })
      .catch(() => {
        // API 不可用时仍然保留演示数据。
      })
      .finally(() => {
        clearTimeout(timeoutId);
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [session.token]);

  return (
    <AppShell
      title="订单"
      subtitle="订单页现在只负责核对执行回报，不再承担主流程判断。"
      currentPath="/orders"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="订单详情"
        title="订单详情页"
        description="先在执行页或任务页判断要不要查结果，再回到这里确认执行器到底回了什么。"
      />

      <ToolDetailHub
        summary='订单页只负责回答"这次执行到底回了什么"，主链判断继续留在首页、执行页和任务页。'
        detail="这里保留关键数量、订单状态和回报明细，帮助你确认执行是否真正落地，但不再把订单页当成下一步动作的起点。"
        mainHint="首页已经说明要不要继续执行；要核对订单回报时，再回订单页看明细。"
        strategiesHint="执行按钮和推进判断留在策略页，这里只用来确认订单状态。"
        tasksHint="任务页提示失败或需要人工复核时，再回订单页对照最近回报。"
      />

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : (
        <MetricGrid
          items={[
            { label: "订单数量", value: String(model.items.length), detail: "来自控制平面的聚合视图" },
            { label: "最新品种", value: model.items[0]?.symbol ?? "n/a", detail: "优先确认最新订单是不是你刚刚派发的品种" },
            { label: "最新状态", value: model.items[0]?.status ?? "waiting", detail: "看到 closed 或 filled，说明执行已经落地" },
          ]}
        />
      )}

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        {isLoading ? (
          <Skeleton className="h-64" />
        ) : (
          <DataTable
            columns={["Symbol", "Side", "Type", "Status"]}
            rows={model.items.map((item) => ({
              id: item.id,
              cells: [item.symbol, item.side, item.orderType, <StatusBadge key={item.id} value={item.status} />],
            }))}
            emptyTitle="还没有订单"
            emptyDetail="先去策略页派发最新信号；如果这里已经清空，但余额页还有少量币，优先按余额页提示判断是不是交易所零头。"
          />
        )}

        <div className="space-y-6">
          <Card className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">同步来源</p>
              <CardTitle>先确认订单数据来自哪里</CardTitle>
              <CardDescription>右侧只保留结果解释，不再在主区重复堆说明文字。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
              {isLoading ? (
                <>
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-48" />
                </>
              ) : (
                <>
                  <p>source：<span className="text-foreground">{model.source}</span></p>
                  <p>truth source：<span className="text-foreground">{model.truthSource}</span></p>
                  <p>最新订单：<span className="text-foreground">{model.items[0]?.symbol ?? "n/a"} / {model.items[0]?.status ?? "waiting"}</span></p>
                </>
              )}
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