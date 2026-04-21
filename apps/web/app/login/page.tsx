"use client";

/* 这个文件负责渲染登录页，并明确告诉用户登录后该去哪里。 */

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell } from "../../components/app-shell";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
import { MetricGrid } from "../../components/metric-grid";
import { PageHero } from "../../components/page-hero";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { readFeedback } from "../../lib/feedback";
import { getLoginPageModel, LoginPageModel } from "../../lib/api";
import { normalizeAppPath } from "../../lib/session-client";

type SessionState = {
  token: string;
  isAuthenticated: boolean;
};

export default function LoginPage() {
  const searchParams = useSearchParams();
  const [session, setSession] = useState<SessionState>({ token: "", isAuthenticated: false });
  const [model, setModel] = useState<LoginPageModel | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchSession() {
      try {
        const response = await fetch("/api/control/session");
        if (response.ok) {
          const data = await response.json();
          setSession({
            token: data.token ?? "",
            isAuthenticated: data.isAuthenticated ?? false,
          });
        }
      } catch {
        // Keep default unauthenticated state
      }
    }

    async function fetchModel() {
      try {
        const data = await getLoginPageModel();
        setModel(data);
      } catch {
        // Keep model as null
      }
    }

    Promise.all([fetchSession(), fetchModel()]).finally(() => {
      setIsLoading(false);
    });
  }, []);

  const nextPath = normalizeAppPath(searchParams?.get("next") ?? undefined, "/strategies");
  const hasError = searchParams?.get("state") === "error";
  const feedback = readFeedback(
    Object.fromEntries(searchParams?.entries() ?? []) as Record<string, string | string[] | undefined>
  );

  if (isLoading || !model) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">加载中...</p>
      </div>
    );
  }

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
        description="这里不做复杂权限体系，只保留单管理员入口。登录后默认保持 7 天，重点是让你知道下一步该去哪，而不是反复重新登录。"
      />

      <MetricGrid
        items={[
          { label: "登录模式", value: "单管理员", detail: "当前阶段不扩展多用户和角色模型" },
          { label: "会话时长", value: "7 天保持", detail: "登录成功后写入本地会话 cookie，页面会直接复用这份状态" },
          { label: "会话方式", value: model.sessionMode, detail: "登录成功后写入本地会话 cookie" },
          { label: "继续前往", value: nextPath, detail: "登录后会优先跳转到这个页面" },
        ]}
      />

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        <Card className="bg-card/90">
          <CardHeader>
            <p className="eyebrow">登录反馈</p>
            <CardTitle>完成管理员认证</CardTitle>
            <CardDescription>登录后直接回到下一步最关键的页面，不在这里停留做额外设置。</CardDescription>
          </CardHeader>
          <CardContent>
            <form action="/login/submit" method="post" className="grid gap-4">
              <input type="hidden" name="next" value={nextPath} />

              <div className="grid gap-2">
                <label htmlFor="username" className="text-sm font-medium text-foreground">管理员账号</label>
                <Input id="username" name="username" type="text" defaultValue={model.defaultUsername} />
              </div>

              <div className="grid gap-2">
                <label htmlFor="password" className="text-sm font-medium text-foreground">密码</label>
                <Input id="password" name="password" type="password" autoComplete="current-password" />
              </div>

              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px] md:items-center">
                <p className="text-sm leading-6 text-muted-foreground">
                  当前登录只做单管理员入口，目的是快速进入策略、风险和任务控制区。
                </p>
                <FormSubmitButton
                  type="submit"
                  className="w-full"
                  idleLabel="登录并继续"
                  pendingLabel="登录中..."
                  pendingHint="正在建立管理员会话，完成后会自动跳转。"
                />
              </div>
            </form>
          </CardContent>
        </Card>

        <Card className="bg-card/90">
          <CardHeader>
            <p className="eyebrow">继续前往</p>
            <CardTitle>受保护页面</CardTitle>
            <CardDescription>右侧只保留登录后的目标页和当前约束，避免登录页继续纵向堆信息。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="rounded-2xl border border-border/70 bg-background/60 p-4">
              <p className="text-sm font-semibold text-foreground">登录后优先跳转</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{nextPath}</p>
            </div>

            <div className="space-y-3">
              <p className="text-sm font-semibold text-foreground">受保护页面</p>
              <div className="grid gap-2">
                {model.protectedPages.map((page) => (
                  <div key={page} className="rounded-xl border border-border/60 bg-background/40 px-3 py-2 text-sm text-muted-foreground">
                    {page}
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3">
              <p className="text-sm font-semibold text-foreground">当前约束</p>
              <div className="grid gap-2">
                {model.notes.map((note) => (
                  <div key={note} className="rounded-xl border border-border/60 bg-background/40 px-3 py-2 text-sm leading-6 text-muted-foreground">
                    {note}
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    </AppShell>
  );
}