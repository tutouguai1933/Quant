/* 这个文件负责渲染登录页，并明确告诉用户登录后该去哪里。 */

import { AppShell } from "../../components/app-shell";
import { FeedbackBanner } from "../../components/feedback-banner";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { readFeedback } from "../../lib/feedback";
import { getLoginPageModel } from "../../lib/api";
import { getControlSessionState, normalizeAppPath } from "../../lib/session";


type PageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function LoginPage({ searchParams }: PageProps) {
  const params = (await searchParams) ?? {};
  const session = await getControlSessionState();
  const model = await getLoginPageModel();
  const feedback = readFeedback(params);
  const nextPath = normalizeAppPath(params.next, "/strategies");
  const hasError = readSingleParam(params.state) === "error";

  return (
    <AppShell
      title="登录"
      subtitle="完成一次管理员认证，就能解锁策略、风险和任务页的所有受保护动作。"
      currentPath="/login"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner
        feedback={
          hasError
            ? {
                tone: "error",
                title: "登录反馈",
                message: "账号或密码不正确，当前会话没有建立。",
              }
            : feedback
        }
        fallbackTitle="登录反馈"
      />

      <PageHero
        badge="登录"
        title="登录后，系统会直接把你送回下一步最关键的页面"
        description="这里不做复杂权限体系，只保留单管理员入口。重点是让你知道登录完成后该继续去哪，而不是把你困在一个孤立页面里。"
      />

      <MetricGrid
        items={[
          { label: "登录模式", value: "单管理员", detail: "当前阶段不扩展多用户和角色模型" },
          { label: "会话方式", value: model.sessionMode, detail: "登录成功后写入本地会话 cookie" },
          { label: "继续前往", value: nextPath, detail: "登录后会优先跳转到这个页面" },
        ]}
      />

      <section className="content-grid">
        <section className="panel">
          <p className="eyebrow">登录反馈</p>
          <h3>完成管理员认证</h3>
          <form action="/login/submit" method="post" className="stack-form">
            <input type="hidden" name="next" value={nextPath} />

            <label htmlFor="username">管理员账号</label>
            <input id="username" name="username" type="text" defaultValue={model.defaultUsername} />

            <label htmlFor="password">密码</label>
            <input id="password" name="password" type="password" placeholder="1933" />

            <button type="submit">登录并继续</button>
          </form>
        </section>

        <section className="panel">
          <p className="eyebrow">继续前往</p>
          <h3>受保护页面</h3>
          <p>登录完成后，你最可能继续进入下面这些页面：</p>
          <ul className="link-list">
            {model.protectedPages.map((page) => (
              <li key={page}>{page}</li>
            ))}
          </ul>
          <p>当前约束：</p>
          <ul className="link-list">
            {model.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      </section>
    </AppShell>
  );
}

function readSingleParam(value?: string | string[]): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}
