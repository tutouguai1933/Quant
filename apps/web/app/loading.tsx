/**
 * 全局加载状态组件
 * Next.js 15 原生支持，优化页面切换体验
 * 使用终端风格骨架屏
 */
export default function Loading() {
  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] text-[var(--terminal-text)]">
      {/* 主布局：左侧导航 + 右侧内容 */}
      <div className="grid min-h-screen lg:grid-cols-[160px_minmax(0,1fr)]">
        {/* 左侧导航骨架 */}
        <aside className="hidden lg:flex flex-col h-screen sticky top-0 border-r border-[var(--terminal-border)]">
          {/* Logo骨架 */}
          <div className="p-4 border-b border-[var(--terminal-border)]">
            <div className="h-4 w-16 bg-[var(--terminal-border)] rounded animate-pulse" />
            <div className="h-2 w-8 bg-[var(--terminal-border)] rounded animate-pulse mt-1" />
          </div>
          {/* 导航骨架 */}
          <div className="flex-1 p-2 space-y-1">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-8 bg-[var(--terminal-border)]/50 rounded animate-pulse" />
            ))}
          </div>
          {/* 状态骨架 */}
          <div className="p-3 border-t border-[var(--terminal-border)] space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-4 bg-[var(--terminal-border)]/50 rounded animate-pulse" />
            ))}
          </div>
        </aside>

        {/* 主内容骨架 */}
        <div className="flex flex-col">
          {/* 页面头部骨架 */}
          <header className="border-b border-[var(--terminal-border)] px-4 py-3">
            <div className="h-3 w-32 bg-[var(--terminal-border)] rounded animate-pulse mb-2" />
            <div className="h-6 w-48 bg-[var(--terminal-border)] rounded animate-pulse" />
          </header>

          {/* 内容骨架 */}
          <main className="flex-1 p-4 lg:p-5 space-y-4">
            {/* 指标卡骨架 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-20 bg-[var(--terminal-border)]/30 rounded-lg animate-pulse" />
              ))}
            </div>

            {/* 卡片骨架 */}
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-48 bg-[var(--terminal-border)]/20 rounded-lg animate-pulse" />
              ))}
            </div>
          </main>
        </div>
      </div>

      {/* 加载指示器 */}
      <div className="fixed bottom-4 right-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)] shadow-lg">
        <div className="w-3 h-3 border-2 border-[var(--terminal-cyan)] border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-[var(--terminal-muted)]">加载中...</span>
      </div>
    </div>
  );
}
