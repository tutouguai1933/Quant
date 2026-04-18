/* 这个文件负责统一页面区块外壳，把标题、说明和内容层级收成同一套结构。 */

import type { ReactNode } from "react";

import { cn } from "../lib/utils";

type SectionShellProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
};

/* 渲染统一的区块标题层和内容层。 */
export function SectionShell({
  eyebrow,
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
}: SectionShellProps) {
  return (
    <section className={cn("space-y-4", className)}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <div className="space-y-2">
            <h3 className="text-xl font-semibold tracking-tight text-foreground">{title}</h3>
            {description ? <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p> : null}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
      </div>

      <div className={cn("grid gap-5", contentClassName)}>{children}</div>
    </section>
  );
}
