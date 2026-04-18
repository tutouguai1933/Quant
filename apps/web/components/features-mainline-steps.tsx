/* 这个文件负责渲染因子主线五步，把因子挖掘到执行篮子的路径显化在首屏。 */

const MAINLINE_STEPS = [
  { key: "discover", label: "因子挖掘", summary: "确定方向与可用因子池" },
  { key: "validate", label: "因子验证", summary: "先用研究验证有效性" },
  { key: "dedup", label: "去冗余", summary: "压掉重复和噪声因子" },
  { key: "candidate", label: "候选篮子", summary: "在研究页形成候选集" },
  { key: "execution", label: "执行篮子", summary: "评估页收口执行名单" },
] as const;

/* 渲染因子主线五步的可视化清单。 */
export function FeaturesMainlineSteps() {
  return (
    <section className="rounded-3xl border border-border/60 bg-muted/10 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="eyebrow">五步主线</p>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">因子挖掘 → 因子验证 → 去冗余 → 候选篮子 → 执行篮子</p>
      </div>
      <ol className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {MAINLINE_STEPS.map((step, index) => (
          <li key={step.key} className="rounded-2xl border border-border/60 bg-card/80 p-4">
            <div className="flex items-center justify-between gap-2 text-xs uppercase tracking-wide text-muted-foreground">
              <span>第 {index + 1} 步</span>
              <span aria-hidden="true">→</span>
            </div>
            <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{step.label}</p>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">{step.summary}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
