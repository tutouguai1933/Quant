"use client";

import { Loader2 } from "lucide-react";

import { TerminalCard } from "./terminal/terminal-card";

export function LoadingBanner() {
  return (
    <TerminalCard className="border border-[var(--terminal-cyan)]/30! bg-[var(--terminal-cyan)]/10">
      <div className="flex items-center gap-2 text-sm text-[var(--terminal-cyan)]">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>正在加载数据...</span>
      </div>
    </TerminalCard>
  );
}
