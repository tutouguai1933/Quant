/* 任务页入口：先返回 AI 状态加载节点，再由客户端接管查询参数和交互。 */
import { Suspense } from "react";
import TasksPageClient from "./tasks-page-client";

export default function TasksPage() {
  return (
    <Suspense fallback={
      <section aria-label="AI 方向策略（自动化）" className="p-6">
        <h2>AI 方向策略（自动化）</h2>
        <p data-testid="direction-model-admission">正在读取模型准入状态…</p>
      </section>
    }>
      <TasksPageClient />
    </Suspense>
  );
}
