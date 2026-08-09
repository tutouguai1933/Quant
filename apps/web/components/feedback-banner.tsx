/* 这个文件负责统一展示操作成功、失败或提示信息。 */

import type { FeedbackState } from "../lib/feedback";

import { TerminalCard } from "./terminal/terminal-card";

type FeedbackBannerProps = {
  feedback: FeedbackState;
  fallbackTitle?: string;
};

/* 渲染反馈条。 */
export function FeedbackBanner({ feedback, fallbackTitle = "动作反馈" }: FeedbackBannerProps) {
  if (!feedback) {
    return null;
  }

  const toneClass =
    feedback.tone === "error"
      ? "border border-[var(--terminal-red)]/40! bg-[var(--terminal-red)]/10"
      : feedback.tone === "warning"
        ? "border border-[var(--terminal-yellow)]/40! bg-[var(--terminal-yellow)]/10"
        : "border border-[var(--terminal-green)]/40! bg-[var(--terminal-green)]/10";

  return (
    <TerminalCard title={fallbackTitle} className={toneClass}>
      <div className="space-y-1">
        <p className="text-sm font-medium text-[var(--terminal-text)]">{feedback.title}</p>
        <p className="text-sm text-[var(--terminal-muted)]">{feedback.message}</p>
      </div>
    </TerminalCard>
  );
}
