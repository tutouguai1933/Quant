/* 这个文件负责渲染余额页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { getBalancesPageModel, listBalances } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


export default async function BalancesPage() {
  const session = await getControlSessionState();
  let model = getBalancesPageModel();

  try {
    const response = await listBalances();
    if (!response.error) {
      model = response.data;
    }
  } catch {
    // API 不可用时仍然保留演示数据。
  }

  const items = model.items;
  const dustItems = items.filter((item) => item.tradeStatus === "dust");
  const tradableItems = items.filter((item) => item.tradeStatus === "tradable");
  const firstFocusItem = dustItems[0] ?? tradableItems[0] ?? items[0];

  return (
    <AppShell
      title="余额"
      subtitle="余额页先回答账户里现在有什么，再区分哪些是真实可用，哪些还处于冻结中。"
      currentPath="/balances"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="余额"
        title="真实账户余额应该单独看清楚"
        description="这里优先展示真实账户余额，不和 dry-run 的订单与持仓混在一起，避免把资产视图和执行视图看混。页面还会直接标出哪些是可交易余额，哪些只是交易所零头。"
      />

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
    </AppShell>
  );
}
