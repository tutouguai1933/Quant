/* 这个文件负责渲染数据工作台，让研究数据来源和快照状态直接可见。 */

import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { getDataWorkspace, getDataWorkspaceFallback } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";

type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function DataPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const symbol = readStringParam(params.symbol);
  const interval = readStringParam(params.interval);
  const limit = readNumberParam(params.limit, 200);

  let workspace = getDataWorkspaceFallback(symbol, interval, limit);
  try {
    const response = await getDataWorkspace(symbol, interval, limit);
    workspace = response.data.item;
  } catch {
    workspace = getDataWorkspaceFallback(symbol, interval, limit);
  }

  const stateSummary = formatDataStates(workspace.snapshot.data_states);
  const sampleRows = buildSampleRows(workspace.training_window.sample_window);

  return (
    <AppShell
      title="数据工作台"
      subtitle="先把研究到底用了什么数据讲清楚，再进入特征、策略研究和回测。"
      currentPath="/data"
      isAuthenticated={session.isAuthenticated}
    >
      <PageHero
        badge="数据工作台"
        title="先确认数据来源、时间范围、样本数量和快照状态。"
        description="这里把研究主链里最容易被隐藏的部分直接摊开：数据来源、数据快照、时间范围、样本数量，以及 raw / cleaned / feature-ready 现在停在哪一层。"
        aside={
          <div className="grid gap-3">
            <Button asChild size="sm">
              <Link href={buildRefreshHref(workspace.filters.selected_symbol, workspace.filters.selected_interval, workspace.filters.limit)}>
                刷新数据认知
              </Link>
            </Button>
            <p className="text-sm leading-6 text-muted-foreground">先看这页，再进入信号、回测和执行页，避免只看到结果不知道底层数据来自哪里。</p>
          </div>
        }
      />

      <MetricGrid
        items={[
          { label: "数据来源", value: `${workspace.sources.market} / ${workspace.sources.research}`, detail: "市场样本和研究快照都直接显示" },
          { label: "数据快照", value: workspace.snapshot.snapshot_id || "未生成", detail: "每次研究都会回指一个 snapshot id" },
          { label: "样本数量", value: String(workspace.preview.total_rows), detail: `${workspace.preview.symbol} / ${workspace.preview.interval}` },
          { label: "当前状态", value: workspace.snapshot.active_data_state || workspace.status, detail: "raw / cleaned / feature-ready" },
        ]}
      />

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_380px]">
        <div className="space-y-5">
          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>数据快照</CardTitle>
              <CardDescription>回答“这次研究到底用了什么数据”。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-2">
              <InfoBlock label="快照 ID" value={workspace.snapshot.snapshot_id || "未生成"} />
              <InfoBlock label="缓存签名" value={workspace.snapshot.cache_signature || "未命中"} />
              <InfoBlock label="当前状态" value={workspace.snapshot.active_data_state || workspace.status} />
              <InfoBlock label="快照路径" value={workspace.snapshot.dataset_snapshot_path || "当前未落盘"} />
            </CardContent>
          </Card>

          <DataTable
            columns={["状态层", "摘要"]}
            rows={stateSummary.map((item) => ({
              id: item.name,
              cells: [item.name, item.summary],
            }))}
            emptyTitle="还没有数据状态"
            emptyDetail="先运行一次 Qlib 训练，研究层才会把数据快照和状态写出来。"
          />

          <DataTable
            columns={["窗口", "时间范围 / 样本数"]}
            rows={sampleRows.map((item) => ({
              id: item.name,
              cells: [item.name, item.summary],
            }))}
            emptyTitle="时间范围暂不可用"
            emptyDetail="当前还没有训练窗口信息，先运行研究训练再回到这里。"
          />
        </div>

        <div className="space-y-5">
          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>当前筛选条件</CardTitle>
              <CardDescription>这些就是当前数据工作台正在看的币种、周期和样本范围。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <InfoBlock label="币种" value={workspace.filters.selected_symbol || "未选择"} />
              <InfoBlock label="周期" value={workspace.filters.selected_interval} />
              <InfoBlock label="时间范围" value={formatTimeRange(workspace.preview.first_open_time, workspace.preview.last_close_time)} />
              <InfoBlock label="样本数量" value={String(workspace.preview.total_rows)} />
              <InfoBlock label="预览状态" value={workspace.preview.status === "ready" ? "样本预览正常" : workspace.preview.detail || "当前预览不可用"} />
            </CardContent>
          </Card>

          <Card className="bg-card/90">
            <CardHeader>
              <CardTitle>标的列表</CardTitle>
              <CardDescription>先看白名单里哪些币已经进入当前数据认知。</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {workspace.symbols.length ? workspace.symbols.map((item) => (
                <Badge key={item.symbol} variant={item.selected ? "default" : "outline"}>
                  {item.symbol}
                </Badge>
              )) : <p className="text-sm leading-6 text-muted-foreground">当前还没有可展示的白名单标的。</p>}
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
      <p className="mt-2 text-sm font-medium leading-6 text-foreground break-all">{value || "n/a"}</p>
    </div>
  );
}

function readStringParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? String(value[0] ?? "") : String(value ?? "");
}

function readNumberParam(value: string | string[] | undefined, fallback: number): number {
  const parsed = Number(readStringParam(value));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function buildRefreshHref(symbol: string, interval: string, limit: number): string {
  const query = new URLSearchParams({
    symbol: symbol || "BTCUSDT",
    interval: interval || "4h",
    limit: String(limit || 200),
  });
  return `/data?${query.toString()}`;
}

function formatDataStates(dataStates: Record<string, unknown>) {
  const availableNames = ["raw", "cleaned", "feature-ready"].filter((name) => asRecord(dataStates[name]).row_count !== undefined || asRecord(dataStates[name]).symbol_count !== undefined);
  if (!availableNames.length) {
    return [];
  }
  const rows: Array<{ name: string; summary: string }> = [];
  for (const name of availableNames) {
    const payload = asRecord(dataStates[name]);
    const symbolCount = Number(payload.symbol_count ?? 0);
    const rowCount = Number(payload.row_count ?? 0);
    rows.push({
      name,
      summary: `symbol=${symbolCount} / rows=${rowCount}${dataStates.current === name ? " / 当前层" : ""}`,
    });
  }
  return rows;
}

function buildSampleRows(sampleWindow: Record<string, unknown>) {
  const rows: Array<{ name: string; summary: string }> = [];
  for (const name of ["training", "validation", "backtest"]) {
    const payload = asRecord(sampleWindow[name]);
    const start = String(payload.start ?? "");
    const end = String(payload.end ?? "");
    const count = Number(payload.count ?? 0);
    if (!start && !end && count <= 0) {
      continue;
    }
    rows.push({
      name,
      summary: `${start || "n/a"} → ${end || "n/a"} / count=${count}`,
    });
  }
  return rows;
}

function formatTimeRange(first: string, last: string): string {
  if (!first && !last) {
    return "当前没有样本预览";
  }
  return `${first || "n/a"} → ${last || "n/a"}`;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}
