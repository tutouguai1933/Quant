/* 这个文件负责渲染余额页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { getBalancesPageModel, listBalances } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


export default async function BalancesPage() {
  const session = await getControlSessionState();
  let items = getBalancesPageModel().items;

  try {
    const response = await listBalances();
    if (!response.error) {
      items = response.data.items;
    }
  } catch {
    // API 不可用时仍然保留演示数据。
  }

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
        description="这里优先展示真实账户余额，不和 dry-run 的订单与持仓混在一起，避免把资产视图和执行视图看混。"
      />

      <MetricGrid
        items={[
          { label: "资产数量", value: String(items.length), detail: "这是当前返回的资产行数" },
          { label: "最高可用", value: items[0]?.available ?? "n/a", detail: `优先确认 ${items[0]?.asset ?? "主资产"} 的可用余额` },
          { label: "冻结资产", value: items[0]?.locked ?? "0", detail: "有冻结时，说明部分资产暂时不可直接使用" },
        ]}
      />

      <DataTable
        columns={["Asset", "Available", "Locked"]}
        rows={items.map((item) => ({
          id: item.id,
          cells: [item.asset, item.available, item.locked],
        }))}
        emptyTitle="还没有余额数据"
        emptyDetail="先确认 Binance 账户接口已经接通，再回到这里查看真实账户余额。"
      />
    </AppShell>
  );
}
