/* 这个文件负责渲染风险页。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
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
      subtitle="风险页不只是为了看日志，而是为了让拒绝、告警和规则名称对用户直接可见。"
      currentPath="/risk"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />

      <PageHero
        badge="风险"
        title="异常要能被立刻看懂"
        description="当策略停止后再派发最新信号，基础风控会直接把拒绝事件写到这里，帮助你确认不是“没有发生”，而是“被明确阻止”。"
      />

      {!isAuthenticated ? (
        <section className="panel">
          <p className="eyebrow">动作反馈</p>
          <h3>风险页需要管理员登录</h3>
          <p>登录后才能查看真实风控事件和规则名称。</p>
          <a className="button-link primary-link" href="/login?next=%2Frisk">
            前往登录
          </a>
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
