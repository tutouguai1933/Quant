/* 这个文件负责渲染余额页。 */
"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { ToolDetailHub } from "../../components/tool-detail-hub";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Skeleton } from "../../components/ui/skeleton";
import { getBalancesPageModel, listBalances } from "../../lib/api";

interface BalanceItem {
  id: string;
  asset: string;
  available: string;
  locked: string;
  tradeStatus: string;
  sellableQuantity: string;
  tradeHint: string;
}

interface BalancesModel {
  items: BalanceItem[];
  source: string;
  truthSource: string;
}

export default function BalancesPage() {
  const [session, setSession] = useState<{ isAuthenticated: boolean }>({
    isAuthenticated: false,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [model, setModel] = useState<BalancesModel>(getBalancesPageModel());

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {
        // Keep default session state
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 15000);

    listBalances(controller.signal)
      .then((response) => {
        clearTimeout(timeoutId);
        if (!response.error) {
          setModel(response.data);
        }
        setIsLoading(false);
      })
      .catch(() => {
        clearTimeout(timeoutId);
        setIsLoading(false);
      });

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, []);

  const items = model.items;
  const dustItems = items.filter((item) => item.tradeStatus === "dust");
  const tradableItems = items.filter((item) => item.tradeStatus === "tradable");
  const firstFocusItem = dustItems[0] ?? tradableItems[0] ?? items[0];

  return (
    <AppShell
      title="余额"
      subtitle="余额页现在只负责核对账户资产明细，不再承担主流程判断。"
      currentPath="/balances"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="余额详情"
        title="余额详情页"
        description="先在主工作台或执行页决定要不要查账户，再回到这里看真实余额、可交易资产和交易所零头。"
      />

      <ToolDetailHub
        summary="当主工作台或执行页提示要核对账户时，再回余额页看真实资产分布。"
        detail="余额页只保留账户资产、可卖数量和零头判断，帮助你确认执行结果有没有真正回到账户，不再自己承担流程推进。"
        mainHint="首页先告诉你该不该去看账户；需要确认资产时，再回余额页看真实余额。"
        strategiesHint="执行完成后先在策略页看判断，再回余额页核对资金有没有回补。"
        tasksHint="任务页如果提示同步或回填异常，可以回余额页确认问题是不是只停在资产层。"
      />

      {isLoading ? (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-64 rounded-xl" />
        </div>
      ) : (
        <>
          <section className="panel">
            <p className="eyebrow">同步来源</p>
            <h3>先确认这页读的是哪一层状态</h3>
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
            <p>当这里和订单页、持仓页都指向同一真实来源时，页面状态才算对齐。</p>
          </section>

          <MetricGrid
            items={[
              { label: "资产数量", value: String(items.length), detail: "这是当前返回的资产行数" },
              {
                label: "可交易资产",
                value: String(tradableItems.length),
                detail: `优先确认 ${firstFocusItem?.asset ?? "主资产"} 的可卖数量`,
              },
              {
                label: "零头资产",
                value: String(dustItems.length),
                detail: dustItems[0] ? `${dustItems[0].asset} 这类余额当前不能直接整笔卖出` : "当前没有检测到交易所零头",
              },
            ]}
          />

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
            <DataTable
              columns={["Asset", "Available", "Locked", "Status", "Sellable", "Hint"]}
              rows={items.map((item) => ({
                id: item.id,
                cells: [
                  item.asset,
                  item.available,
                  item.locked,
                  item.tradeStatus,
                  item.sellableQuantity,
                  item.tradeHint,
                ],
              }))}
              emptyTitle="还没有余额数据"
              emptyDetail="先确认 Binance 账户接口已经接通，再回到这里查看真实账户余额。"
            />

            <div className="space-y-6">
              <Card className="bg-card/90">
                <CardHeader>
                  <p className="eyebrow">同步来源</p>
                  <CardTitle>先确认这页读的是哪一层状态</CardTitle>
                  <CardDescription>余额、订单和持仓都指向同一真实来源时，页面状态才算对齐。</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>source：<span className="text-foreground">{model.source}</span></p>
                  <p>truth source：<span className="text-foreground">{model.truthSource}</span></p>
                  <p>当前焦点资产：<span className="text-foreground">{firstFocusItem?.asset ?? "n/a"}</span></p>
                </CardContent>
              </Card>

              <Card className="bg-card/90">
                <CardHeader>
                  <p className="eyebrow">账户判断</p>
                  <CardTitle>先分清可交易和零头</CardTitle>
                </CardHeader>
                <CardContent className="grid gap-3">
                  <InfoTile title="可交易资产" detail={tradableItems[0] ? `${tradableItems[0].asset} 当前仍可继续处理。` : "当前没有新的可交易资产。"} />
                  <InfoTile title="交易所零头" detail={dustItems[0] ? `${dustItems[0].asset} 当前更像零头，不要误当成系统卡仓。` : "当前没有检测到交易所零头。"} />
                  <InfoTile title="下一步动作" detail="先看 Sellable 和 Hint，再决定是继续交易还是仅做零头记录。" />
                </CardContent>
              </Card>
            </div>
          </section>
        </>
      )}
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
