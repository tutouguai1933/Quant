/* 这个文件负责统一摘要卡层级，让标题、摘要和动作保持同一套结构。 */

import type { ReactNode } from "react";

import { cn } from "../lib/utils";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./ui/card";

type SummaryCardProps = {
  eyebrow?: string;
  title: string;
  summary: string;
  detail?: string;
  status?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
  className?: string;
  contentClassName?: string;
};

/* 渲染统一的摘要卡。 */
export function SummaryCard({
  eyebrow,
  title,
  summary,
  detail,
  status,
  actions,
  footer,
  children,
  className,
  contentClassName,
}: SummaryCardProps) {
  return (
    <Card className={cn("border-border/70 bg-card/92 shadow-[0_18px_40px_rgba(2,6,23,0.18)]", className)}>
      <CardHeader className="space-y-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
            <CardTitle>{title}</CardTitle>
            <CardDescription className="text-sm leading-6 text-muted-foreground">{summary}</CardDescription>
          </div>
          {status ? <div className="flex flex-wrap items-center gap-2">{status}</div> : null}
        </div>
      </CardHeader>

      <CardContent className={cn("space-y-5", contentClassName)}>
        {detail ? <p className="text-sm leading-6 text-foreground/90">{detail}</p> : null}
        {children}
      </CardContent>

      {actions || footer ? (
        <CardFooter className="flex flex-col items-start gap-4 border-t border-border/60 pt-5 md:flex-row md:items-start md:justify-between">
          {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : <div />}
          {footer ? <div className="max-w-2xl text-sm leading-6 text-muted-foreground">{footer}</div> : null}
        </CardFooter>
      ) : null}
    </Card>
  );
}
