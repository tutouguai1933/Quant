/* 这个文件负责渲染研究页默认首屏的 3 张摘要卡，把配置、说明和实验细节统一收进抽屉或弹窗。 */

import type { ReactNode } from "react";

import { DetailDialog } from "./detail-dialog";
import { DetailDrawer } from "./detail-drawer";
import { SectionShell } from "./section-shell";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "./ui/card";

type ResearchFocusDigest = {
  label: string;
  value: string;
  detail: string;
};

type ResearchFocusAction = {
  key: string;
  label: string;
  title: string;
  description: string;
  content: ReactNode;
  footer?: ReactNode;
  mode: "drawer" | "dialog";
};

export type ResearchFocusCard = {
  id: string;
  eyebrow: string;
  title: string;
  summary: string;
  detail: string;
  digests: ResearchFocusDigest[];
  actions: ResearchFocusAction[];
};

type ResearchFocusGridProps = {
  cards: ResearchFocusCard[];
};

/* 渲染研究页默认首屏的摘要卡。 */
export function ResearchFocusGrid({ cards }: ResearchFocusGridProps) {
  return (
    <SectionShell
      eyebrow="默认视图"
      title="当前研究摘要"
      description="默认只保留当前状态、当前配置摘要和当前产物，完整配置、说明和实验细节都按需展开。"
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
            <CardFooter className="flex flex-wrap items-center gap-3 border-t border-border/60 pt-4">
              {card.actions.map((action) =>
                action.mode === "dialog" ? (
                  <DetailDialog
                    key={`${card.id}-${action.key}`}
                    triggerLabel={action.label}
                    title={action.title}
                    description={action.description}
                    footer={action.footer}
                  >
                    {action.content}
                  </DetailDialog>
                ) : (
                  <DetailDrawer
                    key={`${card.id}-${action.key}`}
                    triggerLabel={action.label}
                    title={action.title}
                    description={action.description}
                    footer={action.footer}
                  >
                    {action.content}
                  </DetailDrawer>
                ),
              )}
            </CardFooter>
          </Card>
        ))}
      </div>
    </SectionShell>
  );
}

/* 渲染研究摘要卡里的摘要块。 */
function DigestBlock({ label, value, detail }: ResearchFocusDigest) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
