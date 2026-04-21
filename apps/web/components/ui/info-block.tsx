"use client";

import { cn } from "../../lib/utils";

type InfoBlockProps = {
  label: string;
  value: string;
  detail?: string;
  variant?: "default" | "secondary" | "tertiary";
  className?: string;
};

const variantStyles = {
  default: "border-border/60 bg-muted/15",
  secondary: "border-border/70 bg-card/90",
  tertiary: "border-border/50 bg-muted/10",
};

export function InfoBlock({ label, value, detail, variant = "default", className }: InfoBlockProps) {
  return (
    <div className={cn("rounded-2xl border p-4", variantStyles[variant], className)}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-3 text-base font-semibold text-foreground">{value || "n/a"}</p>
      {detail && (
        <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
      )}
    </div>
  );
}