"use client";

import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

type ActionCardProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  children?: ReactNode;
  actions?: ReactNode;
  riskLevel?: "safe" | "medium" | "danger" | "critical";
  className?: string;
};

const riskColors = {
  safe: "border-emerald-500/20 bg-emerald-500/5",
  medium: "border-amber-400/20 bg-amber-400/5",
  danger: "border-red-500/20 bg-red-500/5",
  critical: "border-red-600/30 bg-red-600/10",
};

export function ActionCard({
  eyebrow,
  title,
  description,
  children,
  actions,
  riskLevel,
  className,
}: ActionCardProps) {
  return (
    <article
      className={cn(
        "rounded-2xl border border-border/70 bg-card/80 p-5",
        riskLevel && riskColors[riskLevel],
        className
      )}
    >
      <div className="space-y-2">
        {eyebrow && (
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            {eyebrow}
          </p>
        )}
        <h4 className="text-base font-semibold text-foreground">{title}</h4>
        {description && (
          <p className="text-sm leading-6 text-muted-foreground">{description}</p>
        )}
      </div>
      {children && <div className="mt-4 space-y-3">{children}</div>}
      {actions && <div className="mt-4 flex flex-wrap gap-3">{actions}</div>}
    </article>
  );
}