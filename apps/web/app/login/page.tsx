/**
 * 登录页面
 * 终端风格重构
 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  TerminalShell,
  TerminalCard,
  MetricCard,
  ControlPanel,
  FieldRow,
  TerminalInput,
} from "../../components/terminal";
import { FeedbackBanner } from "../../components/feedback-banner";
import { FormSubmitButton } from "../../components/form-submit-button";
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
    <TerminalShell
      breadcrumb="系统 / 登录"
      title="登录"
      subtitle="完成管理员认证，解锁策略、风险和任务页的所有受保护动作"
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

      {/* 指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="登录模式"
          value="单管理员"
          colorType="neutral"
        />
        <MetricCard
          label="会话时长"
          value="7 天保持"
          colorType="neutral"
        />
        <MetricCard
          label="会话方式"
          value={model.sessionMode}
          colorType="neutral"
        />
        <MetricCard
          label="继续前往"
          value={nextPath}
          colorType="neutral"
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        {/* 登录表单 */}
        <TerminalCard title="完成管理员认证">
          <form action="/login/submit" method="post" className="space-y-4">
            <input type="hidden" name="next" value={nextPath} />

            <div className="space-y-2">
              <label htmlFor="username" className="block text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">
                管理员账号
              </label>
              <input
                id="username"
                name="username"
                type="text"
                defaultValue={model.defaultUsername}
                className="w-full rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-3 py-2 text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-dim)] focus:border-[var(--terminal-accent)] focus:outline-none"
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="block text-xs font-semibold uppercase tracking-[0.12em] text-[var(--terminal-muted)]">
                密码
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                className="w-full rounded border border-[var(--terminal-border)] bg-[var(--terminal-bg)] px-3 py-2 text-sm text-[var(--terminal-text)] placeholder:text-[var(--terminal-dim)] focus:border-[var(--terminal-accent)] focus:outline-none"
              />
            </div>

            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px] md:items-center">
              <p className="text-sm text-[var(--terminal-muted)]">
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
        </TerminalCard>

        {/* 右侧信息 */}
        <div className="space-y-4">
          <TerminalCard title="受保护页面">
            <div className="space-y-2">
              {model.protectedPages.map((page) => (
                <div key={page} className="rounded border border-[var(--terminal-border)]/60 px-3 py-2 text-sm text-[var(--terminal-text)]">
                  {page}
                </div>
              ))}
            </div>
          </TerminalCard>

          <TerminalCard title="当前约束">
            <div className="space-y-2">
              {model.notes.map((note) => (
                <div key={note} className="rounded border border-[var(--terminal-border)]/60 px-3 py-2 text-sm text-[var(--terminal-muted)]">
                  {note}
                </div>
              ))}
            </div>
          </TerminalCard>
        </div>
      </div>
    </TerminalShell>
  );
}
