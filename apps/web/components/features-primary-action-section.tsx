/* 这个文件负责把因子页里的配置、说明和研究承接入口收成唯一主动作区。 */

import Link from "next/link";
import type { ReactNode } from "react";

import { FullScreenModal } from "./full-screen-modal";
import { FeaturesMainlineSteps } from "./features-mainline-steps";
import { SectionShell } from "./section-shell";
import { SummaryCard } from "./summary-card";
import { Button } from "./ui/button";

type FeaturesPrimaryActionSectionProps = {
  primaryActionLabel: string;
  primaryActionDetail: string;
  featureStatus: string;
  featureStatusDetail: string;
  categoryHeadline: string;
  categoryDetail: string;
  selectionHeadline: string;
  selectionDetail: string;
  scoreHeadline: string;
  scoreDetail: string;
  configContent: ReactNode;
  guideContent: ReactNode;
  flowContent: ReactNode;
  detailAction?: ReactNode;
};

/* 渲染因子页唯一保留的主动作区。 */
export function FeaturesPrimaryActionSection({
  primaryActionLabel,
  primaryActionDetail,
  featureStatus,
  featureStatusDetail,
  categoryHeadline,
  categoryDetail,
  selectionHeadline,
  selectionDetail,
  scoreHeadline,
  scoreDetail,
  configContent,
  guideContent,
  flowContent,
  detailAction,
}: FeaturesPrimaryActionSectionProps) {
  return (
    <SectionShell
      eyebrow="因子主线"
      title="因子主动作区"
      description="首屏只保留一组因子动作。完整配置、因子说明和研究承接入口都统一从这里展开。"
    >
      <div className="space-y-5">
        <FeaturesMainlineSteps />
        <SummaryCard
          eyebrow="因子主动作区"
          title={primaryActionLabel}
          summary="因子页不再把配置表单、说明表和承接入口拆成多块首屏内容。先看当前协议，再按需展开细节。"
          detail={primaryActionDetail}
          actions={(
            <>
              <FullScreenModal
                triggerLabel="查看因子配置"
                title="因子配置详情"
                description="完整配置表单统一收在这里，默认不再把复选和参数直接铺满首屏。"
                triggerVariant="terminal"
              >
                {configContent}
              </FullScreenModal>
              <FullScreenModal
                triggerLabel="查看因子说明"
                title="因子说明详情"
                description="因子协议、预处理口径和因子细节统一放到这里，需要时再看。"
              >
                {guideContent}
              </FullScreenModal>
              <FullScreenModal
                triggerLabel="查看研究承接"
                title="研究承接详情"
                description="因子怎么进入候选篮子和执行篮子，统一从这里解释和跳转。"
              >
                {flowContent}
              </FullScreenModal>
              {detailAction}
            </>
          )}
          footer="因子配置、因子说明和研究承接都已下沉到抽屉；首屏只保留这一组因子动作。"
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <PrimaryDigest label="当前状态" value={featureStatus} detail={featureStatusDetail} />
            <PrimaryDigest label="因子分类" value={categoryHeadline} detail={categoryDetail} />
            <PrimaryDigest label="当前启用" value={selectionHeadline} detail={selectionDetail} />
            <PrimaryDigest label="总分解释" value={scoreHeadline} detail={scoreDetail} />
          </div>
        </SummaryCard>
      </div>
    </SectionShell>
  );
}

/* 渲染主动作区里的摘要块。 */
function PrimaryDigest({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/70 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-semibold leading-6 text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}

/* 渲染研究承接里的快捷跳转。 */
export function FeatureFlowLinks({
  researchHref,
  evaluationHref,
}: {
  researchHref: string;
  evaluationHref: string;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Button asChild variant="terminal" size="sm">
        <Link href={researchHref}>去研究页看候选篮子</Link>
      </Button>
      <Button asChild variant="outline" size="sm">
        <Link href={evaluationHref}>去评估页看执行篮子</Link>
      </Button>
    </div>
  );
}
