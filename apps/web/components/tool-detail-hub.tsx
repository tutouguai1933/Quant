/* 这个文件负责统一工具页的详情定位说明和返回主线入口。 */

import Link from "next/link";

import { SectionShell } from "./section-shell";
import { SummaryCard } from "./summary-card";
import { Button } from "./ui/button";

type ToolDetailHubProps = {
  summary: string;
  detail: string;
  mainHint: string;
  strategiesHint: string;
  tasksHint: string;
};

/* 渲染工具页统一的详情页定位区块。 */
export function ToolDetailHub({
  summary,
  detail,
  mainHint,
  strategiesHint,
  tasksHint,
}: ToolDetailHubProps) {
  return (
    <SectionShell
      eyebrow="工具详情"
      title="工具详情定位"
      description="工具页现在只负责查明细，不再承担主流程判断。先在主工作台做决定，再回到这里核对具体数据。"
    >
      <SummaryCard
        eyebrow="详情页心智"
        title="这页只负责查明细"
        summary={summary}
        detail={detail}
        actions={(
          <>
            <Button asChild variant="terminal" size="sm">
              <Link href="/">回到主工作台</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/strategies">回到执行工作台</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/tasks">回到运维工作台</Link>
            </Button>
          </>
        )}
        footer="主链页面负责判断，这里负责把判断对应的行情、账户、订单、仓位和风险细节看清楚。"
      >
        <div className="grid gap-3 md:grid-cols-3">
          <ToolDetailDigest label="主工作台" value="先做判断，再下钻细节" detail={mainHint} />
          <ToolDetailDigest label="执行工作台" value="先确认执行，再回来看结果" detail={strategiesHint} />
          <ToolDetailDigest label="运维工作台" value="先确认告警，再核对明细" detail={tasksHint} />
        </div>
      </SummaryCard>
    </SectionShell>
  );
}

/* 渲染工具页定位里的摘要块。 */
function ToolDetailDigest({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}
