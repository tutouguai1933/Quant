/**
 * 错误提示横幅组件
 * 用于在页面顶部显示错误或降级提示信息
 */
"use client";

export type ErrorBannerProps = {
  message: string;
  onDismiss?: () => void;
  /** 提示样式：error 为红色错误条，warning 为黄色降级提示条 */
  tone?: "error" | "warning";
};

export function ErrorBanner({ message, onDismiss, tone = "error" }: ErrorBannerProps) {
  const toneClass =
    tone === "warning"
      ? "bg-[var(--terminal-yellow)]/20 border-[var(--terminal-yellow)]/50"
      : "bg-[var(--terminal-red)]/20 border-[var(--terminal-red)]/50";
  const toneText = tone === "warning" ? "text-[var(--terminal-yellow)]" : "text-[var(--terminal-red)]";

  return (
    <div className={`${toneClass} border rounded-lg p-3 mb-4`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={toneText}>⚠️</span>
          <span className="text-[var(--terminal-text)] text-[13px]">{message}</span>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-[var(--terminal-muted)] hover:text-[var(--terminal-text)]"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
