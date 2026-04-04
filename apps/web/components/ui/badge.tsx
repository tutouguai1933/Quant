/* 这个文件提供统一徽章组件，供状态、标签和摘要条复用。 */

import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold tracking-[0.14em] uppercase",
  {
    variants: {
      variant: {
        default: "border-border bg-muted/60 text-muted-foreground",
        neutral: "border-border bg-muted/60 text-muted-foreground",
        outline: "border-border/80 bg-transparent text-foreground",
        success: "border-emerald-500/30 bg-emerald-500/12 text-emerald-100",
        warning: "border-amber-400/30 bg-amber-400/12 text-amber-100",
        danger: "border-red-500/30 bg-red-500/12 text-red-100",
        accent: "border-sky-400/30 bg-sky-500/12 text-sky-100",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

/* 渲染统一徽章。 */
export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
