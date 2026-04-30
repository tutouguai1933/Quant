"use client";

import * as React from "react";

import { cn } from "../../lib/utils";

export function Select({ className, children, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function SelectTrigger({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("relative", className)} {...props}>
      {children}
    </div>
  );
}

export function SelectContent({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("absolute top-full left-0 z-50 mt-1 min-w-full rounded-md border bg-popover p-1 shadow-md", className)} {...props}>
      {children}
    </div>
  );
}

export function SelectItem({ className, children, value, ...props }: React.OptionHTMLAttributes<HTMLOptionElement>) {
  return (
    <option
      className={cn("relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-2 pr-8 text-sm outline-none focus:bg-accent focus:text-accent-foreground", className)}
      value={value}
      {...props}
    >
      {children}
    </option>
  );
}

export function SelectValue({ placeholder, className }: { placeholder?: string; className?: string }) {
  return (
    <span className={cn("text-muted-foreground", className)}>
      {placeholder}
    </span>
  );
}