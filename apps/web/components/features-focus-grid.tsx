/* 这个文件负责渲染因子页默认首屏的摘要卡，把分类、启用、有效性、冗余和总分解释统一收进详情抽屉。 */

import type { ReactNode } from "react";

import { DetailDrawer } from "./detail-drawer";
import { SectionShell } from "./section-shell";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "./ui/card";

type FeaturesFocusDigest = {
  label: string;
  value: string;
  detail: string;
};

export type FeaturesFocusCard = {
  id: string;
  eyebrow: string;
  title: string;
  summary: string;
  detail: string;
  triggerLabel: string;
  drawerTitle: string;
  drawerDescription: string;
  drawerContent: ReactNode;
  drawerFooter?: ReactNode;
  digests: FeaturesFocusDigest[];
};

type FeaturesFocusGridProps = {
  cards: FeaturesFocusCard[];
};

/* 渲染因子页默认首屏的摘要卡。 */
export function FeaturesFocusGrid({ cards }: FeaturesFocusGridProps) {
  return (
    <SectionShell
      eyebrow="默认视图"
      title="当前因子摘要"
      description="默认只保留因子分类总览、当前启用、有效性摘要、冗余摘要和总分解释入口，细节按需展开。"
    >
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <Card key={card.id} className="bg-card/90">
            <CardHeader className="space-y-3">
              <p className="eyebrow">{card.eyebrow}</p>
              <div className="space-y-2">
                <CardTitle>{card.title}</CardTitle>
                <p className="text-sm leading-6 text-muted-foreground">{card.summary}</p>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-6 text-foreground">{card.detail}</p>
              <div className="grid gap-3">
                {card.digests.map((item) => (
                  <DigestBlock key={`${card.id}-${item.label}`} label={item.label} value={item.value} detail={item.detail} />
                ))}
              </div>
            </CardContent>
            <CardFooter className="border-t border-border/60 pt-4">
              <DetailDrawer
                triggerLabel={card.triggerLabel}
                title={card.drawerTitle}
                description={card.drawerDescription}
                footer={card.drawerFooter}
              >
                {card.drawerContent}
              </DetailDrawer>
            </CardFooter>
          </Card>
        ))}
      </div>
    </SectionShell>
  );
}

/* 渲染因子摘要卡里的摘要块。 */
function DigestBlock({ label, value, detail }: FeaturesFocusDigest) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
