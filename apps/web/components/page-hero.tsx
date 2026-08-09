/* 这个文件负责统一页面头部说明和行动提示。 */

import type { ReactNode } from "react";

import { TerminalCard } from "./terminal/terminal-card";
import { Badge } from "./ui/badge";

type PageHeroProps = {
  badge: string;
  title: string;
  description: string;
  aside?: ReactNode;
};

/* 渲染统一页头。 */
export function PageHero({ badge, title, description, aside }: PageHeroProps) {
  return (
    <TerminalCard title={title} actions={<Badge variant="default">{badge}</Badge>}>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <p className="max-w-3xl text-sm leading-7 text-[var(--terminal-muted)]">{description}</p>
        {aside ? (
          <div className="terminal-card p-4">
            <p className="eyebrow">侧边动作</p>
            {aside}
          </div>
        ) : null}
      </div>
    </TerminalCard>
  );
}
