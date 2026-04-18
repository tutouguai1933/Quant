"use client";

/* 这个文件负责把单因子的说明与观察维度收进统一抽屉，避免因子页首屏再次摊开成长列表。 */

import type { ReactNode } from "react";

import { DataTable } from "./data-table";
import { DetailDrawer } from "./detail-drawer";

export type FeatureFactorDetailItem = {
  id: string;
  name: string;
  categoryLabel: string;
  currentRole: string;
  description: string;
  timeSeries: string;
  icSummary: string;
  bucketSummary: string;
  stabilitySummary: string;
  correlationSummary: string;
};

type FeaturesFactorDetailDrawerProps = {
  items: FeatureFactorDetailItem[];
  primaryCount: number;
  auxiliaryCount: number;
  preprocessingSummary: string;
  timeframeSummary: string;
};

/* 渲染因子详情抽屉，让单因子信息按需展开。 */
export function FeaturesFactorDetailDrawer({
  items,
  primaryCount,
  auxiliaryCount,
  preprocessingSummary,
  timeframeSummary,
}: FeaturesFactorDetailDrawerProps) {
  const selectedCount = items.length;

  return (
    <DetailDrawer
      triggerLabel="查看因子详情"
      title="因子详情抽屉"
      description="单因子的说明、时间序列、IC、分组收益、稳定性和相关性统一收在这里，默认不占首屏。"
      footer="因子页首屏只保留摘要；单因子细节统一从这个抽屉进入。"
    >
      <div className="space-y-5">
        <DetailSection title="当前抽屉摘要" description="先确认这次要看的因子范围和当前配置口径。">
          <div className="grid gap-3 md:grid-cols-2">
            <InfoBlock label="当前启用因子" value={`${selectedCount} 个`} />
            <InfoBlock label="角色分布" value={`主判断 ${primaryCount} 个 / 辅助 ${auxiliaryCount} 个`} />
            <InfoBlock label="预处理" value={preprocessingSummary} />
            <InfoBlock label="时间序列" value={timeframeSummary} />
          </div>
        </DetailSection>

        <DetailSection title="因子说明" description="先把当前启用因子的类别、角色和用途看清楚。">
          <DataTable
            columns={["因子", "类别", "当前角色", "因子说明"]}
            rows={items.map((item) => ({
              id: item.id,
              cells: [item.name, item.categoryLabel, item.currentRole, item.description],
            }))}
            emptyTitle="当前还没有因子详情"
            emptyDetail="先启用至少一个主判断或辅助因子，再回来看单因子详情。"
          />
        </DetailSection>

        <DetailSection title="单因子观察" description="每个因子都按时间序列、IC、分组收益、稳定性和相关性五个角度统一展示。">
          <div className="space-y-4">
            {items.map((item) => (
              <article key={item.id} className="rounded-2xl border border-border/60 bg-muted/10 p-4">
                <div className="space-y-2">
                  <p className="eyebrow">{item.categoryLabel}</p>
                  <h5 className="text-base font-semibold leading-6 text-foreground">{item.name}</h5>
                  <p className="text-sm leading-6 text-muted-foreground">{item.description}</p>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <InfoBlock label="时间序列" value={item.timeSeries} />
                  <InfoBlock label="IC" value={item.icSummary} />
                  <InfoBlock label="分组收益" value={item.bucketSummary} />
                  <InfoBlock label="稳定性" value={item.stabilitySummary} />
                  <InfoBlock label="相关性" value={item.correlationSummary} />
                </div>
              </article>
            ))}
          </div>
        </DetailSection>
      </div>
    </DetailDrawer>
  );
}

/* 渲染抽屉里的细节分组。 */
function DetailSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-border/60 bg-muted/10 p-4">
      <div className="space-y-2">
        <p className="eyebrow">{title}</p>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

/* 渲染抽屉里的信息块。 */
function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-foreground break-all">{value}</p>
    </div>
  );
}
