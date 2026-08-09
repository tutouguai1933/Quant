import { AlertCircle } from "lucide-react";
import { TerminalCard } from "./terminal/terminal-card";

type ApiErrorFallbackProps = {
  title?: string;
  message?: string;
  detail?: string;
};

export function ApiErrorFallback({
  title = "数据加载失败",
  message = "后端 API 暂时不可用",
  detail = "当前显示的是降级数据，请稍后刷新页面重试。",
}: ApiErrorFallbackProps) {
  return (
    <TerminalCard title={title} className="border border-[var(--terminal-yellow)]/40! bg-[var(--terminal-yellow)]/10">
      <div className="flex items-center gap-3 mb-2">
        <AlertCircle className="size-4 text-[var(--terminal-yellow)]" />
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-yellow)]">降级模式</p>
      </div>
      <p className="text-sm text-[var(--terminal-muted)]">{message}</p>
      <p className="text-sm text-[var(--terminal-muted)] mt-1">{detail}</p>
    </TerminalCard>
  );
}
