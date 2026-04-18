/* 这个文件负责渲染首页主工作台卡片，把当前推荐、研究、执行、风险、下一步和回看入口统一收成一组摘要卡。 */

import Link from "next/link";

import { DetailDrawer } from "./detail-drawer";
import { SectionShell } from "./section-shell";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./ui/card";

type HomeWorkbenchCardLink = {
  href: string;
  label: string;
  variant?: "terminal" | "secondary" | "outline";
};

type HomeWorkbenchCardDigest = {
  label: string;
  value: string;
  detail: string;
};

export type HomeWorkbenchCardItem = {
  id: string;
  eyebrow: string;
  title: string;
  summary: string;
  detail: string;
  triggerLabel: string;
  drawerTitle: string;
  drawerDescription: string;
  drawerNotes?: string[];
  digests: HomeWorkbenchCardDigest[];
  links: HomeWorkbenchCardLink[];
};

type HomeWorkbenchGridProps = {
  cards: HomeWorkbenchCardItem[];
};

/* 渲染首页主工作台卡片组。 */
export function HomeWorkbenchGrid({ cards }: HomeWorkbenchGridProps) {
  return (
    <SectionShell
      eyebrow="主工作台"
      title="当前主工作台"
      description="默认只显示当前主线最该看的 6 个判断块，细节和跳转都放进详情抽屉。"
    >
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
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
                  <div className="grid gap-3 sm:grid-cols-2">
                    {card.links.map((item) => (
                      <Button key={`${card.id}-${item.label}`} asChild variant={item.variant ?? "outline"} size="sm">
                        <Link href={item.href}>{item.label}</Link>
                      </Button>
                    ))}
                  </div>
                </div>
              </DetailDrawer>
            </CardFooter>
          </Card>
        ))}
      </div>
    </SectionShell>
  );
}

/* 渲染首页主工作台卡片里的摘要块。 */
function DigestBlock({ label, value, detail }: HomeWorkbenchCardDigest) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
