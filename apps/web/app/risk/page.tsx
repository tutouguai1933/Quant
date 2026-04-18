/* 这个文件负责渲染风险页。 */

import Link from "next/link";

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { ToolDetailHub } from "../../components/tool-detail-hub";
import { readFeedback } from "../../lib/feedback";
import { getRiskPageModel, listRiskEvents } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function RiskPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { isAuthenticated } = session;
  const feedback = readFeedback(params);
  let items = getRiskPageModel().items;

  if (session.token) {
    try {
      const response = await listRiskEvents(session.token);
      if (!response.error) {
        items = response.data.items;
      }
    } catch {
      // API 不可用时仍然保留占位数据。
    }
  }

  return (
    <AppShell
      title="风险"
      subtitle="风险页现在只负责核对告警和规则明细，不再承担主流程判断。"
      currentPath="/risk"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="风险详情"
        title="风险详情页"
        description="先在任务页或首页确认是否有异常，再回到这里核对规则、决定和最近风险事件。"
      />

      <ToolDetailHub
        summary="风险页只负责把告警、规则和拒绝事件看清楚，主链判断继续留在首页、执行页和任务页。"
        detail="这里保留规则名称、决策和风险事件明细，帮助你确认系统不是“没发生”，而是“被明确阻止”，但不再把风险页当成主流程入口。"
        mainHint="首页已经先告诉你有没有头号阻塞，再回风险页核对具体规则。"
        strategiesHint="执行页先决定是否继续推进；如果被挡住，再回风险页看具体拒绝原因。"
        tasksHint="任务页负责恢复和接管，这里只负责把告警和规则明细看清楚。"
      />

      {!isAuthenticated ? (
        <section className="panel">
          <p className="eyebrow">动作反馈</p>
          <h3>风险页需要管理员登录</h3>
          <p>登录后才能查看真实风控事件和规则名称。</p>
          <Link className="button-link primary-link" href="/login?next=%2Frisk">
            前往登录
          </Link>
        </section>
      ) : (
        <MetricGrid
          items={[
            { label: "风险事件数", value: String(items.length), detail: "优先确认异常是不是已经被记录" },
            { label: "最新规则", value: items[0]?.ruleName ?? "n/a", detail: "规则名称能帮助你快速定位拒绝原因" },
            { label: "最新决定", value: items[0]?.decision ?? "waiting", detail: "block / warn / allow" },
          ]}
        />
      )}

      <DataTable
        columns={["Level", "Rule", "Decision"]}
        rows={items.map((item) => ({
          id: item.id,
          cells: [item.level, item.ruleName, <StatusBadge key={item.id} value={item.decision} />],
        }))}
        emptyTitle="当前没有风险事件"
        emptyDetail="如果要验证异常路径，先去策略页停止策略，再派发最新信号。"
      />
    </AppShell>
  );
}
