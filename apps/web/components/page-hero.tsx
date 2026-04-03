/* 这个文件负责统一页面头部说明和行动提示。 */

import type { ReactNode } from "react";

import { Badge } from "./ui/badge";
import { Card, CardContent, CardTitle } from "./ui/card";

type PageHeroProps = {
  badge: string;
  title: string;
  description: string;
  aside?: ReactNode;
};

/* 渲染统一页头。 */
export function PageHero({ badge, title, description, aside }: PageHeroProps) {
  return (
    <Card className="overflow-hidden bg-card/90">
      <CardContent className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <div className="space-y-3">
          <Badge variant="default" className="w-fit">{badge}</Badge>
          <div className="space-y-2">
            <CardTitle className="text-2xl md:text-3xl">{title}</CardTitle>
            <p className="max-w-3xl text-sm leading-7 text-muted-foreground">{description}</p>
          </div>
        </div>
        {aside ? (
          <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
            <p className="eyebrow">侧边动作</p>
            {aside}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
