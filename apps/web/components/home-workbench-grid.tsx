/* 这个文件负责渲染首页主工作台：首屏 3 个核心数字卡 + "更多详情"折叠区，以及原有的 6 卡摘要组（供旧版首页复用）。 */

"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";

import { DetailDrawer } from "./detail-drawer";
import { SectionShell } from "./section-shell";
import { TerminalCard } from "./terminal/terminal-card";
import { Button } from "./ui/button";

type HomeWorkbenchCardLink = {
  href: string;
  label: string;
  variant?: "terminal" | "secondary" | "outline";
};

type HomeWorkbenchCardDigest = {
  label: string;
  value: string;
  detail: string;
};

export type HomeWorkbenchCardItem = {
  id: string;
  eyebrow: string;
  title: string;
  summary: string;
  detail: string;
  triggerLabel: string;
  drawerTitle: string;
  drawerDescription: string;
  drawerNotes?: string[];
  digests: HomeWorkbenchCardDigest[];
  links: HomeWorkbenchCardLink[];
};

type HomeWorkbenchGridProps = {
  cards: HomeWorkbenchCardItem[];
};

/* 核心数字卡属性 */
export type CoreNumberCardProps = {
  /** 卡标题 */
  label: string;
  /** 大数字 */
  value: string;
  /** 短说明 */
  detail: string;
  /** 点击跳转的详情页地址 */
  href: string;
  /** 数字颜色：positive=绿, negative=红, neutral=默认 */
  tone?: "positive" | "negative" | "neutral";
  /** 数据降级（接口不可用）时显示提示 */
  degraded?: boolean;
};

/* 渲染首屏核心数字卡：大数字 + 短说明，整卡可点击跳详情页 */
export function CoreNumberCard({
  label,
  value,
  detail,
  href,
  tone = "neutral",
  degraded = false,
}: CoreNumberCardProps) {
  const toneClass =
    tone === "positive"
      ? "text-green-400"
      : tone === "negative"
        ? "text-red-400"
        : "text-[var(--terminal-text)]";

  return (
    <Link
      href={href}
      className="terminal-card block p-4 hover:border-[var(--terminal-cyan)] transition-colors"
    >
      <div className="text-[var(--terminal-dim)] text-[11px] font-medium">{label}</div>
      <div className={`mt-2 font-mono text-[28px] font-bold leading-tight ${toneClass}`}>
        {value}
      </div>
      <div className="mt-2 text-[12px] text-[var(--terminal-muted)]">
        {degraded ? "数据暂不可用，请刷新或稍后再试" : detail}
      </div>
    </Link>
  );
}

/* "更多详情"折叠区属性 */
export type HomeMoreDetailsProps = {
  /** 折叠区标题，默认"更多详情" */
  title?: string;
  /** 折叠区内容 */
  children: ReactNode;
};

/* 渲染"更多详情"折叠区：默认收起且不挂载子组件，首次展开才加载内容。
   折叠区卡片会触发 rsi-summary/entry-conditions/freqtrade 等重请求，
   懒挂载避免切换首页时全部并发拉取导致 api 卡顿。 */
export function HomeMoreDetails({ title = "更多详情", children }: HomeMoreDetailsProps) {
  const [expanded, setExpanded] = useState(false);
  return (
    <details
      className="terminal-card"
      onToggle={(e) => {
        if (e.currentTarget.open) {
          setExpanded(true);
        }
      }}
    >
      <summary className="cursor-pointer select-none px-4 py-3 flex items-center justify-between text-[13px] font-semibold text-[var(--terminal-text)]">
        <span>{title}</span>
        <span className="text-[11px] font-normal text-[var(--terminal-dim)]">
          {expanded ? "已展开" : "点击展开"}
        </span>
      </summary>
      {expanded && (
        <div className="border-t border-[var(--terminal-border)] p-4 space-y-4">
          {children}
        </div>
      )}
    </details>
  );
}

/* 渲染首页主工作台卡片组。 */
export function HomeWorkbenchGrid({ cards }: HomeWorkbenchGridProps) {
  return (
    <SectionShell
      eyebrow="主工作台"
      title="当前主工作台"
      description="默认只显示当前主线最该看的 6 个判断块，细节和跳转都放进详情抽屉。"
    >
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <TerminalCard key={card.id} title={card.title}>
            <p className="text-[var(--terminal-dim)] text-[11px] font-medium mb-1">{card.eyebrow}</p>
            <p className="text-xs text-[var(--terminal-muted)] mb-3">{card.summary}</p>
            <div className="space-y-4">
              <p className="text-sm leading-6 text-[var(--terminal-text)]">{card.detail}</p>
              <div className="grid gap-3">
                {card.digests.map((item) => (
                  <DigestBlock key={`${card.id}-${item.label}`} label={item.label} value={item.value} detail={item.detail} />
                ))}
              </div>
            </div>
            <div className="mt-4 border-t border-[var(--terminal-border)] pt-4">
              <DetailDrawer
                triggerLabel={card.triggerLabel}
                title={card.drawerTitle}
                description={card.drawerDescription}
                triggerVariant="outline"
              >
                <div className="space-y-4">
                  {card.drawerNotes?.length ? (
                    <div className="space-y-2 text-sm leading-6 text-muted-foreground">
                      {card.drawerNotes.map((note, index) => (
                        <p key={`${card.id}-note-${index}`}>{note}</p>
                      ))}
                    </div>
                  ) : null}
                  <div className="grid gap-3 md:grid-cols-2">
                    {card.digests.map((item) => (
                      <DigestBlock key={`${card.id}-drawer-${item.label}`} label={item.label} value={item.value} detail={item.detail} />
                    ))}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {card.links.map((item) => (
                      <Button key={`${card.id}-${item.label}`} asChild variant={item.variant ?? "outline"} size="sm">
                        <Link href={item.href}>{item.label}</Link>
                      </Button>
                    ))}
                  </div>
                </div>
              </DetailDrawer>
            </div>
          </TerminalCard>
        ))}
      </div>
    </SectionShell>
  );
}

/* 渲染首页主工作台卡片里的摘要块。 */
function DigestBlock({ label, value, detail }: HomeWorkbenchCardDigest) {
  return (
    <div className="terminal-card p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-[var(--terminal-text)]">{value}</p>
      <p className="mt-2 text-sm leading-6 text-[var(--terminal-muted)]">{detail}</p>
    </div>
  );
}
