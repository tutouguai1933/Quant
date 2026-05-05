/**
 * 错误提示横幅组件
 * 用于在页面顶部显示错误信息
 */
"use client";

export type ErrorBannerProps = {
  message: string;
  onDismiss?: () => void;
};

export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="bg-[var(--terminal-red)]/20 border border-[var(--terminal-red)]/50 rounded-lg p-3 mb-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[var(--terminal-red)]">⚠️</span>
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
