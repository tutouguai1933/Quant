/* 这个文件提供统一表格组件，供订单、信号和研究列表复用。 */

import * as React from "react";

import { cn } from "../../lib/utils";

/* 渲染表格外层容器。 */
export function Table({ className, ...props }: React.TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full caption-bottom text-sm", className)} {...props} />;
}

/* 渲染表头。 */
export function TableHeader({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("[&_tr]:border-b [&_tr]:border-border/70", className)} {...props} />;
}

/* 渲染表体。 */
export function TableBody({ className, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}

/* 渲染行。 */
export function TableRow({ className, ...props }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("border-b border-border/60 transition-colors hover:bg-muted/30 data-[state=selected]:bg-muted/50", className)}
      {...props}
    />
  );
}

/* 渲染头单元格。 */
export function TableHead({ className, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn("h-11 px-4 text-left align-middle text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground break-words whitespace-normal", className)}
      {...props}
    />
  );
}

/* 渲染数据单元格。 */
export function TableCell({ className, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-4 py-3 align-middle text-sm text-foreground break-all whitespace-normal", className)} {...props} />;
}
