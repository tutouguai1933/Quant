/* 这个文件负责渲染执行页默认首屏的 4 张摘要卡，把候选篮子、研究差异和账户回填下沉到详情抽屉。 */

import Link from "next/link";
import type { ReactNode } from "react";

import { DetailDrawer } from "./detail-drawer";
import { SectionShell } from "./section-shell";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./ui/card";

type StrategiesFocusLink = {
  href: string;
  label: string;
  variant?: "terminal" | "secondary" | "outline";
};

type StrategiesFocusDigest = {
  label: string;
  value: string;
  detail: string;
};

export type StrategiesFocusCard = {
  id: string;
  eyebrow: string;
  title: string;
  summary: string;
  detail: string;
  triggerLabel: string;
  drawerTitle: string;
  drawerDescription: string;
  drawerNotes?: string[];
  digests: StrategiesFocusDigest[];
  links?: StrategiesFocusLink[];
  detailContent?: ReactNode;
};

type StrategiesFocusGridProps = {
  cards: StrategiesFocusCard[];
};

/* 渲染执行页默认首屏的摘要卡。 */
export function StrategiesFocusGrid({ cards }: StrategiesFocusGridProps) {
  return (
    <SectionShell
      eyebrow="默认视图"
      title="当前执行摘要"
      description="默认只保留当前执行器状态、当前候选可推进性、当前执行模式和当前账户收口摘要，候选篮子与执行篮子的承接关系放在卡片里说明。"
    >
      <div className="grid gap-5 md:grid-cols-2">
        {cards.map((card) => (
          <Card key={card.id} className="bg-card/90">
            <CardHeader>
              <p className="eyebrow">{card.eyebrow}</p>
              <CardTitle>{card.title}</CardTitle>
              <CardDescription>{card.summary}</CardDescription>
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
                triggerVariant="outline"
              >
                <div className="space-y-4">
                  {card.drawerNotes?.length ? (
                    <div className="space-y-2 text-sm leading-6 text-muted-foreground">
                      {card.drawerNotes.map((note, index) => (
                        <p key={`${card.id}-note-${index}`}>{note}</p>
                      ))}
                    </div>
                  ) : null}
                  <div className="grid gap-3 md:grid-cols-2">
                    {card.digests.map((item) => (
                      <DigestBlock key={`${card.id}-drawer-${item.label}`} label={item.label} value={item.value} detail={item.detail} />
                    ))}
                  </div>
                  {card.detailContent ? <div className="space-y-4">{card.detailContent}</div> : null}
                  {card.links?.length ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      {card.links.map((item) => (
                        <Button key={`${card.id}-${item.label}`} asChild variant={item.variant ?? "outline"} size="sm">
                          <Link href={item.href}>{item.label}</Link>
                        </Button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </DetailDrawer>
            </CardFooter>
          </Card>
        ))}
      </div>
    </SectionShell>
  );
}

/* 渲染摘要块。 */
function DigestBlock({ label, value, detail }: StrategiesFocusDigest) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
