/* 这个文件负责渲染任务页，并提供统一任务触发入口。 */

import { AppShell } from "../../components/app-shell";
import { DataTable } from "../../components/data-table";
import { FeedbackBanner } from "../../components/feedback-banner";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { StatusBadge } from "../../components/status-badge";
import { readFeedback } from "../../lib/feedback";
import { getTasksPageModel, listTasks } from "../../lib/api";
import { getControlSessionState } from "../../lib/session";


type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function TasksPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const { isAuthenticated } = session;
  const feedback = readFeedback(params);
  let items = getTasksPageModel().items;

  if (session.token) {
    try {
      const response = await listTasks(session.token);
      if (!response.error) {
        items = response.data.items;
      }
    } catch {
      // API 不可用时仍然保留占位数据。
    }
  }

  return (
    <AppShell
      title="任务"
      subtitle="任务页负责告诉用户：系统刚刚执行了什么、成功还是失败、下一步该去哪。"
      currentPath="/tasks"
      isAuthenticated={isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} fallbackTitle="任务反馈" />

      <PageHero
        badge="任务"
        title="把训练、同步、归档和异常任务放进同一个操作区"
        description="任务页的核心不是“展示很多任务”，而是让你知道最关键的动作有哪些，以及它们执行后有没有真正留下状态反馈。"
      />

      {!isAuthenticated ? (
        <section className="panel">
          <p className="eyebrow">任务反馈</p>
          <h3>任务页需要管理员登录</h3>
          <p>登录后才能触发训练、同步、归档和失败任务演示。</p>
          <a className="button-link primary-link" href="/login?next=%2Ftasks">
            前往登录
          </a>
        </section>
      ) : (
        <>
          <MetricGrid
            items={[
              { label: "任务总数", value: String(items.length), detail: "所有非交易任务都在这里汇总" },
              { label: "最新任务", value: items[0]?.taskType ?? "n/a", detail: "优先关注刚刚触发的动作有没有留下记录" },
              { label: "最新状态", value: items[0]?.status ?? "waiting", detail: "failed 和 succeeded 都应该清晰可见" },
            ]}
          />

          <section className="panel">
            <p className="eyebrow">任务反馈</p>
            <h3>触发训练</h3>
            <p>建议先跑训练和同步；如果要验收异常路径，再主动制造失败任务。</p>
            <div className="action-grid">
              <TaskAction action="trigger_train" label="触发训练" />
              <TaskAction action="trigger_sync" label="触发同步" />
              <TaskAction action="trigger_archive" label="触发归档" />
              <TaskAction action="trigger_reconcile_failure" label="制造失败任务" />
            </div>
          </section>
        </>
      )}

      <DataTable
        columns={["Task", "Source", "Status"]}
        rows={items.map((item) => ({
          id: item.id,
          cells: [item.taskType, item.source, <StatusBadge key={item.id} value={item.status} />],
        }))}
        emptyTitle="当前没有任务记录"
        emptyDetail="先触发训练或同步任务，再回到这里确认状态是不是已经可见。"
      />
    </AppShell>
  );
}

type TaskActionProps = {
  action: string;
  label: string;
};

function TaskAction({ action, label }: TaskActionProps) {
  return (
    <form action="/actions" method="post" className="action-card">
      <input type="hidden" name="action" value={action} />
      <input type="hidden" name="returnTo" value="/tasks" />
      <button type="submit">{label}</button>
      <p>所有任务都统一回写状态，避免用户只能猜系统刚刚做了什么。</p>
    </form>
  );
}
