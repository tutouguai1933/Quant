/* 这个文件负责在路由切换期间显示统一终端加载状态。 */

export default function Loading() {
  return (
    <div className="min-h-screen bg-background px-4 py-6 text-foreground sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-[1680px] gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="rounded-2xl border border-border/70 bg-card/80 p-5">
          <p className="eyebrow">Quant Terminal</p>
          <h2 className="mt-3 text-xl font-semibold tracking-tight">正在切换工作区</h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">页面会先显示骨架，再补研究、市场和执行数据，避免切换时整屏卡住。</p>
        </aside>

        <section className="space-y-5">
          <div className="rounded-2xl border border-border/70 bg-card/80 p-5">
            <div className="h-3 w-28 rounded-full bg-muted/60" />
            <div className="mt-4 h-9 w-56 rounded-xl bg-muted/40" />
            <div className="mt-4 h-4 w-3/4 rounded-full bg-muted/30" />
          </div>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.9fr)]">
            <div className="space-y-5">
              <div className="rounded-2xl border border-border/70 bg-card/80 p-5">
                <div className="h-3 w-24 rounded-full bg-muted/60" />
                <div className="mt-4 h-8 w-2/5 rounded-xl bg-muted/40" />
                <div className="mt-4 h-56 rounded-2xl bg-muted/20" />
              </div>
            </div>
            <div className="rounded-2xl border border-border/70 bg-card/80 p-5">
              <div className="h-3 w-24 rounded-full bg-muted/60" />
              <div className="mt-4 h-8 w-2/3 rounded-xl bg-muted/40" />
              <div className="mt-4 grid gap-3">
                <div className="h-16 rounded-2xl bg-muted/20" />
                <div className="h-16 rounded-2xl bg-muted/20" />
                <div className="h-16 rounded-2xl bg-muted/20" />
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
